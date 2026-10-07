"""Synthetic agreement examples; no real human judgments or source evidence."""

import ast
import hashlib
import json
import socket
from fractions import Fraction
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_agreement import (
    BINARY,
    CATEGORIES,
    CaseAlignment,
    PairedDecision,
    agreement_statistics,
    align_decisions,
    analyze_agreement,
)
from archguard.benchmark.semantic_review import ReviewerASubmission, ReviewerBSubmission
from archguard.infrastructure.semantic_agreement import (
    PRIVATE_FILES,
    PUBLIC_FILES,
    SOURCE_LINEAGE_KEYS,
    FrozenDecisions,
    ReviewExpectation,
    build_agreement_artifacts,
    freeze_agreement_artifacts,
    verify_agreement_artifacts,
    verify_frozen_review,
)
from archguard.infrastructure.semantic_holdout import verify_file_freeze


def case(i):
    return CaseAlignment(
        case_id=f"synthetic-case-{i:03}",
        a_blinded_id=f"synthetic-a-{i}",
        b_blinded_id=f"synthetic-b-{i}",
        rule_id=f"ARCH20{i % 5 + 1}",
        language="JAVA" if i % 2 else "TYPESCRIPT",
    )


def paired(decisions):
    return tuple(
        PairedDecision(**case(i).model_dump(), a_decision=a, b_decision=b)
        for i, (a, b) in enumerate(decisions)
    )


def synthetic_artifacts():
    cases = tuple(case(i) for i in range(100))
    choices = list(product(CATEGORIES, repeat=2)) + [(CATEGORIES[i % 4],) * 2 for i in range(84)]
    a, b = (
        FrozenDecisions(
            reviewer_slot=slot,
            submission_sha256="1" * 64,
            acceptance_receipt_fingerprint="2" * 64,
            submission_fingerprint="3" * 64,
            bundle_fingerprint="4" * 64,
            decisions={
                getattr(c, f"{slot.lower()}_blinded_id"): row[index]
                for c, row in reversed(list(zip(cases, choices, strict=True)))
            },
        )
        for index, slot in enumerate(("A", "B"))
    )
    lineage = {key: "5" * 64 for key in SOURCE_LINEAGE_KEYS}
    return cases, a, b, lineage, build_agreement_artifacts(cases, a, b, lineage)


@pytest.fixture(params=("A", "B"))
def frozen_review(tmp_path, request):
    slot = request.param
    model = ReviewerASubmission if slot == "A" else ReviewerBSubmission
    data = {
        "schema_version": "semantic-holdout-human-submission-v1",
        "reviewer_slot": slot,
        "bundle_fingerprint": "4" * 64,
        "reviewer_identity": "Synthetic identity; never public",
        "attestation": "REAL_HUMAN_INDEPENDENT_REVIEW",
        "responses": [
            {
                "blinded_id": f"synthetic-{slot.lower()}-{i}",
                "decision": "UNCERTAIN",
                "rationale": "Synthetic private rationale",
                "note": "Synthetic private note",
                "evidence": [{"evidence_id": "synthetic-e", "start_line": 1, "end_line": 1}],
            }
            for i in range(100)
        ],
    }
    raw = (json.dumps(data, indent=2) + "\n").encode()
    receipt = {
        "bundle_fingerprint": "4" * 64,
        "reviewer_slot": slot,
        "submission_sha256": hashlib.sha256(raw).hexdigest(),
        "submission_fingerprint": digest(model.model_validate(data)),
        "responses": 100,
        "decision_counts": {"UNCERTAIN": 100},
        "final_ground_truth": False,
    }
    receipt["fingerprint"] = digest(receipt)
    root = tmp_path / f"reviewer-{slot.lower()}-submissions-v1/frozen-v1"
    root.mkdir(parents=True)
    (root / "submission-v1.json").write_bytes(raw)
    (root / "submission-freeze-v1.json").write_text(json.dumps(receipt))
    expected = ReviewExpectation(
        reviewer_slot=slot,
        submission_sha256=receipt["submission_sha256"],
        acceptance_receipt_fingerprint=receipt["fingerprint"],
        submission_fingerprint=receipt["submission_fingerprint"],
        bundle_fingerprint="4" * 64,
    )
    return root, expected, data


