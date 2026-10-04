import json
from uuid import uuid5

from pydantic import JsonValue

from archguard.architecture.conformance.dependencies import (
    ProvenDependency,
    dependency_order,
    dependency_properties,
    location_order,
)
from archguard.architecture.specification.models import RuleSpecification
from archguard.core.evidence import Evidence, EvidenceType
from archguard.core.findings.detector import Detector
from archguard.core.findings.enums import DetectorSource, FindingNamespace
from archguard.core.findings.model import Finding
from archguard.core.identifiers import EvidenceId, FindingId, ProjectId, TraceId
from archguard.core.traces import Trace, TraceStep

TITLES = {
    "ARCH001": "Forbidden Dependency",
    "ARCH002": "Layer Violation",
    "ARCH004": "Reverse Dependency",
    "ARCH005": "Module Boundary Violation",
}


def build_finding(
    project_id: ProjectId,
    rule: RuleSpecification,
    dependencies: tuple[ProvenDependency, ...],
    spec_fingerprint: str,
) -> Finding:
    ordered = sorted(dependencies, key=dependency_order)
    primary = ordered[0]
    source, target = primary.source_classification, primary.target_classification
    scope = rule.model_dump(
        mode="json", by_alias=True, exclude={"severity", "description", "enabled", "relations"}
    )
    identity = json.dumps(
        ["static-finding-v1", rule.id, str(source.file_id), str(target.file_id), scope],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    finding_id = FindingId(uuid5(project_id, identity))
    description = (
        f"Dependency from '{source.file_path}' (layer={source.layer or 'unclassified'}, "
        f"module={source.module or 'unclassified'}) to '{target.file_path}' "
        f"(layer={target.layer or 'unclassified'}, module={target.module or 'unclassified'}) "
        f"violates {rule.id} ({rule.type.value})."
    )
    evidence = [
        Evidence(
            id=EvidenceId(uuid5(finding_id, "architecture-rule-v1")),
            namespace=FindingNamespace.ARCH,
            type=EvidenceType.ARCHITECTURE_RULE,
            message="The explicit target architecture constraint forbids this dependency.",
            properties={
                "rule_id": rule.id,
                "rule_type": rule.type.value,
                "expected": rule.model_dump(mode="json", by_alias=True),
                "spec_fingerprint": spec_fingerprint,
                "source_layer": source.layer,
                "source_module": source.module,
                "target_layer": target.layer,
                "target_module": target.module,
            },
        )
    ]
    for dependency in ordered:
        evidence.append(
            Evidence(
                id=EvidenceId(uuid5(finding_id, "dependency:" + str(dependency.edge.id))),
                namespace=FindingNamespace.ARCH,
                type=EvidenceType.STATIC_RULE,
                message=f"Actual resolved internal {dependency.edge.kind.value} dependency.",
                location=dependency.locations[0],
                properties=dependency_properties(dependency),
            )
        )
    locations = sorted(
        set(location for dependency in ordered for location in dependency.locations),
        key=location_order,
    )
    edges: list[JsonValue] = [str(dependency.edge.id) for dependency in ordered]
    relations: list[JsonValue] = [
        value for value in sorted({dependency.edge.kind.value for dependency in ordered})
    ]
    trace = Trace(
        id=TraceId(uuid5(finding_id, "direct-trace-v1")),
        steps=(
            TraceStep(
                sequence=1,
                node_id=primary.source.id,
                location=primary.locations[0],
                label=primary.source.qualified_name,
            ),
            TraceStep(
                sequence=2,
                node_id=primary.target.id,
                edge_id=primary.edge.id,
                relation=primary.edge.kind,
                location=primary.locations[0],
                label=primary.target.qualified_name,
            ),
        ),
        metadata={
            "source_component_file_id": str(source.file_id),
            "target_component_file_id": str(target.file_id),
            "edge_ids": edges,
        },
    )
    return Finding(
        id=finding_id,
        namespace=FindingNamespace.ARCH,
        rule_id=rule.id,
        category=rule.type.value,
        title=TITLES[rule.id],
        description=description,
        severity=rule.severity,
        confidence=None,
        primary_location=locations[0],
        related_locations=tuple(locations[1:]),
        evidence=tuple(evidence),
        trace=trace,
        detector=Detector(
            source=DetectorSource.STATIC, name="static-architecture-rule-engine", version="1.0.0"
        ),
        recommendation=(
            "Route the dependency through an allowed architecture boundary, or update "
            "the target specification if the dependency is intentional."
        ),
        metadata={
            "source_component_file_id": str(source.file_id),
            "target_component_file_id": str(target.file_id),
            "source_component": source.file_path,
            "target_component": target.file_path,
            "relation_kinds": relations,
            "edge_ids": edges,
            "deterministic": True,
            "occurrences": sum(dependency.occurrences for dependency in ordered),
            "provenance_truncated": sum(dependency.truncated for dependency in ordered),
        },
    )
