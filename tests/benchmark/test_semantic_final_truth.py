"""Synthetic category-only final merge examples; no real human/source/AI payloads."""

import ast
import hashlib
import json
import socket
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_agreement import CaseAlignment
from archguard.infrastructure.semantic_final_truth import (
    LINEAGE_KEYS,
    METHODOLOGY,
    FinalHumanTruth,
    TruthCase,
    freeze_final_truth,
    merge_final_truth,
    truth_receipt,
    verify_final_truth,
)


@pytest.fixture
def inputs():
    cases = tuple(
        CaseAlignment(
            case_id=f"synthetic-scientific-{i:03}",
            a_blinded_id=f"synthetic-a-{i}",
            b_blinded_id=f"synthetic-b-{i}",
            rule_id=f"ARCH20{i % 5 + 1}",
            language="JAVA" if i < 50 else "TYPESCRIPT",
        )
        for i in range(100)
    )
    final = ["POSITIVE"] * 50 + ["NEGATIVE"] * 46 + ["UNCERTAIN"] * 3 + ["OUT_OF_SCOPE"]
    a = {c.a_blinded_id: value for c, value in zip(cases, final, strict=True)}
    b = {c.b_blinded_id: value for c, value in zip(cases, final, strict=True)}
    conflicts = (0, 50, 51, 52)
    for i in conflicts:
        b[cases[i].b_blinded_id] = "NEGATIVE" if final[i] == "POSITIVE" else "POSITIVE"
    adjudicator = {f"synthetic-third-{i}": final[i] for i in conflicts}
    mapping = {f"synthetic-third-{i}": cases[i].case_id for i in conflicts}
    lineage = {key: "a" * (40 if key.endswith("commit") else 64) for key in LINEAGE_KEYS}
    return [cases, a, b, adjudicator, mapping, set(mapping.values()), lineage]


def truth(inputs):
    return merge_final_truth(*inputs)


def test_exact_partition_counts_propagation_and_eligibility(inputs):
    result = truth(inputs)
    receipt = truth_receipt(result)
    assert receipt["counts"] == dict(
        N=100,
        POSITIVE=50,
        NEGATIVE=46,
        UNCERTAIN=3,
        OUT_OF_SCOPE=1,
        binary_eligible=96,
        binary_excluded=4,
    )
    assert receipt["agreement_cases"] == 96 and receipt["adjudicated_cases"] == 4
    reverse = {case: key for key, case in inputs[4].items()}
    a_by_case = {c.case_id: inputs[1][c.a_blinded_id] for c in inputs[0]}
    for row in result.cases:
        if row.scientific_case_id in reverse:
            assert row.final_category == inputs[3][reverse[row.scientific_case_id]]
            assert row.resolution_provenance == "THIRD_HUMAN_ADJUDICATION"
        else:
            assert row.final_category == a_by_case[row.scientific_case_id]
            assert row.resolution_provenance == "A_B_AGREEMENT"
    assert sum(v["N"] for v in receipt["by_rule"].values()) == 100
    assert all(v["N"] == 20 for v in receipt["by_rule"].values())
    assert all(v["N"] == 50 for v in receipt["by_language"].values())


def test_identity_join_is_independent_of_every_input_order(inputs):
    expected = truth(inputs)
    inputs[0] = tuple(reversed(inputs[0]))
    for index in (1, 2, 3, 4, 6):
        inputs[index] = dict(reversed(list(inputs[index].items())))
    assert truth(inputs) == expected
    assert digest(truth(inputs)) == digest(expected)


@pytest.mark.parametrize("index", [1, 2, 3, 4])
@pytest.mark.parametrize("operation", ["missing", "extra"])
def test_missing_extra_identity_rejected(inputs, index, operation):
    if operation == "missing":
        inputs[index].pop(next(iter(inputs[index])))
    else:
        inputs[index]["synthetic-unexpected"] = "POSITIVE" if index != 4 else "synthetic-case"
    with pytest.raises(ValueError):
        truth(inputs)


def test_adjudicator_cannot_map_to_agreement(inputs):
    inputs[4][next(iter(inputs[4]))] = inputs[0][1].case_id
    with pytest.raises(ValueError):
        truth(inputs)


def test_duplicate_adjudicator_destination_rejected(inputs):
    keys = list(inputs[4])
    inputs[4][keys[1]] = inputs[4][keys[0]]
    with pytest.raises(ValueError):
        truth(inputs)


