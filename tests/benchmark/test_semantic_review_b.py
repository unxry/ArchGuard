"""B handoff isolation guards; synthetic contracts, never real human case judgments."""

import ast
import builtins
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_holdout import BlindedPacket, SourceEvidence
from archguard.benchmark.semantic_review import (
    HumanResponse,
    ReviewerASubmission,
    ReviewerBBundle,
    ReviewerBSubmission,
)
from archguard.infrastructure.semantic_review_b import (
    freeze_b_submission,
    prepare_b_handoff,
    verify_b_handoff,
    verify_b_submission_contract,
)


def sealed_map(value):
    payload = {k: v for k, v in value.items() if k != "fingerprint"}
    return payload | {"fingerprint": digest(payload)}


@pytest.fixture
def frozen_b(tmp_path):
    text = "Synthetic frozen source line one.\nSynthetic frozen source line two.\n"
    packets = tuple(
        seal(
            BlindedPacket,
            blinded_id=f"synthetic-b-{i}",
            rule_id=f"ARCH20{i % 5 + 1}",
            language="JAVA" if i % 2 else "TYPESCRIPT",
            project_alias="synthetic-b",
            target_path="src/Frozen.txt",
            target_component="Frozen",
            architecture_contract="Synthetic contract only.",
            evidence=(
                SourceEvidence(
                    evidence_id=f"synthetic-e-{i}",
                    path="src/Frozen.txt",
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                ),
            ),
        )
        for i in reversed(range(100))
    )
    bundle = seal(
        ReviewerBBundle,
        schema_version="blank-independent-human-bundle-v1",
        reviewer_slot="B",
        status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
        packets=packets,
        protocol=sealed_map({"reviewer_slots": ["A", "B"], "auto_review": False}),
        guidance=sealed_map(
            {
                "general": "Frozen synthetic guidance.",
                "arch201_vs_arch205": "Frozen distinction.",
                "rules": {f"ARCH20{i}": "Frozen synthetic rubric." for i in range(1, 6)},
            }
        ),
    )
    path = tmp_path / "private/review/B/bundle-v1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2) + "\n")
    return path, bundle


def test_b_fingerprint_order_source_blank_template_and_schema_preserved(frozen_b, tmp_path):
    original, bundle = frozen_b
    before = original.read_bytes()
    destination = tmp_path / "handoff"
    fp = prepare_b_handoff(original, bundle.fingerprint, destination)
    assert verify_b_handoff(original, bundle.fingerprint, destination) == fp
    assert original.read_bytes() == before == (destination / "bundle-v1.json").read_bytes()
    template = json.loads((destination / "response-template.json").read_text())
    ids = [p.blinded_id for p in bundle.packets]
    assert len(ids) == len(set(ids)) == 100
    assert [r["blinded_id"] for r in template["responses"]] == ids
    assert template["reviewer_slot"] == "B" and template["bundle_fingerprint"] == bundle.fingerprint
    assert not template["reviewer_identity"] and template["attestation"] is None
    assert all(
        r["decision"] is None and not r["rationale"] and not r["evidence"] and not r["note"]
        for r in template["responses"]
    )
    assert (
        json.loads((destination / "submission-schema.json").read_text())
        == ReviewerBSubmission.model_json_schema()
    )
    with pytest.raises(ValidationError):
        ReviewerBSubmission.model_validate(template)
    html = (destination / "index.html").read_text()
    assert html.count("<section id=") == 100 and "Frozen synthetic rubric." in html
    assert html.index('id="synthetic-b-99"') < html.index('id="synthetic-b-98"')
    assert "default-src 'none'" in html and "<script" not in html
    assert "DIFFERENT PERSON" in (destination / "README.txt").read_text()
    for forbidden in (
        "b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e",
        "58488f51c3050266ecdc930e8c24814d7d4040ba1101765ed2180d8a1c0ffb08",
        "5c9e97870a96b195eee3d2331f3003918cdf30ad30236922b56b93b16cf114d2",
    ):
        assert not any(forbidden.encode() in p.read_bytes() for p in destination.iterdir())
    with pytest.raises(ValueError, match="immutable"):
        prepare_b_handoff(original, bundle.fingerprint, destination)
    (destination / "index.html").write_text("tampered")
    with pytest.raises(ValueError, match="differs"):
        verify_b_handoff(original, bundle.fingerprint, destination)


