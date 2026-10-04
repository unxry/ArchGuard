from dataclasses import dataclass

from pydantic import JsonValue, ValidationError

from archguard.architecture.classification.models import ConformanceDiagnostic, NodeClassification
from archguard.architecture.specification.models import DEFAULT_RELATIONS
from archguard.core.locations import SourceLocation
from archguard.core.model.enums import EdgeKind, NodeKind
from archguard.core.model.types import JsonObject
from archguard.iam.edges import ArchitectureEdge
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode

_REFERENCE_KINDS = {
    EdgeKind.IMPORTS: "IMPORT",
    EdgeKind.INHERITS: "EXTENDS",
    EdgeKind.IMPLEMENTS: "IMPLEMENTS",
    EdgeKind.CALLS: "CALL",
    EdgeKind.CREATES: "CREATE",
    EdgeKind.USES: "TYPE_USE",
}
_INTERNAL_METHODS = {
    "EXACT_QUALIFIED",
    "EXACT_IMPORT",
    "SAME_FILE",
    "SAME_PACKAGE",
    "EXPLICIT_RELATIVE_MODULE",
    "UNIQUE_CONTAINER",
    "STATIC_QUALIFIED",
}


@dataclass(frozen=True)
class ProvenDependency:
    edge: ArchitectureEdge
    source: ArchitectureNode
    target: ArchitectureNode
    source_classification: NodeClassification
    target_classification: NodeClassification
    locations: tuple[SourceLocation, ...]
    provenance: tuple[JsonObject, ...]
    occurrences: int
    truncated: int


def proven_dependencies(
    model: ArchitectureModel, classification: dict[str, NodeClassification]
) -> tuple[tuple[ProvenDependency, ...], tuple[ConformanceDiagnostic, ...]]:
    nodes = {node.id: node for node in model.nodes}
    dependencies = []
    diagnostics = []
    for edge in sorted(model.edges, key=lambda item: str(item.id)):
        source, target = nodes[edge.source_id], nodes[edge.target_id]
        if (
            edge.kind not in DEFAULT_RELATIONS
            or source.kind == NodeKind.EXTERNAL_DEPENDENCY
            or target.kind == NodeKind.EXTERNAL_DEPENDENCY
        ):
            continue
        left, right = classification.get(str(source.id)), classification.get(str(target.id))
        if left is None or right is None:
            continue
        try:
            raw = edge.attributes.get("provenance")
            if not isinstance(raw, list) or not raw:
                raise ValueError("missing proof")
            proof: list[JsonObject] = []
            locations = []
            for item in raw:
                if not isinstance(item, dict) or item.get("resolution_status") != "RESOLVED":
                    raise ValueError("uncertain proof")
                method = item.get("resolution_method")
                if not isinstance(method, str) or method not in _INTERNAL_METHODS:
                    raise ValueError("missing method")
                reference = item.get("reference_kind")
                if reference != _REFERENCE_KINDS[edge.kind]:
                    raise ValueError("mismatched reference kind")
                location = SourceLocation.model_validate(item.get("source_location"))
                if location.file_path != left.file_path:
                    raise ValueError("mismatched location")
                locations.append(location)
                proof.append(
                    {
                        "source_location": location.model_dump(mode="json"),
                        "resolution_status": "RESOLVED",
                        "resolution_method": method,
                        "reference_kind": reference,
                    }
                )
            count = edge.attributes.get("occurrences", len(proof))
            truncated = edge.attributes.get("provenance_truncated", 0)
            if (
                type(count) is not int
                or type(truncated) is not int
                or count != len(proof) + truncated
                or truncated < 0
            ):
                raise ValueError("invalid proof counts")
            ordered = sorted(
                zip(locations, proof, strict=True),
                key=lambda item: (location_order(item[0]), str(item[1]["resolution_method"])),
            )
            dependencies.append(
                ProvenDependency(
                    edge=edge,
                    source=source,
                    target=target,
                    source_classification=left,
                    target_classification=right,
                    locations=tuple(item[0] for item in ordered),
                    provenance=tuple(item[1] for item in ordered),
                    occurrences=count,
                    truncated=truncated,
                )
            )
            if truncated:
                diagnostics.append(
                    ConformanceDiagnostic(
                        code="PROVENANCE_TRUNCATED",
                        message="IAM edge has incomplete callsite provenance",
                        node_id=source.id,
                        file_path=left.file_path,
                    )
                )
        except (ValueError, ValidationError):
            diagnostics.append(
                ConformanceDiagnostic(
                    code="UNPROVEN_DEPENDENCY",
                    message="edge lacks valid explicit internal resolution provenance",
                    node_id=source.id,
                    file_path=left.file_path,
                )
            )
    return tuple(dependencies), tuple(diagnostics)


def location_order(location: SourceLocation) -> tuple[str, int, int, int, int]:
    return (
        location.file_path,
        location.start_line,
        location.start_column,
        location.end_line or location.start_line,
        location.end_column or location.start_column,
    )


def dependency_order(
    dependency: ProvenDependency,
) -> tuple[tuple[str, int, int, int, int], str, str]:
    return (
        location_order(dependency.locations[0]),
        dependency.edge.kind.value,
        str(dependency.edge.id),
    )


def dependency_properties(dependency: ProvenDependency) -> JsonObject:
    provenance: list[JsonValue] = list(dependency.provenance)
    return {
        "edge_id": str(dependency.edge.id),
        "relation": dependency.edge.kind.value,
        "source_node_id": str(dependency.source.id),
        "target_node_id": str(dependency.target.id),
        "source_name": dependency.source.qualified_name,
        "target_name": dependency.target.qualified_name,
        "source_file_id": str(dependency.source_classification.file_id),
        "target_file_id": str(dependency.target_classification.file_id),
        "occurrences": dependency.occurrences,
        "provenance_truncated": dependency.truncated,
        "provenance": provenance,
    }
