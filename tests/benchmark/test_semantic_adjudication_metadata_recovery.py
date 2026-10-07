"""Known OS metadata requires explicit recovery; frozen/workflow bytes stay strict."""

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure.semantic_adjudication_corrected_acceptance import (
    CorrectedAcceptanceBlocked,
    recover_round_os_metadata,
    verify_frozen_correction_lineage,
)
from archguard.infrastructure.semantic_adjudication_correction import prepare_correction_round
from tests.benchmark.test_semantic_adjudication import frozen as frozen
from tests.benchmark.test_semantic_adjudication_acceptance import acceptance as acceptance
from tests.benchmark.test_semantic_adjudication_correction import args
from tests.benchmark.test_semantic_adjudication_correction import correction as correction


@pytest.fixture
def metadata_round(correction):
    f = correction
    public = prepare_correction_round(
        f["source"], f["destination"], f["bundle"], expected_sha=f["sha"], **args(f)
    )
    f["correction_public_path"] = f["public"] / "correction-audit.json"
    f["correction_public_path"].write_text(canonical(public) + "\n")
    f["correction_expectations"] = {
        "package": public["correction_package_fingerprint"],
        "template": public["template_fingerprint"],
        "audit": public["fingerprint"],
    }
    f["metadata"] = f["destination"] / ".DS_Store"
    return f


def verify(f):
    return verify_frozen_correction_lineage(
        f["source"],
        f["destination"],
        f["correction_public_path"],
        f["bundle"],
        original_sha=f["sha"],
        package_fp=f["expected"]["package"],
        expected=f["correction_expectations"],
    )


def recover(f):
    return recover_round_os_metadata(f["destination"], f["correction_expectations"]["package"])


def test_known_os_metadata_is_strictly_rejected_until_explicit_recovery(metadata_round):
    f = metadata_round
    before = {p: p.read_bytes() for p in f["private"].rglob("*") if p.is_file()}
    f["metadata"].write_bytes(b"synthetic OS metadata")
    with pytest.raises(ValueError, match="UNEXPECTED_OS_METADATA_DS_STORE"):
        verify(f)
    assert f["metadata"].exists()
    receipt = json.loads((f["destination"] / "correction-round-v1.json").read_bytes())
    assert ".DS_Store" not in receipt["files"]
    report = recover(f)
    assert report["event"] == "NON_SCIENTIFIC_FILESYSTEM_METADATA_REMOVAL"
    assert report["intended_file_count"] == 8
    assert report["intended_hashes_valid_before_removal"] is True
    assert report["metadata_was_sole_unexpected_entry"] is True
    assert report["scientific_human_files_changed"] is False
    assert report["correction_round_regenerated"] is False
    assert not f["metadata"].exists()
    assert before == {p: p.read_bytes() for p in before}
    assert report["correction_package_fingerprint"] == receipt["fingerprint"]
    assert verify(f)[2]["fingerprint"] == receipt["fingerprint"]
    assert not (f["source"].parent / "frozen-v1").exists()
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover(f)


@pytest.mark.parametrize("extra", ["unknown.json", ".hidden", "handoff/.DS_Store", "other-folder"])
def test_any_other_extra_entry_blocks_and_is_not_removed(metadata_round, extra):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic OS metadata")
    path = f["destination"] / extra
    if extra == "other-folder":
        path.mkdir()
    else:
        path.write_bytes(b"unknown extra")
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover(f)
    assert f["metadata"].exists() and path.exists()
    with pytest.raises(ValueError, match="UNEXPECTED_WORKFLOW_OR_UNKNOWN_ARTIFACT"):
        verify(f)


@pytest.mark.parametrize(
    "name",
    [
        "handoff/response-template-corrected-v1.json",
        "original-submission-v1.json",
        "handoff/README.txt",
    ],
)
def test_changed_intended_hash_blocks_before_metadata_removal(metadata_round, name):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic OS metadata")
    target = f["destination"] / name
    target.write_bytes(target.read_bytes() + b"\n")
    before = {p: p.read_bytes() for p in f["destination"].rglob("*") if p.is_file()}
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover(f)
    assert before == {p: p.read_bytes() for p in before}


def test_missing_expected_file_blocks_before_metadata_removal(metadata_round):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic OS metadata")
    (f["destination"] / "handoff/index.html").unlink()
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover(f)
    assert f["metadata"].exists()


def test_metadata_listed_in_a_frozen_manifest_is_never_deleted(metadata_round):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic frozen OS metadata")
    path = f["destination"] / "correction-round-v1.json"
    receipt = json.loads(path.read_bytes())
    receipt["files"][".DS_Store"] = hashlib.sha256(f["metadata"].read_bytes()).hexdigest()
    receipt.pop("fingerprint")
    receipt["fingerprint"] = digest(receipt)
    path.write_text(canonical(receipt) + "\n")
    with pytest.raises(CorrectedAcceptanceBlocked, match="DS_STORE_WAS_FROZEN"):
        recover_round_os_metadata(f["destination"], receipt["fingerprint"])
    assert f["metadata"].exists()


