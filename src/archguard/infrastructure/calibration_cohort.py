from pathlib import Path

from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.cohort import AIAssessmentManifest, CalibrationCohort, join_label
from archguard.benchmark.materialization import (
    CohortVariant,
    EvaluationAnchor,
    MaterializeEvaluationCase,
)
from archguard.benchmark.models import Split
from archguard.benchmark.mutations import MutationRegistry
from archguard.benchmark.readiness import CalibrationReadinessReport, CalibrationReadinessValidator
from archguard.infrastructure.benchmark import LoadedBenchmark, prepared


def extract_cohort(loaded: LoadedBenchmark) -> tuple[CalibrationCohort, CalibrationReadinessReport]:
    records = []
    diagnostics = []
    for repo in loaded.dataset.repositories:
        pipeline, inputs = prepared(loaded, repo.repository_id)
        if not inputs.iam.metadata.get("is_valid") or not inputs.iam.metadata.get("is_complete"):
            diagnostics.append("INCOMPLETE_IAM:" + repo.repository_id)
        for mutation in loaded.mutations:
            if mutation.derived_repository_id == repo.repository_id and not MutationRegistry().get(
                mutation.operator_id
            ).verify(inputs.iam, mutation.config):
                diagnostics.append("INVALID_MUTATION:" + repo.repository_id)
        pipeline.execute_prepared(inputs)  # Validate the genuine upstream channel results once.
        graph_config = inputs.graph.reproducibility.configuration.model_copy(
            update={"calculate_betweenness": False}
        )
        bounded_graph = GraphAnalyzer().analyze(inputs.iam, graph_config)
        bounded_discovery = ArchitectureDiscoveryAnalyzer().analyze(
            inputs.iam, bounded_graph, ArchitectureDiscoveryConfig(graph=graph_config)
        )
        for variant in CohortVariant:
            static = None if variant == CohortVariant.WITHOUT_STATIC else inputs.static
            graph = (
                None
                if variant == CohortVariant.WITHOUT_GRAPH
                else bounded_graph
                if variant == CohortVariant.BOUNDED_METRICS
                else inputs.graph
            )
            discovery = (
                None
                if graph is None
                else bounded_discovery
                if variant == CohortVariant.BOUNDED_METRICS
                else inputs.discovery
            )
            conformance = inputs.graph_conformance if graph is not None else None
            materializer = MaterializeEvaluationCase(
                inputs.iam, static, graph, discovery, conformance=conformance
            )
            for truth in loaded.truths:
                if truth.repository_id != repo.repository_id:
                    continue
                # Only locators/rule cross the label-free feature-extraction boundary.
                anchor = EvaluationAnchor(
                    repository_id=repo.repository_id, rule_id=truth.rule_id, subjects=truth.subjects
                )
                if materializer.resolver.subjects(anchor.subjects) is None:
                    diagnostics.append("UNRESOLVED_ANCHOR:" + str(truth.case_id))
                    continue
                materialized = materializer.execute(anchor, variant)
                records.append(
                    join_label(
                        materialized,
                        truth,
                        repo,
                        loaded.dataset.dataset_id,
                        loaded.dataset.dataset_version,
                        loaded.fingerprint,
                    )
                )
    cohort = CalibrationCohort(
        dataset_id=loaded.dataset.dataset_id,
        dataset_version=loaded.dataset.dataset_version,
        dataset_fingerprint=loaded.fingerprint,
        records=tuple(
            sorted(records, key=lambda r: (r.repository_id, str(r.case_id), r.variant.value))
        ),
        ai_assessments=tuple(
            AIAssessmentManifest(case_id=t.case_id)
            for t in sorted(loaded.truths, key=lambda t: str(t.case_id))
            if t.rule_id.startswith("ARCH20")
        ),
        diagnostics=tuple(sorted(set(diagnostics))),
    )
    report = CalibrationReadinessValidator().validate(
        loaded.dataset, loaded.truths, cohort, dataset_valid=not diagnostics
    )
    return cohort, report


def export_cohort(
    cohort: CalibrationCohort, report: CalibrationReadinessReport, output: Path
) -> None:
    if output.exists():
        raise ValueError("cohort output must be a new directory")
    output.mkdir(parents=True)
    for split in Split:
        (output / (split.value.lower() + ".jsonl")).write_text(
            "".join(canonical(r) + "\n" for r in cohort.records if r.split == split),
            encoding="utf-8",
        )
    (output / "ai-assessments.json").write_text(
        canonical([m.model_dump(mode="json") for m in cohort.ai_assessments]) + "\n",
        encoding="utf-8",
    )
    (output / "readiness.json").write_text(canonical(report) + "\n", encoding="utf-8")
