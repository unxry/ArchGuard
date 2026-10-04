from tree_sitter import Node

from archguard.core.model.enums import NodeKind
from archguard.extraction.collector import FactCollector, collect_shadow_names
from archguard.extraction.common import child, dotted_name, location, text, type_signature, walk
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ImportKind, ReferenceKind, Visibility
from archguard.extraction.models import (
    ExtractedFileFacts,
    ExtractedImport,
    ExtractedParameter,
    ExtractorMetadata,
)
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParsedSourceFile

JAVA_TYPES = {
    "class_declaration": NodeKind.CLASS,
    "interface_declaration": NodeKind.INTERFACE,
    "enum_declaration": NodeKind.ENUM,
    "annotation_type_declaration": NodeKind.INTERFACE,
    "record_declaration": NodeKind.CLASS,
}


def _modifiers(node: Node) -> tuple[tuple[str, ...], tuple[str, ...], Visibility]:
    modifier = next((item for item in node.named_children if item.type == "modifiers"), None)
    if modifier is None:
        return (), (), Visibility.DEFAULT
    values = tuple(sorted(text(item) for item in modifier.children if not item.is_named))
    annotations = tuple(
        sorted(
            name
            for item in modifier.named_children
            if (name := dotted_name(child(item, "name"))) is not None
        )
    )
    visibility = next(
        (
            Visibility(value.upper())
            for value in values
            if value in {"public", "private", "protected"}
        ),
        Visibility.DEFAULT,
    )
    return values, annotations, visibility


def _parameters(node: Node) -> tuple[ExtractedParameter, ...]:
    formal = child(node, "parameters")
    if formal is None:
        return ()
    result = []
    for parameter in formal.named_children:
        name = text(child(parameter, "name"))
        if not name:
            name = next(
                (
                    text(item)
                    for item in parameter.named_children
                    if item.type == "variable_declarator"
                ),
                "parameter",
            )
        result.append(
            ExtractedParameter(
                name=name,
                type_name=type_signature(child(parameter, "type")),
                is_rest=parameter.type == "spread_parameter",
            )
        )
    return tuple(result)


def _heritage_types(node: Node) -> list[Node]:
    if node.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
        return [node]
    return [item for child_node in node.named_children for item in _heritage_types(child_node)]


def _base_type(node: Node) -> str | None:
    return (
        dotted_name(node.named_children[0])
        if node.type == "generic_type" and node.named_children
        else dotted_name(node)
    )


def _type_parameters(node: Node) -> tuple[str, ...]:
    generics = child(node, "type_parameters")
    if generics is None:
        return ()
    return tuple(
        text(identifier)
        for parameter in generics.named_children
        if (
            identifier := next(
                (item for item in parameter.named_children if item.type == "type_identifier"), None
            )
        )
        is not None
    )