def test_b_builder_cannot_read_A_answers_and_A_changes_cannot_affect_B(
    frozen_b, tmp_path, monkeypatch
):
    original, bundle = frozen_b
    a_root = tmp_path / "private/reviewer-a-submissions-v1"
    snapshot = a_root / "frozen-v1/submission-v1.json"
    snapshot.parent.mkdir(parents=True)
    source = a_root / "completed-response.json"
    source.write_text("SYNTHETIC_PRIVATE_A_CANARY_ONE")
    snapshot.write_text("SYNTHETIC_PRIVATE_A_SNAPSHOT")
    path_open = Path.open
    builtin_open = builtins.open
    observed = []

    def guard(path):
        if isinstance(path, (str, Path)):
            candidate = Path(path).resolve()
            if candidate.is_relative_to(a_root.resolve()):
                raise AssertionError("B builder attempted access to private A answers")
            observed.append(candidate)

    def guarded_path_open(path, *args, **kwargs):
        guard(path)
        return path_open(path, *args, **kwargs)

    def guarded_builtin_open(path, *args, **kwargs):
        guard(path)
        return builtin_open(path, *args, **kwargs)

    def build(name):
        with monkeypatch.context() as patch:
            patch.setattr(Path, "open", guarded_path_open)
            patch.setattr(builtins, "open", guarded_builtin_open)
            with pytest.raises(AssertionError):
                source.read_bytes()
            with pytest.raises(AssertionError), builtins.open(snapshot, "rb"):
                pass
            return prepare_b_handoff(original, bundle.fingerprint, tmp_path / name)

    first = build("first")
    source.write_text("SYNTHETIC_PRIVATE_A_CANARY_TWO")
    second = build("second")
    assert first == second and observed
    assert not any(path.is_relative_to(a_root.resolve()) for path in observed)
    for file in (tmp_path / "first").iterdir():
        assert file.read_bytes() == (tmp_path / "second" / file.name).read_bytes()
        assert b"SYNTHETIC_PRIVATE_A" not in file.read_bytes()
    assert source.read_text() == "SYNTHETIC_PRIVATE_A_CANARY_TWO"


@pytest.mark.parametrize(
    "field",
    [
        "reviewer_a_identity",
        "reviewer_a_decision_counts",
        "reviewer_a_notes",
        "reviewer_a_answers",
        "pair_id",
        "construction_intent",
        "operator_id",
        "private_provenance",
        "ai_results",
        "static_predictions",
        "graph_predictions",
        "structural_v2_predictions",
        "hybrid_predictions",
    ],
)
def test_B_rejects_A_construction_and_prediction_metadata(frozen_b, tmp_path, field):
    original, bundle = frozen_b
    data = bundle.model_dump(mode="json")
    data["guidance"] = sealed_map(data["guidance"] | {field: "FORBIDDEN_SYNTHETIC_METADATA"})
    data = sealed_map(data)
    original.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="forbidden"):
        prepare_b_handoff(original, data["fingerprint"], tmp_path / "handoff")
    assert not (tmp_path / "handoff").exists()


@pytest.mark.parametrize("change", ["fingerprint", "duplicate", "wrong_slot"])
def test_B_rejects_wrong_binding_and_duplicate_cases(frozen_b, tmp_path, change):
    original, bundle = frozen_b
    expected = bundle.fingerprint
    if change == "fingerprint":
        expected = "0" * 64
    else:
        data = bundle.model_dump(mode="json")
        if change == "duplicate":
            data["packets"][1] = data["packets"][0]
        else:
            data["reviewer_slot"] = "A"
        data = sealed_map(data)
        original.write_text(json.dumps(data))
        expected = data["fingerprint"]
    with pytest.raises(ValueError):
        prepare_b_handoff(original, expected, tmp_path / "handoff")
    assert not (tmp_path / "handoff").exists()


@pytest.mark.parametrize(
    "change", ["decision", "multiple", "rationale", "evidence", "reference", "range"]
)
def test_B_response_evidence_and_category_requirements(change):
    row = {
        "blinded_id": "synthetic-only",
        "decision": "UNCERTAIN",
        "rationale": "Synthetic contract fixture.",
        "evidence": [{"evidence_id": "synthetic-source", "start_line": 1, "end_line": 1}],
    }
    if change == "decision":
        row["decision"] = None
    elif change == "multiple":
        row["decision"] = ["POSITIVE", "NEGATIVE"]
    elif change == "rationale":
        row["rationale"] = " "
    elif change == "evidence":
        row["evidence"] = []
    elif change == "reference":
        del row["evidence"][0]["end_line"]
    else:
        row["evidence"][0]["start_line"] = 0
    with pytest.raises(ValidationError):
        HumanResponse.model_validate(row)


