from pydantic import ValidationError

from archguard.architecture.conformance.dependencies import (
    _INTERNAL_METHODS,
    _REFERENCE_KINDS,
    location_order,
)
from archguard.architecture.graph.models import DependencyProof
from archguard.core.locations import SourceLocation
from archguard.core.model.types import JsonObject
from archguard.iam.edges import ArchitectureEdge


def dependency_proof(edge: ArchitectureEdge, file_path: str, external: bool) -> DependencyProof:
    raw = edge.attributes.get("provenance")
    if not isinstance(raw, list) or not raw:
        raise ValueError("missing provenance")
    records: list[tuple[SourceLocation, JsonObject]] = []
    status = "EXTERNAL" if external else "RESOLVED"
    methods = {"EXTERNAL_PACKAGE"} if external else _INTERNAL_METHODS
    for item in raw:
        if not isinstance(item, dict) or item.get("resolution_status") != status:
            raise ValueError("uncertain dependency")
        method = item.get("resolution_method")
        if not isinstance(method, str) or method not in methods:
            raise ValueError("invalid resolution method")
        reference = _REFERENCE_KINDS[edge.kind]
        if item.get("reference_kind") != reference:
            raise ValueError("mismatched reference")
        try:
            location = SourceLocation.model_validate(item.get("source_location"))
        except ValidationError:
            raise ValueError("invalid location") from None
        if location.file_path != file_path:
            raise ValueError("mismatched source file")
        records.append(
            (
                location,
                {
                    "source_location": location.model_dump(mode="json"),
                    "resolution_status": status,
                    "resolution_method": method,
                    "reference_kind": reference,
                },
            )
        )
    count = edge.attributes.get("occurrences", len(records))
    truncated = edge.attributes.get("provenance_truncated", 0)
    if type(count) is not int or type(truncated) is not int or truncated < 0:
        raise ValueError("invalid provenance counts")
    records.sort(key=lambda item: (location_order(item[0]), str(item[1]["resolution_method"])))
    return DependencyProof(
        iam_edge_id=edge.id,
        source_node_id=edge.source_id,
        target_node_id=edge.target_id,
        relation=edge.kind,
        locations=tuple(item[0] for item in records),
        provenance=tuple(item[1] for item in records),
        occurrences=count,
        provenance_truncated=truncated,
    )
