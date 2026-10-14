"""Source-safe engineering protocols and read-only historical freeze bindings."""

import json
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_foundation as foundation
from archguard.infrastructure.thesis_closure import sealed
from archguard.infrastructure.unified_human_review import read_seal


def test_protocols_are_deterministic_and_do_not_contain_fixture_source(monkeypatch):
    monkeypatch.setattr(v2, "historical_audit", lambda: {"status": "PASS"})
    monkeypatch.setattr(foundation, "import_firewall", lambda: {"status": "PASS"})
    value = v2.build(sealed({"make_check": "PASS"}), "1" * 40)
    assert value == v2.build(sealed({"make_check": "PASS"}), "1" * 40)
    assert len(value["framework-pack-registry.json"]["packs"]) == 17
    assert len(value["detector-registry-v2.json"]["detectors"]) == 10
    assert value["security-analysis-v2.json"]["provider_calls"] == 0
    assert all(
        "source" not in c and "files" not in c for c in value["fixture-inventory.json"]["cases"]
    )


def test_historical_pins_and_byte_inventory():
    for root, pins in ((v2.v1.ROOT, v2.V1_PINS), (foundation.ROOT, v2.v1.P027_PINS)):
        for name, fp in pins.items():
            assert read_seal(root / name, fp)["fingerprint"] == fp


def test_quality_precedes_completion(tmp_path):
    p = tmp_path / "quality.json"
    p.write_text(canonical(sealed({"make_check": "FAIL"})))
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        v2.freeze(p, "1" * 40)


def test_import_firewall_includes_v2_service_and_engine():
    receipt = foundation.import_firewall()
    assert receipt["status"] == "PASS"
    assert "src/archguard/security/engine_v2.py" in receipt["module_hashes"]
    assert "src/archguard/security/analyzer_v2.py" in receipt["module_hashes"]


def test_privacy_never_opens_credential_file(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("credential file opened"))
    with pytest.raises(ValueError, match="UNSAFE_PUBLIC_PATH"):
        v2.privacy((Path(".env.ai.local"),))


def test_fixture_inventory_has_no_effectiveness_labels():
    fixtures = json.loads(v2.FIXTURES.read_text())
    assert fixtures["purpose"] == "ENGINEERING_TEST_FIXTURES_NOT_SECURITY_GROUND_TRUTH"
    assert not {"TP", "FP", "TN", "FN", "precision", "recall", "F1"} & fixtures.keys()