def test_B_submission_path_ignored_by_existing_repository_policy(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    root = Path(__file__).resolve().parents[2]
    (tmp_path / ".gitignore").write_bytes((root / ".gitignore").read_bytes())
    assert (
        subprocess.run(
            [
                "git",
                "check-ignore",
                "-q",
                "experiments/semantic-holdout/private/reviewer-b-submissions-v1/completed-response.json",
            ],
            cwd=tmp_path,
        ).returncode
        == 0
    )


def test_no_ai_or_A_answer_input_or_order_regeneration_in_B_code():
    root = Path(__file__).resolve().parents[2]
    paths = [
        root / "src/archguard/infrastructure/semantic_review_b.py",
        root / "scripts/prompt015b_handoff.py",
    ]
    forbidden = (
        "llm_provider",
        "semantic_evaluation",
        "hybrid",
        "structural_v2",
        "urllib",
        "socket",
        "requests",
        "httpx",
        "random",
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = [n.name for n in node.names]
                if isinstance(node, ast.ImportFrom):
                    names.append(node.module or "")
                assert not any(word in name for name in names for word in forbidden)
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert "reviewer-a-submissions-v1/completed-response.json" not in node.value
                assert "reviewer-a-submissions-v1/frozen-v1/submission-v1.json" not in node.value
                assert ".env" not in node.value
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in {"sorted", "shuffle", "agreement", "adjudicate", "kappa"}


def test_shared_refactor_preserves_frozen_A_submission_schema():
    assert digest(ReviewerASubmission.model_json_schema()) == (
        "3c57f92c6ff6ecd0b8ecdffa42c1542d3b568da0f36beab0a5a5ad76e2dd5aea"
    )


def synthetic_b_submission(bundle):
    return {
        "schema_version": "semantic-holdout-human-submission-v1",
        "reviewer_slot": "B",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_identity": "Synthetic test identity only",
        "attestation": "REAL_HUMAN_INDEPENDENT_REVIEW",
        "responses": [
            {
                "blinded_id": p.blinded_id,
                "decision": "UNCERTAIN",
                "rationale": "  Synthetic DTO fixture; keep spacing and spelling untouched.  ",
                "evidence": [
                    {"evidence_id": p.evidence[0].evidence_id, "start_line": 1, "end_line": 2}
                ],
                "note": "Synthetic note\nwith formatting.",
            }
            for p in bundle.packets
        ],
    }


def b_intake(tmp_path, data):
    source = tmp_path / "private/reviewer-b-submissions-v1/completed-response.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes((json.dumps(data, indent=3) + "\n\n").encode())
    return source, hashlib.sha256(source.read_bytes()).hexdigest(), source.parent / "frozen-v1"


def test_B_acceptance_byte_identity_privacy_lineage_and_append_only(frozen_b, tmp_path):
    original, bundle = frozen_b
    data = synthetic_b_submission(bundle)
    source, sha, destination = b_intake(tmp_path, data)
    before = source.read_bytes()
    fp = freeze_b_submission(
        original,
        bundle.fingerprint,
        source,
        destination,
        expected_sha256=sha,
        expected_counts={"UNCERTAIN": 100},
        lineage={"sample_fingerprint": "1" * 64, "B_handoff_freeze_fingerprint": "2" * 64},
    )
    assert fp == digest(ReviewerBSubmission.model_validate(data))
    assert source.read_bytes() == before == (destination / "submission-v1.json").read_bytes()
    assert json.loads((destination / "submission-v1.json").read_bytes()) == data
    receipt = json.loads((destination / "submission-freeze-v1.json").read_text())
    assert receipt["reviewer_slot"] == "B" and receipt["responses"] == 100
    assert receipt["submission_sha256"] == sha and receipt["submission_fingerprint"] == fp
    assert receipt["decision_counts"] == {"UNCERTAIN": 100}
    assert receipt["schema_validation"] == receipt["evidence_validation"] == "PASS"
    assert receipt["final_ground_truth"] is False and receipt["adjudicated_truth"] is False
    assert receipt["human_answers_modified"] is False
    assert all(
        receipt[k] == 0
        for k in (
            "missing_cases",
            "extra_cases",
            "duplicate_ids",
            "invalid_evidence_refs",
            "invalid_line_ranges",
        )
    )
    assert receipt["fingerprint"] == digest(
        {k: v for k, v in receipt.items() if k != "fingerprint"}
    )
    assert receipt["lineage"]["sample_fingerprint"] == "1" * 64
    assert (
        not {"reviewer_identity", "rationale", "note", "evidence", "individual_decisions"}
        & receipt.keys()
    )
    encoded = json.dumps(receipt)
    assert "Synthetic test identity" not in encoded and "keep spacing" not in encoded
    receipt_before = (destination / "submission-freeze-v1.json").read_bytes()
    with pytest.raises(ValueError, match="immutable"):
        freeze_b_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256=sha,
            expected_counts={"UNCERTAIN": 100},
            lineage={},
        )
    assert (
        source.read_bytes() == before
        and (destination / "submission-freeze-v1.json").read_bytes() == receipt_before
    )


@pytest.mark.parametrize(
    "change",
    [
        "sha",
        "counts",
        "schema",
        "slot",
        "bundle",
        "missing",
        "extra",
        "duplicate",
        "identity",
        "attestation",
        "rationale",
        "source",
        "range",
        "pair_field",
    ],
)
def test_B_acceptance_rejects_invalid_input_without_creating_snapshot(frozen_b, tmp_path, change):
    original, bundle = frozen_b
    data = synthetic_b_submission(bundle)
    if change == "schema":
        data["schema_version"] = "invalid"
    elif change == "slot":
        data["reviewer_slot"] = "A"
    elif change == "bundle":
        data["bundle_fingerprint"] = "0" * 64
    elif change == "missing":
        data["responses"].pop()
    elif change == "extra":
        data["responses"].append(data["responses"][0])
    elif change == "duplicate":
        data["responses"][1] = data["responses"][0]
    elif change == "identity":
        data["reviewer_identity"] = "  "
    elif change == "attestation":
        data["attestation"] = None
    elif change == "rationale":
        data["responses"][0]["rationale"] = " "
    elif change == "source":
        data["responses"][0]["evidence"][0]["evidence_id"] = "foreign"
    elif change == "range":
        data["responses"][0]["evidence"][0]["end_line"] = 3
    elif change == "pair_field":
        data["responses"][0]["pair_id"] = "not-permitted"
    source, sha, destination = b_intake(tmp_path, data)
    raw = source.read_bytes()
    with pytest.raises(ValueError):
        freeze_b_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256="0" * 64 if change == "sha" else sha,
            expected_counts={"NEGATIVE": 100} if change == "counts" else {"UNCERTAIN": 100},
            lineage={},
        )
    assert not destination.exists() and source.read_bytes() == raw


