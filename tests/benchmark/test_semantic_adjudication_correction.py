"""Synthetic structural handoff tests; never adjudicate real scientific cases."""

import copy
import hashlib
import json
import socket
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, seal
from archguard.benchmark.semantic_adjudication import AdjudicatorBundle, AdjudicatorPacket
from archguard.benchmark.semantic_holdout import SourceEvidence
from archguard.infrastructure.semantic_adjudication_correction import (
    correction_material,
    diagnose_structure,
    load_original_candidate,
    prepare_correction_round,
    verify_correction_round,
)
from tests.benchmark.test_semantic_adjudication import frozen as frozen
from tests.benchmark.test_semantic_adjudication_acceptance import acceptance as acceptance


@pytest.fixture
def correction(acceptance):
    f = acceptance
    f["missing"] = f["data"]["responses"][0]["blinded_id"]
    f["extra"] = "adj-" + "f" * 32
    f["data"]["responses"][0]["blinded_id"] = f["extra"]
    f["data"]["responses"][1]["note"] = "Own immutable note: λ\nSecond line."
    f["raw"] = (json.dumps(f["data"], indent=3) + "\n").encode()
    f["sha"] = hashlib.sha256(f["raw"]).hexdigest()
    f["source"].write_bytes(f["raw"])
    f["destination"] = f["source"].parent / "corrections-v1/round-1"
    return f


def args(f):
    return {
        "package_fingerprint": f["expected"]["package"],
        "guidance_bytes": f["contents"]["rule-guidance-v1.json"],
        "schema_bytes": f["contents"]["submission-schema.json"],
    }


def material(f):
    return correction_material(f["raw"], f["data"], f["bundle"], **args(f))


def rewrite_fixture(f):
    f["raw"] = json.dumps(f["data"], indent=3).encode()
    f["sha"] = hashlib.sha256(f["raw"]).hexdigest()
    f["source"].write_bytes(f["raw"])


def test_original_sha_guard_before_any_json_diagnostic(correction, monkeypatch):
    f = correction
    f["source"].write_bytes(b"unapproved not JSON")
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("unapproved human parsed"))
    with pytest.raises(ValueError, match="original human SHA"):
        load_original_candidate(f["source"], f["sha"])
    assert not f["destination"].exists()


def test_exact_id_set_diff_and_private_invalid_evidence_diagnostic(correction):
    f = correction
    diagnostic = diagnose_structure(f["bundle"], f["data"])
    assert set(diagnostic["expected_blinded_ids"]) == {p.blinded_id for p in f["bundle"].packets}
    assert set(diagnostic["submitted_blinded_ids"]) == {
        r["blinded_id"] for r in f["data"]["responses"]
    }
    assert diagnostic["missing_blinded_ids"] == [f["missing"]]
    assert diagnostic["extra_blinded_ids"] == [f["extra"]]
    assert diagnostic["counts"] == {
        "expected_ids": 4,
        "submitted_ids": 4,
        "unique_submitted_ids": 4,
        "missing": 1,
        "extra": 1,
        "duplicate_ids": 0,
        "invalid_evidence_ids": 1,
        "invalid_line_ranges": 0,
    }
    invalid = diagnostic["invalid_evidence"][0]
    assert invalid["response_position_1_based"] == 1
    assert invalid["invalid_evidence_id"] == f["data"]["responses"][0]["evidence"][0]["evidence_id"]
    assert invalid["permitted_evidence_ids"] is None
    assert invalid["frozen_evidence_owner_ids"] == [f["missing"]]
    assert invalid["belongs_to_different_frozen_id"] is True
    assert diagnostic["affected_response_positions_1_based"] == [1]
    assert diagnostic["root_cause_classification"].startswith("A_UNKNOWN_BLINDED_ID")
    assert diagnostic["intent_status"] == "HUMAN_CLARIFICATION_REQUIRED"
    assert diagnostic["extra_to_missing_mapping_inferred"] is False


def test_valid_case_with_another_cases_evidence_is_identified_not_remapped(correction):
    f = correction
    f["data"]["responses"][0]["blinded_id"] = f["missing"]
    first, second = f["data"]["responses"][:2]
    second["evidence"] = copy.deepcopy(first["evidence"])
    diagnostic = diagnose_structure(f["bundle"], f["data"])
    invalid = diagnostic["invalid_evidence"][0]
    assert invalid["submitted_blinded_id"] == second["blinded_id"]
    assert invalid["permitted_evidence_ids"] == [f["bundle"].packets[1].evidence[0].evidence_id]
    assert invalid["frozen_evidence_owner_ids"] == [first["blinded_id"]]
    assert diagnostic["root_cause_classification"] == "B_CASE_EVIDENCE_MEMBERSHIP_MISMATCH"
    assert diagnostic["extra_to_missing_mapping_inferred"] is False
    assert second["evidence"] == first["evidence"]


