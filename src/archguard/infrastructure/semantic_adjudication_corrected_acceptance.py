"""Accept approved corrected bytes only after checking immutable human correction scope."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_adjudication import AdjudicatorBundle, AdjudicatorSubmission
from archguard.infrastructure.semantic_adjudication_acceptance import (
    SubmissionMismatch,
    freeze_completed_adjudication,
    validate_completed_adjudication,
    verify_opaque_seal,
)
from archguard.infrastructure.semantic_adjudication_correction import load_original_candidate

ROUND_FILES = {
    "original-submission-v1.json",
    "structural-diagnostic-v1.json",
    "handoff/README.txt",
    "handoff/index.html",
    "handoff/response-template-corrected-v1.json",
    "handoff/affected-packets-v1.json",
    "handoff/rule-guidance-v1.json",
    "handoff/submission-schema.json",
}


class CorrectedAcceptanceBlocked(ValueError):
    """Public-safe stop code and aggregate diagnostics only."""


def recover_round_os_metadata(round_path: Path, expected_package_fp: str) -> dict[str, Any]:
    """Explicitly remove only a non-frozen root .DS_Store after all hashes match."""
    blocked = "PROMPT_015_E_3_1_BLOCKED_ADDITIONAL_DRIFT"
    if (
        round_path.name != "round-1"
        or round_path.parent.name != "corrections-v1"
        or round_path.parent.parent.name != "adjudicator-submissions-v1"
        or round_path.is_symlink()
        or round_path.parent.is_symlink()
        or (round_path / "handoff").is_symlink()
    ):
        raise CorrectedAcceptanceBlocked(blocked)
    manifest = round_path / "correction-round-v1.json"
    try:
        manifest_raw = verify_opaque_seal(manifest, expected_package_fp)
        receipt = json.loads(manifest_raw)
    except (ValueError, OSError, KeyError):
        raise CorrectedAcceptanceBlocked(blocked) from None
    files = receipt["files"]
    if any(Path(name).name == ".DS_Store" for name in files):
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_1_BLOCKED_DS_STORE_WAS_FROZEN")
    expected_inventory = {*files, "correction-round-v1.json", "handoff"}
    actual_inventory = {p.relative_to(round_path).as_posix() for p in round_path.rglob("*")}
    differences = {
        "missing": sorted(expected_inventory - actual_inventory),
        "unexpected": sorted(actual_inventory - expected_inventory),
        "changed_files": [],
    }
    if set(files) != ROUND_FILES:
        raise CorrectedAcceptanceBlocked(blocked)
    for name, sha in files.items():
        path = round_path / name
        if (
            not path.is_file()
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != sha
        ):
            differences["changed_files"].append(name)
    metadata = round_path / ".DS_Store"
    if (
        differences["missing"]
        or differences["changed_files"]
        or differences["unexpected"] != [".DS_Store"]
        or not metadata.is_file()
        or metadata.is_symlink()
    ):
        raise CorrectedAcceptanceBlocked(blocked + ": " + json.dumps(differences, sort_keys=True))
    metadata.unlink()
    if (
        {p.relative_to(round_path).as_posix() for p in round_path.rglob("*")} != expected_inventory
        or manifest.read_bytes() != manifest_raw
        or any(
            hashlib.sha256((round_path / name).read_bytes()).hexdigest() != sha
            for name, sha in files.items()
        )
    ):
        raise CorrectedAcceptanceBlocked(blocked)
    return {
        "schema_version": "adjudicator-os-metadata-recovery-v1",
        "event": "NON_SCIENTIFIC_FILESYSTEM_METADATA_REMOVAL",
        "metadata_present_in_frozen_manifest": False,
        "intended_file_count": len(files),
        "intended_hashes_valid_before_removal": True,
        "metadata_was_sole_unexpected_entry": True,
        "metadata_removal_performed": True,
        "scientific_human_files_changed": False,
        "correction_round_regenerated": False,
        "correction_package_fingerprint": expected_package_fp,
        "post_recovery_inventory": "PASS",
    }


def corrected_sha_guard(path: Path, expected_sha: str) -> bytes:
    if (
        path.name != "completed-response-corrected-v1.json"
        or path.parent.name != "adjudicator-submissions-v1"
        or path.is_symlink()
        or path.parent.is_symlink()
    ):
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_BLOCKED_PREREQUISITE_DRIFT")
    raw = path.read_bytes()
    actual = hashlib.sha256(raw).hexdigest()
    if actual != expected_sha:
        raise CorrectedAcceptanceBlocked(
            "PROMPT_015_E_3_BLOCKED_CORRECTED_SHA_MISMATCH: actual_sha=" + actual
        )
    return raw


def verify_frozen_correction_lineage(
    original_path: Path,
    round_path: Path,
    public_audit: Path,
    bundle: AdjudicatorBundle,
    *,
    original_sha: str,
    package_fp: str,
    expected: dict[str, str],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read the existing seals/inventory; never rebuild correction material."""
    if round_path != original_path.parent / "corrections-v1/round-1":
        raise ValueError("frozen private correction round required")
    if (
        round_path.is_symlink()
        or round_path.parent.is_symlink()
        or (round_path / "handoff").is_symlink()
    ):
        raise ValueError("symlinked correction lineage forbidden")
    raw, original = load_original_candidate(original_path, original_sha)
    receipt = json.loads(
        verify_opaque_seal(round_path / "correction-round-v1.json", expected["package"])
    )
    inventory = {p.relative_to(round_path).as_posix() for p in round_path.rglob("*")}
    expected_inventory = {*ROUND_FILES, "correction-round-v1.json", "handoff"}
    if set(receipt["files"]) != ROUND_FILES or inventory != expected_inventory:
        kind = (
            "UNEXPECTED_OS_METADATA_DS_STORE"
            if inventory - expected_inventory == {".DS_Store"}
            else "UNEXPECTED_WORKFLOW_OR_UNKNOWN_ARTIFACT"
        )
        raise ValueError("frozen correction inventory changed: " + kind)
    for name, sha in receipt["files"].items():
        path = round_path / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("frozen correction file changed")
    template_bytes = (round_path / "handoff/response-template-corrected-v1.json").read_bytes()
    if (
        hashlib.sha256(template_bytes).hexdigest() != expected["template"]
        or (round_path / "original-submission-v1.json").read_bytes() != raw
        or receipt["original_submission_sha256"] != original_sha
        or receipt["frozen_package_fingerprint"] != package_fp
        or receipt["bundle_fingerprint"] != bundle.fingerprint
        or receipt["template_fingerprint"] != expected["template"]
        or receipt["correction_round"] != 1
        or receipt["adjudicator_accepted"] is not False
        or receipt["final_ground_truth_materialized"] is not False
        or receipt["A_B_leakage_findings"] != 0
        or receipt["construction_leakage_findings"] != 0
    ):
        raise ValueError("frozen correction lineage changed")
    public = json.loads(verify_opaque_seal(public_audit, expected["audit"]))
    for field, value in {
        "correction_package_fingerprint": expected["package"],
        "template_fingerprint": expected["template"],
        "original_submission_sha256": original_sha,
        "frozen_package_fingerprint": package_fp,
        "bundle_fingerprint": bundle.fingerprint,
        "retained_response_count": 3,
        "blank_response_count": 1,
    }.items():
        if public[field] != value:
            raise ValueError("frozen public correction audit binding changed")
    template = json.loads(template_bytes)
    rows = {r["blinded_id"]: r for r in template["responses"]}
    provenance = receipt["retained_response_provenance"]
    locked_ids = {p["blinded_id"] for p in provenance}
    if (
        len(template["responses"]) != 4
        or len(rows) != 4
        or set(rows) != {p.blinded_id for p in bundle.packets}
        or template["bundle_fingerprint"] != bundle.fingerprint
        or template["reviewer_identity"] != original["reviewer_identity"]
        or template["attestation"] is not None
        or len(provenance) != 3
        or len(locked_ids) != 3
        or not locked_ids <= set(rows)
    ):
        raise ValueError("correction template/scope binding changed")
    original_rows = {r["blinded_id"]: r for r in original["responses"]}
    for item in provenance:
        identifier = item["blinded_id"]
        if (
            item["origin"] != "PREVIOUSLY_HUMAN_SUPPLIED"
            or item["field_for_field_unchanged"] is not True
            or original_rows.get(identifier) != rows[identifier]
            or digest(rows[identifier]) != item["original_response_fingerprint"]
        ):
            raise ValueError("locked original human response changed")
    for identifier in set(rows) - locked_ids:
        if rows[identifier] != {
            "blinded_id": identifier,
            "decision": None,
            "rationale": "",
            "evidence": [],
            "note": "",
        }:
            raise ValueError("affected template row must remain blank")
    return original, template, receipt