def test_B_SHA_guard_precedes_parsing_and_duplicate_fields_rejected(frozen_b, tmp_path):
    original, bundle = frozen_b
    source, _, destination = b_intake(tmp_path, synthetic_b_submission(bundle))
    source.write_bytes(b"not even JSON")
    actual = hashlib.sha256(source.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match=actual):
        freeze_b_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256="0" * 64,
            expected_counts={"UNCERTAIN": 100},
            lineage={},
        )
    source.write_text(
        json.dumps(synthetic_b_submission(bundle)).replace(
            '"decision": "UNCERTAIN"', '"decision": "UNCERTAIN", "decision": "NEGATIVE"', 1
        )
    )
    with pytest.raises(ValueError, match="duplicate submission field"):
        freeze_b_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
            expected_counts={"UNCERTAIN": 100},
            lineage={},
        )
    assert not destination.exists()


def test_B_acceptance_never_opens_A_private_answers(frozen_b, tmp_path, monkeypatch):
    original, bundle = frozen_b
    source, sha, destination = b_intake(tmp_path, synthetic_b_submission(bundle))
    a_root = tmp_path / "private/reviewer-a-submissions-v1"
    a_snapshot = a_root / "frozen-v1/submission-v1.json"
    a_snapshot.parent.mkdir(parents=True)
    a_source = a_root / "completed-response.json"
    a_source.write_text("PRIVATE_A_CANARY_NOT_A_HUMAN_REVIEW")
    a_snapshot.write_text("PRIVATE_A_SNAPSHOT_CANARY")
    before = (a_source.read_bytes(), a_snapshot.read_bytes())
    original_open = Path.open

    def guarded(path, *args, **kwargs):
        if "reviewer-a-submissions-v1" in path.parts:
            raise AssertionError("A private answers must never be opened by B acceptance")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", guarded)
        with pytest.raises(AssertionError):
            a_source.read_bytes()
        with pytest.raises(ValueError, match="own private"):
            freeze_b_submission(
                original,
                bundle.fingerprint,
                a_source,
                destination,
                expected_sha256=sha,
                expected_counts={"UNCERTAIN": 100},
                lineage={},
            )
        freeze_b_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256=sha,
            expected_counts={"UNCERTAIN": 100},
            lineage={},
        )
    assert (a_source.read_bytes(), a_snapshot.read_bytes()) == before


def test_B_frozen_submission_schema_survives_returned_working_form(frozen_b, tmp_path):
    original, bundle = frozen_b
    handoff = tmp_path / "handoff"
    fp = prepare_b_handoff(original, bundle.fingerprint, handoff)
    (handoff / "response-template.json").rename(handoff / "completed-response.json")
    assert verify_b_submission_contract(handoff, bundle.fingerprint) == fp
    (handoff / "submission-schema.json").write_text("{}")
    with pytest.raises(ValueError, match="contract changed"):
        verify_b_submission_contract(handoff, bundle.fingerprint)
