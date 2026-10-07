"""Mechanical diagnostics and an immutable handoff; only the human may correct answers."""

import copy
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_adjudication import AdjudicatorBundle, AdjudicatorSubmission
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication import audit_adjudicator_bundle

INSTRUCTIONS = """Round 1: structural correction by the SAME third human adjudicator

Status: WAITING_FOR_ADJUDICATOR_CORRECTION
This is a correction handoff, not accepted adjudication or final ground truth.

1. Read ../structural-diagnostic-v1.json for the exact mechanical ID/evidence errors.
   The package does not infer any extra-ID to missing-ID correspondence. Evidence-ID
   ownership and literal references in rationale/note are diagnostics, not intended
   case assignments. No category, rationale or evidence is suggested.
2. Review the relevant unchanged frozen packets below and affected-packets-v1.json.
   rule-guidance-v1.json and submission-schema.json are the original frozen files.
   The complete original source-only handoff remains available at:
   ../../../../adjudicator-handoff-v1/index.html
3. Consult your own original attempt in ../original-submission-v1.json if needed.
   Explicitly confirm the correct frozen adjudicator ID, your own decision, your
   own rationale and your own structured evidence for the affected response(s).
   You may reuse your previous answer only after personally confirming it.
4. Copy response-template-corrected-v1.json to a NEW completed file. Retained rows
   are previously human-supplied, field-for-field unchanged, and locked in this
   round; their provenance is recorded in ../correction-round-v1.json. Do not
   rewrite those rows. If a retained answer needs reconsideration, stop and request
   a separate correction round from the coordinator. Blank rows contain no answer.
5. Confirm you are the same human who submitted the original reviewer_identity.
   Set attestation to REAL_HUMAN_INDEPENDENT_ADJUDICATION only if you personally
   performed this correction. Complete exactly the four frozen IDs, with an allowed
   decision, nonblank rationale, nonempty own-case evidence and valid inclusive
   integer line ranges. Do not force any decision distribution.
6. Save completed-response-corrected-v1.json beside the original completed-response.json:
   ../../../completed-response-corrected-v1.json (relative to this README).
   Never overwrite the original attempt, this history, or any frozen handoff file.

Only a separately authorized later stage may validate and accept the corrected file.
No adjudicator acceptance, final truth, AI, V2 or Hybrid execution occurs here.
"""


def load_original_candidate(response_path: Path, expected_sha: str) -> tuple[bytes, dict[str, Any]]:
    if (
        response_path.name != "completed-response.json"
        or response_path.parent.name != "adjudicator-submissions-v1"
        or response_path.is_symlink()
        or response_path.parent.is_symlink()
    ):
        raise ValueError("original private adjudicator intake path required")
    raw = response_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise ValueError("approved original human SHA mismatch")

    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate original JSON key")
            value[key] = item
        return value

    data: dict[str, Any] = json.loads(raw, object_pairs_hook=unique)
    AdjudicatorSubmission.model_validate(data)
    return raw, data


