from tree_sitter import Node

from archguard.core.locations import SourceLocation
from archguard.core.model.enums import Language, NodeKind
from archguard.extraction.common import child, location, text, walk
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ExtractionDiagnosticCode, ReferenceKind, Visibility
from archguard.extraction.errors import ExtractionLimitError
from archguard.extraction.identity import canonical_identity, declaration_key
from archguard.extraction.models import (
    ExtractedDeclaration,
    ExtractedExport,
    ExtractedFileFacts,
    ExtractedImport,
    ExtractedParameter,
    ExtractionDiagnostic,
    ExtractorMetadata,
    SymbolReference,
)
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParsedSourceFile


class FactCollector:
    def __init__(
        self, parsed: ParsedSourceFile, metadata: ExtractorMetadata, config: ExtractionConfig
    ) -> None:
        self.parsed = parsed
        self.metadata = metadata
        self.config = config
        self.path = parsed.metadata.source_file.relative_path
        self.language = (
            Language.TYPESCRIPT
            if metadata.dialect == ParserLanguage.TSX
            else Language(metadata.dialect.value)
        )
        self.package: str | None = "" if self.language == Language.JAVA else None
        self.declarations: dict[str, ExtractedDeclaration] = {}
        self.node_keys: dict[int, str] = {}
        self.owners: dict[int, str | None] = {}
        self.ignored: set[int] = set()
        self.ignore_cache: dict[int, bool] = {}
        self.imports: list[ExtractedImport] = []
        self.exports: list[ExtractedExport] = []
        self.references: list[SymbolReference] = []
        self.diagnostics: list[ExtractionDiagnostic] = []
        self.shadows: dict[str | None, set[str]] = {}

    def owner(self, node: Node | None) -> str | None:
        chain = []
        key: str | None = None
        while node is not None and node.id not in self.owners:
            if node.id in self.node_keys:
                key = self.node_keys[node.id]
                break
            chain.append(node.id)
            node = node.parent
        else:
            key = self.owners.get(node.id) if node is not None else None
        for item in chain:
            self.owners[item] = key
        return key

    def is_ignored(self, node: Node) -> bool:
        chain = []
        current: Node | None = node
        while current is not None and current.id not in self.ignore_cache:
            if current.id in self.ignored:
                value = True
                break
            chain.append(current.id)
            current = current.parent
        else:
            value = self.ignore_cache.get(current.id, False) if current is not None else False
        for item in chain:
            self.ignore_cache[item] = value
        return value

    def ignore(self, node: Node) -> None:
        self.ignored.add(node.id)
        self.ignore_cache[node.id] = True

    def declare(
        self,
        node: Node,
        kind: NodeKind,
        name: str,
        container: str | None,
        signature: str | None = None,
        visibility: Visibility = Visibility.DEFAULT,
        modifiers: tuple[str, ...] = (),
        annotations: tuple[str, ...] = (),
        type_parameters: tuple[str, ...] = (),
        parameters: tuple[ExtractedParameter, ...] = (),
        type_name: str | None = None,
        exported: bool = False,
        default_export: bool = False,
    ) -> str:
        if len(self.declarations) >= self.config.max_declarations_per_file:
            raise ExtractionLimitError("declaration limit exceeded")
        parent = self.declarations.get(container) if container is not None else None
        if parent is not None:
            delimiter = (
                "."
                if kind in {NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.ENUM}
                and self.language == Language.JAVA
                else "#"
            )
            qualified = parent.qualified_name + delimiter + name + (signature or "")
        elif self.language == Language.JAVA:
            qualified = (self.package + "." if self.package else "") + name + (signature or "")
        else:
            qualified = self.path + "::" + name + (signature or "")
        key = declaration_key(self.path, self.language, kind, qualified, signature)
        if key in self.declarations:
            raise ValueError("duplicate incompatible declaration identity")
        self.declarations[key] = ExtractedDeclaration(
            key=key,
            kind=kind,
            name=name,
            qualified_name=qualified,
            container_key=container,
            signature=signature,
            visibility=visibility,
            modifiers=modifiers,
            annotations=annotations,
            type_parameters=type_parameters,
            parameters=parameters,
            type_name=type_name,
            is_exported=exported,
            is_default_export=default_export,
            source_location=location(node, self.path),
        )
        self.node_keys[node.id] = key
        return key

    def add_import(self, value: ExtractedImport) -> None:
        if len(self.imports) >= self.config.max_imports_per_file:
            raise ExtractionLimitError("import limit exceeded")
        index = len(self.imports)
        self.imports.append(value)
        self.reference(
            None,
            value.imported_name or value.module_specifier,
            ReferenceKind.IMPORT,
            import_index=index,
            module_specifier=value.module_specifier,
            source_location=value.source_location,
        )

    def reference(
        self,
        node: Node | None,
        name: str,
        kind: ReferenceKind,
        source_key: str | None = None,
        qualified_hint: str | None = None,
        module_specifier: str | None = None,
        import_index: int | None = None,
        receiver: str | None = None,
        unknown_receiver: bool = False,
        argument_count: int | None = None,
        dynamic: bool = False,
        source_location: SourceLocation | None = None,
    ) -> None:
        if len(self.references) >= self.config.max_references_per_file:
            raise ExtractionLimitError("reference limit exceeded")
        if source_location is None:
            assert node is not None
            site = location(node, self.path)
        else:
            site = source_location
        blocked = self.is_shadowed(receiver.split(".")[0] if receiver else name, source_key)
        self.references.append(
            SymbolReference(
                key=canonical_identity("reference-v1", self.path, str(len(self.references))),
                name=name,
                reference_kind=kind,
                source_key=source_key,
                qualified_name_hint=qualified_hint,
                module_specifier=module_specifier,
                import_index=import_index,
                receiver=receiver,
                unknown_receiver=unknown_receiver,
                argument_count=argument_count,
                blocked_by_local_binding=blocked,
                is_dynamic=dynamic,
                source_location=site,
            )
        )

    def is_shadowed(self, name: str, scope: str | None) -> bool:
        if name in self.shadows.get(None, set()):
            return True
        while scope is not None:
            if name in self.shadows.get(scope, set()):
                return True
            scope = self.declarations[scope].container_key
        return False

    def diagnostic(self, node: Node, message: str) -> None:
        self.diagnostics.append(
            ExtractionDiagnostic(
                code=ExtractionDiagnosticCode.UNSUPPORTED_CONSTRUCT,
                message=message,
                source_location=location(node, self.path),
            )
        )

    def finish(self) -> ExtractedFileFacts:
        parser = self.parsed.metadata.parser
        assert parser is not None
        declarations = tuple(
            item.model_copy(update={"shadowed_names": tuple(sorted(self.shadows.get(key, set())))})
            for key, item in sorted(self.declarations.items())
        )
        return ExtractedFileFacts(
            snapshot_id=self.parsed.metadata.snapshot_id,
            source_file=self.parsed.metadata.source_file,
            language=self.language,
            package_name=self.package,
            declarations=declarations,
            imports=tuple(self.imports),
            exports=tuple(self.exports),
            references=tuple(self.references),
            shadowed_names=tuple(sorted(self.shadows.get(None, set()))),
            diagnostics=tuple(self.diagnostics),
            source_had_syntax_errors=self.parsed.metadata.has_syntax_errors,
            extractor=self.metadata,
            parser=parser,
        )