def test_unknown_evidence_plus_unknown_case_is_mechanically_multiple_mistakes(correction):
    f = correction
    f["data"]["responses"][0]["evidence"][0]["evidence_id"] = "aev-" + "0" * 24
    diagnostic = diagnose_structure(f["bundle"], f["data"])
    assert diagnostic["root_cause_classification"] == "D_MULTIPLE_STRUCTURAL_MISTAKES"
    assert diagnostic["invalid_evidence"][0]["frozen_evidence_owner_ids"] == []


def test_missing_response_never_receives_unknown_responses_human_answer(correction):
    f = correction
    before = copy.deepcopy(f["data"])
    contents, receipt, public = material(f)
    template = json.loads(contents["handoff/response-template-corrected-v1.json"])
    rows = {r["blinded_id"]: r for r in template["responses"]}
    assert f["extra"] not in rows
    assert set(rows) == {p.blinded_id for p in f["bundle"].packets}
    assert rows[f["missing"]] == {
        "blinded_id": f["missing"],
        "decision": None,
        "rationale": "",
        "evidence": [],
        "note": "",
    }
    assert template["attestation"] is None
    assert template["reviewer_identity"] == before["reviewer_identity"]
    for row in before["responses"][1:]:
        assert rows[row["blinded_id"]] == row
    assert receipt["blank_response_count"] == 1
    assert public["retained_response_count"] == 3
    assert all(
        p["origin"] == "PREVIOUSLY_HUMAN_SUPPLIED" for p in receipt["retained_response_provenance"]
    )
    assert f["data"] == before


@pytest.mark.parametrize("field", ["rationale", "note"])
def test_literal_text_references_reported_but_never_used_to_infer_identity(correction, field):
    f = correction
    identifier = f["bundle"].packets[0].evidence[0].evidence_id
    f["data"]["responses"][0][field] = f"My own text mentions {identifier} and {f['missing']}."
    rewrite_fixture(f)
    contents, _, _ = material(f)
    diagnostic = json.loads(contents["structural-diagnostic-v1.json"])
    refs = [r for r in diagnostic["literal_rationale_note_references"] if r["field"] == field]
    assert refs[0]["literal_evidence_id"] == identifier
    assert refs[0]["refers_to_different_frozen_id"] is True
    assert refs[0]["used_for_case_assignment"] is False
    row = next(
        r
        for r in json.loads(contents["handoff/response-template-corrected-v1.json"])["responses"]
        if r["blinded_id"] == f["missing"]
    )
    assert row["rationale"] == "" and row["decision"] is None and row["evidence"] == []


def test_source_content_similarity_cannot_change_id_diagnostic(correction):
    f = correction
    before = diagnose_structure(f["bundle"], f["data"])
    packets = []
    for packet in f["bundle"].packets:
        text = f"Human may probably mean {f['missing']}.\nSame semantic text for every case.\n"
        source = packet.evidence[0]
        evidence = SourceEvidence(
            evidence_id=source.evidence_id,
            path=source.path,
            text=text,
            sha256=hashlib.sha256(text.encode()).hexdigest(),
        )
        values = packet.model_dump(exclude={"fingerprint", "evidence"})
        packets.append(seal(AdjudicatorPacket, **values, evidence=(evidence,)))
    bundle = seal(
        AdjudicatorBundle,
        **f["bundle"].model_dump(exclude={"fingerprint", "packets"}),
        packets=tuple(packets),
    )
    data = copy.deepcopy(f["data"])
    data["bundle_fingerprint"] = bundle.fingerprint
    assert diagnose_structure(bundle, data) == before


def test_correction_preserves_original_and_all_frozen_inputs_without_network(
    correction, monkeypatch
):
    f = correction
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    monkeypatch.setattr(socket, "socket", lambda *a, **k: pytest.fail("AI/network forbidden"))
    public = prepare_correction_round(
        f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
    )
    contents, _, expected_public = material(f)
    assert public == expected_public
    verify_correction_round(f["destination"], contents)
    assert before == {p: p.read_bytes() for p in before}
    assert (f["destination"] / "original-submission-v1.json").read_bytes() == f["raw"]
    assert not (f["source"].parent / "frozen-v1").exists()
    assert not (f["source"].parent / "completed-response-corrected-v1.json").exists()
    assert public["adjudicator_accepted"] is False
    assert public["final_ground_truth_materialized"] is False
    assert public["live_ai_calls"] == 0
    for path in [f["destination"].parent, f["destination"], *f["destination"].rglob("*")]:
        assert path.stat().st_mode & 0o777 == (0o700 if path.is_dir() else 0o600)
    with pytest.raises(ValueError, match="append-only"):
        prepare_correction_round(
            f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
        )


@pytest.mark.parametrize("tamper", ["extra_file", "template", "original_copy"])
def test_round_byte_and_inventory_tampering_blocks(correction, tamper):
    f = correction
    prepare_correction_round(
        f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
    )
    contents, _, _ = material(f)
    name = {
        "extra_file": "extra.json",
        "template": "handoff/response-template-corrected-v1.json",
        "original_copy": "original-submission-v1.json",
    }[tamper]
    (f["destination"] / name).write_bytes(b"tampered")
    with pytest.raises(ValueError):
        verify_correction_round(f["destination"], contents)
    assert f["source"].read_bytes() == f["raw"]


def test_no_private_answers_or_identifiers_in_public_audit(correction):
    f = correction
    contents, _, public = material(f)
    public_bytes = canonical(public)
    assert f["data"]["reviewer_identity"] not in public_bytes
    for row in f["data"]["responses"]:
        assert row["blinded_id"] not in public_bytes
        assert row["rationale"] not in public_bytes
        for ref in row["evidence"]:
            assert ref["evidence_id"] not in public_bytes
    forbidden = {
        "a_decision",
        "b_decision",
        "a_category",
        "b_category",
        "disagreement_type",
        "pair_id",
        "operator_id",
        "construction_intent",
        "private_provenance",
        "ai_results",
        "detector_results",
        "final_human_label",
        "case_id",
        "conflict_id",
    }

    def walk(value):
        if isinstance(value, dict):
            assert not forbidden & set(value)
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for name, body in contents.items():
        if name.endswith(".json"):
            walk(json.loads(body))
    assert public["A_B_leakage_findings"] == public["construction_leakage_findings"] == 0
    assert b"&lt;script&gt;not executable&lt;/script&gt;" in contents["handoff/index.html"]
    assert b"<script>not executable</script>" not in contents["handoff/index.html"]


@pytest.mark.parametrize(
    "marker",
    [
        "Reviewer A chose POSITIVE",
        "Reviewer B selected NEGATIVE",
        "MUTATION_CANDIDATE",
        "MATCHED_CONTROL",
    ],
)
def test_private_outcome_or_intent_hints_block_without_rewriting_human(correction, marker):
    f = correction
    f["data"]["responses"][0]["note"] = marker
    rewrite_fixture(f)
    with pytest.raises(ValueError, match="hint"):
        prepare_correction_round(
            f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
        )
    assert f["source"].read_bytes() == f["raw"]
    assert not f["destination"].exists()


def test_source_raw_and_fields_cannot_diverge_or_generate_new_answers(correction):
    f = correction
    f["data"]["responses"][1]["decision"] = "POSITIVE"
    with pytest.raises(ValueError, match="match original bytes"):
        material(f)
    assert f["source"].read_bytes() == f["raw"]


def test_no_corrected_file_read_or_acceptance_execution(correction):
    f = correction
    corrected = f["source"].parent / "completed-response-corrected-v1.json"
    corrected.write_text("NOT APPROVED NOT JSON")
    prepare_correction_round(
        f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
    )
    assert corrected.read_text() == "NOT APPROVED NOT JSON"
    assert not (f["source"].parent / "frozen-v1").exists()
    root = Path(__file__).resolve().parents[2]
    for name in (
        "scripts/prompt015e2_correction.py",
        "src/archguard/infrastructure/semantic_adjudication_correction.py",
    ):
        text = (root / name).read_text()
        for forbidden in (
            "freeze_completed_adjudication(",
            "validate_completed_adjudication(",
            "verify_frozen_review(",
            "build_agreement_artifacts(",
            "construct_holdout(",
            "openai.",
            "requests.",
            "httpx.",
        ):
            assert forbidden not in text