def validate_corrected_adjudication(
    corrected_path: Path,
    original_path: Path,
    round_path: Path,
    public_audit: Path,
    bundle: AdjudicatorBundle,
    *,
    corrected_sha: str,
    original_sha: str,
    package_fp: str,
    expected_correction: dict[str, str],
    expected_counts: dict[str, int],
) -> tuple[bytes, AdjudicatorSubmission, dict[str, int], dict[str, int], dict[str, str]]:
    raw = corrected_sha_guard(corrected_path, corrected_sha)
    try:
        original, template, receipt = verify_frozen_correction_lineage(
            original_path,
            round_path,
            public_audit,
            bundle,
            original_sha=original_sha,
            package_fp=package_fp,
            expected=expected_correction,
        )
    except (ValueError, OSError, KeyError):
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_BLOCKED_PREREQUISITE_DRIFT") from None
    checked_raw, submission, counts = validate_completed_adjudication(
        corrected_path,
        bundle,
        expected_sha=corrected_sha,
        expected_counts=None,
        corrected=True,
    )
    if checked_raw != raw:
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_BLOCKED_CORRECTED_SHA_MISMATCH")
    data = json.loads(raw)  # duplicate keys were already rejected by formal validation
    if data["reviewer_identity"] != original["reviewer_identity"]:
        raise CorrectedAcceptanceBlocked("PROMPT_015_E_3_BLOCKED_SELF_DECLARED_IDENTITY_DRIFT")
    rows = {r["blinded_id"]: r for r in data["responses"]}
    frozen_rows = {r["blinded_id"]: r for r in template["responses"]}
    locked = {p["blinded_id"] for p in receipt["retained_response_provenance"]}
    changed = sum(rows[identifier] != frozen_rows[identifier] for identifier in locked)
    if changed:
        raise CorrectedAcceptanceBlocked(
            "PROMPT_015_E_3_BLOCKED_UNAFFECTED_RESPONSE_DRIFT: changed=" + str(changed)
        )
    # Multiset difference, without pairing unknown original IDs with missing expected IDs.
    old_affected = Counter(
        canonical(r) for r in original["responses"] if r["blinded_id"] not in locked
    )
    new_affected = Counter(canonical(r) for r in data["responses"] if r["blinded_id"] not in locked)
    scope = {
        "locked_unaffected_responses": len(locked),
        "unaffected_responses_changed": changed,
        "corrected_affected_responses": sum(new_affected.values()),
        "affected_responses_changed": sum((new_affected - old_affected).values()),
    }
    if counts != expected_counts:
        raise SubmissionMismatch(
            "ADJUDICATOR_COUNTS_MISMATCH: " + json.dumps(counts, sort_keys=True)
        )
    lineage = {
        "original_attempt_sha256": original_sha,
        "correction_package_fingerprint": expected_correction["package"],
        "correction_template_fingerprint": expected_correction["template"],
        "correction_audit_fingerprint": expected_correction["audit"],
    }
    return raw, submission, counts, scope, lineage


