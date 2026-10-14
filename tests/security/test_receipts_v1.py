"""Versioned engineering metadata and permanent Architecture/Security boundary."""

from pathlib import Path

import pytest

from archguard.infrastructure import security_analysis_v1 as v1
from archguard.infrastructure import security_foundation as foundation
from archguard.infrastructure.thesis_closure import sealed


def test_registries_are_deterministic_source_safe(monkeypatch):
    monkeypatch.setattr(v1, "science_audit", lambda: {"status": "PASS"})
    monkeypatch.setattr(foundation, "import_firewall", lambda: {"status": "PASS"})
    quality = sealed({"make_check": "PASS"})
    first = v1.build(quality, "1" * 40)
    assert first == v1.build(quality, "1" * 40)
    assert len(first["detector-registry.json"]["detectors"]) == 10
    assert first["security-analysis-v1.json"]["fixture_count"] == 80
    assert all("source" not in c for c in first["fixture-inventory.json"]["cases"])
    assert first["security-analysis-v1.json"]["provider_calls"] == 0
    assert first["security-analysis-v1.json"]["Security_precision"] == "NOT_AVAILABLE"


def test_actual_import_firewall_includes_engine():
    receipt = foundation.import_firewall()
    assert receipt["status"] == "PASS"
    assert "src/archguard/security/engine_v1.py" in receipt["module_hashes"]


@pytest.mark.parametrize("name", ["sec-rule-registry.json", "security-domain-model.json"])
def test_canonical_p027_contract_is_unchanged(name):
    from archguard.infrastructure.unified_human_review import read_seal

    assert (
        read_seal(foundation.ROOT / name, v1.P027_PINS[name])["fingerprint"] == v1.P027_PINS[name]
    )


def test_quality_precedes_freeze(tmp_path):
    p = tmp_path / "quality.json"
    from archguard.benchmark.oss.models import canonical

    p.write_text(canonical(sealed({"make_check": "FAIL"})))
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        v1.freeze(p, "1" * 40)


def test_privacy_does_not_open_env(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *args, **kwargs: pytest.fail("env was opened"))
    with pytest.raises(ValueError, match="UNSAFE_PUBLIC_PATH"):
        v1.privacy((Path(".env.ai.local"),))


def test_secret_audit_rejects_credential_shape(tmp_path):
    p = tmp_path / "unsafe.txt"
    p.write_text("sk-" + "TEST_ONLY_SYNTHETIC_SECRET_NO_PROVIDER")
    with pytest.raises(ValueError, match="SECRET_AUDIT_FAILED"):
        v1.privacy((p,))
