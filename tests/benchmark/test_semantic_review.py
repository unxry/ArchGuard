"""Synthetic contract fixtures only; never labels for the real frozen cohort."""

import hashlib
import json

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_holdout import BlindedPacket, SourceEvidence
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    validate_submission,
)
from archguard.infrastructure.semantic_review import (
    audit_bundle,
    blank_template,
    freeze_submission,
    prepare_handoff,
    render_handoff,
    verify_handoff,
    verify_submission_contract,
)


def sealed_map(value):
    payload = {k: v for k, v in value.items() if k != "fingerprint"}
    return payload | {"fingerprint": digest(payload)}


@pytest.fixture
def bundle():
    text = 'synthetic evidence\n</pre><script>alert("synthetic")</script>\n'
    packets = tuple(
        seal(
            BlindedPacket,
            blinded_id=f"synthetic-case-{i}",
            rule_id=f"ARCH20{i % 5 + 1}",
            language="JAVA" if i % 2 == 0 else "TYPESCRIPT",
            project_alias="synthetic",
            target_path="src/Example.txt",
            target_component="Example",
            architecture_contract="Synthetic contract only.",
            evidence=(
                SourceEvidence(
                    evidence_id=f"synthetic-source-{i}",
                    path="src/Example.txt",
                    text=text,
                    sha256=hashlib.sha256(text.encode()).hexdigest(),
                ),
            ),
        )
        for i in range(100)
    )
    return seal(
        ReviewerABundle,
        schema_version="blank-independent-human-bundle-v1",
        reviewer_slot="A",
        status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
        packets=packets,
        protocol=sealed_map({"reviewer_slots": ["A", "B"], "auto_review": False}),
        guidance=sealed_map(
            {
                "general": "Synthetic guidance.",
                "arch201_vs_arch205": "Test only.",
                "rules": {f"ARCH20{i}": "Synthetic rubric." for i in range(1, 6)},
            }
        ),
    )


def synthetic_submission(bundle):
    data = blank_template(bundle)
    data["reviewer_identity"] = "Synthetic test fixture; not a real reviewer"
    data["attestation"] = "REAL_HUMAN_INDEPENDENT_REVIEW"
    for i, row in enumerate(data["responses"]):
        row.update(
            decision=["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"][i % 4],
            rationale="Synthetic validator fixture only.",
            evidence=[{"evidence_id": f"synthetic-source-{i}", "start_line": 1, "end_line": 1}],
        )
    return data


def test_handoff_preserves_frozen_evidence_order_guidance_and_blank_answers(bundle, tmp_path):
    original = tmp_path / "original.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    destination = tmp_path / "handoff"
    fingerprint = prepare_handoff(original, bundle.fingerprint, destination)
    assert verify_handoff(destination, bundle.fingerprint) == fingerprint
    assert (destination / "bundle-v1.json").read_bytes() == original.read_bytes()
    html = (destination / "index.html").read_text()
    assert html.count("<section id=") == 100
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert html.index('id="synthetic-case-0"') < html.index('id="synthetic-case-1"')
    assert "Synthetic rubric." in html
    template = json.loads((destination / "response-template.json").read_text())
    assert len(template["responses"]) == 100
    assert all(
        r["decision"] is None and not r["rationale"] and not r["evidence"]
        for r in template["responses"]
    )
    with pytest.raises(ValidationError):
        ReviewerASubmission.model_validate(template)
    with pytest.raises(ValueError, match="immutable"):
        prepare_handoff(original, bundle.fingerprint, destination)
    (destination / "index.html").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        verify_handoff(destination, bundle.fingerprint)


@pytest.mark.parametrize("decision", [None, "", ["POSITIVE", "NEGATIVE"], "SUPPORTED"])
def test_blank_multiple_and_ai_decisions_rejected(bundle, decision):
    data = synthetic_submission(bundle)
    data["responses"][0]["decision"] = decision
    with pytest.raises(ValidationError):
        ReviewerASubmission.model_validate(data)