def test_symlink_metadata_cannot_remove_external_files(metadata_round, tmp_path):
    f = metadata_round
    external = tmp_path / "external"
    external.write_bytes(b"untouched external bytes")
    f["metadata"].symlink_to(external)
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover(f)
    assert external.read_bytes() == b"untouched external bytes"
    assert f["metadata"].is_symlink()


def test_recovery_requires_exact_frozen_manifest_fingerprint(metadata_round):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic OS metadata")
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        recover_round_os_metadata(f["destination"], "0" * 64)
    assert f["metadata"].exists()


def test_recovery_entry_point_maps_corrected_sha_error_without_parsing(metadata_round, monkeypatch):
    root = Path(__file__).resolve().parents[2]
    scripts = root / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "metadata_recovery_cli", scripts / "prompt015e31_recover_metadata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    corrected = metadata_round["source"].parent / "completed-response-corrected-v1.json"
    raw = b"not approved not JSON"
    corrected.write_bytes(raw)
    monkeypatch.setattr(module, "CORRECTED", corrected)
    monkeypatch.setattr(module, "CORRECTED_SHA", "0" * 64)
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("unapproved human parsed"))
    with pytest.raises(
        CorrectedAcceptanceBlocked, match="PROMPT_015_E_3_1_BLOCKED_CORRECTED_SHA_MISMATCH"
    ) as caught:
        module.corrected_input_guard()
    assert hashlib.sha256(raw).hexdigest() in str(caught.value)
    assert "not approved" not in str(caught.value)
    sys.modules.pop("metadata_recovery_cli", None)


def load_recovery_cli(monkeypatch):
    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "metadata_recovery_cli", scripts / "prompt015e31_recover_metadata.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("field", ["FROZEN", "PUBLIC_RECEIPT"])
def test_recovery_rejects_dangling_acceptance_symlinks_before_removal(
    metadata_round, monkeypatch, tmp_path, field
):
    f = metadata_round
    f["metadata"].write_bytes(b"synthetic OS metadata")
    module = load_recovery_cli(monkeypatch)
    monkeypatch.setattr(module, "SOURCE", f["source"])
    monkeypatch.setattr(module, "SOURCE_SHA", f["sha"])
    monkeypatch.setattr(module, "corrected_input_guard", lambda: b"synthetic approved bytes")
    for name in ("AUDIT", "FROZEN", "PUBLIC_RECEIPT"):
        monkeypatch.setattr(module, name, tmp_path / name)
    link = getattr(module, field)
    link.symlink_to(tmp_path / "nonexistent")
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: module.D_CLOSURE)
    monkeypatch.setattr(
        module, "recover_round_os_metadata", lambda *a, **k: pytest.fail("deletion forbidden")
    )
    monkeypatch.setattr(sys, "argv", ["recovery", "--recover-os-metadata"])
    with pytest.raises(CorrectedAcceptanceBlocked, match="ADDITIONAL_DRIFT"):
        module.main()
    assert f["metadata"].exists()
    assert link.is_symlink()


def test_verify_recovery_rejects_resealed_private_audit_before_parsing_or_printing(
    metadata_round, monkeypatch, tmp_path, capsys
):
    f = metadata_round
    module = load_recovery_cli(monkeypatch)
    audit = {"event": "NON_SCIENTIFIC_FILESYSTEM_METADATA_REMOVAL"}
    trusted = digest(audit)
    audit["reviewer_identity"] = "SYNTHETIC_PRIVATE_CANARY"
    audit["fingerprint"] = digest(audit)
    path = tmp_path / "audit.json"
    path.write_text(canonical(audit) + "\n")
    monkeypatch.setattr(module, "SOURCE", f["source"])
    monkeypatch.setattr(module, "SOURCE_SHA", f["sha"])
    monkeypatch.setattr(module, "corrected_input_guard", lambda: b"synthetic approved bytes")
    monkeypatch.setattr(module, "prerequisites", lambda: None)
    monkeypatch.setattr(module, "AUDIT", path)
    monkeypatch.setattr(module, "AUDIT_FINGERPRINT", trusted)
    monkeypatch.setattr(sys, "argv", ["recovery", "--verify-recovery"])
    monkeypatch.setattr(json, "loads", lambda *a, **k: pytest.fail("untrusted audit parsed"))
    with pytest.raises(ValueError):
        module.main()
    output = capsys.readouterr()
    assert "SYNTHETIC_PRIVATE_CANARY" not in output.out + output.err
