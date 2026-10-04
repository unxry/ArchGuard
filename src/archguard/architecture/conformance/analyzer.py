import hashlib
import json
from collections import Counter, defaultdict
from uuid import UUID

from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.classification.models import ClassificationStatus, ConformanceDiagnostic
from archguard.architecture.conformance.dependencies import ProvenDependency, proven_dependencies
from archguard.architecture.conformance.findings import build_finding
from archguard.architecture.conformance.models import (
    ConformanceReproducibility,
    ConformanceStatus,
    StaticAnalysisConfig,
    StaticConformanceResult,
    StaticConformanceStatistics,
)
from archguard.architecture.rules.registry import StaticRuleRegistry, create_static_rule_registry
from archguard.architecture.specification.errors import StaticRuleRegistrationError
from archguard.architecture.specification.models import ArchitectureSpecification, RuleSpecification
from archguard.core.findings.model import Finding
from archguard.core.identifiers import SnapshotId
from archguard.core.model.types import JsonObject
from archguard.iam.model import ArchitectureModel


def iam_fingerprint(model: ArchitectureModel) -> str:
    data = model.model_dump(mode="json")
    for key in ("modules", "packages", "source_files", "symbols", "nodes", "edges"):
        data[key].sort(key=lambda item: item["id"])
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


class StaticConformanceAnalyzer:
    version = "1.0.0"

    def __init__(
        self,
        registry: StaticRuleRegistry | None = None,
        classifier: ArchitectureClassifier | None = None,
        config: StaticAnalysisConfig | None = None,
    ) -> None:
        self.registry = registry if registry is not None else create_static_rule_registry()
        self.classifier = classifier if classifier is not None else ArchitectureClassifier()
        self.config = config if config is not None else StaticAnalysisConfig()

    def analyze(
        self, model: ArchitectureModel, spec: ArchitectureSpecification
    ) -> StaticConformanceResult:
        model = ArchitectureModel.model_validate(model)
        spec = ArchitectureSpecification.model_validate(spec)
        classification = self.classifier.classify(model, spec)
        records = {str(node.node_id): node for node in classification.nodes}
        diagnostics = list(classification.diagnostics)
        valid = classification.is_valid
        complete = model.metadata.get("is_complete") is not False
        if model.metadata.get("is_valid") is False:
            valid = False
            diagnostics.append(
                ConformanceDiagnostic(
                    code="INVALID_IAM",
                    message="IAM build was invalid; static findings are suppressed",
                )
            )
        if not complete:
            diagnostics.append(
                ConformanceDiagnostic(
                    code="INCOMPLETE_IAM", message="IAM build did not cover all source constructs"
                )
            )
        enabled = tuple(rule for rule in spec.rules if rule.enabled)
        for rule in enabled:
            try:
                self.registry.get(rule.type)
            except StaticRuleRegistrationError:
                valid = False
                diagnostics.append(
                    ConformanceDiagnostic(
                        code="MISSING_RULE_EVALUATOR",
                        message="enabled rule has no registered evaluator",
                    )
                )
        dependencies, proof_diagnostics = proven_dependencies(model, records)
        diagnostics.extend(proof_diagnostics)
        if proof_diagnostics:
            complete = False
        findings: list[Finding] = []
        evaluated = 0
        if valid:
            grouped: dict[tuple[str, str, str], list[ProvenDependency]] = defaultdict(list)
            by_relation = {
                kind: tuple(rule for rule in enabled if kind in rule.relations)
                for kind in {dependency.edge.kind for dependency in dependencies}
            }
            for dependency in dependencies:
                for rule in by_relation[dependency.edge.kind]:
                    if self.registry.get(rule.type).violates(
                        rule, dependency.source_classification, dependency.target_classification
                    ):
                        grouped[
                            rule.id,
                            str(dependency.source_classification.file_id),
                            str(dependency.target_classification.file_id),
                        ].append(dependency)
            rules: dict[str, RuleSpecification] = {rule.id: rule for rule in enabled}
            findings = [
                build_finding(model.project.id, rules[key[0]], tuple(group), spec.fingerprint)
                for key, group in sorted(grouped.items())
            ]
            findings.sort(
                key=lambda item: (
                    item.rule_id,
                    str(item.metadata["source_component"]),
                    str(item.metadata["target_component"]),
                    str(item.id),
                )
            )
            evaluated = len(enabled)
        else:
            complete = False
        states = Counter(node.status for node in classification.nodes)
        layers = Counter(node.layer for node in classification.nodes if node.layer is not None)
        modules = Counter(node.module for node in classification.nodes if node.module is not None)
        stats = StaticConformanceStatistics(
            iam_nodes_total=len(model.nodes),
            iam_edges_total=len(model.edges),
            nodes_considered=len(classification.nodes),
            nodes_classified=states[ClassificationStatus.CLASSIFIED],
            nodes_unclassified=states[ClassificationStatus.UNCLASSIFIED],
            ambiguous_nodes=states[ClassificationStatus.AMBIGUOUS],
            edges_considered=len(dependencies),
            edges_ignored=len(model.edges) - len(dependencies),
            rules_enabled=len(enabled),
            rules_evaluated=evaluated,
            findings_total=len(findings),
            findings_by_rule=dict(sorted(Counter(f.rule_id for f in findings).items())),
            findings_by_severity=dict(sorted(Counter(f.severity.value for f in findings).items())),
            nodes_by_layer=dict(sorted(layers.items())),
            nodes_by_module=dict(sorted(modules.items())),
        )
        status = (
            ConformanceStatus.INVALID
            if not valid
            else ConformanceStatus.NON_CONFORMANT
            if findings
            else ConformanceStatus.CONFORMANT
            if complete
            else ConformanceStatus.INCOMPLETE
        )
        snapshot_raw = model.metadata.get("snapshot_id")
        snapshot = SnapshotId(UUID(snapshot_raw)) if isinstance(snapshot_raw, str) else None
        fingerprint = model.metadata.get("snapshot_fingerprint")
        reproducibility = ConformanceReproducibility(
            project_id=model.project.id,
            snapshot_id=snapshot,
            snapshot_fingerprint=fingerprint if isinstance(fingerprint, str) else None,
            iam_schema_version=model.iam_schema_version,
            iam_fingerprint=iam_fingerprint(model),
            architecture_spec_version=spec.version,
            architecture_spec_fingerprint=spec.fingerprint,
            analyzer_version=self.version,
            rule_engine_version=self.registry.version,
            classifier_version=self.classifier.version,
            configuration=self.config,
        )
        summary: JsonObject = {
            "version": spec.version,
            "fingerprint": spec.fingerprint,
            "layers": [layer.name for layer in spec.architecture.layers],
            "modules": [module.name for module in spec.architecture.modules],
            "rules": [rule.id for rule in spec.rules],
        }
        return StaticConformanceResult(
            status=status,
            is_valid=valid,
            is_complete=complete,
            classification=classification,
            statistics=stats,
            findings=tuple(findings),
            diagnostics=tuple(diagnostics),
            reproducibility=reproducibility,
            specification_summary=summary,
        )


def serialize_conformance(result: StaticConformanceResult) -> str:
    validated = StaticConformanceResult.model_validate(result)
    return (
        json.dumps(validated.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, indent=2)
        + "\n"
    )
