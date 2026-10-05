from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from archguard.application.analyze_architecture_hybrid import AnalyzeArchitectureHybrid
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig, HybridAnalyzer
from archguard.architecture.hybrid.assembler import HybridInputError
from archguard.architecture.hybrid.models import (
    CalibrationStatus,
    HybridCaseType,
    HybridDecisionState,
)
from archguard.architecture.hybrid.policies import DeterministicPrecedencePolicy, HybridPolicyError
from archguard.architecture.hybrid.serialization import serialize_hybrid
from archguard.architecture.intelligence.models import ContextSelectionConfig
from archguard.core.findings.enums import Severity
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel
from tests.hybrid.conftest import building, semantic


def analyze(inputs, ai=None, config=None):
    return AnalyzeArchitectureHybrid(building()).execute_prepared(inputs, ai, config)


def target(inputs, name):
    return next(n.id for n in inputs.iam.nodes if n.name == name and n.kind == NodeKind.CLASS)


def test_static_only_confirms_original_arch002(violating):
    inputs, _ = violating
    result = HybridAnalyzer().analyze(inputs.iam, static=inputs.static, spec=inputs.spec)
    assert result.confirmed_finding_ids == (inputs.static.findings[0].id,)
    decision = result.decisions[0]
    assert decision.state == HybridDecisionState.CONFIRMED_DETERMINISTIC
    assert decision.severity == Severity.HIGH and decision.confidence is None
    assert decision.calibration_status == CalibrationStatus.DETERMINISTIC
    assert result.evidence_bundles[0].completeness.graph_complete is None
    assert result.evidence_bundles[0].completeness.ai_requested is None


@pytest.mark.parametrize("decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT"])
def test_ai_never_suppresses_static(violating, decision):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202", decision)
    result = analyze(inputs, ai)
    confirmed = [d for d in result.decisions if d.confirmed_finding_ids]
    assert len(confirmed) == 1 and confirmed[0].confirmed_finding_ids == (
        inputs.static.findings[0].id,
    )
    assert confirmed[0].state == HybridDecisionState.CONFIRMED_DETERMINISTIC
    assert confirmed[0].severity == inputs.static.findings[0].severity
    assert all(d.confidence is None for d in result.decisions)


@pytest.mark.parametrize("with_ai", [False, True])
def test_explicit_arch003_survives_negative_ai(cyclic, with_ai):
    inputs, workspace = cyclic
    ai = (
        semantic(inputs, workspace, target(inputs, "A"), "ARCH205", "NOT_SUPPORTED")
        if with_ai
        else None
    )
    result = analyze(inputs, ai)
    proof = inputs.graph_conformance.findings[0]
    assert result.confirmed_finding_ids == (proof.id,)
    decision = next(d for d in result.decisions if d.confirmed_finding_ids)
    assert decision.state == HybridDecisionState.CONFIRMED_DETERMINISTIC
    assert decision.reason_codes[0] == "DET_GRAPH_CYCLE_RULE_PROOF"
    assert decision.severity == proof.severity and decision.confidence is None


def test_actual_cycles_without_target_rule_are_not_findings(cyclic):
    inputs, _ = cyclic
    result = analyze(replace(inputs, static=None, spec=None, graph_conformance=None))
    assert not result.confirmed_finding_ids and inputs.graph.cycles


def test_metrics_are_graph_evidence_without_candidate(violating):
    inputs, _ = violating
    result = analyze(inputs)
    assert result.evidence_bundles[0].graph_measurements
    assert result.statistics.channel_cases["graph"] == 1
    assert any(
        a.reason_code == "MISSING_GRAPH_CANDIDATE_EVIDENCE"
        for a in result.evidence_bundles[0].alignments
    )
    assert any(
        a.reason_code == "GRAPH_MEASUREMENT_CONTEXT" and a.agreement.value == "NEUTRAL"
        for a in result.evidence_bundles[0].alignments
    )


