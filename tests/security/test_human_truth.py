"""P031.A.3 schema/state-machine tests; no evidence analysis or simulated human review."""

import ast
import copy
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from archguard.infrastructure import security_human_truth as t
from archguard.infrastructure import security_review_recovery as recovery
from archguard.infrastructure import unified_human_review as io
from archguard.security_benchmark.foundation import PredictionInputs, truth_join_gate

CASE = "sc-" + "0" * 24


def record(label: str = "UNCERTAIN") -> dict[str, Any]:
    # An enum-validation token, with no security case evidence or human authorship claim.
    return dict(case_id=CASE, final_label=label, rationale="\u00a0\n…  ", completed=True)


@pytest.mark.parametrize("label", t.LABELS)
def test_frozen_schema_preserves_each_of_four_states_and_exact_text(label: str) -> None:
    original = record(label) | dict(ordinal=9, rule_id="SEC001", file="transport.json")
    before = copy.deepcopy(original)
    assert t.project(original) == record(label)
    assert original == before


@pytest.mark.parametrize(
    "change",
    [
        {"final_label": "invalid"},
        {"completed": False},
        {"completed": 1},
        {"rationale": None},
        {"rationale": "x" * 8001},
        {"unexpected": 1},
    ],
)
def test_rejects_incomplete_unknown_enum_and_unapproved_fields(change: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        t.project(record() | change)


def test_transport_single_missing_brace_is_in_memory_only() -> None:
    raw = (
        json.dumps(
            dict(responses=[record()], total=300, reviewer_slot="B"), ensure_ascii=False
        ).encode()[:-1]
        + b"\n"
    )
    saved = bytes(raw)
    parsed, repaired = t.envelope(raw)
    assert repaired and parsed["responses"] == [record()] and raw == saved
    with pytest.raises(ValueError):
        t.envelope(b'{"responses":[{"broken":')
    with pytest.raises(ValueError):
        t.envelope(b'{"responses":[],"responses":[]}')


def test_human_only_provenance_rejects_ai_and_does_not_require_blindness() -> None:
    value = dict(
        human_origin_attestation="AI was not involved; LLMs were not used; a person was involved.",
        independence_attestation="The adjudicator decided himself, without anyone else.",
    )
    t.human_only(value)
    with pytest.raises(ValueError, match="REDO_REQUIRED"):
        t.human_only(value | {"AI_OR_LLM_ASSISTANCE": "YES"})
    with pytest.raises(ValueError, match="REDO_REQUIRED"):
        t.human_only(value | {"human_origin_attestation": "AI was used"})
    with pytest.raises(ValueError):
        t.human_only({})


def test_truth_join_is_exact_equality_or_supplied_adjudication_only() -> None:
    # Opaque algebraic categories are deliberately unrelated to vulnerability decisions.
    result = t.derive({"one": "x", "two": "u"}, {"one": "x", "two": "v"}, {"two": "z"})
    assert result == [
        dict(case_id="one", final_label="x", truth_source="A_B_AGREEMENT"),
        dict(case_id="two", final_label="z", truth_source="HUMAN_ADJUDICATION"),
    ]
    for adjudications in ({}, {"one": "x", "two": "z"}, {"foreign": "z"}):
        with pytest.raises(ValueError):
            t.derive({"one": "x", "two": "u"}, {"one": "x", "two": "v"}, adjudications)
    with pytest.raises(ValueError):
        t.derive({"one": "x"}, {}, {})


@pytest.mark.parametrize("unknown", [False, True])
def test_intake_rejects_duplicate_or_unknown_identity_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, unknown: bool
) -> None:
    root = tmp_path.resolve() / "adjudication"
    monkeypatch.setattr(t, "ADJ", root)
    nested = root / "responses/nested"
    nested.mkdir(parents=True)
    first = nested / "one.json"
    first.write_text(json.dumps(record()))
    second = nested / "two.json"
    row = record()
    if unknown:
        row["case_id"] = "sc-" + "f" * 24
    second.write_text(json.dumps(row))
    before = {p: p.read_bytes() for p in (first, second)}
    with pytest.raises(ValueError, match="DUPLICATE_OR_UNKNOWN"):
        t.intake({CASE: {"response_destination": str(root / "responses" / f"{CASE}.json")}})
    assert all(p.read_bytes() == raw for p, raw in before.items())