def diagnose_structure(bundle: AdjudicatorBundle, data: dict[str, Any]) -> dict[str, Any]:
    """Compare literal IDs/ranges only. Never assign a case based on human or source text."""
    submission = AdjudicatorSubmission.model_validate(data)
    if submission.bundle_fingerprint != bundle.fingerprint:
        raise ValueError("original response bundle binding changed")
    packets = {p.blinded_id: p for p in bundle.packets}
    expected_ids = set(packets)
    submitted_ids = {r.blinded_id for r in submission.responses}
    owners: dict[str, list[str]] = {}
    for frozen_packet in bundle.packets:
        for evidence in frozen_packet.evidence:
            owners.setdefault(evidence.evidence_id, []).append(frozen_packet.blinded_id)
    invalid_evidence: list[dict[str, Any]] = []
    invalid_ranges: list[dict[str, Any]] = []
    literal_references: list[dict[str, Any]] = []
    affected_positions: set[int] = set()
    affected_valid_ids: set[str] = set()
    for position, response in enumerate(submission.responses, start=1):
        packet = packets.get(response.blinded_id)
        allowed = {} if packet is None else {e.evidence_id: e for e in packet.evidence}
        if packet is None:
            affected_positions.add(position)
        for ref_index, reference in enumerate(response.evidence, start=1):
            source = allowed.get(reference.evidence_id)
            if source is None:
                invalid_evidence.append(
                    {
                        "response_position_1_based": position,
                        "evidence_position_1_based": ref_index,
                        "submitted_blinded_id": response.blinded_id,
                        "invalid_evidence_id": reference.evidence_id,
                        "submitted_case_is_frozen": packet is not None,
                        "permitted_evidence_ids": sorted(allowed) if packet is not None else None,
                        "frozen_evidence_owner_ids": sorted(owners.get(reference.evidence_id, [])),
                        "belongs_to_different_frozen_id": any(
                            owner != response.blinded_id
                            for owner in owners.get(reference.evidence_id, [])
                        ),
                    }
                )
                affected_positions.add(position)
            elif reference.end_line > len(source.text.splitlines()):
                invalid_ranges.append(
                    {
                        "response_position_1_based": position,
                        "evidence_position_1_based": ref_index,
                        "evidence_id": reference.evidence_id,
                        "start_line": reference.start_line,
                        "end_line": reference.end_line,
                        "frozen_line_count": len(source.text.splitlines()),
                    }
                )
                affected_positions.add(position)
        if position in affected_positions and packet is not None:
            affected_valid_ids.add(packet.blinded_id)
        for field in ("rationale", "note"):
            # Literal identifier tokens only; their text is never compared to source/case content.
            for identifier in sorted(
                set(re.findall(r"\baev-[a-f0-9]{24}\b", getattr(response, field)))
            ):
                known_owners = owners.get(identifier, [])
                literal_references.append(
                    {
                        "response_position_1_based": position,
                        "field": field,
                        "literal_evidence_id": identifier,
                        "frozen_evidence_owner_ids": sorted(known_owners),
                        "refers_to_different_frozen_id": any(
                            owner != response.blinded_id for owner in known_owners
                        ),
                        "used_for_case_assignment": False,
                    }
                )
    missing, extra = sorted(expected_ids - submitted_ids), sorted(submitted_ids - expected_ids)
    if extra and any(not ref["frozen_evidence_owner_ids"] for ref in invalid_evidence):
        cause = "D_MULTIPLE_STRUCTURAL_MISTAKES"
    elif extra:
        cause = "A_UNKNOWN_BLINDED_ID; typo_or_intended_case_NOT_DETERMINED"
    elif invalid_evidence:
        cause = "B_CASE_EVIDENCE_MEMBERSHIP_MISMATCH"
    else:
        cause = "E_OTHER_FORMAL_MISMATCH"
    counts = {
        "expected_ids": len(expected_ids),
        "submitted_ids": len(submission.responses),
        "unique_submitted_ids": len(submitted_ids),
        "missing": len(missing),
        "extra": len(extra),
        "duplicate_ids": len(submission.responses) - len(submitted_ids),
        "invalid_evidence_ids": len(invalid_evidence),
        "invalid_line_ranges": len(invalid_ranges),
    }
    return {
        "schema_version": "private-adjudicator-structural-diagnostic-v1",
        "schema_validation": "PASS",
        "schema_errors": [],
        "bundle_binding_validation": "PASS",
        "expected_blinded_ids": sorted(expected_ids),
        "submitted_blinded_ids": sorted(submitted_ids),
        "missing_blinded_ids": missing,
        "extra_blinded_ids": extra,
        "invalid_evidence": invalid_evidence,
        "invalid_line_ranges": invalid_ranges,
        "literal_rationale_note_references": literal_references,
        "affected_response_positions_1_based": sorted(affected_positions),
        "affected_valid_blinded_ids": sorted(affected_valid_ids),
        "counts": counts,
        "root_cause_classification": cause,
        "intent_status": "HUMAN_CLARIFICATION_REQUIRED",
        "extra_to_missing_mapping_inferred": False,
        "source_text_used_for_identity_inference": False,
        "rationale_note_used_for_identity_inference": False,
    }