def test_graph_candidates_only_review(hub):
    inputs, _ = hub
    result = analyze(inputs)
    assert {c.rule_id for c in result.cases} == {"ARCH101", "ARCH102"}
    assert all(d.state == HybridDecisionState.REVIEW_REQUIRED for d in result.decisions)
    assert all(d.confidence is None and d.severity is None for d in result.decisions)
    assert all("MISSING_AI_EVIDENCE" in d.reason_codes for d in result.decisions)


@pytest.mark.parametrize(
    "decision,expected",
    [
        ("SUPPORTED", "REVIEW_REQUIRED"),
        ("NOT_SUPPORTED", "REVIEW_REQUIRED"),
        ("INSUFFICIENT_CONTEXT", "INSUFFICIENT_EVIDENCE"),
    ],
)
def test_semantic_only_states(violating, decision, expected):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202", decision)
    result = HybridAnalyzer().analyze(inputs.iam, ai=ai)
    assert len(result.decisions) == 1 and result.decisions[0].state.value == expected
    assert not result.confirmed_finding_ids and result.decisions[0].confidence is None
    assert result.evidence_bundles[0].completeness.graph_complete is None


@pytest.mark.parametrize(
    "decision,agreement",
    [
        ("SUPPORTED", "SUPPORTING"),
        ("NOT_SUPPORTED", "CONTRADICTING"),
        ("INSUFFICIENT_CONTEXT", "MISSING"),
    ],
)
def test_exact_arch102_and_arch205_agreement(hub, decision, agreement):
    inputs, workspace = hub
    candidate = next(c for c in inputs.graph.candidates if c.rule_id == "ARCH102")
    node = next(
        c.iam_node_id
        for c in inputs.discovery.discovered.components
        if c.id == candidate.subject_node_id
    )
    result = analyze(inputs, semantic(inputs, workspace, node, decision=decision))
    index = next(i for i, c in enumerate(result.cases) if candidate.candidate_id in c.anchor_ids)
    bundle, output = result.evidence_bundles[index], result.decisions[index]
    assert bundle.graph and bundle.ai
    assert any(
        a.agreement.value == agreement and a.reason_code == "MAPPED_GRAPH_SEMANTIC_CONCERN"
        for a in bundle.alignments
    )
    assert output.state == HybridDecisionState.REVIEW_REQUIRED and output.confidence is None
    assert not result.confirmed_finding_ids


def test_high_pagerank_does_not_support_controller_logic(hub):
    inputs, workspace = hub
    node = inputs.discovery.discovered.components[0].iam_node_id
    result = analyze(inputs, semantic(inputs, workspace, node, "ARCH202"))
    for case, bundle in zip(result.cases, result.evidence_bundles, strict=True):
        if case.case_type == HybridCaseType.GRAPH_STRUCTURAL:
            assert not any(
                a.agreement.value in {"SUPPORTING", "CONTRADICTING"} for a in bundle.alignments
            )


def test_truncated_supported_context_is_still_review(hub):
    inputs, workspace = hub
    candidate = next(c for c in inputs.graph.candidates if c.rule_id == "ARCH102")
    ai = semantic(
        inputs,
        workspace,
        candidate.subject_node_id,
        "ARCH205",
        context=ContextSelectionConfig(max_nodes=1),
    )
    assert ai.candidates and ai.manifests[0].truncated
    result = analyze(inputs, ai)
    index = next(i for i, c in enumerate(result.cases) if c.origin == "AI")
    assert result.decisions[index].state == HybridDecisionState.REVIEW_REQUIRED
    assert result.evidence_bundles[index].completeness.context_truncated is True


def test_skipped_metric_stays_missing(hub):
    inputs, _ = hub
    config = GraphAnalysisConfig(
        calculate_betweenness=False,
        calculate_pagerank=False,
        candidates=inputs.graph.reproducibility.configuration.candidates,
    )
    graph = GraphAnalyzer().analyze(inputs.iam, config)
    result = analyze(replace(inputs, graph=graph, discovery=None))
    assert result.cases
    for vector in result.features:
        selected = {f.name: f for f in vector.values}
        assert selected["graph.betweenness"].value is None
        assert selected["graph.betweenness"].availability.value == "MISSING"
        assert selected["graph.pagerank"].value is None
        assert selected["quality.metrics_skipped"].value == ("betweenness", "pagerank")