def test_frozen_only_read_and_private_content_projection(frozen_review, monkeypatch):
    root, expected, _ = frozen_review
    working = root.parent / "completed-response.json"
    working.write_text("MUTABLE_WORKING_COPY_MUST_NOT_BE_READ")
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    original = Path.open

    def guard(path, *args, **kwargs):
        if path == working:
            raise AssertionError("mutable submission accessed")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", guard)
    result = verify_frozen_review(root, expected)
    assert len(result.decisions) == 100
    assert not {"reviewer_identity", "rationale", "note", "evidence"} & result.model_dump().keys()
    assert "Synthetic private" not in result.model_dump_json()
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before


@pytest.mark.parametrize(
    "field",
    [
        "submission_sha256",
        "acceptance_receipt_fingerprint",
        "submission_fingerprint",
        "bundle_fingerprint",
    ],
)
def test_exact_approved_input_guards(frozen_review, field):
    root, expected, _ = frozen_review
    changed = ReviewExpectation.model_validate(expected.model_dump() | {field: "0" * 64})
    with pytest.raises(ValueError):
        verify_frozen_review(root, changed)


def test_raw_guard_precedes_json_parsing(frozen_review):
    root, expected, _ = frozen_review
    (root / "submission-v1.json").write_bytes(b"not JSON")
    with pytest.raises(ValueError, match="SHA-256"):
        verify_frozen_review(root, expected)


def test_receipt_seal_and_path_guards(frozen_review, tmp_path):
    root, expected, _ = frozen_review
    receipt = json.loads((root / "submission-freeze-v1.json").read_text())
    receipt["responses"] = 99
    (root / "submission-freeze-v1.json").write_text(json.dumps(receipt))
    with pytest.raises(ValueError, match="receipt"):
        verify_frozen_review(root, expected)
    with pytest.raises(ValueError, match="path"):
        verify_frozen_review(root.parent, expected)
    link = tmp_path / "linked"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError):
        verify_frozen_review(link, expected)


@pytest.mark.parametrize("change", ["missing", "duplicate"])
def test_frozen_response_count_and_duplicate_guards(frozen_review, change):
    root, expected, data = frozen_review
    if change == "missing":
        data["responses"].pop()
    else:
        data["responses"][1] = data["responses"][0]
    raw = json.dumps(data).encode()
    (root / "submission-v1.json").write_bytes(raw)
    expected = ReviewExpectation.model_validate(
        expected.model_dump() | {"submission_sha256": hashlib.sha256(raw).hexdigest()}
    )
    with pytest.raises(ValueError):
        verify_frozen_review(root, expected)


def test_identity_join_not_array_position_and_100_pairs():
    cases, a, b, _, _ = synthetic_artifacts()
    result = align_decisions(tuple(reversed(cases)), a.decisions, b.decisions)
    assert len(result) == 100 and len({p.case_id for p in result}) == 100
    assert all(
        p.a_decision == a.decisions[p.a_blinded_id] and p.b_decision == b.decisions[p.b_blinded_id]
        for p in result
    )
    assert result == align_decisions(cases, dict(reversed(list(a.decisions.items()))), b.decisions)


@pytest.mark.parametrize(
    "change",
    ["missing_a", "extra_b", "duplicate_case", "duplicate_a", "duplicate_b", "missing_case"],
)
def test_counterpart_and_mapping_guards(change):
    cases, a, b, _, _ = synthetic_artifacts()
    av, bv = dict(a.decisions), dict(b.decisions)
    if change == "missing_a":
        av.pop(cases[0].a_blinded_id)
    elif change == "extra_b":
        bv["extra"] = "POSITIVE"
    elif change == "missing_case":
        cases = cases[:-1]
    else:
        field = {
            "duplicate_case": "case_id",
            "duplicate_a": "a_blinded_id",
            "duplicate_b": "b_blinded_id",
        }[change]
        cases = (
            cases[0],
            CaseAlignment.model_validate(cases[1].model_dump() | {field: getattr(cases[0], field)}),
            *cases[2:],
        )
    with pytest.raises(ValueError):
        align_decisions(cases, av, bv)


def test_four_category_matrix_binary_filter_and_taxonomy():
    rows = paired(product(CATEGORIES, repeat=2))
    report = analyze_agreement(rows)
    primary = report["primary"]
    assert primary["n"] == 16 and primary["exact_agreement"] == 4 and primary["disagreement"] == 12
    assert primary["agreement_percentage"] == 25 and primary["cohens_kappa"] == 0
    assert all(value == 1 for row in primary["matrix"].values() for value in row.values())
    binary = report["binary"]
    assert binary["n"] == 4 and binary["excluded_nonbinary"] == 12
    assert binary["exact_agreement"] == binary["disagreement"] == 2 and binary["cohens_kappa"] == 0
    assert binary["agreement_percentage"] == 50
    assert all(value == 1 for row in binary["matrix"].values() for value in row.values())
    assert len(report["disagreement_taxonomy"]) == 6 and set(
        report["disagreement_taxonomy"].values()
    ) == {2}


def test_known_unweighted_kappa_examples():
    rows = paired(
        [("POSITIVE", "POSITIVE")] * 8
        + [("POSITIVE", "NEGATIVE")] * 2
        + [("NEGATIVE", "POSITIVE")] * 3
        + [("NEGATIVE", "NEGATIVE")] * 7
    )
    binary = agreement_statistics(rows, BINARY)
    assert binary["matrix"] == {
        "POSITIVE": {"POSITIVE": 8, "NEGATIVE": 2},
        "NEGATIVE": {"POSITIVE": 3, "NEGATIVE": 7},
    }
    assert binary["observed_agreement"] == 0.75 and binary["expected_chance_agreement"] == 0.5
    assert binary["cohens_kappa"] == 0.5
    full = agreement_statistics(
        rows + paired([("UNCERTAIN", "UNCERTAIN")] * 5 + [("OUT_OF_SCOPE", "OUT_OF_SCOPE")] * 5)
    )
    assert full["observed_agreement"] == float(Fraction(5, 6))
    assert full["expected_chance_agreement"] == float(Fraction(5, 18))
    assert full["cohens_kappa"] == float(Fraction(10, 13))
    assert (
        agreement_statistics(paired([("POSITIVE", "NEGATIVE"), ("NEGATIVE", "POSITIVE")]), BINARY)[
            "cohens_kappa"
        ]
        == -1
    )
    assert agreement_statistics(paired([(c, c) for c in CATEGORIES]))["cohens_kappa"] == 1


@pytest.mark.parametrize(
    "rows,reason",
    [
        ((), "NO_PAIRED_CASES"),
        ((("POSITIVE", "POSITIVE"),) * 5, "EXPECTED_CHANCE_AGREEMENT_IS_ONE"),
    ],
)
def test_undefined_kappa(rows, reason):
    stats = agreement_statistics(paired(rows))
    assert stats["cohens_kappa"] is None and stats["kappa_undefined_reason"].startswith(reason)


def test_strata_marginals_are_descriptive_and_complete():
    _, _, _, _, artifacts = synthetic_artifacts()
    primary = artifacts["analysis"]["primary"]
    for dimension in ("rule_id", "language"):
        strata = artifacts["analysis"]["strata"][dimension]
        assert sum(s["n"] for s in strata.values()) == 100
        assert sum(s["exact_agreement"] for s in strata.values()) == primary["exact_agreement"]
        assert all("DESCRIPTIVE_ONLY" in s["interpretation"] for s in strata.values())
        assert all(
            sum(s["marginals_A"].values()) == sum(s["marginals_B"].values()) == s["n"]
            for s in strata.values()
        )


def test_exact_conflicts_deterministic_ids_and_safe_index():
    cases, a, b, lineage, artifacts = synthetic_artifacts()
    manifest = artifacts["conflicts"]
    expected = {
        c.case_id for c in cases if a.decisions[c.a_blinded_id] != b.decisions[c.b_blinded_id]
    }
    assert {c["case_id"] for c in manifest["conflicts"]} == expected
    assert manifest["conflict_count"] == len(expected) == 12
    assert len({c["conflict_id"] for c in manifest["conflicts"]}) == 12
    assert artifacts == build_agreement_artifacts(tuple(reversed(cases)), a, b, lineage)
    safe = artifacts["index"]
    assert {c["case_id"] for c in safe["cases"]} == expected
    assert all(set(c) == {"conflict_id", "case_id", "rule_id", "language"} for c in safe["cases"])
    assert not any(category in json.dumps(safe) for category in CATEGORIES)
    for value in artifacts.values():
        assert value["fingerprint"] == digest(
            {k: v for k, v in value.items() if k != "fingerprint"}
        )
    assert artifacts["receipt"]["final_ground_truth_materialized"] is False
    assert artifacts["receipt"]["conflicts_resolved"] == 0
    assert safe["full_handoff_created"] is False
    for key in ("analysis", "receipt"):
        assert not expected.intersection(set(json.dumps(artifacts[key]).split('"')))


@pytest.mark.parametrize(
    "field",
    [
        "construction_intent",
        "pair_id",
        "operator_id",
        "reviewer_identity",
        "rationale",
        "evidence",
        "ai_results",
    ],
)
def test_construction_and_human_content_cannot_enter_alignment_or_safe_lineage(field):
    with pytest.raises(ValidationError):
        CaseAlignment.model_validate(case(0).model_dump() | {field: "FORBIDDEN"})
    cases, a, b, lineage, _ = synthetic_artifacts()
    with pytest.raises(ValueError, match="lineage"):
        build_agreement_artifacts(cases, a, b, lineage | {field: "FORBIDDEN"})


def test_no_live_calls_or_resolution_and_immutable_four_artifacts(tmp_path, monkeypatch):
    _, _, _, _, artifacts = synthetic_artifacts()

    def denied(*args, **kwargs):
        raise AssertionError("network path forbidden")

    monkeypatch.setattr(socket, "socket", denied)
    public, private = tmp_path / "public", tmp_path / "private"
    freeze_agreement_artifacts(public, private, artifacts)
    verify_agreement_artifacts(public, private, artifacts)
    assert {p.name for p in public.iterdir()} == set(PUBLIC_FILES.values())
    assert {p.name for p in private.iterdir()} == set(PRIVATE_FILES.values())
    before = {str(p): p.read_bytes() for root in (public, private) for p in root.iterdir()}
    with pytest.raises(ValueError, match="immutable"):
        freeze_agreement_artifacts(public, private, artifacts)
    assert before == {str(p): p.read_bytes() for root in (public, private) for p in root.iterdir()}
    for root in (public, private):
        assert all("truth" not in p.name and "handoff" not in p.name for p in root.iterdir())
    path = private / "adjudicator-safe-index-v1.json"
    path.write_text("tamper")
    with pytest.raises(ValueError, match="changed"):
        verify_agreement_artifacts(public, private, artifacts)


def test_old_inventory_integrity_without_decoding_construction(tmp_path, monkeypatch):
    source = tmp_path / "provenance-v1.json"
    raw = b"PRIVATE_CONSTRUCTION_CANARY_DO_NOT_DECODE"
    source.write_bytes(raw)
    freeze = {"files": {source.name: hashlib.sha256(raw).hexdigest()}}
    freeze["fingerprint"] = digest(freeze)
    original = json.loads

    def guarded(value, *args, **kwargs):
        assert "PRIVATE_CONSTRUCTION_CANARY" not in str(value)
        return original(value, *args, **kwargs)

    monkeypatch.setattr(json, "loads", guarded)
    verify_file_freeze(tmp_path, freeze)
    source.write_bytes(b"changed")
    with pytest.raises(ValueError):
        verify_file_freeze(tmp_path, freeze)


def test_execution_code_excludes_providers_construction_and_truth_materialization():
    root = Path(__file__).resolve().parents[2]
    for relative in (
        "src/archguard/benchmark/semantic_agreement.py",
        "src/archguard/infrastructure/semantic_agreement.py",
        "scripts/prompt015c_agreement.py",
    ):
        tree = ast.parse((root / relative).read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names] + (
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
                )
                assert not any(
                    token in name
                    for name in names
                    for token in (
                        "llm_provider",
                        "semantic_evaluation",
                        "hybrid",
                        "structural_v2",
                        "httpx",
                        "requests",
                        "socket",
                        "urllib",
                        "PrivatePair",
                        "Operator",
                    )
                )
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "completed-response.json" not in node.value and ".env" not in node.value
                assert "provenance-v1.json" not in node.value
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                assert name not in {
                    "adjudicate",
                    "construct_holdout",
                    "majority_vote",
                    "finalize_truth",
                }
