"""Synthetic corrected-human acceptance; no real human data or provider execution."""

import copy
import hashlib
import json
import socket

import pytest

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import semantic_adjudication_correction
from archguard.infrastructure.semantic_adjudication_acceptance import (
    SubmissionMismatch,
    verify_opaque_seal,
)
from archguard.infrastructure.semantic_adjudication_corrected_acceptance import (
    CorrectedAcceptanceBlocked,
    corrected_sha_guard,
    freeze_corrected_adjudication,
    validate_corrected_adjudication,
    verify_frozen_correction_lineage,
)
from archguard.infrastructure.semantic_adjudication_correction import prepare_correction_round
from tests.benchmark.test_semantic_adjudication import frozen as frozen
from tests.benchmark.test_semantic_adjudication_acceptance import COUNTS
from tests.benchmark.test_semantic_adjudication_acceptance import acceptance as acceptance
from tests.benchmark.test_semantic_adjudication_correction import args
from tests.benchmark.test_semantic_adjudication_correction import correction as correction


@pytest.fixture
def corrected(correction):
    f = correction
    # Two valid references make locked evidence ordering observable.
    f["data"]["responses"][2]["evidence"].append(
        {
            "evidence_id": f["data"]["responses"][2]["evidence"][0]["evidence_id"],
            "start_line": 1,
            "end_line": 1,
        }
    )
    f["raw"] = (json.dumps(f["data"], indent=3, ensure_ascii=False) + "\n").encode()
    f["sha"] = hashlib.sha256(f["raw"]).hexdigest()
    f["source"].write_bytes(f["raw"])
    public = prepare_correction_round(
        f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
    )
    f["audit"] = f["public"] / "adjudicator-correction-verification-v1.json"
    f["audit"].write_text(canonical(public) + "\n")
    f["correction_expected"] = {
        "package": public["correction_package_fingerprint"],
        "template": public["template_fingerprint"],
        "audit": public["fingerprint"],
    }
    f["corrected_data"] = copy.deepcopy(f["data"])
    # Explicit synthetic human action, outside the request/acceptance implementation.
    f["corrected_data"]["responses"][0]["blinded_id"] = f["missing"]
    f["corrected"] = f["source"].parent / "completed-response-corrected-v1.json"
    rewrite_corrected(f)
    f["frozen"] = f["source"].parent / "frozen-v1"
    return f


def rewrite_corrected(f):
    raw = (json.dumps(f["corrected_data"], indent=5, ensure_ascii=False) + "\n\n").encode()
    f["corrected"].write_bytes(raw)
    f["corrected"].chmod(0o600)
    f["corrected_raw"] = raw
    f["corrected_sha"] = hashlib.sha256(raw).hexdigest()


def validation_args(f, counts=None):
    return {
        "corrected_sha": f["corrected_sha"],
        "original_sha": f["sha"],
        "package_fp": f["expected"]["package"],
        "expected_correction": f["correction_expected"],
        "expected_counts": COUNTS if counts is None else counts,
    }


def validate(f, counts=None):
    return validate_corrected_adjudication(
        f["corrected"],
        f["source"],
        f["destination"],
        f["audit"],
        f["bundle"],
        **validation_args(f, counts),
    )


def freeze(f):
    return freeze_corrected_adjudication(
        f["corrected"],
        f["source"],
        f["destination"],
        f["audit"],
        f["frozen"],
        f["bundle"],
        lineage={"bundle_fingerprint": f["bundle"].fingerprint},
        **validation_args(f),
    )


def test_corrected_sha_is_checked_before_any_json_parse(corrected, monkeypatch):
    f = corrected
    f["corrected"].write_bytes(b"unapproved, invalid JSON")
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("unapproved human parsed"))
    with pytest.raises(CorrectedAcceptanceBlocked, match="CORRECTED_SHA_MISMATCH"):
        validate(f)
    assert f["source"].read_bytes() == f["raw"]
    assert not f["frozen"].exists()


def test_expected_sha_does_not_make_invalid_json_valid(corrected):
    f = corrected
    f["corrected"].write_bytes(b"not JSON")
    f["corrected_sha"] = hashlib.sha256(b"not JSON").hexdigest()
    with pytest.raises(ValueError):
        validate(f)
    assert not f["frozen"].exists()