def render_correction(instructions: str, packets: list[dict[str, Any]]) -> bytes:
    sections = []
    for packet in packets:
        evidence_sections = []
        for evidence in packet["evidence"]:
            lines = "\n".join(
                f"{i}: {line}" for i, line in enumerate(evidence["text"].splitlines(), 1)
            )
            evidence_sections.append(
                f"<h3>{html.escape(evidence['evidence_id'])}</h3>"
                f"<p>{html.escape(evidence['path'])}</p><pre>{html.escape(lines)}</pre>"
            )
        sections.append(
            f"<article><h2>{html.escape(packet['blinded_id'])}</h2>"
            f"<p>{html.escape(packet['rule_id'])} / {html.escape(packet['language'])}</p>"
            f"<p>{html.escape(packet['target_path'])} / "
            f"{html.escape(packet['target_component'])}</p>"
            f"<pre>{html.escape(packet['architecture_contract'])}</pre>"
            + "".join(evidence_sections)
            + "</article>"
        )
    return (
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        "<title>Adjudicator structural correction — round 1</title>"
        "<style>body{max-width:1100px;margin:2rem auto;padding:0 1rem;font:16px system-ui}"
        "pre{white-space:pre-wrap;overflow-wrap:anywhere;padding:1rem;background:#f4f4f4}"
        "article{border-top:1px solid #ccc;margin-top:2rem}</style>"
        "<h1>Same-human structural correction</h1>"
        '<p><a href="../structural-diagnostic-v1.json">Exact private diagnostic</a> · '
        '<a href="response-template-corrected-v1.json">Correction template</a> · '
        '<a href="../original-submission-v1.json">Your original attempt</a> · '
        '<a href="rule-guidance-v1.json">Frozen guidance</a></p>'
        f"<pre>{html.escape(instructions)}</pre>" + "".join(sections) + "</html>\n"
    ).encode()


