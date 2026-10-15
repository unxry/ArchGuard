import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import security_final_boundary as b
from archguard.infrastructure import security_final_prediction as p
from archguard.security.completeness_v3 import CompletenessCertificate, map_v3_outcome
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome, map_p029_outcome


@pytest.fixture
def manifest():
    cases = [
        dict(
            case_id="sc-" + f"{i:024x}",
            language="JAVA" if i < 100 else "TYPESCRIPT",
            rule_id=f"SEC{i % 10 + 1:03d}",
            source_paths=["src/Unit.java" if i < 100 else "src/Unit.ts"],
        )
        for i in range(200)
    ]
    return b.seal(
        dict(
            cases=cases,
            source_hashes={r["case_id"] + "/" + r["source_paths"][0]: "0" * 64 for r in cases},
            runtime_hashes={},
            limits=V2Limits().model_dump(mode="json"),
            candidate_source_fingerprint=b.SOURCE_FP,
            capabilities={
                f"SEC{i:03d}": dict(JAVA="PARTIAL_V3", TYPESCRIPT="PARTIAL_V3")
                for i in range(1, 11)
            },
        )
    )


def reseal(value):
    return b.seal({k: v for k, v in value.items() if k != "fingerprint"})


def registries(manifest):
    rows = [
        dict(
            case_id=r["case_id"],
            language=r["language"],
            rule_id=r["rule_id"],
            capability="PARTIAL_V3",
            candidate_version=b.VERSION,
            candidate_source_fingerprint=b.SOURCE_FP,
            execution_status="FAILED",
            result=None,
            analysis_exception="SyntheticInfrastructureIndependentFailure",
        )
        for r in manifest["cases"]
    ]
    raw = b.seal(dict(input_fingerprint=manifest["fingerprint"], rows=rows))
    adapted = [
        dict(
            case_id=r["case_id"],
            language=r["language"],
            rule_id=r["rule_id"],
            capability=r["capability"],
            outcome=Outcome.FAILED.value,
            raw_row_fingerprint=digest(r),
        )
        for r in rows
    ]
    return raw, b.seal(dict(raw_prediction_fingerprint=raw["fingerprint"], rows=adapted))


def test_exact_p033_public_candidate():
    candidate = p.verify_candidate()
    assert candidate["source_fingerprint"] == b.SOURCE_FP
    assert candidate["candidate"] == "iteration-004"


def test_candidate_immutability(monkeypatch):
    original = p.io.sha
    monkeypatch.setattr(
        p.io, "sha", lambda path: "0" * 64 if path.name == "engine_v3.py" else original(path)
    )
    with pytest.raises(ValueError):
        p.verify_candidate()


def test_final_roster_and_source_only_manifest(tmp_path, manifest):
    fence = b.FinalFence(tmp_path, tmp_path / "output", manifest)
    assert len(fence.cases) == len(fence.paths) == 200
    assert len(manifest["cases"]) == 200
    assert (
        digest({k: v for k, v in manifest.items() if k != "fingerprint"}) == manifest["fingerprint"]
    )


@pytest.mark.parametrize("field", ["truth", "review", "adjudication", "construction", "expected"])
@pytest.mark.parametrize("where", ["manifest", "roster"])
def test_forbidden_fields(tmp_path, manifest, field, where):
    if where == "manifest":
        manifest[field] = "forbidden"
    else:
        manifest["cases"][0][field] = "forbidden"
    with pytest.raises(ValueError, match="FORBIDDEN"):
        b.FinalFence(tmp_path, tmp_path / "output", reseal(manifest))


@pytest.mark.parametrize("path", ["../truth.json", "/truth.json", "reviews/A.json", "unknown.ts"])
def test_application_path_denial(tmp_path, manifest, path):
    with pytest.raises(ValueError):
        b.FinalFence(tmp_path, tmp_path / "out", manifest).source(path)


@pytest.mark.parametrize(
    "event,args",
    [
        ("open", ("/unmounted/truth", "r", 0)),
        ("open", ("/outside/write", "w", os.O_WRONLY)),
        ("socket.connect", ()),
        ("subprocess.Popen", ()),
        ("os.system", ()),
    ],
)
def test_application_audit_denial(tmp_path, manifest, event, args):
    with pytest.raises(PermissionError):
        b.FinalFence(tmp_path, tmp_path / "out", manifest).audit(event, args)


def test_credential_free_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-never-propagated")
    env = b.environment(tmp_path, tmp_path / "temp")
    assert set(env) == {
        "PATH",
        "PYTHONPATH",
        "PYTHONHASHSEED",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "TMPDIR",
        "LC_ALL",
    }
    assert "synthetic-never-propagated" not in env.values()


def test_missing_os_mechanism_is_fail_closed(monkeypatch):
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(ValueError, match="P034_BLOCKED_OS_ISOLATION_UNAVAILABLE"):
        b.mechanism()


@pytest.fixture(scope="module")
def os_receipt(tmp_path_factory):
    if sys.platform != "darwin":
        pytest.skip("macOS Seatbelt integration requires macOS")
    root = tmp_path_factory.mktemp("p034-os-only")
    bundle, output, temporary = (root / name for name in ("bundle", "output", "temp"))
    for path in (bundle, output, temporary):
        path.mkdir()
    (bundle / "input.json").write_text("{}")
    for name, source in p.runtime_sources().items():
        target = bundle / "runtime" / name
        target.parent.mkdir(exist_ok=True, parents=True)
        shutil.copyfile(source, target)
    site = Path(sys.prefix, "lib", "python3.13", "site-packages").resolve()
    (bundle / "runtime/launch.py").write_text(
        "import runpy,sys\n" + f"sys.path.append({str(site)!r})\n"
        "runpy.run_module('archguard.infrastructure.security_final_worker',run_name='__main__')\n"
    )
    policy = root / "sandbox.sb"
    policy.write_text(b.profile(bundle, output, temporary))
    return b.preflight(bundle, output, temporary, policy)


