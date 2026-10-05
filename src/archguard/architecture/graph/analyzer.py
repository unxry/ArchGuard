import json
from collections import Counter

import networkx as nx
from pydantic import JsonValue

from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.graph.algorithms import (
    cycle_observations,
    strongly_connected_components,
)
from archguard.architecture.graph.builder import GraphBuilder
from archguard.architecture.graph.candidates import generate_candidates
from archguard.architecture.graph.config import GraphAnalysisConfig, fingerprint
from archguard.architecture.graph.conformance import GraphConformanceAnalyzer
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.graph.metrics import calculate_metrics
from archguard.architecture.graph.models import GraphDiagnostic
from archguard.architecture.graph.result import (
    GraphAnalysisResult,
    GraphReproducibility,
    GraphStatistics,
)
from archguard.architecture.specification.models import ArchitectureSpecification, RuleType
from archguard.iam.model import ArchitectureModel


class GraphAnalyzer:
    version = "1.0.0"

    def analyze(
        self,
        model: ArchitectureModel,
        config: GraphAnalysisConfig | None = None,
        spec: ArchitectureSpecification | None = None,
    ) -> GraphAnalysisResult:
        model = ArchitectureModel.model_validate(model)
        config = GraphAnalysisConfig.model_validate(
            config if config is not None else GraphAnalysisConfig()
        )
        spec = ArchitectureSpecification.model_validate(spec) if spec is not None else None
        classification = ArchitectureClassifier().classify(model, spec) if spec else None
        built = GraphBuilder().build(
            model, config, classification, spec.fingerprint if spec else None
        )
        valid = built.is_valid and model.metadata.get("is_valid") is not False
        diagnostics = list(built.diagnostics)
        if model.metadata.get("is_valid") is False:
            diagnostics.append(
                GraphDiagnostic(
                    code="INVALID_IAM", message="invalid IAM cannot support structural analysis"
                )
            )
        if model.metadata.get("is_complete") is False:
            diagnostics.append(
                GraphDiagnostic(
                    code="INCOMPLETE_IAM", message="IAM processing coverage was incomplete"
                )
            )
        sccs = strongly_connected_components(built.graph) if valid else ()
        cycles = cycle_observations(built.graph, sccs, config.max_cycle_trace_length)
        if any(item.truncated for item in cycles):
            diagnostics.append(
                GraphDiagnostic(
                    code="CYCLE_TRACE_LIMIT",
                    message="representative cycle exceeds the configured proof budget",
                )
            )
        metrics, metric_diagnostics, computed, skipped = (
            calculate_metrics(built.graph, sccs, config) if valid else ((), (), (), ("all",))
        )
        diagnostics.extend(metric_diagnostics)
        candidates = generate_candidates(built.graph, metrics, config) if valid else ()
        if (
            config.candidates.god_min_members is not None
            and config.projection.projection != GraphProjection.COMPONENT
        ):
            diagnostics.append(
                GraphDiagnostic(
                    code="CANDIDATE_PROJECTION_UNSUPPORTED",
                    message="ARCH103 structural size requires COMPONENT projection",
                )
            )
        conformance = (
            GraphConformanceAnalyzer().analyze(model, spec, config)
            if spec is not None
            and any(rule.type == RuleType.CIRCULAR and rule.enabled for rule in spec.rules)
            else None
        )
        if conformance is not None:
            diagnostics.extend(conformance.diagnostics)
            valid = valid and conformance.is_valid
        complete = (
            valid
            and built.is_complete
            and not diagnostics
            and model.metadata.get("is_complete") is not False
            and (conformance is None or conformance.is_complete)
        )
        findings = conformance.findings if conformance is not None and valid else ()
        raw_fingerprint = model.metadata.get("snapshot_fingerprint")
        return GraphAnalysisResult(
            status="INVALID" if not valid else "COMPLETE" if complete else "INCOMPLETE",
            is_valid=valid,
            is_complete=complete,
            graph=built.graph,
            projection_statistics=built.statistics,
            statistics=GraphStatistics(
                scc_count=len(sccs),
                cyclic_scc_count=len(cycles),
                cycle_observation_count=len(cycles),
                cycle_findings=len(findings),
                candidate_count_by_rule=dict(
                    sorted(Counter(item.rule_id for item in candidates).items())
                ),
                metric_node_count=len(metrics),
                metrics_computed=computed,
                metrics_skipped=skipped,
            ),
            metrics=metrics,
            sccs=sccs,
            cycles=cycles,
            findings=findings,
            candidates=candidates,
            conformance=conformance,
            diagnostics=tuple(diagnostics),
            reproducibility=GraphReproducibility(
                project_id=model.project.id,
                snapshot_fingerprint=raw_fingerprint if isinstance(raw_fingerprint, str) else None,
                iam_schema_version=model.iam_schema_version,
                iam_fingerprint=iam_fingerprint(model),
                networkx_version=nx.__version__,
                configuration=config,
                configuration_fingerprint=config.fingerprint,
                projection_fingerprint=fingerprint(config.projection),
                architecture_spec_fingerprint=spec.fingerprint if spec else None,
            ),
        )


def _quantize(value: JsonValue) -> JsonValue:
    if isinstance(value, float):
        rounded = round(value, 12)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, list):
        return [_quantize(item) for item in value]
    if isinstance(value, dict):
        return {key: _quantize(item) for key, item in value.items()}
    return value


def serialize_graph_result(result: GraphAnalysisResult) -> str:
    validated = GraphAnalysisResult.model_validate(result)
    data = validated.model_dump(mode="json")
    data["metrics"] = _quantize(data["metrics"])
    for candidate in data["candidates"]:
        candidate["metrics"] = _quantize(candidate["metrics"])
        for evidence in candidate["evidence"]:
            evidence["properties"]["metrics"] = _quantize(evidence["properties"]["metrics"])
    return (
        json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )
