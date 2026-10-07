"""Synthetic recovery, formal acceptance, and private byte-preservation regressions."""

import hashlib
import json
import socket
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure.semantic_adjudication import (
    freeze_adjudicator_handoff,
    verify_adjudicator_handoff,
)
from archguard.infrastructure.semantic_adjudication_acceptance import (
    HandoffRecoveryBlocked,
    SubmissionMismatch,
    freeze_completed_adjudication,
    recover_exact_blank,
    validate_completed_adjudication,
    verify_adjudicator_prerequisites,
    verify_opaque_seal,
    verify_primary_integrity,
    verify_recoverable_handoff,
)
from tests.benchmark.test_semantic_adjudication import (
    frozen as frozen,
)
from tests.benchmark.test_semantic_adjudication import (
    material,
    sealed,
    synthetic_response,
)

COUNTS = {"POSITIVE": 1, "NEGATIVE": 3, "UNCERTAIN": 0, "OUT_OF_SCOPE": 0}


@pytest.fixture
def acceptance(frozen, tmp_path):
    public, private = tmp_path / "public", tmp_path / "private"
    handoff, coordinator = (
        private / "adjudicator-handoff-v1",
        private / "adjudicator-coordinator-v1",
    )
    bundle, mapping, contents = material(frozen)
    receipt = freeze_adjudicator_handoff(handoff, coordinator, bundle, mapping, contents)
    for key, base, name in (
        ("conflicts", private, "conflict-manifest-v1.json"),
        ("index", private, "adjudicator-safe-index-v1.json"),
        ("analysis", public, "agreement-analysis-v1.json"),
        ("receipt", public, "agreement-verification-v1.json"),
    ):
        destination = base / "inter-reviewer-agreement-v1" / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(frozen["paths"][key].read_bytes() + b"\n")
    expected = {
        **{k: v for k, v in frozen["expected"].items() if k != "receipt"},
        "c_receipt": frozen["expected"]["receipt"],
        "package": receipt["fingerprint"],
        "blank": hashlib.sha256(contents["response-template.json"]).hexdigest(),
        "mapping": mapping["fingerprint"],
        "bundle": bundle.fingerprint,
    }
    report = sealed(
        {
            "conflict_manifest_fingerprint": expected["conflicts"],
            "safe_index_fingerprint": expected["index"],
            "agreement_analysis_fingerprint": expected["analysis"],
            "package_fingerprint": expected["package"],
            "blank_template_fingerprint": expected["blank"],
            "private_mapping_fingerprint": expected["mapping"],
            "bundle_fingerprint": bundle.fingerprint,
            "package_case_count": 4,
            "final_ground_truth_materialized": False,
        }
    )
    expected["d_receipt"] = report["fingerprint"]
    (public / "adjudicator-handoff-verification-v1.json").write_text(canonical(report) + "\n")
    source = private / "adjudicator-submissions-v1/completed-response.json"
    source.parent.mkdir(mode=0o700)
    data = synthetic_response(bundle, "NEGATIVE")
    data["responses"][0]["decision"] = "POSITIVE"
    raw = (json.dumps(data, indent=3) + "\n").encode()
    source.write_bytes(raw)
    source.chmod(0o600)
    return {
        "public": public,
        "private": private,
        "handoff": handoff,
        "coordinator": coordinator,
        "bundle": bundle,
        "mapping": mapping,
        "contents": contents,
        "receipt": receipt,
        "expected": expected,
        "source": source,
        "raw": raw,
        "data": data,
        "sha": hashlib.sha256(raw).hexdigest(),
    }


def prerequisites(f):
    return verify_adjudicator_prerequisites(f["public"], f["private"], f["expected"])


def validate(f, sha=None, counts=COUNTS):
    return validate_completed_adjudication(
        f["source"], f["bundle"], expected_sha=sha or f["sha"], expected_counts=counts
    )


def replace_human(f):
    raw = json.dumps(f["data"]).encode()
    f["source"].write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def drift(f):
    (f["handoff"] / "response-template.json").unlink()
    (f["handoff"] / "completed-response.json").write_bytes(f["raw"])


def recover(f, candidate=None):
    recover_exact_blank(
        f["source"],
        f["handoff"],
        f["contents"]["response-template.json"] if candidate is None else candidate,
        source_sha=f["sha"],
        package_fp=f["expected"]["package"],
        blank_sha=f["expected"]["blank"],
    )