def test_partial_source_quality_is_explicit(violating):
    inputs, _ = violating
    metadata = inputs.iam.metadata | {
        "is_complete": False,
        "statistics": dict(inputs.iam.metadata["statistics"])
        | {"files_with_parse_errors": 1, "references_unresolved": 3, "references_ambiguous": 2},
    }
    iam = ArchitectureModel.model_validate(inputs.iam.model_dump() | {"metadata": metadata})
    static = StaticConformanceAnalyzer().analyze(iam, inputs.spec)
    result = HybridAnalyzer().analyze(iam, static=static, spec=inputs.spec)
    quality = result.evidence_bundles[0].completeness
    assert quality.iam_complete is False and quality.parse_errors_present is True
    assert quality.unresolved_references == 3 and quality.ambiguous_references == 2
    assert result.decisions[0].state == HybridDecisionState.CONFIRMED_DETERMINISTIC


def test_stale_upstream_is_rejected(violating):
    inputs, _ = violating
    iam = ArchitectureModel.model_validate(
        inputs.iam.model_dump() | {"metadata": inputs.iam.metadata | {"is_complete": False}}
    )
    with pytest.raises(HybridInputError, match="same IAM"):
        HybridAnalyzer().analyze(iam, graph=inputs.graph)
    with pytest.raises(HybridInputError, match="specification"):
        HybridAnalyzer().analyze(inputs.iam, static=inputs.static)


def test_unresolved_ai_subject_and_reference_are_rejected(violating):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    candidate = ai.candidates[0]
    for update in ({"subject_node_ids": (uuid4(),)}, {"evidence_refs": ("SRC999",)}):
        changed = candidate.model_copy(
            update={"assessment": candidate.assessment.model_copy(update=update)}
        )
        with pytest.raises(HybridInputError, match="subjects and references"):
            analyze(inputs, ai.model_copy(update={"candidates": (changed,)}))


def test_candidate_budget_retains_deterministic_refs(violating):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    result = analyze(inputs, ai, HybridAnalysisConfig(max_candidate_cases=1))
    assert result.confirmed_finding_ids == (inputs.static.findings[0].id,)
    assert len(result.cases) == 2


def test_policy_cannot_suppress_deterministic_finding(violating):
    class BadPolicy(DeterministicPrecedencePolicy):
        def decide(self, case, evidence, features):
            return (
                super()
                .decide(case, evidence, features)
                .model_copy(update={"state": HybridDecisionState.REVIEW_REQUIRED})
            )

    inputs, _ = violating
    with pytest.raises(HybridPolicyError, match="suppress"):
        HybridAnalyzer(BadPolicy()).analyze(inputs.iam, inputs.static, spec=inputs.spec)


def test_canonical_result_is_deterministic_and_source_free(violating):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    a = serialize_hybrid(analyze(inputs, ai))
    b = serialize_hybrid(analyze(inputs, ai))
    assert a == b
    for forbidden in (
        "invocation_id",
        "latency_seconds",
        "provider_request_id",
        "system_instructions",
        "short_reason",
        "source_fragments",
        "code_snippet",
        "/Users/",
        "total_score",
        '"label"',
    ):
        assert forbidden not in a
    assert all(d.confidence is None for d in analyze(inputs, ai).decisions)


def test_policy_schema_mismatch(hub):
    class NewSchemaPolicy(DeterministicPrecedencePolicy):
        @property
        def metadata(self):
            return super().metadata.model_copy(
                update={"feature_schema_version": "hybrid-evidence-v2"}
            )

    inputs, _ = hub
    with pytest.raises(HybridPolicyError, match="schema"):
        HybridAnalyzer(NewSchemaPolicy()).analyze(inputs.iam, graph=inputs.graph)


def test_numeric_confidence_is_forbidden(hub):
    inputs, _ = hub
    decision = analyze(inputs).decisions[0]
    with pytest.raises(ValidationError, match="numeric confidence"):
        type(decision).model_validate(decision.model_dump() | {"confidence": {"score": 0.9}})