@pytest.mark.parametrize(
    "category",
    [
        "FINAL_truth",
        "HUMAN_truth_300",
        "review_response",
        "adjudication_response",
        "construction_intent",
        "DEV_truth",
        "credentials",
        "unrelated_home",
        "network",
        "write_outside",
        "unauthorized_process",
    ],
)
def test_real_os_denials(os_receipt, category):
    assert os_receipt["checks"][category] is True
    assert os_receipt["protected_reads_succeeded"] == 0
    assert os_receipt["runtime_imports_verified"] is True


def test_200_row_replay_and_aggregate_privacy(tmp_path, manifest):
    raw, registry = registries(manifest)
    rows = p.prediction_rows(raw, registry, manifest["cases"])
    assert len(rows) == 200
    assert p.summaries(rows) == p.summaries(copy.deepcopy(rows))
    path = tmp_path / "summary.json"
    path.write_text(json.dumps(p.summaries(rows)))
    p.privacy([path])


@pytest.mark.parametrize("problem", ["duplicate", "unknown", "missing", "truth_field", "raw_field"])
def test_registry_rejects_corruption(manifest, problem):
    raw, registry = registries(manifest)
    if problem == "duplicate":
        registry["rows"][1] = registry["rows"][0]
    elif problem == "unknown":
        registry["rows"][0]["case_id"] = "sc-" + "f" * 24
    elif problem == "missing":
        registry["rows"].pop()
    elif problem == "truth_field":
        registry["rows"][0]["truth"] = "forbidden"
    else:
        raw["rows"][0]["review"] = "forbidden"
    with pytest.raises(ValueError):
        p.prediction_rows(reseal(raw), reseal(registry), manifest["cases"])


def test_frozen_mapping_ordinary_no_finding():
    result = dict(
        requested_rules=["SEC008"],
        findings=[],
        diagnostics=[],
        analysis_metadata=dict(
            coverage=dict(SEC008=dict(status="SUPPORTED_PARTIAL_V2_SCOPE", evaluated=True))
        ),
    )
    assert map_v3_outcome(result, "SEC008", "TYPESCRIPT") == map_p029_outcome(result, "SEC008")
    assert map_v3_outcome(result, "SEC008", "TYPESCRIPT") != Outcome.DEFINITIVE_NEGATIVE


def test_invalid_complete_certificate():
    with pytest.raises(ValueError):
        CompletenessCertificate(
            rule_id="SEC008",
            language="TYPESCRIPT",
            declared_scope="test",
            reason_codes=(),
            certificate_status="COMPLETE",
        )


def test_writer_close_and_post_close_rejection(tmp_path):
    path = tmp_path / "raw.json"
    b.write_new(path, b.seal(dict(rows=[])))
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    p.readonly(tmp_path)
    try:
        with pytest.raises((FileExistsError, PermissionError)):
            b.write_new(path, b.seal(dict(rows=["changed"])))
        with pytest.raises(PermissionError):
            path.write_text("changed")
        assert not path.stat().st_mode & 0o222
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    finally:
        tmp_path.chmod(0o700)
        path.chmod(0o600)


def test_zero_blindness_counters():
    assert len(b.ZERO) >= 17
    assert set(b.ZERO.values()) == {0}


def test_authoritative_invocation_cannot_reopen(tmp_path, monkeypatch):
    monkeypatch.setattr(p, "PRIVATE", tmp_path)
    (tmp_path / "execution-reservation.json").write_text("reserved")
    with pytest.raises(ValueError, match="WRITER_CLOSED"):
        p.run()


def test_capability_binding_rejects_drift(manifest):
    raw, registry = registries(manifest)
    manifest["capabilities"]["SEC001"]["JAVA"] = "CONTRACT_ONLY"
    with pytest.raises(ValueError, match="CAPABILITY_DRIFT"):
        p.prediction_rows(raw, registry, manifest["cases"], manifest["capabilities"])


@pytest.mark.parametrize(
    "source",
    [
        "if case_id: pass",
        "if source_hash == 'x': pass",
        "if split: pass",
        "if filename == 'Unit" + "abcdef12.ts': pass",
        "if name == 'DEV': pass",
        "if name == 'FINAL': pass",
    ],
)
def test_anti_memorization(tmp_path, monkeypatch, source):
    path = tmp_path / "detector.py"
    path.write_text(source)
    monkeypatch.setattr(p.refinement, "DETECTOR_SOURCES", (str(path),))
    with pytest.raises(ValueError, match="MEMORIZATION"):
        p.refinement.anti_memorization()


def test_private_git_exclusion():
    assert subprocess.run(["git", "check-ignore", "-q", str(p.PRIVATE / "probe")]).returncode == 0
    assert not subprocess.check_output(["git", "ls-files", "--", str(p.PRIVATE)])


def test_history_freeze_public_only():
    result = p.verify_history()
    assert result["status"] == "PASS"
    assert result["P030_inventory"] == 927
    assert result["P031"] == "PUBLIC_OPAQUE_SEALS_ONLY"
