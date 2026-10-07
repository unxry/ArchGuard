"""Formal byte-preserving acceptance; primary judgments remain opaque."""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_adjudication import (
    AdjudicatorBundle,
    AdjudicatorSubmission,
    SafeConflictIndex,
    validate_adjudication_response,
)
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory

CATEGORIES = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
HANDOFF_FILES = {
    "bundle-v1.json",
    "rule-guidance-v1.json",
    "index.html",
    "README.txt",
    "response-template.json",
    "submission-schema.json",
}
LINEAGE_FIELDS = {
    "conflicts_fingerprint",
    "index_fingerprint",
    "analysis_fingerprint",
    "c_receipt_fingerprint",
    "package_fingerprint",
    "blank_fingerprint",
    "mapping_fingerprint",
    "d_receipt_fingerprint",
    "bundle_fingerprint",
    "p015_commit",
    "C_closure_commit",
    "D_closure_commit",
    "sample_freeze_fingerprint",
    "corpus_fingerprint",
    "sample_fingerprint",
    "A_receipt_fingerprint",
    "B_receipt_fingerprint",
    "original_attempt_sha256",
    "correction_package_fingerprint",
    "correction_template_fingerprint",
    "correction_audit_fingerprint",
}


class SubmissionMismatch(ValueError):
    """Only source-free SHA/count diagnostics may cross the CLI error boundary."""


class HandoffRecoveryBlocked(ValueError):
    """Safe recovery stop code, without human or source content."""


def verify_recoverable_handoff(
    response_path: Path,
    handoff: Path,
    *,
    source_sha: str,
    package_fp: str,
    blank_sha: str,
) -> bytes:
    """Allow only the missing blank plus an exact duplicate of the approved human file."""
    drift = "PROMPT_015_E_1_BLOCKED_HANDOFF_DRIFT"
    if (
        response_path.is_symlink()
        or response_path.parent.is_symlink()
        or handoff.is_symlink()
        or response_path.name != "completed-response.json"
        or response_path.parent.name != "adjudicator-submissions-v1"
    ):
        raise HandoffRecoveryBlocked(drift)
    raw = response_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source_sha:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HUMAN_FILE_DIVERGENCE")
    duplicate = handoff / "completed-response.json"
    if duplicate.is_symlink():
        raise HandoffRecoveryBlocked(drift)
    if duplicate.read_bytes() != raw:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HUMAN_FILE_DIVERGENCE")
    receipt = json.loads(verify_opaque_seal(handoff / "handoff-freeze.json", package_fp))
    if (
        set(receipt["files"]) != HANDOFF_FILES
        or receipt["files"]["response-template.json"] != blank_sha
        or {p.name for p in handoff.iterdir()}
        != (HANDOFF_FILES - {"response-template.json"}) | {"handoff-freeze.json", duplicate.name}
    ):
        raise HandoffRecoveryBlocked(drift)
    for name, sha in receipt["files"].items():
        if name == "response-template.json":
            continue
        path = handoff / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise HandoffRecoveryBlocked(drift)
    return raw


def recover_exact_blank(
    response_path: Path,
    handoff: Path,
    candidate: bytes,
    *,
    source_sha: str,
    package_fp: str,
    blank_sha: str,
) -> None:
    """Restore only approved blank bytes; remove only the proven duplicate."""
    raw = verify_recoverable_handoff(
        response_path, handoff, source_sha=source_sha, package_fp=package_fp, blank_sha=blank_sha
    )
    if hashlib.sha256(candidate).hexdigest() != blank_sha:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_TEMPLATE_UNRECOVERABLE")
    with (handoff / "response-template.json").open("xb") as stream:
        stream.write(candidate)
    duplicate = handoff / "completed-response.json"
    if response_path.read_bytes() != raw or duplicate.read_bytes() != raw:
        raise HandoffRecoveryBlocked("PROMPT_015_E_1_BLOCKED_HUMAN_FILE_DIVERGENCE")
    duplicate.unlink()