class JavaExtractor:
    language = ParserLanguage.JAVA
    metadata = ExtractorMetadata(
        extractor_id="java-syntax-extractor", extractor_version="1.0.0", dialect=language
    )

    def extract(
        self, parsed_file: ParsedSourceFile, config: ExtractionConfig
    ) -> ExtractedFileFacts:
        collector = FactCollector(parsed_file, self.metadata, config)
        nodes = list(walk(parsed_file.root))
        name: str | None
        for node in parsed_file.root.named_children:
            if node.type == "package_declaration":
                collector.package = (
                    next(
                        (
                            dotted_name(item)
                            for item in node.named_children
                            if item.type in {"identifier", "scoped_identifier"}
                        ),
                        "",
                    )
                    or ""
                )
            elif node.type == "import_declaration":
                import_target = next(
                    (
                        dotted_name(item)
                        for item in node.named_children
                        if item.type in {"identifier", "scoped_identifier"}
                    ),
                    None,
                )
                if import_target is not None:
                    wildcard = any(item.type == "asterisk" for item in node.named_children)
                    static = any(item.type == "static" for item in node.children)
                    module, _, name = import_target.rpartition(".")
                    collector.add_import(
                        ExtractedImport(
                            module_specifier=import_target if wildcard or not static else module,
                            imported_name=None if wildcard else name or import_target,
                            local_alias=None if wildcard else name or import_target,
                            kind=ImportKind.JAVA,
                            is_wildcard=wildcard,
                            is_static=static,
                            source_location=location(node, collector.path),
                        )
                    )
        for node in nodes:
            if collector.is_ignored(node):
                continue
            parent_key = collector.owner(node.parent)
            parent = collector.declarations.get(parent_key) if parent_key is not None else None
            if node.type in JAVA_TYPES:
                if parent is not None and parent.kind not in {
                    NodeKind.CLASS,
                    NodeKind.INTERFACE,
                    NodeKind.ENUM,
                }:
                    collector.shadows.setdefault(parent_key, set()).add(text(child(node, "name")))
                    collector.ignore(node)
                    collector.diagnostic(
                        node, "local type declaration is omitted from architecture symbols"
                    )
                    continue
                name = text(child(node, "name"))
                if not name:
                    continue
                values, annotations, visibility = _modifiers(node)
                collector.declare(
                    node,
                    JAVA_TYPES[node.type],
                    name,
                    parent_key,
                    visibility=visibility,
                    modifiers=values,
                    annotations=annotations,
                    type_parameters=_type_parameters(node),
                )
            elif node.type in {
                "method_declaration",
                "constructor_declaration",
                "compact_constructor_declaration",
                "annotation_type_element_declaration",
            }:
                if parent is None or parent.kind not in {
                    NodeKind.CLASS,
                    NodeKind.INTERFACE,
                    NodeKind.ENUM,
                }:
                    collector.ignore(node)
                    continue
                name = text(child(node, "name"))
                if not name:
                    continue
                parameters = _parameters(node)
                signature = (
                    "("
                    + ",".join(
                        (item.type_name or "?") + ("..." if item.is_rest else "")
                        for item in parameters
                    )
                    + ")"
                )
                values, annotations, visibility = _modifiers(node)
                kind = NodeKind.CONSTRUCTOR if "constructor" in node.type else NodeKind.METHOD
                collector.declare(
                    node,
                    kind,
                    name,
                    parent_key,
                    signature,
                    visibility,
                    values,
                    annotations,
                    type_parameters=_type_parameters(node),
                    parameters=parameters,
                    type_name=type_signature(child(node, "type")),
                )
            elif node.type in {"field_declaration", "constant_declaration"} and parent is not None:
                values, annotations, visibility = _modifiers(node)
                for declarator in node.named_children:
                    if declarator.type == "variable_declarator":
                        collector.declare(
                            declarator,
                            NodeKind.FIELD,
                            text(child(declarator, "name")),
                            parent_key,
                            visibility=visibility,
                            modifiers=values,
                            annotations=annotations,
                            type_name=type_signature(child(node, "type")),
                        )
            elif (
                node.type == "class_body"
                and node.parent is not None
                and node.parent.type == "object_creation_expression"
            ):
                collector.ignore(node)
        collector.owners.clear()
        collect_shadow_names(collector, nodes)
        for node in nodes:
            if collector.is_ignored(node):
                continue
            owner = collector.owner(node)
            if node.type in {"superclass", "super_interfaces", "extends_interfaces"}:
                reference_kind = (
                    ReferenceKind.IMPLEMENTS
                    if node.type == "super_interfaces"
                    else ReferenceKind.EXTENDS
                )
                for heritage_node in _heritage_types(node):
                    name = _base_type(heritage_node)
                    if name:
                        collector.reference(
                            heritage_node,
                            name,
                            reference_kind,
                            owner,
                            qualified_hint=name if "." in name else None,
                        )
            elif node.type == "method_invocation":
                name = text(child(node, "name"))
                receiver_node = child(node, "object")
                receiver = dotted_name(receiver_node)
                arguments = child(node, "arguments")
                if name:
                    collector.reference(
                        node,
                        name,
                        ReferenceKind.CALL,
                        owner,
                        receiver=receiver,
                        unknown_receiver=receiver_node is not None and receiver is None,
                        argument_count=len(arguments.named_children)
                        if arguments is not None
                        else 0,
                    )
            elif node.type == "object_creation_expression":
                creation_type = child(node, "type")
                name = _base_type(creation_type) if creation_type is not None else None
                if name:
                    collector.reference(
                        node,
                        name,
                        ReferenceKind.CREATE,
                        owner,
                        qualified_hint=name if "." in name else None,
                    )
            elif node.type in {"type_identifier", "scoped_type_identifier"}:
                if node.parent is not None and node.parent.type == "scoped_type_identifier":
                    continue
                name = dotted_name(node)
                if name and not self._is_heritage_or_generic_parameter(node, collector):
                    collector.reference(
                        node,
                        name,
                        ReferenceKind.TYPE_USE,
                        owner,
                        qualified_hint=name if "." in name else None,
                    )
            elif node.type in {"annotation", "marker_annotation"}:
                name = dotted_name(child(node, "name"))
                if name:
                    collector.reference(node, name, ReferenceKind.TYPE_USE, owner)
        return collector.finish()

    @staticmethod
    def _is_heritage_or_generic_parameter(node: Node, collector: FactCollector) -> bool:
        current = node.parent
        while current is not None:
            if current.type in {
                "superclass",
                "super_interfaces",
                "extends_interfaces",
                "type_parameter",
                "object_creation_expression",
            }:
                return True
            if current.id in collector.node_keys:
                declaration = collector.declarations[collector.node_keys[current.id]]
                if text(node) in declaration.type_parameters:
                    return True
                if declaration.container_key is None:
                    break
            current = current.parent
        return False