@pytest.mark.parametrize("change", ["missing", "replaced", "extra_completed"])
def test_blank_or_inventory_drift_blocks_acceptance(acceptance, change):
    f = acceptance
    assert prerequisites(f)[0] == f["bundle"]
    blank = f["handoff"] / "response-template.json"
    if change == "missing":
        blank.unlink()
    elif change == "replaced":
        blank.write_bytes(f["raw"])
    else:
        (f["handoff"] / "completed-response.json").write_bytes(f["raw"])
    with pytest.raises(ValueError):
        prerequisites(f)
    assert not (f["source"].parent / "frozen-v1").exists()


def test_exact_recovery_preserves_human_and_all_other_scientific_bytes(acceptance, monkeypatch):
    f = acceptance
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    drift(f)
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    recover(f)
    assert f["source"].read_bytes() == f["raw"]
    assert before == {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    verify_adjudicator_handoff(
        f["handoff"], f["coordinator"], f["mapping"], f["contents"], f["receipt"]
    )
    assert prerequisites(f)[0] == f["bundle"]
    assert validate(f)[2] == COUNTS


@pytest.mark.parametrize("candidate", ["equivalent_json", "changed_blank", "human_bytes"])
def test_only_exact_blank_sha_is_accepted(acceptance, candidate):
    f = acceptance
    drift(f)
    body = f["contents"]["response-template.json"]
    if candidate == "equivalent_json":
        body = json.dumps(json.loads(body), sort_keys=True).encode()
        assert json.loads(body) == json.loads(f["contents"]["response-template.json"])
    elif candidate == "changed_blank":
        body += b"\n"
    else:
        body = f["raw"]
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    with pytest.raises(HandoffRecoveryBlocked, match="TEMPLATE_UNRECOVERABLE"):
        recover(f, body)
    assert before == {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}


def test_divergent_duplicate_blocks_without_deletion_or_rewrite(acceptance):
    f = acceptance
    drift(f)
    duplicate = f["handoff"] / "completed-response.json"
    duplicate.write_bytes(f["raw"] + b"\n")
    with pytest.raises(HandoffRecoveryBlocked, match="HUMAN_FILE_DIVERGENCE"):
        recover(f)
    assert duplicate.read_bytes() == f["raw"] + b"\n"
    assert f["source"].read_bytes() == f["raw"]
    assert not (f["handoff"] / "response-template.json").exists()


@pytest.mark.parametrize("name", ["README.txt", "bundle-v1.json", "unexpected.json"])
def test_unrelated_handoff_drift_cannot_be_repaired(acceptance, name):
    f = acceptance
    drift(f)
    (f["handoff"] / name).write_bytes(b"synthetic drift")
    with pytest.raises(HandoffRecoveryBlocked, match="HANDOFF_DRIFT"):
        recover(f)
    assert (f["handoff"] / "completed-response.json").read_bytes() == f["raw"]
    assert not (f["handoff"] / "response-template.json").exists()


def test_canonical_source_sha_checked_before_recovery_and_json_parse(acceptance, monkeypatch):
    f = acceptance
    drift(f)
    f["source"].write_bytes(b"not JSON")
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("unapproved bytes parsed"))
    with pytest.raises(SubmissionMismatch, match="SUBMITTED_SHA256_MISMATCH"):
        validate(f)
    with pytest.raises(HandoffRecoveryBlocked, match="HUMAN_FILE_DIVERGENCE"):
        recover(f)


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "slot",
        "bundle",
        "identity",
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
def test_formal_validation_rejects_malformed_human_inputs(acceptance, change):
    f, data = acceptance, acceptance["data"]
    row = data["responses"][0]
    if change in {"schema", "slot", "bundle", "identity", "attestation"}:
        field = {
            "schema": "schema_version",
            "slot": "reviewer_slot",
            "bundle": "bundle_fingerprint",
            "identity": "reviewer_identity",
            "attestation": "attestation",
        }[change]
        data[field] = " " if change == "identity" else "0" * 64
    elif change == "missing":
        data["responses"].pop()
    elif change == "extra":
        data["responses"].append(dict(row))
    elif change == "duplicate":
        data["responses"][1] = dict(row)
    elif change == "foreign_case":
        row["blinded_id"] = "adj-" + "f" * 32
    elif change == "decision":
        row["decision"] = "SUPPORTED"
    elif change == "rationale":
        row["rationale"] = "   "
    elif change == "empty_evidence":
        row["evidence"] = []
    elif change == "extra_field":
        row["construction_intent"] = "synthetic forbidden field"
    elif change in {"foreign_evidence", "cross_case_evidence"}:
        row["evidence"][0]["evidence_id"] = (
            "foreign"
            if change == "foreign_evidence"
            else data["responses"][1]["evidence"][0]["evidence_id"]
        )
    else:
        field, value = {
            "zero_line": ("start_line", 0),
            "reverse_range": ("start_line", 3),
            "past_eof": ("end_line", 3),
            "float_line": ("start_line", 1.0),
            "bool_line": ("start_line", True),
        }[change]
        row["evidence"][0][field] = value
    with pytest.raises(ValueError):
        validate(f, replace_human(f))
    assert not (f["source"].parent / "frozen-v1").exists()


