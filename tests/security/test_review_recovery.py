"""Mechanical guards and categorical arithmetic; no fabricated human case decisions."""

import ast
import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.infrastructure import security_review_recovery as r
from archguard.security_benchmark.protocol import ReviewEvidence, ReviewPacket

CASE = "sc-" + "0" * 24


def blank(slot="B"):
    return dict(
        reviewer_slot=slot,
        case_id=CASE,
        label=None,
        rationale="\u00a0\n\t…  ",
        evidence_note="\r\n  ",
        completed=False,
    )


def test_projection_preserves_every_value_and_does_not_touch_source():
    source = blank() | dict(
        ordinal=1, rule_id="SEC001", packet_reference="unused", response_destination="untrusted"
    )
    before = copy.deepcopy(source)
    projected = r.project(source, "B")
    assert projected == blank() and source == before
    assert all(projected[k] is source[k] for k in r.FIELDS)


@pytest.mark.parametrize("change", ["unknown", "missing", "wrong_slot", "A_extra"])
def test_projection_rejects_unapproved_shape_without_filling_fields(change):
    raw = blank()
    slot = "B"
    if change == "unknown":
        raw["unapproved"] = 1
    elif change == "missing":
        raw.pop("rationale")
    elif change == "wrong_slot":
        raw["reviewer_slot"] = "A"
    else:
        raw["ordinal"] = 1
        slot = "A"
        raw["reviewer_slot"] = "A"
    with pytest.raises(ValueError):
        r.project(raw, slot)


def test_incomplete_form_cannot_pass_destination_binding():
    with pytest.raises(ValueError, match="INCOMPLETE"):
        r.bind(blank(), "B", {})


def test_extra_workflow_fields_cannot_pass_frozen_response_schema():
    with pytest.raises(ValidationError):
        r.bind(blank() | {"ordinal": 1}, "B", {})


def test_immutable_output_rejects_edits_and_symlinks(tmp_path):
    path = tmp_path.resolve() / "private/item.json"
    r.write_once(path, blank())
    original = path.read_bytes()
    r.write_once(path, blank())
    with pytest.raises(ValueError, match="IMMUTABLE"):
        r.write_once(path, blank() | {"completed": True})
    assert path.read_bytes() == original and path.stat().st_mode & 0o077 == 0
    link = path.parent / "link.json"
    link.symlink_to(path)
    with pytest.raises(ValueError, match="UNSAFE_PATH"):
        r.write_once(link, blank())


@pytest.mark.parametrize("kind", ["duplicate", "hardlink", "oversized", "traversal"])
def test_input_safety(tmp_path, kind):
    root = tmp_path.resolve()
    path = root / "input.json"
    path.write_text('{"completed":false,"completed":false}' if kind == "duplicate" else "{}")
    if kind == "hardlink":
        (root / "alias.json").hardlink_to(path)
    elif kind == "oversized":
        path.write_text(" " * 100)
    elif kind == "traversal":
        path = root / ".." / "input.json"
    with pytest.raises(ValueError):
        r.read_object(path, limit=50)


def test_finder_cleanup_preserves_frozen_bytes_and_rechecks_inventory(tmp_path):
    root = tmp_path.resolve()
    expected = root / "expected.json"
    expected.write_text("{}")
    meta = root / "nested/.DS_Store"
    meta.parent.mkdir()
    # The directory itself must belong to the expected frozen inventory.
    frozen = meta.parent / "bound.json"
    frozen.write_text("{}")
    inventory = {"expected.json": r.io.sha(expected), "nested/bound.json": r.io.sha(frozen)}
    meta.write_bytes(b"\x00\x00\x00\x01Bud1" + b"metadata")
    receipt = r.clean_metadata(root, inventory, 1)
    assert len(receipt) == 1 and not meta.exists()
    assert expected.read_text() == frozen.read_text() == "{}"
    r.io.verify_files(root, inventory)


@pytest.mark.parametrize("kind", ["expected_metadata", "other_file", "bad_header", "byte_drift"])
def test_metadata_cleanup_never_weakens_strict_inventory(tmp_path, kind):
    root = tmp_path.resolve()
    frozen = root / "frozen.json"
    frozen.write_text("{}")
    expected = {"frozen.json": r.io.sha(frozen)}
    meta = root / ("other.json" if kind == "other_file" else ".DS_Store")
    meta.write_bytes(b"\x00\x00\x00\x01Bud1")
    if kind == "expected_metadata":
        expected[meta.name] = r.io.sha(meta)
    elif kind == "bad_header":
        meta.write_bytes(b"not Finder metadata")
    elif kind == "byte_drift":
        frozen.write_text('{"drift":true}')
    with pytest.raises(ValueError):
        r.clean_metadata(root, expected, 1)
    assert meta.exists()


def test_agreement_arithmetic_four_categories_and_undefined_kappa():
    labels = ("w", "x", "y", "z")
    result = r.agreement(["w", "x", "y", "z"], ["w", "x", "z", "z"], labels)
    assert result["N"] == 4 and result["exact_agreements"] == 3
    assert result["raw_agreement"] == 0.75
    assert result["cohens_kappa"] == pytest.approx(2 / 3)
    assert sum(sum(row.values()) for row in result["cross_tab"].values()) == 4
    assert result["cross_tab"]["y"]["z"] == 1
    assert r.agreement(["w"], ["w"], labels)["cohens_kappa"] is None
    assert r.agreement([], [], labels)["raw_agreement"] is None
    with pytest.raises(ValueError):
        r.agreement(["w"], [], labels)
    with pytest.raises(ValueError):
        r.agreement(["foreign"], ["w"], labels)