def collect_shadow_names(collector: FactCollector, nodes: list[Node]) -> None:
    for node in nodes:
        if collector.is_ignored(node):
            continue
        if node.type in {
            "formal_parameter",
            "spread_parameter",
            "required_parameter",
            "optional_parameter",
            "catch_formal_parameter",
        }:
            pattern = child(node, "name") or child(node, "pattern")
        elif node.parent is not None and node.parent.type in {
            "formal_parameters",
            "inferred_parameters",
        }:
            pattern = child(node, "pattern") or child(node, "left") or node
        elif node.type in {"arrow_function", "catch_clause", "lambda_expression"}:
            pattern = child(node, "parameter") or child(node, "parameters")
        elif node.type == "assignment_expression":
            pattern = child(node, "left")
            if pattern is None or pattern.type not in {
                "identifier",
                "object_pattern",
                "array_pattern",
            }:
                continue
        elif node.type == "variable_declarator":
            if node.id in collector.node_keys:
                declaration = collector.declarations[collector.node_keys[node.id]]
                if declaration.kind in {NodeKind.FIELD, NodeKind.PROPERTY}:
                    collector.shadows.setdefault(declaration.container_key, set()).add(
                        declaration.name
                    )
                continue
            value = child(node, "value")
            if (
                value is not None
                and value.type == "call_expression"
                and text(child(value, "function")) == "require"
                and collector.owner(node) is None
            ):
                continue
            pattern = child(node, "name")
        elif (
            node.type in {"function_declaration", "class_declaration"}
            and node.id not in collector.node_keys
        ):
            pattern = child(node, "name")
        else:
            continue
        if pattern is not None:
            owner = collector.owner(node)
            for leaf in walk(pattern):
                if leaf.type in {"identifier", "shorthand_property_identifier_pattern"}:
                    collector.shadows.setdefault(owner, set()).add(text(leaf))