def verify_opaque_seal(path: Path, fingerprint: str) -> bytes:
    """Check frozen canonical writer bytes without decoding private human values."""
    if path.is_symlink():
        raise ValueError("symlinked frozen artifact forbidden")
    raw = path.read_bytes()
    field = b'"fingerprint":"' + fingerprint.encode("ascii") + b'"'
    if not raw.endswith(b"\n") or raw.count(field) != 1:
        raise ValueError("frozen canonical artifact/seal changed")
    if raw.startswith(b"{" + field + b","):
        payload = b"{" + raw[len(field) + 2 : -1]
    else:
        payload = raw[:-1].replace(b"," + field, b"", 1)
    if hashlib.sha256(payload).hexdigest() != fingerprint:
        raise ValueError("approved frozen artifact fingerprint mismatch")
    return raw


def verify_primary_integrity(root: Path, *, source_sha: str, receipt_fp: str) -> None:
    """Opaque snapshot SHA plus source-free receipt; never parse primary responses."""
    snapshot = root / "submission-v1.json"
    if root.is_symlink() or snapshot.is_symlink():
        raise ValueError("primary freeze cannot be symlinked")
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != source_sha:
        raise ValueError("primary frozen snapshot changed")
    receipt = json.loads(verify_opaque_seal(root / "submission-freeze-v1.json", receipt_fp))
    if receipt["submission_sha256"] != source_sha or receipt["final_ground_truth"] is not False:
        raise ValueError("primary source-free receipt binding changed")


def verify_adjudicator_prerequisites(
    public: Path,
    private: Path,
    expected: dict[str, str],
) -> tuple[AdjudicatorBundle, dict[str, str]]:
    c_private = private / "inter-reviewer-agreement-v1"
    c_public = public / "inter-reviewer-agreement-v1"
    # The private C judgments are integrity-checked, never JSON-decoded.
    verify_opaque_seal(c_private / "conflict-manifest-v1.json", expected["conflicts"])
    index = SafeConflictIndex.model_validate_json(
        verify_opaque_seal(c_private / "adjudicator-safe-index-v1.json", expected["index"])
    )
    analysis = json.loads(
        verify_opaque_seal(c_public / "agreement-analysis-v1.json", expected["analysis"])
    )
    c_receipt = json.loads(
        verify_opaque_seal(c_public / "agreement-verification-v1.json", expected["c_receipt"])
    )
    if (
        analysis["primary"]["n"] != 100
        or analysis["primary"]["exact_agreement"] != 96
        or analysis["primary"]["disagreement"] != 4
        or c_receipt["paired_cases"] != 100
        or c_receipt["conflict_count"] != 4
        or c_receipt["conflict_manifest_fingerprint"] != expected["conflicts"]
        or c_receipt["adjudicator_safe_index_fingerprint"] != expected["index"]
        or c_receipt["agreement_analysis_fingerprint"] != expected["analysis"]
        or c_receipt["final_ground_truth_materialized"] is not False
    ):
        raise ValueError("approved C count/lineage/truth state changed")
    d_report = json.loads(
        verify_opaque_seal(
            public / "adjudicator-handoff-verification-v1.json", expected["d_receipt"]
        )
    )
    for field, key in (
        ("conflict_manifest_fingerprint", "conflicts"),
        ("safe_index_fingerprint", "index"),
        ("agreement_analysis_fingerprint", "analysis"),
        ("package_fingerprint", "package"),
        ("blank_template_fingerprint", "blank"),
        ("private_mapping_fingerprint", "mapping"),
        ("bundle_fingerprint", "bundle"),
    ):
        if d_report[field] != expected[key]:
            raise ValueError("approved D lineage changed")
    if (
        d_report["package_case_count"] != 4
        or d_report["final_ground_truth_materialized"] is not False
    ):
        raise ValueError("approved D scope changed")
    handoff = private / "adjudicator-handoff-v1"
    receipt = json.loads(verify_opaque_seal(handoff / "handoff-freeze.json", expected["package"]))
    if receipt["bundle_fingerprint"] != expected["bundle"] or receipt["case_count"] != 4:
        raise ValueError("frozen bundle/package binding mismatch")
    if (
        handoff.is_symlink()
        or set(receipt["files"]) != HANDOFF_FILES
        or {p.name for p in handoff.iterdir()} != {*HANDOFF_FILES, "handoff-freeze.json"}
    ):
        raise ValueError("frozen D package inventory changed")
    for name, sha in receipt["files"].items():
        path = handoff / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("frozen D handoff file changed")
    if receipt["files"]["response-template.json"] != expected["blank"]:
        raise ValueError("approved blank template changed")
    bundle = AdjudicatorBundle.model_validate_json((handoff / "bundle-v1.json").read_bytes())
    if (
        bundle.fingerprint != expected["bundle"]
        or json.loads((handoff / "submission-schema.json").read_bytes())
        != AdjudicatorSubmission.model_json_schema()
    ):
        raise ValueError("frozen adjudicator response contract changed")
    mapping = json.loads(
        verify_opaque_seal(
            private / "adjudicator-coordinator-v1/adjudicator-mapping-v1.json", expected["mapping"]
        )
    )
    coordinator = private / "adjudicator-coordinator-v1"
    if coordinator.is_symlink() or {p.name for p in coordinator.iterdir()} != {
        "adjudicator-mapping-v1.json"
    }:
        raise ValueError("private adjudicator coordinator inventory changed")
    rows = mapping["rows"]
    if (
        mapping["bundle_fingerprint"] != bundle.fingerprint
        or mapping["safe_index_fingerprint"] != index.fingerprint
        or len(rows) != 4
        or len({r["adjudicator_blinded_id"] for r in rows}) != 4
        or {r["adjudicator_blinded_id"] for r in rows} != {p.blinded_id for p in bundle.packets}
        or {(r["case_id"], r["conflict_id"]) for r in rows}
        != {(c.case_id, c.conflict_id) for c in index.cases}
        or {r["adjudicator_blinded_id"]: r["adjudicator_packet_fingerprint"] for r in rows}
        != {p.blinded_id: p.fingerprint for p in bundle.packets}
    ):
        raise ValueError("private four-case adjudicator mapping changed")
    return bundle, {key + "_fingerprint": value for key, value in expected.items()}