def test_frozen_conflict_membership_drift_rejected(inputs):
    inputs[5] = {"unexpected"}
    with pytest.raises(ValueError):
        truth(inputs)


@pytest.mark.parametrize("field", ["case_id", "a_blinded_id", "b_blinded_id"])
def test_duplicate_scientific_or_reviewer_identity_rejected(inputs, field):
    cases = list(inputs[0])
    cases[1] = cases[1].model_copy(update={field: getattr(cases[0], field)})
    inputs[0] = tuple(cases)
    with pytest.raises(ValueError):
        truth(inputs)


def test_expected_counts_verified_never_forced(inputs):
    inputs[3][next(iter(inputs[3]))] = "NEGATIVE"
    with pytest.raises(ValueError, match="COUNT_MISMATCH"):
        truth(inputs)


@pytest.mark.parametrize("field", ["mutation_operator", "pair_id", "expected_effect", "AI_output"])
def test_construction_and_detector_metadata_rejected(inputs, field):
    inputs[6][field] = "b" * 64
    with pytest.raises(ValueError):
        truth(inputs)


@pytest.mark.parametrize(
    "field", ["reviewer_identity", "rationale", "note", "source_text", "evidence"]
)
def test_final_rows_cannot_duplicate_human_or_source_payloads(inputs, field):
    row = truth(inputs).cases[0].model_dump()
    row[field] = "SYNTHETIC_PRIVATE_CANARY"
    with pytest.raises(ValidationError):
        TruthCase.model_validate(row)


def test_final_truth_privacy_and_no_model_access(inputs, monkeypatch):
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    result = truth(inputs)
    receipt = truth_receipt(result)
    raw = canonical(receipt)
    assert all(c.scientific_case_id not in raw for c in result.cases)
    assert METHODOLOGY in receipt.values()
    assert receipt["live_ai_calls"] == 0
    assert receipt["construction_intent_used"] is False
    assert receipt["detector_effectiveness_calculated"] is False
    assert all(
        set(c.model_dump())
        == {
            "scientific_case_id",
            "target_rule",
            "language",
            "final_category",
            "resolution_provenance",
        }
        for c in result.cases
    )
    tree = ast.parse(Path("src/archguard/infrastructure/semantic_final_truth.py").read_text())
    imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not any(
        "intelligence" in name or "provider" in name or "hybrid" in name for name in imports
    )


def test_append_only_raw_canonical_freeze_and_permissions(inputs, tmp_path):
    result = truth(inputs)
    destination = tmp_path / "private/final-human-ground-truth-v1"
    receipt = freeze_final_truth(destination, result)
    assert verify_final_truth(destination, result) == receipt
    raw = (destination / "ground-truth-v1.json").read_bytes()
    assert raw == (canonical(result) + "\n").encode()
    assert hashlib.sha256(raw).hexdigest() == receipt["ground_truth_sha256"]
    assert destination.stat().st_mode & 0o777 == 0o700
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in destination.iterdir())
    with pytest.raises(ValueError, match="immutable"):
        freeze_final_truth(destination, result)
    assert (destination / "ground-truth-v1.json").read_bytes() == raw


@pytest.mark.parametrize("drift", ["bytes", "unknown", "symlink", "receipt"])
def test_frozen_truth_drift_rejected(inputs, tmp_path, drift):
    result = truth(inputs)
    destination = tmp_path / "private/final-human-ground-truth-v1"
    freeze_final_truth(destination, result)
    if drift == "unknown":
        (destination / ".hidden").write_text("unexpected")
    else:
        path = destination / (
            "ground-truth-freeze-v1.json" if drift == "receipt" else "ground-truth-v1.json"
        )
        if drift == "symlink":
            raw = path.read_bytes()
            path.unlink()
            external = tmp_path / "external"
            external.write_bytes(raw)
            path.symlink_to(external)
        else:
            path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        verify_final_truth(destination, result)


def test_resealed_case_level_change_cannot_pass_expected_freeze(inputs, tmp_path):
    result = truth(inputs)
    destination = tmp_path / "private/final-human-ground-truth-v1"
    freeze_final_truth(destination, result)
    data = result.model_dump(mode="json")
    data["cases"][0]["final_category"] = "NEGATIVE"
    data.pop("fingerprint")
    data["fingerprint"] = digest(data)
    with pytest.raises(ValueError, match="COUNT_MISMATCH"):
        FinalHumanTruth.model_validate(data)
    assert (
        json.loads((destination / "ground-truth-v1.json").read_bytes())["fingerprint"]
        == result.fingerprint
    )