def freeze_corrected_adjudication(
    corrected_path: Path,
    original_path: Path,
    round_path: Path,
    public_audit: Path,
    destination: Path,
    bundle: AdjudicatorBundle,
    *,
    corrected_sha: str,
    original_sha: str,
    package_fp: str,
    expected_correction: dict[str, str],
    expected_counts: dict[str, int],
    lineage: dict[str, str],
) -> dict[str, Any]:
    _, _, _, scope, correction_lineage = validate_corrected_adjudication(
        corrected_path,
        original_path,
        round_path,
        public_audit,
        bundle,
        corrected_sha=corrected_sha,
        original_sha=original_sha,
        package_fp=package_fp,
        expected_correction=expected_correction,
        expected_counts=expected_counts,
    )
    receipt = freeze_completed_adjudication(
        corrected_path,
        destination,
        bundle,
        expected_sha=corrected_sha,
        expected_counts=expected_counts,
        lineage=lineage | correction_lineage,
        corrected=True,
        correction_scope=scope,
    )
    validate_corrected_adjudication(
        corrected_path,
        original_path,
        round_path,
        public_audit,
        bundle,
        corrected_sha=corrected_sha,
        original_sha=original_sha,
        package_fp=package_fp,
        expected_correction=expected_correction,
        expected_counts=expected_counts,
    )
    return receipt