def test_provenance_clone_guard_is_exact_and_not_an_agreement_threshold():
    a = {CASE: blank("A")}
    b = {CASE: blank("B")}
    result = r.integrity(a, b)
    assert result["normalized_sets_identical"] and not result["independence_accepted"]
    b[CASE]["evidence_note"] += "\n"
    result = r.integrity(a, b)
    assert result["same_labels"] == 1 and result["independence_accepted"]
    assert result["identical_rationales"] == 1 and result["different_evidence_notes"] == 1
    with pytest.raises(ValueError, match="JOIN_CASE"):
        r.integrity(a, {})


def test_mechanical_relocation_and_master_exclusion_with_unlabelled_io_fixture(
    tmp_path, monkeypatch
):
    private = tmp_path.resolve() / "security-human-review-v1/private"
    monkeypatch.setattr(r, "PRIVATE", private)
    # This isolated IO fixture tests copying only; real completed-schema binding is separate.
    monkeypatch.setattr(
        r,
        "bind",
        lambda row, slot, packets: private / "responses" / slot / f"{row['case_id']}.json",
    )
    sets = {s: {CASE: None} for s in ("A", "B")}
    sources = {}
    for slot in ("A", "B"):
        root = private / "responses" / slot
        nested = root / r.NESTED / slot
        nested.mkdir(parents=True)
        row = blank(slot)
        if slot == "B":
            row |= dict(
                ordinal=1,
                rule_id="SEC001",
                packet_reference="unused",
                response_destination="must-not-be-trusted",
            )
        name = f"001_{CASE}.json" if slot == "B" else f"{CASE}.json"
        (nested / name).write_text(json.dumps(row))
        sources[slot] = copy.deepcopy(row)
        aggregate_row = copy.deepcopy(row)
        if slot == "A":
            aggregate_row["evidence_note"] += "\n"
        (root / "aggregate.json").write_text(
            json.dumps(
                dict(
                    reviewer_slot=slot,
                    total=1,
                    responses=[aggregate_row],
                    human_origin_attestation="fixture provenance",
                    independence_attestation="fixture",
                )
            )
        )
    r.io.append_seal(private / "readiness/resume-structural-diagnostics.json", {"fixture": True})
    receipt = r.recover(sets, [])
    assert receipt["provenance_masters_preserved"] == 2
    for slot in ("A", "B"):
        root = private / "responses" / slot
        assert len(list(root.iterdir())) == 1
        assert r.read_object(root / f"{CASE}.json") == blank(slot)
        master = r.read_object(private / "provenance" / slot / "aggregate-master.json")
        assert master["responses"][0]["label"] == sources[slot]["label"]
        if slot == "A":
            assert master["responses"][0]["evidence_note"] == sources[slot]["evidence_note"] + "\n"
            assert receipt["aggregate_crosschecks"][slot]["evidence_note"]["different"] == 1
        else:
            assert master["responses"] == [sources[slot]]
        assert receipt["preserved"][slot]["semantic_changes"] == 0
    assert r.recover(sets, []) == receipt


def test_no_provider_detector_label_generation_or_adjudication_execution():
    source = Path(r.SOURCES[0]).read_text()
    tree = ast.parse(source)
    forbidden = {
        "run_security_analysis",
        "analyze_security",
        "generate",
        "reconcile",
        "eval",
        "exec",
        "getenv",
        "urlopen",
        "request",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else (node.func.attr if isinstance(node.func, ast.Attribute) else "")
            )
            assert name not in forbidden
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("openai", "archguard.security.analyzer"))
    assert "coordinator/construction-intent" not in source
    assert "coordinator/DEV-cohort" not in source


def test_adjudication_packet_copies_only_locked_evidence_and_reviewer_fields():
    evidence = ReviewEvidence(
        case_id=CASE,
        rule_id="SEC001",
        rule_definition="Frozen definition",
        language="TYPESCRIPT",
        framework_context="static",
        review_scope="static evidence",
        source_files=({"path": "src/Unit.ts", "content": "export const n=1;"},),
    )
    packet = ReviewPacket(
        reviewer_slot="A",
        evidence=evidence,
        evidence_fingerprint=r.digest(evidence.model_dump(mode="json")),
        response_destination=f"responses/A/{CASE}.json",
    )
    inputs = {s: blank(s) for s in ("A", "B")}
    result = r.adjudication_packet(packet, inputs)
    assert result["evidence"] == evidence.model_dump(mode="json")
    assert set(result) == {
        "case_id",
        "evidence",
        "evidence_fingerprint",
        "reviewers",
        "allowed_final_labels",
    }
    for slot in ("A", "B"):
        assert result["reviewers"][slot] == {k: inputs[slot][k] for k in ("label", "rationale")}
    assert "final_label" not in result and "completed" not in result


@pytest.mark.parametrize(
    "value",
    [
        {"rationale": "private prose"},
        {"evidence": {}},
        {"responses": []},
        {"identifier": CASE},
        {"human_origin_attestation": "private provenance"},
    ],
)
def test_privacy_rejects_case_content_instead_of_only_checking_key_names(tmp_path, value):
    path = tmp_path.resolve() / "public.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="PUBLIC|PRIVATE"):
        r.privacy((path,))


def test_privacy_accepts_only_aggregate_field_comparison_counts(tmp_path):
    path = tmp_path.resolve() / "public.json"
    path.write_text(json.dumps({"rationale": {"identical": 0, "different": 300}}))
    r.privacy((path,))
