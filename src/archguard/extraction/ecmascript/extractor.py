from tree_sitter import Node

from archguard.core.model.enums import NodeKind
from archguard.extraction.collector import FactCollector, collect_shadow_names
from archguard.extraction.common import (
    child,
    dotted_name,
    location,
    module_literal,
    text,
    type_signature,
    walk,
)
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ImportKind, ReferenceKind, Visibility
from archguard.extraction.models import (
    ExtractedExport,
    ExtractedFileFacts,
    ExtractedImport,
    ExtractedParameter,
    ExtractorMetadata,
)
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParsedSourceFile

ES_TYPES = {
    "class_declaration": NodeKind.CLASS,
    "abstract_class_declaration": NodeKind.CLASS,
    "interface_declaration": NodeKind.INTERFACE,
    "enum_declaration": NodeKind.ENUM,
    "type_alias_declaration": NodeKind.TYPE_ALIAS,
    "internal_module": NodeKind.MODULE,
    "module": NodeKind.MODULE,
}


def _parameters(node: Node) -> tuple[ExtractedParameter, ...]:
    formal = child(node, "parameters")
    parameters = formal.named_children if formal is not None else []
    single = child(node, "parameter")
    if single is not None:
        parameters = [single]
    result = []
    for item in parameters:
        pattern = child(item, "pattern") or child(item, "left")
        name = dotted_name(pattern or item) or "pattern"
        result.append(
            ExtractedParameter(
                name=name,
                type_name=type_signature(child(item, "type")),
                optional=item.type in {"optional_parameter", "assignment_pattern"}
                or child(item, "value") is not None,
                is_rest=item.type == "rest_pattern"
                or (pattern is not None and pattern.type == "rest_pattern"),
            )
        )
    return tuple(result)


def _flags(node: Node) -> tuple[tuple[str, ...], Visibility, bool, bool]:
    values = {
        text(item)
        for item in node.children
        if not item.is_named
        and text(item) in {"static", "async", "abstract", "readonly", "declare", "override"}
    }
    accessibility = next(
        (text(item) for item in node.named_children if item.type == "accessibility_modifier"), None
    )
    if accessibility is not None:
        values.add(accessibility)
    visibility = (
        Visibility(accessibility.upper())
        if accessibility in {"public", "private", "protected"}
        else Visibility.DEFAULT
    )
    export_parent = node.parent
    if export_parent is not None and export_parent.type in {
        "lexical_declaration",
        "variable_declaration",
    }:
        export_parent = export_parent.parent
    exported = export_parent is not None and export_parent.type == "export_statement"
    default = (
        exported
        and export_parent is not None
        and any(item.type == "default" for item in export_parent.children)
    )
    return tuple(sorted(values)), visibility, exported, default


def _decorators(node: Node) -> tuple[str, ...]:
    owners = [node]
    if node.parent is not None and node.parent.type == "export_statement":
        owners.append(node.parent)
    names = set()
    for owner in owners:
        for decorator in owner.named_children:
            if decorator.type != "decorator" or not decorator.named_children:
                continue
            expression = decorator.named_children[0]
            target = (
                child(expression, "function")
                if expression.type == "call_expression"
                else expression
            )
            if name := dotted_name(target):
                names.add(name)
    return tuple(sorted(names))