def test_binary_eligibility_excludes_uncertain_and_out_of_scope() -> None:
    rows = [
        dict(case_id=str(i), final_label=label, truth_source="A_B_AGREEMENT")
        for i, label in enumerate(t.LABELS)
    ]
    result = t.distribution(rows)
    assert result["N"] == 4 and result["binary_eligible"] == 2
    assert all(n == 1 for n in result["labels"].values())
    with pytest.raises(ValueError):
        t.distribution([dict(final_label="invalid")])


def test_final_prediction_capability_denies_all_truth_and_review_paths(tmp_path: Path) -> None:
    root = tmp_path.resolve() / "sources"
    path = root / CASE / "src/Unit.ts"
    path.parent.mkdir(parents=True)
    path.write_text("export const n=1;")
    roster = (
        dict(case_id=CASE, rule_id="SEC001", language="TYPESCRIPT", source_paths=["src/Unit.ts"]),
    )
    capability = PredictionInputs(root, roster)
    for forbidden in (
        "../truth.json",
        "/truth.json",
        str(t.TRUTH / "FINAL/truth.json"),
        str(t.PRIVATE / "responses/A"),
        str(t.ADJ / "responses"),
    ):
        with pytest.raises(ValueError):
            capability.read(forbidden)
    with pytest.raises(ValueError):
        PredictionInputs(root, (roster[0] | {"final_label": "forbidden"},))
    with pytest.raises(ValueError):
        truth_join_gate(False, "SECURITY_FINAL_POST_PREDICTION_TRUTH_JOIN")


def test_actual_private_truth_is_deterministic_complete_and_partitioned() -> None:
    if not (t.TRUTH / "human-truth-300.json").exists():
        pytest.skip("Private human truth is not mounted or has not been accepted yet")
    a = {
        s: io.read_seal(t.PRIVATE / "frozen" / f"reviewer-{s}.json")["responses"]
        for s in ("A", "B")
    }
    decisions = io.read_seal(t.ADJ / "accepted/response-set.json")["responses"]
    public, private = t.build(a, decisions)
    public_again, private_again = t.build(a, decisions)
    if public != public_again or private != private_again:
        pytest.fail("Non-deterministic truth closure")
    assert len(private["whole"]["rows"]) == 300
    assert len(private["DEV"]["rows"]) == 100
    assert len(private["FINAL"]["rows"]) == 200
    dev = {r["case_id"] for r in private["DEV"]["rows"]}
    final = {r["case_id"] for r in private["FINAL"]["rows"]}
    assert not dev & final and len(dev | final) == 300
    assert public["closure"]["agreement_derived"] == 290
    assert public["closure"]["adjudication_derived"] == 10
    assert public["custody"]["truth_read_capability_granted"] is False
    assert public["custody"]["source_file_count"] > 0
    assert "source_files" not in public["custody"]
    for name, expected in (
        ("security-human-truth-closure.json", public["closure"]),
        ("security-final-truth-custody.json", public["custody"]),
    ):
        if io.read_seal(t.PUBLIC / name) != expected:
            pytest.fail("Frozen public closure drift")
    recovery.privacy(tuple(t.PUBLIC / n for n in t.PUBLIC_NAMES[:2]))


def test_truth_path_schema_and_execution_boundaries() -> None:
    tree = ast.parse(Path(t.SOURCES[0]).read_text())
    forbidden = {
        "SecurityAnalyzer",
        "SecurityAnalyzerV2",
        "run_security_analysis",
        "generate",
        "getenv",
        "urlopen",
        "request",
        "exec",
        "eval",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
            )
            assert name not in forbidden
    with pytest.raises(ValidationError):
        t.Adjudication.model_validate(record() | {"detector_result": "forbidden"})
