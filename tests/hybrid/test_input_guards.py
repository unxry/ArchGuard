from dataclasses import replace

import pytest
from pydantic import ValidationError

from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig, GraphProjectionSpec
from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.hybrid.analyzer import HybridAnalyzer
from archguard.architecture.hybrid.assembler import HybridInputError
from archguard.architecture.hybrid.models import HybridCase
from archguard.iam.model import ArchitectureModel
from tests.hybrid.test_decisions import analyze


def test_stale_graph_conformance_is_rejected(cyclic):
    inputs, _ = cyclic
    changed = inputs.graph_conformance.model_copy(
        update={
            "reproducibility": inputs.graph_conformance.reproducibility
            | {"iam_fingerprint": "a" * 64}
        }
    )
    with pytest.raises(HybridInputError, match="explicit target"):
        analyze(replace(inputs, graph_conformance=changed))


def test_arch003_requires_closed_proof(cyclic):
    inputs, _ = cyclic
    finding = inputs.graph_conformance.findings[0].model_copy(update={"trace": None})
    changed = inputs.graph_conformance.model_copy(update={"findings": (finding,)})
    with pytest.raises(HybridInputError, match="closed directed trace"):
        analyze(replace(inputs, graph_conformance=changed))


def test_finding_spec_fingerprint_must_match(violating):
    inputs, _ = violating
    finding = inputs.static.findings[0]
    changed = finding.model_copy(
        update={
            "evidence": tuple(
                e.model_copy(update={"properties": e.properties | {"spec_fingerprint": "a" * 64}})
                if e.type.value == "ARCHITECTURE_RULE"
                else e
                for e in finding.evidence
            )
        }
    )
    with pytest.raises(HybridInputError, match="specification fingerprint"):
        analyze(replace(inputs, static=inputs.static.model_copy(update={"findings": (changed,)})))


def test_disabled_arch003_cannot_confirm_old_proof(cyclic):
    inputs, _ = cyclic
    spec = inputs.spec.model_copy(
        update={"rules": tuple(r.model_copy(update={"enabled": False}) for r in inputs.spec.rules)}
    )
    with pytest.raises(HybridInputError):
        HybridAnalyzer().analyze(inputs.iam, spec=spec, graph_conformance=inputs.graph_conformance)


def test_group_projection_cannot_masquerade_as_component_metrics(violating):
    inputs, _ = violating
    graph = GraphAnalyzer().analyze(
        inputs.iam,
        GraphAnalysisConfig(projection=GraphProjectionSpec(projection=GraphProjection.FILE)),
    )
    with pytest.raises(HybridInputError, match="component graph"):
        HybridAnalyzer().analyze(inputs.iam, graph=graph)


def test_sec_case_is_rejected(hub):
    inputs, _ = hub
    data = analyze(inputs).cases[0].model_dump() | {"rule_id": "SEC001"}
    with pytest.raises(ValidationError):
        HybridCase.model_validate(data)


def test_missing_iam_quality_is_not_invented(violating):
    inputs, _ = violating
    iam = ArchitectureModel.model_validate(inputs.iam.model_dump() | {"metadata": {}})
    static = StaticConformanceAnalyzer().analyze(iam, inputs.spec)
    result = HybridAnalyzer().analyze(iam, static=static, spec=inputs.spec)
    assert result.reproducibility.snapshot_fingerprint is None
    quality = result.evidence_bundles[0].completeness
    assert quality.iam_complete is None and quality.parse_errors_present is None
    assert quality.unresolved_references is None and quality.ambiguous_references is None