def validate_completed_adjudication(
    response_path: Path,
    bundle: AdjudicatorBundle,
    *,
    expected_sha: str,
    expected_counts: dict[str, int] | None,
    corrected: bool = False,
) -> tuple[bytes, AdjudicatorSubmission, dict[str, int]]:
    if (
        response_path.name
        != ("completed-response-corrected-v1.json" if corrected else "completed-response.json")
        or response_path.parent.name != "adjudicator-submissions-v1"
        or response_path.is_symlink()
        or response_path.parent.is_symlink()
    ):
        raise ValueError("private adjudicator intake path required")
    raw = response_path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != expected_sha:
        raise SubmissionMismatch("SUBMITTED_SHA256_MISMATCH: " + actual_sha)

    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate adjudicator JSON key")
            result[key] = value
        return result

    submission = AdjudicatorSubmission.model_validate(
        json.loads(raw, object_pairs_hook=unique_object)
    )
    packets = {p.blinded_id: p for p in bundle.packets}
    actual_ids = {r.blinded_id for r in submission.responses}
    invalid_ids = invalid_ranges = 0
    for response in submission.responses:
        packet = packets.get(response.blinded_id)
        evidence = {} if packet is None else {e.evidence_id: e for e in packet.evidence}
        for ref in response.evidence:
            source = evidence.get(ref.evidence_id)
            if source is None:
                invalid_ids += 1
            elif ref.end_line > len(source.text.splitlines()):
                invalid_ranges += 1
    diagnostics = {
        "missing_cases": len(set(packets) - actual_ids),
        "extra_cases": len(actual_ids - set(packets)),
        "invalid_evidence_ids": invalid_ids,
        "invalid_line_ranges": invalid_ranges,
    }
    if any(diagnostics.values()):
        raise SubmissionMismatch(
            "ADJUDICATOR_MEMBERSHIP_EVIDENCE_MISMATCH: " + json.dumps(diagnostics, sort_keys=True)
        )
    validate_adjudication_response(bundle, submission)
    counts = {
        category: sum(r.decision == category for r in submission.responses)
        for category in CATEGORIES
    }
    if expected_counts is not None and counts != expected_counts:
        raise SubmissionMismatch(
            "ADJUDICATOR_COUNTS_MISMATCH: " + json.dumps(counts, sort_keys=True)
        )
    return raw, submission, counts