class ECMAScriptExtractor:
    def __init__(self, language: ParserLanguage) -> None:
        if language not in {
            ParserLanguage.TYPESCRIPT,
            ParserLanguage.JAVASCRIPT,
            ParserLanguage.TSX,
        }:
            raise ValueError("ECMAScript extractor requires an ES dialect")
        self.language = language
        self.metadata = ExtractorMetadata(
            extractor_id=f"{language.value.lower()}-syntax-extractor",
            extractor_version="1.1.0",
            dialect=language,
        )

    def extract(
        self, parsed_file: ParsedSourceFile, config: ExtractionConfig
    ) -> ExtractedFileFacts:
        collector = FactCollector(parsed_file, self.metadata, config)
        nodes = list(walk(parsed_file.root))
        for node in nodes:
            if collector.is_ignored(node):
                continue
            container = collector.owner(node.parent)
            parent = collector.declarations.get(container) if container is not None else None
            values, visibility, exported, default = _flags(node)
            if node.type in ES_TYPES or node.type in {
                "function_declaration",
                "generator_function_declaration",
                "function_signature",
            }:
                if parent is not None and parent.kind not in {NodeKind.MODULE, NodeKind.CLASS}:
                    collector.ignore(node)
                    collector.shadows.setdefault(container, set()).add(
                        text(child(node, "name")) or "local"
                    )
                    collector.diagnostic(
                        node, "local declaration is omitted from architecture symbols"
                    )
                    continue
                name = dotted_name(child(node, "name"))
                if name is None:
                    collector.ignore(node)
                    collector.diagnostic(node, "anonymous or ambient declaration is omitted")
                    continue
                kind = ES_TYPES.get(node.type, NodeKind.FUNCTION)
                parameters = _parameters(node) if kind == NodeKind.FUNCTION else ()
                signature = (
                    "(" + ",".join(item.type_name or "?" for item in parameters) + ")"
                    if kind == NodeKind.FUNCTION
                    else None
                )
                generics = child(node, "type_parameters")
                type_parameters = (
                    tuple(
                        text(
                            child(item, "name")
                            or (item.named_children[0] if item.named_children else item)
                        )
                        for item in generics.named_children
                    )
                    if generics is not None
                    else ()
                )
                collector.declare(
                    node,
                    kind,
                    name,
                    container,
                    signature,
                    visibility,
                    values,
                    annotations=_decorators(node),
                    type_parameters=type_parameters,
                    parameters=parameters,
                    type_name=type_signature(child(node, "return_type")),
                    exported=exported,
                    default_export=default,
                )
            elif node.type in {
                "method_definition",
                "method_signature",
                "abstract_method_signature",
            }:
                if parent is None or parent.kind not in {NodeKind.CLASS, NodeKind.INTERFACE}:
                    collector.ignore(node)
                    continue
                name = dotted_name(child(node, "name"))
                if name is None:
                    collector.ignore(node)
                    collector.diagnostic(
                        node, "computed method name is not statically identifiable"
                    )
                    continue
                parameters = _parameters(node)
                signature = "(" + ",".join(item.type_name or "?" for item in parameters) + ")"
                kind = NodeKind.CONSTRUCTOR if name == "constructor" else NodeKind.METHOD
                collector.declare(
                    node,
                    kind,
                    name,
                    container,
                    signature,
                    visibility,
                    values,
                    parameters=parameters,
                    type_name=type_signature(child(node, "return_type")),
                )
            elif node.type in {"public_field_definition", "field_definition", "property_signature"}:
                if parent is not None and parent.kind in {NodeKind.CLASS, NodeKind.INTERFACE}:
                    name = dotted_name(child(node, "name"))
                    if name is not None:
                        collector.declare(
                            node,
                            NodeKind.PROPERTY,
                            name,
                            container,
                            visibility=visibility,
                            modifiers=values,
                            type_name=type_signature(child(node, "type")),
                        )
            elif node.type == "variable_declarator":
                value = child(node, "value")
                if value is not None and value.type in {
                    "arrow_function",
                    "function_expression",
                    "generator_function",
                }:
                    name = dotted_name(child(node, "name"))
                    if name is not None and (parent is None or parent.kind == NodeKind.MODULE):
                        parameters = _parameters(value)
                        signature = (
                            "(" + ",".join(item.type_name or "?" for item in parameters) + ")"
                        )
                        modifiers = tuple(
                            sorted(
                                set(values)
                                | (
                                    {"async"}
                                    if any(item.type == "async" for item in value.children)
                                    else set()
                                )
                            )
                        )
                        collector.declare(
                            node,
                            NodeKind.FUNCTION,
                            name,
                            container,
                            signature,
                            modifiers=modifiers,
                            parameters=parameters,
                            exported=exported,
                            default_export=default,
                        )
                    else:
                        collector.ignore(value)
            elif node.type in {"arrow_function", "function_expression", "generator_function"}:
                if node.parent is None or node.parent.id not in collector.node_keys:
                    collector.ignore(node)
        collector.owners.clear()
        collect_shadow_names(collector, nodes)
        for declaration in collector.declarations.values():
            if declaration.name == "require":
                collector.shadows.setdefault(declaration.container_key, set()).add("require")
            if declaration.kind == NodeKind.PROPERTY:
                collector.shadows.setdefault(declaration.container_key, set()).add(declaration.name)
        for node in nodes:
            if not collector.is_ignored(node) and node.type == "import_statement":
                self._es_import(collector, node)
            elif not collector.is_ignored(node) and node.type == "export_statement":
                self._export(collector, node)
            elif not collector.is_ignored(node) and node.type == "assignment_expression":
                self._commonjs_export(collector, node)
        for node in nodes:
            if collector.is_ignored(node):
                continue
            owner = collector.owner(node)
            if node.type in {"extends_clause", "implements_clause", "extends_type_clause"}:
                targets = node.named_children
                reference_kind = (
                    ReferenceKind.IMPLEMENTS
                    if node.type == "implements_clause"
                    else ReferenceKind.EXTENDS
                )
                for target in targets:
                    base = (
                        target.named_children[0]
                        if target.type == "generic_type" and target.named_children
                        else target
                    )
                    name = dotted_name(base)
                    if name:
                        collector.reference(target, name, reference_kind, owner)
                    else:
                        collector.diagnostic(target, "dynamic heritage target remains unresolved")
            elif node.type == "call_expression":
                function = child(node, "function")
                arguments = child(node, "arguments")
                name = dotted_name(function)
                if name == "require" and not self._require_shadowed(collector, owner):
                    self._require(collector, node)
                    continue
                receiver = None
                unknown = False
                if function is not None and function.type == "member_expression":
                    receiver_node = child(function, "object")
                    receiver = dotted_name(receiver_node)
                    name = dotted_name(child(function, "property"))
                    unknown = receiver is None
                if name:
                    collector.reference(
                        node,
                        name,
                        ReferenceKind.CALL,
                        owner,
                        receiver=receiver,
                        unknown_receiver=unknown,
                        argument_count=len(arguments.named_children)
                        if arguments is not None
                        else 0,
                    )
                else:
                    collector.reference(
                        node, "<dynamic-call>", ReferenceKind.CALL, owner, dynamic=True
                    )
            elif node.type == "new_expression":
                constructor_node = child(node, "constructor")
                name = dotted_name(constructor_node)
                if name:
                    collector.reference(node, name, ReferenceKind.CREATE, owner)
                else:
                    collector.reference(
                        node, "<dynamic-constructor>", ReferenceKind.CREATE, owner, dynamic=True
                    )
            elif node.type == "type_identifier":
                if not self._skip_type(node, collector):
                    name = dotted_name(node)
                    if name:
                        collector.reference(node, name, ReferenceKind.TYPE_USE, owner)
        return collector.finish()

    @staticmethod
    def _es_import(collector: FactCollector, node: Node) -> None:
        module = module_literal(child(node, "source"))
        if module is None:
            collector.diagnostic(node, "unsupported module specifier is omitted")
            return
        clause = next((item for item in node.named_children if item.type == "import_clause"), None)
        if clause is None:
            collector.add_import(
                ExtractedImport(
                    module_specifier=module,
                    kind=ImportKind.ES_SIDE_EFFECT,
                    source_location=location(node, collector.path),
                )
            )
            return
        for item in walk(clause):
            if item.type == "import_specifier":
                name = dotted_name(child(item, "name"))
                alias = dotted_name(child(item, "alias")) or name
                if name:
                    collector.add_import(
                        ExtractedImport(
                            module_specifier=module,
                            imported_name=name,
                            local_alias=alias,
                            kind=ImportKind.ES_NAMED,
                            source_location=location(item, collector.path),
                        )
                    )
            elif item.type == "namespace_import":
                alias = next(
                    (text(value) for value in item.named_children if value.type == "identifier"),
                    None,
                )
                collector.add_import(
                    ExtractedImport(
                        module_specifier=module,
                        local_alias=alias,
                        is_wildcard=True,
                        kind=ImportKind.ES_NAMESPACE,
                        source_location=location(item, collector.path),
                    )
                )
            elif (
                item.type == "identifier"
                and item.parent is not None
                and item.parent.type == "import_clause"
            ):
                collector.add_import(
                    ExtractedImport(
                        module_specifier=module,
                        imported_name="default",
                        local_alias=text(item),
                        kind=ImportKind.ES_DEFAULT,
                        source_location=location(item, collector.path),
                    )
                )

    @staticmethod
    def _export(collector: FactCollector, node: Node) -> None:
        module_node = child(node, "source")
        module = module_literal(module_node)
        if module_node is not None and module is None:
            collector.diagnostic(node, "unsupported re-export specifier is omitted")
            return
        clause = next((item for item in node.named_children if item.type == "export_clause"), None)
        if clause is not None:
            for specifier in clause.named_children:
                local = dotted_name(child(specifier, "name"))
                alias = dotted_name(child(specifier, "alias")) or local
                if local and alias:
                    collector.exports.append(
                        ExtractedExport(
                            exported_name=alias,
                            local_name=local,
                            module_specifier=module,
                            source_location=location(specifier, collector.path),
                        )
                    )
        elif module is not None:
            collector.exports.append(
                ExtractedExport(
                    exported_name="*",
                    module_specifier=module,
                    is_wildcard=True,
                    source_location=location(node, collector.path),
                )
            )
        elif child(node, "declaration") is None:
            value = child(node, "value")
            name = dotted_name(value)
            if name:
                collector.exports.append(
                    ExtractedExport(
                        exported_name="default",
                        local_name=name,
                        source_location=location(node, collector.path),
                    )
                )
        if module is not None:
            collector.add_import(
                ExtractedImport(
                    module_specifier=module,
                    kind=ImportKind.ES_SIDE_EFFECT,
                    source_location=location(node, collector.path),
                )
            )

    @staticmethod
    def _require_shadowed(collector: FactCollector, owner: str | None) -> bool:
        return collector.is_shadowed("require", owner)

    @staticmethod
    def _require(collector: FactCollector, node: Node) -> None:
        arguments = child(node, "arguments")
        module = (
            module_literal(arguments.named_children[0])
            if arguments is not None and len(arguments.named_children) == 1
            else None
        )
        if module is None:
            collector.reference(
                node, "require", ReferenceKind.IMPORT, collector.owner(node), dynamic=True
            )
            collector.diagnostic(node, "dynamic or unsupported require remains unresolved")
            return
        parent = node.parent
        binding = (
            child(parent, "name")
            if parent is not None
            and parent.type == "variable_declarator"
            and collector.owner(parent) is None
            else None
        )
        if binding is not None and binding.type == "object_pattern":
            for entry in binding.named_children:
                if entry.type == "pair_pattern":
                    name = dotted_name(child(entry, "key"))
                    alias = dotted_name(child(entry, "value"))
                else:
                    name = alias = dotted_name(entry)
                if name and alias:
                    collector.add_import(
                        ExtractedImport(
                            module_specifier=module,
                            imported_name=name,
                            local_alias=alias,
                            kind=ImportKind.COMMONJS,
                            source_location=location(entry, collector.path),
                        )
                    )
        else:
            collector.add_import(
                ExtractedImport(
                    module_specifier=module,
                    local_alias=dotted_name(binding),
                    kind=ImportKind.COMMONJS,
                    source_location=location(node, collector.path),
                )
            )

    @staticmethod
    def _commonjs_export(collector: FactCollector, node: Node) -> None:
        if collector.owner(node) is not None:
            return
        left = dotted_name(child(node, "left"))
        if left is not None and left.split(".")[0] in collector.shadows.get(None, set()):
            return
        right = child(node, "right")
        if left == "module.exports" and right is not None and right.type == "object":
            for entry in right.named_children:
                if entry.type == "pair":
                    exported = dotted_name(child(entry, "key"))
                    local = dotted_name(child(entry, "value"))
                else:
                    exported = local = dotted_name(entry)
                if exported and local:
                    collector.exports.append(
                        ExtractedExport(
                            exported_name=exported,
                            local_name=local,
                            source_location=location(entry, collector.path),
                        )
                    )
        elif left is not None and (
            left.startswith("exports.") or left.startswith("module.exports.")
        ):
            local = dotted_name(right)
            if local:
                collector.exports.append(
                    ExtractedExport(
                        exported_name=left.rsplit(".", 1)[-1],
                        local_name=local,
                        source_location=location(node, collector.path),
                    )
                )
        elif left == "module.exports":
            local = dotted_name(right)
            if local:
                collector.exports.append(
                    ExtractedExport(
                        exported_name="default",
                        local_name=local,
                        source_location=location(node, collector.path),
                    )
                )

    @staticmethod
    def _skip_type(node: Node, collector: FactCollector) -> bool:
        current = node.parent
        while current is not None:
            if current.type in {
                "type_parameter",
                "extends_clause",
                "implements_clause",
                "extends_type_clause",
            }:
                return True
            if current.id in collector.node_keys:
                declaration = collector.declarations[collector.node_keys[current.id]]
                if child(current, "name") == node or text(node) in declaration.type_parameters:
                    return True
                if declaration.container_key is None:
                    break
            current = current.parent
        return False


class TypeScriptExtractor(ECMAScriptExtractor):
    def __init__(self) -> None:
        super().__init__(ParserLanguage.TYPESCRIPT)


class JavaScriptExtractor(ECMAScriptExtractor):
    def __init__(self) -> None:
        super().__init__(ParserLanguage.JAVASCRIPT)


class TSXExtractor(ECMAScriptExtractor):
    def __init__(self) -> None:
        super().__init__(ParserLanguage.TSX)