@pytest.mark.parametrize("change", ["rationale", "identity", "attestation", "evidence", "extra"])
def test_incomplete_or_contaminated_submission_rejected(bundle, change):
    data = synthetic_submission(bundle)
    if change == "rationale":
        data["responses"][0]["rationale"] = "  "
    elif change == "identity":
        data["reviewer_identity"] = "  "
    elif change == "attestation":
        data["attestation"] = None
    elif change == "evidence":
        data["responses"][0]["evidence"] = []
    else:
        data["responses"][0]["construction_intent"] = "unallowed"
    with pytest.raises(ValidationError):
        ReviewerASubmission.model_validate(data)


@pytest.mark.parametrize(
    "change", ["duplicate", "missing", "unknown", "wrong_bundle", "wrong_source", "outside"]
)
def test_submission_must_match_exact_case_and_source_scope(bundle, change):
    data = synthetic_submission(bundle)
    if change == "duplicate":
        data["responses"][1] = data["responses"][0]
    elif change == "missing":
        data["responses"].pop()
    elif change == "unknown":
        data["responses"][0]["blinded_id"] = "not-in-bundle"
    elif change == "wrong_bundle":
        data["bundle_fingerprint"] = "0" * 64
    elif change == "wrong_source":
        data["responses"][0]["evidence"][0]["evidence_id"] = "synthetic-source-1"
    else:
        data["responses"][0]["evidence"][0]["end_line"] = 10
    with pytest.raises(ValueError):
        validate_submission(bundle, ReviewerASubmission.model_validate(data))


def test_append_only_freeze_has_independent_fingerprint_no_truth_join(bundle, tmp_path):
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    responses = tmp_path / "synthetic.json"
    data = synthetic_submission(bundle)
    responses.write_text(json.dumps(data))
    destination = tmp_path / "frozen"
    fingerprint = freeze_submission(original, bundle.fingerprint, responses, destination)
    assert fingerprint == digest(ReviewerASubmission.model_validate(data))
    receipt = json.loads((destination / "submission-freeze-v1.json").read_text())
    assert receipt["identity_verification"] == "SELF_DECLARED_ONLY"
    assert receipt["submission_fingerprint"] == fingerprint
    before = (destination / "submission-v1.json").read_bytes()
    data["responses"][0]["decision"] = "UNCERTAIN"
    responses.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="immutable"):
        freeze_submission(original, bundle.fingerprint, responses, destination)
    assert (destination / "submission-v1.json").read_bytes() == before
    assert original.read_text() == json.dumps(bundle.model_dump(mode="json"))


def test_duplicate_json_decisions_cannot_be_silently_collapsed(bundle, tmp_path):
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    responses = tmp_path / "synthetic.json"
    responses.write_text(
        json.dumps(synthetic_submission(bundle)).replace(
            '"decision": "POSITIVE"', '"decision": "POSITIVE", "decision": "NEGATIVE"', 1
        )
    )
    with pytest.raises(ValueError, match="duplicate submission field"):
        freeze_submission(original, bundle.fingerprint, responses, tmp_path / "frozen")
    assert not (tmp_path / "frozen").exists()


def test_bundle_leakage_audit_and_wrong_fingerprint(bundle, tmp_path):
    audit_bundle(bundle)
    contaminated = bundle.model_dump(mode="json")
    contaminated["guidance"] = sealed_map(bundle.guidance | {"pair_id": "secret pair"})
    contaminated["fingerprint"] = digest(
        {k: v for k, v in contaminated.items() if k != "fingerprint"}
    )
    with pytest.raises(ValueError, match="forbidden"):
        audit_bundle(ReviewerABundle.model_validate(contaminated))
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    with pytest.raises(ValueError, match="fingerprint mismatch"):
        prepare_handoff(original, "0" * 64, tmp_path / "handoff")
    assert not (tmp_path / "handoff").exists()


