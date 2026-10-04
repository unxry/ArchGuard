from uuid import UUID

from pydantic import ValidationError

from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.extraction.errors import IAMValidationError
from archguard.iam.model import ArchitectureModel


def validate_built_iam(model: ArchitectureModel) -> None:
    try:
        ArchitectureModel.model_validate(model.model_dump())
        _validate_structure(model)
    except (ValueError, TypeError, ValidationError) as error:
        raise IAMValidationError("IAM structure or provenance is invalid") from error


def _validate_structure(model: ArchitectureModel) -> None:
    nodes = {str(node.id): node for node in model.nodes}
    roots = [node for node in model.nodes if node.kind == NodeKind.PROJECT]
    if len(roots) != 1 or roots[0].attributes.get("parent_node_id") is not None:
        raise ValueError("exactly one containment root is required")
    root = str(roots[0].id)
    parents: dict[str, str] = {}
    symbols = {str(symbol.id): symbol for symbol in model.symbols}
    for node in model.nodes:
        if str(node.id) == root:
            continue
        parent = node.attributes.get("parent_node_id")
        if not isinstance(parent, str) or parent not in nodes:
            raise ValueError("every non-root node requires an existing parent")
        UUID(parent)
        parents[str(node.id)] = parent
        parent_node = nodes[parent]
        if node.symbol_id is not None:
            symbol = symbols[str(node.symbol_id)]
            container = symbol.attributes.get("container_symbol_id")
            if container is None:
                if parent_node.kind != NodeKind.FILE or parent_node.file_id != node.file_id:
                    raise ValueError("top declaration must belong to its source file")
            elif str(parent_node.symbol_id) != container or parent_node.file_id != node.file_id:
                raise ValueError("symbol container must be a declaration in the same file")
        elif node.kind in {NodeKind.MODULE, NodeKind.EXTERNAL_DEPENDENCY}:
            if parent != root:
                raise ValueError("structural modules and external dependencies belong to project")
        elif node.kind == NodeKind.PACKAGE:
            if (
                parent_node.kind not in {NodeKind.MODULE, NodeKind.PACKAGE}
                or parent_node.module != node.module
            ):
                raise ValueError("package hierarchy must belong to one module")
        elif node.kind == NodeKind.FILE:
            if (
                parent_node.kind not in {NodeKind.MODULE, NodeKind.PACKAGE}
                or parent_node.module != node.module
            ):
                raise ValueError("file hierarchy must agree with its module")
            if node.package is not None and parent_node.package != node.package:
                raise ValueError("file parent must be its package")
        else:
            raise ValueError("declaration node requires a symbol")
    complete = {root}
    for key in parents:
        chain: set[str] = set()
        cursor = key
        while cursor not in complete:
            if cursor in chain or cursor not in parents:
                raise ValueError("cyclic or disconnected containment")
            chain.add(cursor)
            cursor = parents[cursor]
        complete.update(chain)
    for records, attribute in (
        (model.modules, "module"),
        (model.packages, "package"),
        (model.source_files, "file_id"),
        (model.symbols, "symbol_id"),
    ):
        expected_kind = {
            "module": NodeKind.MODULE,
            "package": NodeKind.PACKAGE,
            "file_id": NodeKind.FILE,
        }.get(attribute)
        linked = [
            getattr(node, attribute)
            for node in model.nodes
            if (
                node.kind == expected_kind and node.symbol_id is None
                if expected_kind
                else node.symbol_id is not None
            )
        ]
        if sorted(str(item) for item in linked) != sorted(str(item.id) for item in records):
            raise ValueError("each entity requires exactly one corresponding node")
    for edge in model.edges:
        source, target = nodes[str(edge.source_id)], nodes[str(edge.target_id)]
        proof = edge.attributes.get("provenance")
        if not isinstance(proof, list) or not proof:
            raise ValueError("built edges require provenance")
        count = edge.attributes.get("occurrences")
        truncated = edge.attributes.get("provenance_truncated")
        if not isinstance(count, int) or count < len(proof) or truncated != count - len(proof):
            raise ValueError("provenance counts must agree")
        for item in proof:
            if not isinstance(item, dict) or item.get("resolution_method") in {None, "NONE"}:
                raise ValueError("edge requires an explicit resolution method")
            status = item.get("resolution_status")
            if status not in {"RESOLVED", "EXTERNAL"}:
                raise ValueError("uncertain references cannot produce edges")
            if status == "EXTERNAL" and (
                edge.kind != EdgeKind.IMPORTS or target.kind != NodeKind.EXTERNAL_DEPENDENCY
            ):
                raise ValueError("external targets are only definite import dependencies")
            location = item.get("source_location")
            if not isinstance(location, dict) or (
                source.source_location is not None
                and location.get("file_path") != source.source_location.file_path
            ):
                raise ValueError("provenance location must agree with its source")
        if edge.kind == EdgeKind.CALLS and target.kind not in {NodeKind.METHOD, NodeKind.FUNCTION}:
            raise ValueError("call target must be callable")
        if edge.kind == EdgeKind.CREATES and target.kind != NodeKind.CLASS:
            raise ValueError("creation target must be a constructor-bearing declaration")