def test_duplicate_json_keys_rejected_even_with_approved_raw_sha(acceptance):
    f = acceptance
    raw = f["raw"].replace(b"{", b'{"reviewer_slot":"ADJUDICATOR",', 1)
    f["source"].write_bytes(raw)
    with pytest.raises(ValueError, match="duplicate adjudicator JSON key"):
        validate(f, hashlib.sha256(raw).hexdigest())


def test_counts_are_checked_never_forced(acceptance):
    f = acceptance
    f["data"]["responses"][0]["decision"] = "NEGATIVE"
    before = replace_human(f)
    with pytest.raises(SubmissionMismatch, match="COUNTS_MISMATCH"):
        validate(f, before)
    assert hashlib.sha256(f["source"].read_bytes()).hexdigest() == before


def test_foreign_human_case_blocks_freeze_with_only_aggregate_diagnostics(acceptance):
    f = acceptance
    foreign = "adj-" + "f" * 32
    f["data"]["responses"][0]["blinded_id"] = foreign
    sha = replace_human(f)
    destination = f["source"].parent / "frozen-v1"
    with pytest.raises(SubmissionMismatch) as caught:
        freeze_completed_adjudication(
            f["source"],
            destination,
            f["bundle"],
            expected_sha=sha,
            expected_counts=COUNTS,
            lineage={},
        )
    message = str(caught.value)
    diagnostics = json.loads(message.split(": ", 1)[1])
    assert diagnostics == {
        "missing_cases": 1,
        "extra_cases": 1,
        "invalid_evidence_ids": 1,
        "invalid_line_ranges": 0,
    }
    assert foreign not in message
    assert f["data"]["reviewer_identity"] not in message
    assert not destination.exists()
    assert hashlib.sha256(f["source"].read_bytes()).hexdigest() == sha


@pytest.mark.parametrize("category", ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"])
def test_all_four_categories_preserved_without_primary_comparison(acceptance, category):
    f = acceptance
    for row in f["data"]["responses"]:
        row["decision"] = category
    counts = {name: 4 if name == category else 0 for name in COUNTS}
    assert validate(f, replace_human(f), counts)[2] == counts


def test_immutable_exact_raw_snapshot_source_free_receipt_and_no_truth(acceptance, monkeypatch):
    f = acceptance
    _, lineage = prerequisites(f)
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    destination = f["source"].parent / "frozen-v1"
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("network forbidden"))
    receipt = freeze_completed_adjudication(
        f["source"],
        destination,
        f["bundle"],
        expected_sha=f["sha"],
        expected_counts=COUNTS,
        lineage=lineage,
    )
    assert (destination / "submission-v1.json").read_bytes() == f["raw"]
    assert before == {p: p.read_bytes() for p in before}
    assert receipt["submission_fingerprint"] == digest(validate(f)[1])
    assert receipt["fingerprint"] == digest(
        {k: v for k, v in receipt.items() if k != "fingerprint"}
    )
    assert receipt["decision_counts"] == COUNTS
    assert receipt["final_ground_truth_materialized"] is False
    assert receipt["A_B_human_payloads_decoded"] is False
    assert receipt["construction_intent_compared"] is False
    assert receipt["semantic_correctness_assessed"] is False
    assert receipt["live_ai_calls"] == 0
    assert receipt["ground_truth_status"] == "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN"
    assert {p.name for p in destination.iterdir()} == {
        "submission-v1.json",
        "submission-freeze-v1.json",
    }
    assert destination.stat().st_mode & 0o777 == 0o700
    for path in destination.iterdir():
        assert path.stat().st_mode & 0o777 == 0o600
    assert f["data"]["reviewer_identity"] not in canonical(receipt)
    for row in f["data"]["responses"]:
        assert row["blinded_id"] not in canonical(receipt)
        assert row["rationale"] not in canonical(receipt)
        assert row["evidence"][0]["evidence_id"] not in canonical(receipt)
    with pytest.raises(ValueError, match="cannot overwrite"):
        freeze_completed_adjudication(
            f["source"],
            destination,
            f["bundle"],
            expected_sha=f["sha"],
            expected_counts=COUNTS,
            lineage=lineage,
        )