def test_renderer_has_no_network_or_answer_autofill(bundle):
    html = render_handoff(bundle)
    assert "default-src 'none'" in html
    for forbidden in ("<script", "fetch(", "https://", "http://", "selected=", "checked="):
        assert forbidden not in html


def test_returned_form_does_not_change_frozen_submission_contract(bundle, tmp_path):
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    destination = tmp_path / "handoff"
    fingerprint = prepare_handoff(original, bundle.fingerprint, destination)
    (destination / "response-template.json").rename(destination / "completed-response.json")
    assert verify_submission_contract(destination, bundle.fingerprint) == fingerprint
    assert (destination / "completed-response.json").is_file()
    with pytest.raises(ValueError, match="unexpected"):
        verify_handoff(destination, bundle.fingerprint)
    (destination / "submission-schema.json").write_text("{}")
    with pytest.raises(ValueError, match="contract changed"):
        verify_submission_contract(destination, bundle.fingerprint)


def test_acceptance_guards_sha_counts_and_preserves_exact_bytes(bundle, tmp_path):
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    source = tmp_path / "synthetic.json"
    data = synthetic_submission(bundle)
    raw = (json.dumps(data, indent=3) + "\n\n").encode()
    source.write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    destination = tmp_path / "frozen"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        freeze_submission(
            original, bundle.fingerprint, source, destination, expected_sha256="0" * 64
        )
    with pytest.raises(ValueError, match="counts mismatch"):
        freeze_submission(
            original,
            bundle.fingerprint,
            source,
            destination,
            expected_sha256=sha,
            expected_counts={"POSITIVE": 100},
        )
    assert not destination.exists()
    counts = {"POSITIVE": 25, "NEGATIVE": 25, "UNCERTAIN": 25, "OUT_OF_SCOPE": 25}
    lineage = {"sample_fingerprint": "1" * 64, "sample_freeze_fingerprint": "2" * 64}
    fingerprint = freeze_submission(
        original,
        bundle.fingerprint,
        source,
        destination,
        expected_sha256=sha,
        expected_counts=counts,
        lineage=lineage,
    )
    assert source.read_bytes() == raw == (destination / "submission-v1.json").read_bytes()
    receipt = json.loads((destination / "submission-freeze-v1.json").read_text())
    assert receipt["submission_sha256"] == sha
    assert receipt["submission_fingerprint"] == fingerprint
    assert receipt["decision_counts"] == counts and receipt["lineage"] == lineage
    assert receipt["schema_validation"] == receipt["evidence_validation"] == "PASS"
    assert receipt["reviewer_slot"] == "A" and receipt["responses"] == 100
    assert receipt["final_ground_truth"] is False and receipt["adjudicated_truth"] is False
    assert receipt["human_answers_modified"] is False
    assert all(
        receipt[k] == 0
        for k in (
            "invalid_evidence_refs",
            "invalid_line_ranges",
            "missing_cases",
            "extra_cases",
            "duplicate_ids",
        )
    )
    assert receipt["fingerprint"] == digest(
        {k: v for k, v in receipt.items() if k != "fingerprint"}
    )
    for private_field in ("reviewer_identity", "rationale", "evidence", "responses_data"):
        assert private_field not in receipt


@pytest.mark.parametrize("marker", ["MUTATION_CANDIDATE", "hp-" + "a" * 32, "operator_id"])
def test_construction_markers_cannot_be_accepted(bundle, tmp_path, marker):
    original = tmp_path / "bundle.json"
    original.write_text(json.dumps(bundle.model_dump(mode="json")))
    source = tmp_path / "synthetic.json"
    data = synthetic_submission(bundle)
    data["responses"][0]["note"] = marker
    source.write_text(json.dumps(data))
    with pytest.raises(ValueError, match="metadata marker"):
        freeze_submission(original, bundle.fingerprint, source, tmp_path / "frozen")
    assert not (tmp_path / "frozen").exists()