def correction_material(
    raw: bytes,
    data: dict[str, Any],
    bundle: AdjudicatorBundle,
    *,
    package_fingerprint: str,
    guidance_bytes: bytes,
    schema_bytes: bytes,
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    if json.loads(raw) != data:
        raise ValueError("human fields must match original bytes")
    if not re.fullmatch(r"[a-f0-9]{64}", package_fingerprint):
        raise ValueError("frozen package fingerprint required")
    if json.loads(schema_bytes) != AdjudicatorSubmission.model_json_schema():
        raise ValueError("frozen response schema changed")
    if json.loads(guidance_bytes) != bundle.guidance:
        raise ValueError("frozen guidance changed")
    audit_adjudicator_bundle(bundle, ())
    forbidden_hint = re.compile(
        r"MUTATION_CANDIDATE|MATCHED_CONTROL|intended[-_](?:positive|negative)|"
        r"(?:one\s+reviewer|reviewer\s*[ab])\s+(?:chose|said|selected|category|was\s+uncertain)|"
        r"reviewers\s+disagreed\s+between",
        re.IGNORECASE,
    )
    if forbidden_hint.search(canonical(data)):
        raise ValueError("reviewer/construction hint in human-authored material; cannot rewrite")
    diagnostic = diagnose_structure(bundle, data)
    affected = set(diagnostic["affected_response_positions_1_based"])
    retained = {
        row["blinded_id"]: row for i, row in enumerate(data["responses"], 1) if i not in affected
    }
    if not affected and not diagnostic["missing_blinded_ids"]:
        raise ValueError("no structural correction required")
    rows = []
    provenance = []
    relevant = set(diagnostic["missing_blinded_ids"]) | set(
        diagnostic["affected_valid_blinded_ids"]
    )
    for packet in bundle.packets:
        original = retained.get(packet.blinded_id)
        if original is not None:
            rows.append(copy.deepcopy(original))
            provenance.append(
                {
                    "blinded_id": packet.blinded_id,
                    "origin": "PREVIOUSLY_HUMAN_SUPPLIED",
                    "original_response_fingerprint": digest(original),
                    "field_for_field_unchanged": True,
                }
            )
        else:
            rows.append(
                {
                    "blinded_id": packet.blinded_id,
                    "decision": None,
                    "rationale": "",
                    "evidence": [],
                    "note": "",
                }
            )
    template = {
        "schema_version": "semantic-holdout-adjudication-submission-v1",
        "reviewer_slot": "ADJUDICATOR",
        "bundle_fingerprint": bundle.fingerprint,
        "reviewer_identity": data["reviewer_identity"],
        "attestation": None,
        "responses": rows,
    }
    packets = [p.model_dump(mode="json") for p in bundle.packets if p.blinded_id in relevant]
    diagnostic.update(
        original_submission_sha256=hashlib.sha256(raw).hexdigest(),
        frozen_package_fingerprint=package_fingerprint,
        correction_round=1,
        reason="FORMAL_STRUCTURAL_MISMATCH",
    )
    contents = {
        "original-submission-v1.json": raw,
        "structural-diagnostic-v1.json": (canonical(diagnostic) + "\n").encode(),
        "handoff/README.txt": INSTRUCTIONS.encode(),
        "handoff/index.html": render_correction(INSTRUCTIONS, packets),
        "handoff/response-template-corrected-v1.json": (
            json.dumps(template, indent=2, ensure_ascii=False) + "\n"
        ).encode(),
        "handoff/affected-packets-v1.json": (canonical({"packets": packets}) + "\n").encode(),
        "handoff/rule-guidance-v1.json": guidance_bytes,
        "handoff/submission-schema.json": schema_bytes,
    }
    receipt = {
        "schema_version": "private-adjudicator-correction-round-v1",
        "status": "WAITING_FOR_ADJUDICATOR_CORRECTION",
        "ground_truth_status": "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN",
        "correction_round": 1,
        "reason": "FORMAL_STRUCTURAL_MISMATCH",
        "original_submission_sha256": diagnostic["original_submission_sha256"],
        "frozen_package_fingerprint": package_fingerprint,
        "bundle_fingerprint": bundle.fingerprint,
        "counts": diagnostic["counts"],
        "root_cause_classification": diagnostic["root_cause_classification"],
        "human_clarification_required": True,
        "retained_response_provenance": provenance,
        "blank_response_count": len(rows) - len(provenance),
        "template_fingerprint": hashlib.sha256(
            contents["handoff/response-template-corrected-v1.json"]
        ).hexdigest(),
        "template_fingerprint_algorithm": "SHA256_RAW_BYTES",
        "corrected_submission_destination": "../../completed-response-corrected-v1.json",
        "files": {name: hashlib.sha256(body).hexdigest() for name, body in contents.items()},
        "human_decisions_changed": False,
        "rationales_notes_changed": False,
        "evidence_auto_remapped": False,
        "original_byte_identical": True,
        "A_B_leakage_findings": 0,
        "construction_leakage_findings": 0,
        "live_ai_calls": 0,
        "adjudicator_accepted": False,
        "final_ground_truth_materialized": False,
    }
    receipt["fingerprint"] = digest(receipt)
    contents["correction-round-v1.json"] = (canonical(receipt) + "\n").encode()
    public = {
        key: receipt[key]
        for key in (
            "status",
            "ground_truth_status",
            "correction_round",
            "reason",
            "original_submission_sha256",
            "frozen_package_fingerprint",
            "bundle_fingerprint",
            "counts",
            "root_cause_classification",
            "human_clarification_required",
            "blank_response_count",
            "template_fingerprint",
            "template_fingerprint_algorithm",
            "human_decisions_changed",
            "rationales_notes_changed",
            "evidence_auto_remapped",
            "original_byte_identical",
            "A_B_leakage_findings",
            "construction_leakage_findings",
            "live_ai_calls",
            "adjudicator_accepted",
            "final_ground_truth_materialized",
        )
    }
    public.update(
        schema_version="adjudicator-correction-verification-v1",
        retained_response_count=len(provenance),
        correction_package_fingerprint=receipt["fingerprint"],
    )
    public["fingerprint"] = digest(public)
    return contents, receipt, public


def prepare_correction_round(
    response_path: Path,
    destination: Path,
    bundle: AdjudicatorBundle,
    *,
    expected_sha: str,
    package_fingerprint: str,
    guidance_bytes: bytes,
    schema_bytes: bytes,
) -> dict[str, Any]:
    if destination != response_path.parent / "corrections-v1/round-1":
        raise ValueError("private correction round-1 destination required")
    if destination.exists() or destination.is_symlink() or destination.parent.is_symlink():
        raise ValueError("correction history is append-only; cannot overwrite")
    raw, data = load_original_candidate(response_path, expected_sha)
    contents, _, public = correction_material(
        raw,
        data,
        bundle,
        package_fingerprint=package_fingerprint,
        guidance_bytes=guidance_bytes,
        schema_bytes=schema_bytes,
    )
    if response_path.read_bytes() != raw:
        raise ValueError("original human file changed during preparation")
    destination.parent.mkdir(mode=0o700, exist_ok=True)

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        (stage / "handoff").mkdir(mode=0o700)
        for name, body in contents.items():
            with (stage / name).open("xb") as output:
                output.write(body)
            (stage / name).chmod(0o600)

    atomic_directory(destination, build)
    verify_correction_round(destination, contents)
    if response_path.read_bytes() != raw:
        raise ValueError("original human bytes changed")
    return public


def verify_correction_round(destination: Path, contents: dict[str, bytes]) -> None:
    if destination.is_symlink() or (destination / "handoff").is_symlink():
        raise ValueError("correction history cannot be symlinked")
    expected_inventory = {*contents, "handoff"}
    if {
        p.relative_to(destination).as_posix() for p in destination.rglob("*")
    } != expected_inventory:
        raise ValueError("correction history inventory changed")
    for name, body in contents.items():
        path = destination / name
        if path.is_symlink() or path.read_bytes() != body:
            raise ValueError("correction history bytes changed")
