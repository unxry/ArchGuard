from archguard.core.model.enums import Language, NodeKind
from archguard.extraction.enums import ImportKind, ReferenceKind, ResolutionMethod, ResolutionStatus
from archguard.extraction.models import ExtractedFileFacts, ExtractedImport, SymbolReference
from archguard.extraction.resolution.index import IndexedSymbol, SymbolIndex
from archguard.extraction.resolution.models import ExternalDependency, ResolutionResult

RESOLVER_VERSION = "1.0.0"
TYPE_KINDS = frozenset(
    {NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.ENUM, NodeKind.TYPE_ALIAS, NodeKind.MODULE}
)
CALL_KINDS = frozenset({NodeKind.FUNCTION, NodeKind.METHOD})


class SymbolResolver:
    version = RESOLVER_VERSION

    def resolve(
        self, files: tuple[ExtractedFileFacts, ...], index: SymbolIndex
    ) -> tuple[ResolutionResult, ...]:
        return tuple(
            self.resolve_reference(file, reference, index)
            for file in files
            for reference in file.references
        )

    def resolve_reference(
        self, file: ExtractedFileFacts, ref: SymbolReference, index: SymbolIndex
    ) -> ResolutionResult:
        if ref.is_dynamic or ref.unknown_receiver or ref.blocked_by_local_binding:
            return self._empty(file, ref)
        if ref.reference_kind == ReferenceKind.IMPORT:
            if ref.import_index is None:
                return self._empty(file, ref)
            return self._import(file, ref, file.imports[ref.import_index], index)
        if ref.reference_kind == ReferenceKind.CALL:
            return self._call(file, ref, index)
        result = self._type(file, ref, ref.qualified_name_hint or ref.name, index)
        if result.status == ResolutionStatus.RESOLVED and result.target_key is None:
            return self._empty(file, ref)
        if result.status == ResolutionStatus.RESOLVED and result.target_key is not None:
            kind = index.symbols[result.target_key].declaration.kind
            allowed = TYPE_KINDS
            if ref.reference_kind == ReferenceKind.CREATE:
                allowed = frozenset({NodeKind.CLASS})
            if ref.reference_kind == ReferenceKind.IMPLEMENTS:
                allowed = frozenset({NodeKind.INTERFACE, NodeKind.TYPE_ALIAS})
            if kind not in allowed:
                return self._empty(file, ref)
        return result

    @staticmethod
    def _empty(file: ExtractedFileFacts, ref: SymbolReference) -> ResolutionResult:
        return ResolutionResult(
            source_file=file.source_file.relative_path,
            reference=ref,
            status=ResolutionStatus.UNRESOLVED,
        )

    @staticmethod
    def _external(
        file: ExtractedFileFacts, ref: SymbolReference, target: ExternalDependency
    ) -> ResolutionResult:
        return ResolutionResult(
            source_file=file.source_file.relative_path,
            reference=ref,
            status=ResolutionStatus.EXTERNAL,
            method=ResolutionMethod.EXTERNAL_PACKAGE,
            external=target,
        )

    @staticmethod
    def _compatible_arity(symbol: IndexedSymbol, count: int | None) -> bool:
        if count is None:
            return True
        parameters = symbol.declaration.parameters
        minimum = sum(not (item.optional or item.is_rest) for item in parameters)
        return count >= minimum and (
            any(item.is_rest for item in parameters) or count <= len(parameters)
        )

    def _choose(
        self,
        file: ExtractedFileFacts,
        ref: SymbolReference,
        keys: tuple[str, ...],
        method: ResolutionMethod,
        index: SymbolIndex,
        kinds: frozenset[NodeKind] | None = None,
        static_only: bool = False,
    ) -> ResolutionResult:
        candidates = tuple(
            sorted(
                set(
                    key
                    for key in keys
                    if (kinds is None or index.symbols[key].declaration.kind in kinds)
                    and (not static_only or "static" in index.symbols[key].declaration.modifiers)
                    and (
                        ref.reference_kind != ReferenceKind.CALL
                        or index.symbols[key].declaration.kind not in CALL_KINDS
                        or self._compatible_arity(index.symbols[key], ref.argument_count)
                    )
                )
            )
        )
        if len(candidates) == 1:
            target = index.symbols[candidates[0]]
            return ResolutionResult(
                source_file=file.source_file.relative_path,
                reference=ref,
                status=ResolutionStatus.RESOLVED,
                method=method,
                target_key=candidates[0],
                target_file=target.file.source_file.relative_path,
            )
        if len(candidates) > 1:
            return ResolutionResult(
                source_file=file.source_file.relative_path,
                reference=ref,
                status=ResolutionStatus.AMBIGUOUS,
                method=method,
                candidates=candidates,
            )
        return self._empty(file, ref)

    def _import(
        self,
        file: ExtractedFileFacts,
        ref: SymbolReference,
        imported: ExtractedImport,
        index: SymbolIndex,
    ) -> ResolutionResult:
        if imported.kind == ImportKind.JAVA:
            if imported.is_wildcard:
                if imported.module_specifier not in index.java_packages and not imported.is_static:
                    return self._external(
                        file,
                        ref,
                        ExternalDependency(
                            ecosystem="java_namespace", namespace=imported.module_specifier
                        ),
                    )
                return self._empty(file, ref)
            qualified = imported.module_specifier
            if imported.is_static:
                classes = index.qualified.get((Language.JAVA, qualified), ())
                keys = tuple(
                    key
                    for owner in classes
                    for key in index.container.get((owner, imported.imported_name or ""), ())
                )
                if keys:
                    return self._choose(
                        file, ref, keys, ResolutionMethod.EXACT_IMPORT, index, static_only=True
                    )
            else:
                keys = index.qualified.get((Language.JAVA, qualified), ())
                if keys:
                    return self._choose(
                        file, ref, keys, ResolutionMethod.EXACT_IMPORT, index, TYPE_KINDS
                    )
            namespace = qualified.rpartition(".")[0]
            if imported.is_static:
                namespace = imported.module_specifier.rpartition(".")[0]
            if namespace in index.java_packages:
                return self._empty(file, ref)
            return self._external(
                file,
                ref,
                ExternalDependency(ecosystem="java_namespace", namespace=namespace or qualified),
            )
        module = imported.module_specifier
        if not module.startswith("."):
            if module.startswith("node:"):
                external = ExternalDependency(ecosystem="node", namespace=module[5:].split("/")[0])
            else:
                parts = module.split("/")
                external = ExternalDependency(
                    ecosystem="npm",
                    namespace="/".join(parts[:2]) if module.startswith("@") else parts[0],
                )
            return self._external(file, ref, external)
        targets = index.relative_modules(file.source_file.relative_path, module)
        if len(targets) > 1:
            return ResolutionResult(
                source_file=file.source_file.relative_path,
                reference=ref,
                status=ResolutionStatus.AMBIGUOUS,
                method=ResolutionMethod.EXPLICIT_RELATIVE_MODULE,
                candidates=targets,
            )
        if not targets:
            return self._empty(file, ref)
        target_file = targets[0]
        if imported.imported_name is None:
            return ResolutionResult(
                source_file=file.source_file.relative_path,
                reference=ref,
                status=ResolutionStatus.RESOLVED,
                method=ResolutionMethod.EXPLICIT_RELATIVE_MODULE,
                target_file=target_file,
            )
        return self._choose(
            file,
            ref,
            index.exports.get((target_file, imported.imported_name), ()),
            ResolutionMethod.EXACT_IMPORT,
            index,
        )

    @staticmethod
    def _container(
        file: ExtractedFileFacts, ref: SymbolReference, index: SymbolIndex
    ) -> str | None:
        key = ref.source_key
        while key is not None:
            declaration = index.symbols[key].declaration
            if declaration.kind in {
                NodeKind.CLASS,
                NodeKind.INTERFACE,
                NodeKind.ENUM,
                NodeKind.MODULE,
            }:
                return key
            key = declaration.container_key
        return None

    def _type(
        self, file: ExtractedFileFacts, ref: SymbolReference, name: str, index: SymbolIndex
    ) -> ResolutionResult:
        path = file.source_file.relative_path
        if file.language == Language.JAVA and "." in name:
            keys = index.qualified.get((Language.JAVA, name), ())
            if keys:
                return self._choose(
                    file, ref, keys, ResolutionMethod.EXACT_QUALIFIED, index, TYPE_KINDS
                )
            prefix, _, member = name.partition(".")
            root = self._type(file, ref, prefix, index)
            if root.status == ResolutionStatus.RESOLVED and root.target_key:
                qualified = index.symbols[root.target_key].declaration.qualified_name + "." + member
                return self._choose(
                    file,
                    ref,
                    index.qualified.get((Language.JAVA, qualified), ()),
                    ResolutionMethod.EXACT_QUALIFIED,
                    index,
                    TYPE_KINDS,
                )
            return self._empty(file, ref)
        container = self._container(file, ref, index)
        if container is not None:
            declaration = index.symbols[container].declaration
            if declaration.name == name:
                return self._choose(
                    file, ref, (container,), ResolutionMethod.UNIQUE_CONTAINER, index, TYPE_KINDS
                )
            nested = index.container.get((container, name), ())
            if nested:
                return self._choose(
                    file, ref, nested, ResolutionMethod.UNIQUE_CONTAINER, index, TYPE_KINDS
                )
        keys = index.top.get((path, name), ())
        if keys:
            return self._choose(file, ref, keys, ResolutionMethod.SAME_FILE, index, TYPE_KINDS)
        bindings = index.bindings.get((path, name), ())
        if bindings:
            if len(bindings) > 1:
                return ResolutionResult(
                    source_file=path,
                    reference=ref,
                    status=ResolutionStatus.AMBIGUOUS,
                    candidates=tuple(f"binding:{i}" for i in range(len(bindings))),
                )
            return self._import(file, ref, bindings[0], index)
        if file.language == Language.JAVA:
            keys = index.package.get((file.package_name or "", name), ())
            if keys:
                return self._choose(
                    file, ref, keys, ResolutionMethod.SAME_PACKAGE, index, TYPE_KINDS
                )
        global_types = tuple(
            key
            for key in index.simple.get((file.language, name), ())
            if index.symbols[key].declaration.kind in TYPE_KINDS
        )
        if len(global_types) > 1:
            return self._choose(file, ref, global_types, ResolutionMethod.NONE, index, TYPE_KINDS)
        return self._empty(file, ref)

    def _call(
        self, file: ExtractedFileFacts, ref: SymbolReference, index: SymbolIndex
    ) -> ResolutionResult:
        path = file.source_file.relative_path
        container = self._container(file, ref, index)
        source = index.symbols.get(ref.source_key) if ref.source_key is not None else None
        static_context = source is not None and "static" in source.declaration.modifiers
        if ref.receiver == "this":
            if container is None or index.symbols[container].declaration.kind == NodeKind.MODULE:
                return self._empty(file, ref)
            keys = index.container.get((container, ref.name), ())
            if file.language != Language.JAVA:
                keys = tuple(
                    key
                    for key in keys
                    if ("static" in index.symbols[key].declaration.modifiers) == static_context
                )
            return self._choose(
                file,
                ref,
                keys,
                ResolutionMethod.UNIQUE_CONTAINER,
                index,
                CALL_KINDS,
                static_only=static_context,
            )
        if ref.receiver is not None:
            bindings = index.bindings.get((path, ref.receiver), ())
            if (
                len(bindings) == 1
                and bindings[0].imported_name is None
                and file.language != Language.JAVA
            ):
                imported = bindings[0]
                module_result = self._import(file, ref, imported, index)
                if module_result.status == ResolutionStatus.EXTERNAL:
                    return module_result
                if module_result.status == ResolutionStatus.RESOLVED and module_result.target_file:
                    return self._choose(
                        file,
                        ref,
                        index.exports.get((module_result.target_file, ref.name), ()),
                        ResolutionMethod.EXACT_IMPORT,
                        index,
                        frozenset({NodeKind.FUNCTION}),
                    )
                return module_result
            receiver = self._type(file, ref, ref.receiver, index)
            if receiver.status == ResolutionStatus.EXTERNAL:
                return receiver
            if receiver.status != ResolutionStatus.RESOLVED or receiver.target_key is None:
                return receiver
            owner = index.symbols[receiver.target_key].declaration
            keys = index.container.get((owner.key, ref.name), ())
            if owner.kind == NodeKind.MODULE:
                keys = tuple(key for key in keys if index.symbols[key].declaration.is_exported)
                return self._choose(
                    file,
                    ref,
                    keys,
                    ResolutionMethod.UNIQUE_CONTAINER,
                    index,
                    frozenset({NodeKind.FUNCTION}),
                )
            return self._choose(
                file,
                ref,
                keys,
                ResolutionMethod.STATIC_QUALIFIED,
                index,
                frozenset({NodeKind.METHOD}),
                static_only=True,
            )
        if container is not None and (
            file.language == Language.JAVA
            or index.symbols[container].declaration.kind == NodeKind.MODULE
        ):
            keys = index.container.get((container, ref.name), ())
            if keys:
                return self._choose(
                    file,
                    ref,
                    keys,
                    ResolutionMethod.UNIQUE_CONTAINER,
                    index,
                    CALL_KINDS,
                    static_only=static_context,
                )
        keys = index.top.get((path, ref.name), ())
        if keys:
            return self._choose(
                file, ref, keys, ResolutionMethod.SAME_FILE, index, frozenset({NodeKind.FUNCTION})
            )
        bindings = index.bindings.get((path, ref.name), ())
        if len(bindings) == 1:
            binding_result = self._import(file, ref, bindings[0], index)
            if (
                binding_result.status == ResolutionStatus.RESOLVED
                and binding_result.target_key is not None
            ):
                symbol = index.symbols[binding_result.target_key]
                static_only = file.language == Language.JAVA
                return self._choose(
                    file,
                    ref,
                    (symbol.declaration.key,),
                    ResolutionMethod.EXACT_IMPORT,
                    index,
                    CALL_KINDS,
                    static_only=static_only,
                )
            return (
                binding_result
                if binding_result.status != ResolutionStatus.RESOLVED
                else self._empty(file, ref)
            )
        if len(bindings) > 1:
            return ResolutionResult(
                source_file=path,
                reference=ref,
                status=ResolutionStatus.AMBIGUOUS,
                candidates=tuple(f"binding:{i}" for i in range(len(bindings))),
            )
        return self._empty(file, ref)
