from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from archguard.architecture.hybrid.alignment import HybridEvidenceAligner
from archguard.architecture.hybrid.artifacts import CalibratedPolicyArtifact
from archguard.architecture.hybrid.features import extract_features, feature_schema
from archguard.architecture.hybrid.models import (
    AlignmentMethod,
    HybridCase,
    HybridCaseType,
    HybridFeature,
    SubjectPair,
)
from archguard.architecture.hybrid.policies import DeterministicPrecedencePolicy, HybridPolicyError
from archguard.architecture.hybrid.serialization import fingerprint, serialize_hybrid
from archguard.core.model.enums import NodeKind
from tests.hybrid.conftest import semantic
from tests.hybrid.test_decisions import analyze, target


def case(subjects, pairs=()):
    return HybridCase(
        case_id=uuid4(),
        case_type=HybridCaseType.SEMANTIC,
        primary_subject_ids=subjects,
        subject_pairs=pairs,
        origin="CALLER",
        rule_id="ARCH205",
        anchor_ids=(uuid4(),),
        scope="test",
        bundle_id=uuid4(),
    )


def test_exact_subject_never_matches_same_simple_name(violating):
    inputs, _ = violating
    classes = [n for n in inputs.iam.nodes if n.kind == NodeKind.CLASS]
    first, second = classes[:2]
    # Rename only a different node's display name: identity remains its original ID.
    changed = inputs.iam.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"name": first.name}) if n.id == second.id else n
                for n in inputs.iam.nodes
            )
        }
    )
    aligner = HybridEvidenceAligner(changed)
    aligner.dependencies.clear()
    assert aligner.match(case((first.id,)), (second.id,)) is None
    assert aligner.match(case((first.id,)), (first.id,)) == AlignmentMethod.EXACT_SUBJECT


def test_directed_pair_never_matches_other_target(violating):
    inputs, _ = violating
    nodes = [n.id for n in inputs.iam.nodes if n.kind == NodeKind.CLASS]
    a, b, c = nodes[:3]
    aligner = HybridEvidenceAligner(inputs.iam)
    ab, ac, ba = (
        SubjectPair(source_id=a, target_id=b),
        SubjectPair(source_id=a, target_id=c),
        SubjectPair(source_id=b, target_id=a),
    )
    pair_case = case((a, b), (ab,))
    assert aligner.match(pair_case, (a, b), (ab,)) == AlignmentMethod.EXACT_SUBJECT_PAIR
    assert aligner.match(pair_case, (a, c), (ac,)) is None
    assert aligner.match(pair_case, (b, a), (ba,)) is None


def test_method_owner_uses_actual_containment(violating):
    inputs, _ = violating
    method = next(n for n in inputs.iam.nodes if n.kind == NodeKind.METHOD)
    aligner = HybridEvidenceAligner(inputs.iam)
    owner = aligner.parents[method.id]
    assert aligner.match(case((method.id,)), (owner,)) == AlignmentMethod.CONTAINMENT_OWNER
    altered = inputs.iam.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"attributes": {}}) if n.id == method.id else n
                for n in inputs.iam.nodes
            )
        }
    )
    assert HybridEvidenceAligner(altered).match(case((method.id,)), (owner,)) is None


def test_direct_relation_requires_real_edge(violating):
    inputs, _ = violating
    edge = inputs.iam.edges[0]
    aligner = HybridEvidenceAligner(inputs.iam)
    assert (
        aligner.match(case((edge.source_id,)), (edge.target_id,))
        == AlignmentMethod.DIRECT_GRAPH_RELATION
    )


def test_feature_schema_values_provenance_and_fingerprints(hub):
    inputs, _ = hub
    result = analyze(inputs)
    assert result.feature_schema.version == "hybrid-evidence-v1"
    for hybrid_case, bundle, vector, decision in zip(
        result.cases, result.evidence_bundles, result.features, result.decisions, strict=True
    ):
        assert vector == extract_features(hybrid_case, bundle)
        assert tuple(f.name for f in vector.values) == tuple(
            f.name for f in feature_schema().definitions
        )
        assert decision.evidence_fingerprint == fingerprint(bundle)
        assert decision.feature_fingerprint == vector.fingerprint
        assert all(f.provenance_refs for f in vector.values if f.availability.value == "AVAILABLE")
    encoded = serialize_hybrid(result)
    assert serialize_hybrid(type(result).model_validate_json(encoded)) == encoded