def test_receipt_rejects_private_lineage_or_values(acceptance):
    f = acceptance
    for lineage in ({"reviewer_identity": "f" * 64}, {"bundle_fingerprint": "private identity"}):
        with pytest.raises(ValueError, match="source-free"):
            freeze_completed_adjudication(
                f["source"],
                f["source"].parent / "frozen-v1",
                f["bundle"],
                expected_sha=f["sha"],
                expected_counts=COUNTS,
                lineage=lineage,
            )


def test_primary_judgments_and_private_conflicts_are_never_decoded(
    acceptance, tmp_path, monkeypatch
):
    f = acceptance
    primary = tmp_path / "primary"
    primary.mkdir()
    raw = b"SYNTHETIC_OPAQUE_HUMAN_NOT_JSON"
    (primary / "submission-v1.json").write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    receipt = sealed({"submission_sha256": sha, "final_ground_truth": False})
    (primary / "submission-freeze-v1.json").write_text(canonical(receipt) + "\n")
    loads = json.loads

    def guarded(data, *args, **kwargs):
        encoded = data.encode() if isinstance(data, str) else data
        assert b"SYNTHETIC_OPAQUE_HUMAN" not in encoded
        assert b'"a_decision"' not in encoded and b'"b_decision"' not in encoded
        return loads(data, *args, **kwargs)

    monkeypatch.setattr(json, "loads", guarded)
    verify_primary_integrity(primary, source_sha=sha, receipt_fp=receipt["fingerprint"])
    assert prerequisites(f)[0] == f["bundle"]
    assert validate(f)[2] == COUNTS
    (primary / "submission-v1.json").write_bytes(raw + b" ")
    with pytest.raises(ValueError, match="snapshot changed"):
        verify_primary_integrity(primary, source_sha=sha, receipt_fp=receipt["fingerprint"])


@pytest.mark.parametrize(
    "key",
    [
        "conflicts",
        "index",
        "analysis",
        "c_receipt",
        "d_receipt",
        "package",
        "blank",
        "mapping",
        "bundle",
    ],
)
def test_all_frozen_fingerprints_are_mandatory(acceptance, key):
    f = acceptance
    f["expected"][key] = "0" * 64
    with pytest.raises(ValueError):
        prerequisites(f)


def test_opaque_seal_rejects_byte_drift_and_symlinks(tmp_path):
    data = sealed({"schema_version": "synthetic", "private_judgment": "CANARY"})
    path = tmp_path / "opaque.json"
    raw = (canonical(data) + "\n").encode()
    path.write_bytes(raw)
    assert verify_opaque_seal(path, data["fingerprint"]) == raw
    path.write_bytes(raw + b"\n")
    with pytest.raises(ValueError):
        verify_opaque_seal(path, data["fingerprint"])
    target = tmp_path / "target"
    target.write_bytes(raw)
    path.unlink()
    path.symlink_to(target)
    with pytest.raises(ValueError, match="symlink"):
        verify_opaque_seal(path, data["fingerprint"])


def test_symlinked_human_and_extra_coordinator_file_block(acceptance, tmp_path):
    f = acceptance
    (f["coordinator"] / "unexpected.json").write_text("{}")
    with pytest.raises(ValueError, match="inventory"):
        prerequisites(f)
    target = tmp_path / "human"
    target.write_bytes(f["raw"])
    f["source"].unlink()
    f["source"].symlink_to(target)
    with pytest.raises(ValueError, match="intake"):
        validate(f)


def test_recovery_guard_does_not_parse_human_content(acceptance, monkeypatch):
    f = acceptance
    drift(f)
    loads = json.loads

    def guarded(data, *args, **kwargs):
        encoded = data.encode() if isinstance(data, str) else data
        assert b"reviewer_identity" not in encoded
        return loads(data, *args, **kwargs)

    monkeypatch.setattr(json, "loads", guarded)
    assert (
        verify_recoverable_handoff(
            f["source"],
            f["handoff"],
            source_sha=f["sha"],
            package_fp=f["expected"]["package"],
            blank_sha=f["expected"]["blank"],
        )
        == f["raw"]
    )
    recover(f)


def test_cli_paths_do_not_import_provider_or_truth_execution():
    root = Path(__file__).resolve().parents[2]
    for name in ("scripts/prompt015e_acceptance.py", "scripts/prompt015e1_recover_handoff.py"):
        text = (root / name).read_text()
        for forbidden in (
            "requests.",
            "httpx.",
            "openai.",
            "verify_frozen_review(",
            "build_agreement_artifacts(",
            "construct_holdout(",
        ):
            assert forbidden not in text