@pytest.mark.parametrize("kind", ["wrong_name", "symlink", "parent_symlink"])
def test_corrected_sha_guard_requires_private_canonical_intake(corrected, tmp_path, kind):
    f = corrected
    if kind == "wrong_name":
        path = f["source"]
    elif kind == "symlink":
        f["corrected"].unlink()
        f["corrected"].symlink_to(f["source"])
        path = f["corrected"]
    else:
        parent = tmp_path / "linked/adjudicator-submissions-v1"
        parent.parent.mkdir()
        parent.symlink_to(f["source"].parent, target_is_directory=True)
        path = parent / f["corrected"].name
    with pytest.raises(CorrectedAcceptanceBlocked, match="PREREQUISITE_DRIFT"):
        corrected_sha_guard(path, f["corrected_sha"])


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "slot",
        "bundle",
        "attestation",
        "missing",
        "extra",
        "duplicate",
        "foreign_case",
        "decision",
        "rationale",
        "empty_evidence",
        "foreign_evidence",
        "cross_case_evidence",
        "zero_line",
        "reverse_range",
        "past_eof",
        "float_line",
        "bool_line",
        "extra_field",
    ],
)
def test_corrected_formal_validation_keeps_strict_original_guards(corrected, change):
    f, data = corrected, corrected["corrected_data"]
    row = data["responses"][0]
    if change in {"schema", "slot", "bundle", "attestation"}:
        key = {
            "schema": "schema_version",
            "slot": "reviewer_slot",
            "bundle": "bundle_fingerprint",
            "attestation": "attestation",
        }[change]
        data[key] = "0" * 64
    elif change == "missing":
        data["responses"].pop()
    elif change == "extra":
        data["responses"].append(copy.deepcopy(row))
    elif change == "duplicate":
        data["responses"][1] = copy.deepcopy(row)
    elif change == "foreign_case":
        row["blinded_id"] = f["extra"]
    elif change == "decision":
        row["decision"] = "SUPPORTED"
    elif change == "rationale":
        row["rationale"] = " \n "
    elif change == "empty_evidence":
        row["evidence"] = []
    elif change == "extra_field":
        row["construction_intent"] = "forbidden synthetic hint"
    elif change in {"foreign_evidence", "cross_case_evidence"}:
        row["evidence"][0]["evidence_id"] = (
            "unknown"
            if change == "foreign_evidence"
            else data["responses"][1]["evidence"][0]["evidence_id"]
        )
    else:
        key, value = {
            "zero_line": ("start_line", 0),
            "reverse_range": ("start_line", 3),
            "past_eof": ("end_line", 3),
            "float_line": ("start_line", 1.0),
            "bool_line": ("start_line", True),
        }[change]
        row["evidence"][0][key] = value
    rewrite_corrected(f)
    with pytest.raises(ValueError):
        validate(f)
    assert not f["frozen"].exists()
    assert f["source"].read_bytes() == f["raw"]


def test_corrected_duplicate_json_keys_rejected_after_sha_approval(corrected):
    f = corrected
    raw = f["corrected_raw"].replace(b'"responses":', b'"reviewer_slot":"ADJUDICATOR","responses":')
    f["corrected"].write_bytes(raw)
    f["corrected_sha"] = hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError, match="duplicate adjudicator JSON key"):
        validate(f)


@pytest.mark.parametrize("field", ["package", "template", "audit"])
def test_each_frozen_correction_fingerprint_is_mandatory(corrected, field):
    corrected["correction_expected"][field] = "0" * 64
    with pytest.raises(CorrectedAcceptanceBlocked, match="PREREQUISITE_DRIFT"):
        validate(corrected)
    assert not corrected["frozen"].exists()


@pytest.mark.parametrize(
    "change", ["original", "round_copy", "template", "receipt", "public_audit", "extra_file"]
)
def test_frozen_correction_lineage_drift_never_rebuilt_or_repaired(corrected, change, monkeypatch):
    f = corrected
    path = {
        "original": f["source"],
        "round_copy": f["destination"] / "original-submission-v1.json",
        "template": f["destination"] / "handoff/response-template-corrected-v1.json",
        "receipt": f["destination"] / "correction-round-v1.json",
        "public_audit": f["audit"],
        "extra_file": f["destination"] / "unexpected.json",
    }[change]
    path.write_bytes(b"drift")
    monkeypatch.setattr(
        semantic_adjudication_correction,
        "correction_material",
        lambda *a, **k: pytest.fail("frozen material rebuilt"),
    )
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    with pytest.raises(CorrectedAcceptanceBlocked, match="PREREQUISITE_DRIFT"):
        validate(f)
    assert before == {p: p.read_bytes() for p in before}
    assert not f["frozen"].exists()


@pytest.mark.parametrize(
    "change",
    ["decision", "rationale", "note_value", "note_removed", "absent_note_added", "evidence_order"],
)
def test_unaffected_human_rows_are_locked_field_for_field(corrected, change):
    f, data = corrected, corrected["corrected_data"]
    row = data["responses"][1]
    if change == "decision":
        row["decision"] = "UNCERTAIN"
    elif change == "rationale":
        row["rationale"] += " "
    elif change == "note_value":
        row["note"] += " "
    elif change == "note_removed":
        del row["note"]
    elif change == "absent_note_added":
        data["responses"][3]["note"] = ""
    else:
        data["responses"][2]["evidence"].reverse()
    rewrite_corrected(f)
    with pytest.raises(CorrectedAcceptanceBlocked, match="UNAFFECTED_RESPONSE_DRIFT: changed=1"):
        validate(f)
    assert f["source"].read_bytes() == f["raw"]
    assert not f["frozen"].exists()


def test_matching_identity_is_required_without_external_inference(corrected):
    f = corrected
    f["corrected_data"]["reviewer_identity"] = "Another synthetic self-declared human"
    rewrite_corrected(f)
    with pytest.raises(CorrectedAcceptanceBlocked, match="SELF_DECLARED_IDENTITY_DRIFT"):
        validate(f)