@pytest.mark.parametrize(
    "update",
    [
        {"value_type": "INTEGER", "value": True},
        {"value_type": "BOOLEAN", "value": 1},
        {"value_type": "FLOAT", "value": None},
        {"value_type": "MISSING", "value": 0},
        {"availability": "MISSING", "value": 1},
        {"provenance_refs": ()},
    ],
)
def test_feature_type_and_availability_invariants(update):
    with pytest.raises(ValidationError):
        HybridFeature.model_validate(
            {
                "name": "test",
                "value_type": "INTEGER",
                "value": 1,
                "availability": "AVAILABLE",
                "provenance_refs": ("graph:proof",),
            }
            | update
        )


def test_irrelevant_unselected_evidence_does_not_change_bundle(isolated):
    inputs, workspace = isolated
    first = semantic(inputs, workspace, target(inputs, "A"), "ARCH202")
    second = semantic(inputs, workspace, target(inputs, "B"), "ARCH201")
    combined = first.model_copy(
        update={
            "candidates": (*first.candidates, *second.candidates),
            "targets": (*first.targets, *second.targets),
            "manifests": (*first.manifests, *second.manifests),
            "invocations": (*first.invocations, *second.invocations),
        }
    )
    a = analyze(replace(inputs, graph=inputs.graph, discovery=None), first)
    b = analyze(replace(inputs, graph=inputs.graph, discovery=None), combined)
    index_a = next(
        i for i, c in enumerate(a.cases) if first.candidates[0].candidate_id in c.anchor_ids
    )
    index_b = next(
        i for i, c in enumerate(b.cases) if first.candidates[0].candidate_id in c.anchor_ids
    )
    assert not any(
        s.candidate_id == second.candidates[0].candidate_id for s in b.evidence_bundles[index_b].ai
    )
    assert a.decisions[index_a].evidence_fingerprint == b.decisions[index_b].evidence_fingerprint
    assert a.features[index_a].fingerprint == b.features[index_b].fingerprint


def test_schema_mismatch_at_policy_call(hub):
    inputs, _ = hub
    result = analyze(inputs)
    vector = result.features[0].model_copy(update={"schema_version": "hybrid-evidence-v2"})
    with pytest.raises(HybridPolicyError, match="schema"):
        DeterministicPrecedencePolicy().decide(result.cases[0], result.evidence_bundles[0], vector)


def artifact():
    return {
        "method": "LOGISTIC_REGRESSION",
        "metadata": {
            "policy_id": "fixture-future-contract",
            "policy_version": "1",
            "feature_schema_version": "hybrid-evidence-v1",
            "calibration_status": "CALIBRATED",
        },
        "dataset_reference": "test-dataset-schema-only",
        "calibration_run_reference": "test-run-schema-only",
        "repository_split_fingerprint": "a" * 64,
        "training_feature_schema_fingerprint": fingerprint(feature_schema()),
        "intercept": 0.0,
        "coefficients": ({"feature_name": "graph.Ca", "coefficient": 1.0},),
        "decision_threshold": 0.5,
    }


def test_future_artifact_is_metadata_only_and_schema_guarded():
    model = CalibratedPolicyArtifact.model_validate(artifact())
    model.require_compatible_schema()
    with pytest.raises(HybridPolicyError, match="schema"):
        model.model_copy(
            update={"metadata": model.metadata.model_copy(update={"feature_schema_version": "v2"})}
        ).require_compatible_schema()


@pytest.mark.parametrize(
    "field",
    [
        "dataset_reference",
        "calibration_run_reference",
        "repository_split_fingerprint",
        "training_feature_schema_fingerprint",
        "intercept",
        "coefficients",
        "decision_threshold",
    ],
)
def test_future_artifact_requires_calibration_metadata(field):
    data = artifact()
    del data[field]
    with pytest.raises(ValidationError):
        CalibratedPolicyArtifact.model_validate(data)


def test_tampered_result_fingerprint_is_rejected(hub):
    inputs, _ = hub
    result = analyze(inputs)
    data = result.model_dump()
    data["decisions"][0]["evidence_fingerprint"] = "a" * 64
    with pytest.raises(ValidationError, match="fingerprints"):
        type(result).model_validate(data)
