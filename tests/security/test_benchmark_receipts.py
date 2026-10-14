"""Public aggregate freeze checks; no live execution or benchmark labels."""

from pathlib import Path

import pytest

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import security_benchmark as stage
from archguard.infrastructure.thesis_closure import sealed
from archguard.infrastructure.unified_human_review import read_seal
from archguard.security_benchmark.foundation import material


def test_p029_frozen_pins():
    for name, fp in stage.PINS.items():
        assert read_seal(stage.v2.ROOT / name, fp)["fingerprint"] == fp


def test_public_bundle_is_aggregate_deterministic_and_has_no_case_code():
    rows, review, audit = material()
    quality = sealed(dict(make_check="PASS"))
    bundle, private = stage.build_public(
        rows, review, audit, {"status": "PASS"}, {"status": "PASS"}, quality, "1" * 40
    )
    assert (bundle, private) == stage.build_public(
        rows, review, audit, {"status": "PASS"}, {"status": "PASS"}, quality, "1" * 40
    )
    assert len(bundle) == 13
    manifest = bundle["benchmark-manifest.json"]
    assert manifest["human_truth"] == "NOT_YET_AVAILABLE" and manifest["detector_predictions"] == 0
    assert len(manifest["fingerprints"]) == 13
    aggregate = {n: v for n, v in bundle.items() if not n.endswith(".schema.json")}
    assert '"case_id":' not in canonical(aggregate)
    assert '"source_files":' not in canonical(aggregate)
    assert '"construction_intent":' not in canonical(aggregate)
    assert len([p for p in private if p.startswith("packets/A/")]) == 300
    assert len([p for p in private if p.startswith("packets/B/")]) == 300
    assert not any(p.startswith(("responses/", "truth/")) for p in private)


def test_quality_prevents_premature_completion(tmp_path):
    p = tmp_path / "quality.json"
    p.write_text(canonical(sealed({"make_check": "FAIL"})))
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        stage.freeze(p, "1" * 40)


def test_secret_path_never_read(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: pytest.fail("credential read"))
    with pytest.raises(ValueError, match="UNSAFE_PUBLIC_PATH"):
        stage.privacy((Path(".env.ai.local"),))


def test_append_only_public_and_private_files(tmp_path):
    p = tmp_path / "packet.json"
    stage.write_new(p, {"x": 1}, True)
    assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        stage.write_new(p, {"x": 2}, True)
