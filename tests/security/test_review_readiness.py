"""P031 readiness guards. No labeled response fixtures or simulated reviewers."""

import json
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import security_review_readiness as r
from archguard.security_benchmark.protocol import ReviewEvidence, ReviewPacket, ReviewResponse

FAKE = "sc-" + "0" * 24


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    root = tmp_path / "security-human-review-v1/private"
    monkeypatch.setattr(r, "PRIVATE", root)
    for slot in ("A", "B"):
        (root / "responses" / slot).mkdir(parents=True)
    evidence = ReviewEvidence(
        case_id=FAKE,
        rule_id="SEC001",
        rule_definition="Frozen rule definition",
        language="TYPESCRIPT",
        framework_context="static",
        review_scope="static evidence",
        source_files=({"path": "src/Unit.ts", "content": "export const n=1;"},),
    )
    sets = {
        slot: {
            FAKE: ReviewPacket(
                reviewer_slot=slot,
                evidence=evidence,
                evidence_fingerprint=digest(evidence.model_dump(mode="json")),
                response_destination=f"responses/{slot}/{FAKE}.json",
            )
        }
        for slot in ("A", "B")
    }
    return root, sets


def blank(path, slot="A", case=FAKE):
    path.write_text(json.dumps(dict(reviewer_slot=slot, case_id=case, completed=False)))


def test_empty_destinations_do_not_require_or_manufacture_attestation(fixture):
    root, sets = fixture
    counts, missing = r.inspect_responses(root, sets)
    assert counts["A"] == dict(expected=1, valid=0, missing=1, invalid=0, submitted_files=0)
    assert counts["B"] == counts["A"]
    assert missing == {"A": [FAKE], "B": [FAKE]}
    assert not any(root.rglob("*.json"))


def test_existing_input_requires_attestation_before_any_read(fixture, monkeypatch):
    root, sets = fixture
    blank(root / "responses/A" / f"{FAKE}.json")
    monkeypatch.setattr(
        Path, "read_bytes", lambda *a, **k: pytest.fail("input opened without attestation")
    )
    with pytest.raises(ValueError, match="ATTESTATION_REQUIRED"):
        r.inspect_responses(root, sets)


def test_unlabelled_incomplete_input_never_becomes_a_completed_response(fixture):
    root, sets = fixture
    blank(root / "responses/A" / f"{FAKE}.json")
    counts, _ = r.inspect_responses(root, sets, human_attested=True)
    assert counts["A"]["valid"] == 0 and counts["A"]["missing"] == 1
    assert counts["A"]["invalid"] == 0


@pytest.mark.parametrize("slot,case", [("B", FAKE), ("A", "sc-" + "f" * 24)])
def test_slot_and_case_mismatch_rejected_without_assigning_a_label(fixture, slot, case):
    root, sets = fixture
    blank(root / "responses/A" / f"{FAKE}.json", slot, case)
    counts, _ = r.inspect_responses(root, sets, human_attested=True)
    assert counts["A"]["invalid"] == 1 and counts["A"]["valid"] == 0


def test_duplicate_json_fields_rejected(fixture):
    root, sets = fixture
    (root / "responses/A" / f"{FAKE}.json").write_text('{"reviewer_slot":"A","reviewer_slot":"B"}')
    counts, _ = r.inspect_responses(root, sets, human_attested=True)
    assert counts["A"]["invalid"] == 1


def test_duplicate_file_alias_rejected(fixture):
    root, sets = fixture
    p = root / "responses/A" / f"{FAKE}.json"
    blank(p)
    (root / "responses/B" / f"{FAKE}.json").hardlink_to(p)
    counts, _ = r.inspect_responses(root, sets, human_attested=True)
    assert counts["A"]["invalid"] == counts["B"]["invalid"] == 1


def test_symlink_directory_rejected_before_listing(fixture, tmp_path):
    root, sets = fixture
    (root / "responses/A").rmdir()
    (root / "responses/A").symlink_to(tmp_path, target_is_directory=True)
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        r.inspect_responses(root, sets)


def test_symlink_file_does_not_read_target(fixture, tmp_path, monkeypatch):
    root, sets = fixture
    outside = tmp_path / "outside.json"
    outside.write_text("not a response")
    (root / "responses/A" / f"{FAKE}.json").symlink_to(outside)
    monkeypatch.setattr(Path, "read_bytes", lambda *a, **k: pytest.fail("symlink target read"))
    counts, _ = r.inspect_responses(root, sets, human_attested=True)
    assert counts["A"]["invalid"] == 1


def test_unexpected_root_and_traversal_rejected(fixture):
    root, sets = fixture
    with pytest.raises(ValueError, match="UNEXPECTED_RESPONSE_ROOT"):
        r.inspect_responses(root.parent, sets)
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        r.safe(root / "../truth.json")


def test_frozen_schema_keeps_four_labels_and_no_response_fingerprint_extension():
    schema = ReviewResponse.model_json_schema()
    assert schema["$defs"]["TruthLabel"]["enum"] == [
        "POSITIVE",
        "NEGATIVE",
        "UNCERTAIN",
        "OUT_OF_SCOPE",
    ]
    assert "evidence_fingerprint" not in schema["properties"]
    assert schema["additionalProperties"] is False


def test_no_ai_label_no_detector_no_metric_or_truth_execution():
    r.dependency_guard()


def test_credentials_never_opened(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("credential opened"))
    with pytest.raises(ValueError, match="UNSAFE_PUBLIC_PATH"):
        r.privacy((Path(".env.ai.local"),))


def test_public_audit_checks_runtime_values_without_matching_its_own_regex(tmp_path):
    r.privacy(tuple(Path(p) for p in r.SOURCES))
    p = tmp_path / "public.md"
    p.write_text("/" + "Users" + "/" + "unidentified" + "/private")
    with pytest.raises(ValueError, match="PRIVATE_LEAKAGE"):
        r.privacy((p,))
    p.write_text(FAKE)
    with pytest.raises(ValueError, match="PRIVATE_LEAKAGE"):
        r.privacy((p,))