def freeze_completed_adjudication(
    response_path: Path,
    destination: Path,
    bundle: AdjudicatorBundle,
    *,
    expected_sha: str,
    expected_counts: dict[str, int],
    lineage: dict[str, str],
    corrected: bool = False,
    correction_scope: dict[str, int] | None = None,
) -> dict[str, Any]:
    if destination.exists() or destination.is_symlink():
        raise ValueError("adjudicator acceptance is immutable; cannot overwrite")
    if destination != response_path.parent / "frozen-v1":
        raise ValueError("private adjudicator frozen-v1 destination required")
    if set(lineage) - LINEAGE_FIELDS or any(
        not re.fullmatch(r"[a-f0-9]{40}|[a-f0-9]{64}", value) for value in lineage.values()
    ):
        raise ValueError("only source-free approved fingerprint/commit lineage allowed")
    if corrected and (
        correction_scope
        != {
            "locked_unaffected_responses": 3,
            "unaffected_responses_changed": 0,
            "corrected_affected_responses": 1,
            "affected_responses_changed": 1,
        }
        or not {
            "original_attempt_sha256",
            "correction_package_fingerprint",
            "correction_template_fingerprint",
            "correction_audit_fingerprint",
        }
        <= set(lineage)
    ):
        raise ValueError("verified correction scope and lineage required")
    raw, submission, counts = validate_completed_adjudication(
        response_path,
        bundle,
        expected_sha=expected_sha,
        expected_counts=expected_counts,
        corrected=corrected,
    )
    receipt = {
        "schema_version": "independent-adjudicator-submission-freeze-v1",
        "status": "ADJUDICATOR_FROZEN",
        "next_state": "READY_FOR_FINAL_HUMAN_GROUND_TRUTH_FREEZE",
        "ground_truth_status": "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN",
        "submission_sha256": expected_sha,
        "submission_fingerprint": digest(submission),
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_slot": "ADJUDICATOR",
        "responses": 4,
        "unique_adjudicator_ids": 4,
        "decision_counts": counts,
        "schema_validation": "PASS",
        "attestation_validation": "PASS",
        "membership_validation": "PASS",
        "bundle_binding_validation": "PASS",
        "evidence_validation": "PASS",
        "missing_cases": 0,
        "extra_cases": 0,
        "duplicate_ids": 0,
        "invalid_evidence_ids": 0,
        "invalid_line_ranges": 0,
        "human_content_modified": False,
        "snapshot_byte_identical": True,
        "identity_verification": "SELF_DECLARED_ONLY; no external verification",
        "procedural_separation": "SEPARATE_BLINDED_HANDOFF_AND_PRIVATE_INTAKE",
        "reviewer_A_status": "FROZEN",
        "reviewer_B_status": "FROZEN",
        "agreement_conflict_status": "FROZEN",
        "A_B_human_payloads_decoded": False,
        "construction_intent_compared": False,
        "semantic_correctness_assessed": False,
        "final_ground_truth_materialized": False,
        "live_ai_calls": 0,
        "lineage": lineage,
    }
    if corrected:
        receipt.update(
            accepted_input="CORRECTED_HUMAN_SUBMISSION",
            correction_lineage_validation="PASS",
            correction_scope=correction_scope,
            original_rejected_attempt_preserved=True,
            same_identity_verification="MATCHING_SELF_DECLARED_IDENTITY_ONLY",
            no_automatic_remapping=True,
        )
    receipt["fingerprint"] = digest(receipt)
    if response_path.read_bytes() != raw:
        raise ValueError("human source changed during validation")

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        with (stage / "submission-v1.json").open("xb") as output:
            output.write(raw)
        (stage / "submission-v1.json").chmod(0o600)
        write_new(stage / "submission-freeze-v1.json", receipt)
        (stage / "submission-freeze-v1.json").chmod(0o600)

    atomic_directory(destination, build)
    if (
        destination / "submission-v1.json"
    ).read_bytes() != raw or response_path.read_bytes() != raw:
        raise ValueError("human snapshot/source byte identity failed")
    return receipt