@pytest.mark.parametrize("category", ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"])
def test_affected_human_answer_may_change_without_semantic_inference(corrected, category):
    f = corrected
    row = f["corrected_data"]["responses"][0]
    row.update(decision=category, rationale="New synthetic human explanation.", note="Own note.")
    row["evidence"][0]["start_line"] = 2
    counts = {"POSITIVE": 0, "NEGATIVE": 3, "UNCERTAIN": 0, "OUT_OF_SCOPE": 0}
    counts[category] += 1
    rewrite_corrected(f)
    raw, submission, observed, scope, _ = validate(f, counts)
    assert raw == f["corrected_raw"]
    assert submission.responses[0].decision == category
    assert observed == counts
    assert scope == {
        "locked_unaffected_responses": 3,
        "unaffected_responses_changed": 0,
        "corrected_affected_responses": 1,
        "affected_responses_changed": 1,
    }


def test_corrected_counts_are_measured_and_never_forced(corrected):
    f = corrected
    f["corrected_data"]["responses"][0]["decision"] = "OUT_OF_SCOPE"
    rewrite_corrected(f)
    before = f["corrected"].read_bytes()
    with pytest.raises(SubmissionMismatch, match="COUNTS_MISMATCH"):
        validate(f)
    assert f["corrected"].read_bytes() == before
    assert not f["frozen"].exists()


def test_unknown_original_id_is_not_automatically_mapped_on_acceptance(corrected):
    f = corrected
    f["corrected_data"]["responses"][0]["blinded_id"] = f["extra"]
    rewrite_corrected(f)
    before = f["corrected"].read_bytes()
    with pytest.raises(SubmissionMismatch, match="MEMBERSHIP_EVIDENCE_MISMATCH"):
        freeze(f)
    assert f["corrected"].read_bytes() == before
    assert not f["frozen"].exists()


def test_frozen_lineage_reads_existing_template_without_answer_generation(corrected, monkeypatch):
    f = corrected
    monkeypatch.setattr(
        semantic_adjudication_correction,
        "correction_material",
        lambda *a, **k: pytest.fail("answers or correction material generated"),
    )
    original, template, receipt = verify_frozen_correction_lineage(
        f["source"],
        f["destination"],
        f["audit"],
        f["bundle"],
        original_sha=f["sha"],
        package_fp=f["expected"]["package"],
        expected=f["correction_expected"],
    )
    assert original == f["data"]
    assert receipt["adjudicator_accepted"] is False
    assert sum(r["decision"] is None for r in template["responses"]) == 1
    assert not f["frozen"].exists()


def test_corrected_raw_snapshot_is_append_only_private_and_source_free(corrected, monkeypatch):
    f = corrected
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("provider/network forbidden"))
    monkeypatch.setattr(
        semantic_adjudication_correction,
        "correction_material",
        lambda *a, **k: pytest.fail("correction material rebuilt"),
    )
    receipt = freeze(f)
    assert before == {p: p.read_bytes() for p in before}
    assert f["frozen"].stat().st_mode & 0o777 == 0o700
    snapshot = f["frozen"] / "submission-v1.json"
    receipt_path = f["frozen"] / "submission-freeze-v1.json"
    assert {p.name for p in f["frozen"].iterdir()} == {snapshot.name, receipt_path.name}
    assert snapshot.read_bytes() == f["corrected_raw"] != f["raw"]
    assert snapshot.stat().st_mode & 0o777 == receipt_path.stat().st_mode & 0o777 == 0o600
    assert json.loads(verify_opaque_seal(receipt_path, receipt["fingerprint"])) == receipt
    assert receipt["submission_sha256"] == f["corrected_sha"]
    assert receipt["lineage"]["original_attempt_sha256"] == f["sha"]
    assert receipt["accepted_input"] == "CORRECTED_HUMAN_SUBMISSION"
    assert receipt["no_automatic_remapping"] is True
    assert receipt["human_content_modified"] is False
    assert receipt["snapshot_byte_identical"] is True
    assert receipt["status"] == "ADJUDICATOR_FROZEN"
    assert receipt["next_state"] == "READY_FOR_FINAL_HUMAN_GROUND_TRUTH_FREEZE"
    assert receipt["ground_truth_status"] == "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN"
    assert receipt["final_ground_truth_materialized"] is False
    assert receipt["live_ai_calls"] == 0
    assert receipt["semantic_correctness_assessed"] is False
    assert receipt["A_B_human_payloads_decoded"] is False
    assert receipt["construction_intent_compared"] is False
    public_bytes = canonical(receipt)
    assert f["data"]["reviewer_identity"] not in public_bytes
    for row in f["corrected_data"]["responses"]:
        assert row["blinded_id"] not in public_bytes
        assert row["rationale"] not in public_bytes
        for reference in row["evidence"]:
            assert reference["evidence_id"] not in public_bytes
    assert receipt["fingerprint"] == digest(
        {k: v for k, v in receipt.items() if k != "fingerprint"}
    )
    with pytest.raises(ValueError, match="cannot overwrite"):
        freeze(f)
    assert snapshot.read_bytes() == f["corrected_raw"]
