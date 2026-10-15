"""P032 capability/enum/arithmetic tests; no generated human benchmark responses."""

import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_dev_evaluation as e
from archguard.infrastructure import security_review_recovery as safety
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.security_dev_worker import SourceFence
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome, TruthLabel, map_p029_outcome


def manifest() -> dict[str, Any]:
    cases: list[dict[str, Any]] = [
        dict(
            case_id="sc-" + f"{i:024x}",
            rule_id="SEC001",
            language="TYPESCRIPT",
            source_paths=["src/Unit.ts"],
        )
        for i in range(100)
    ]
    return dict(
        thesis.sealed(
            dict(
                cases=cases,
                limits=V2Limits().model_dump(mode="json"),
                capabilities={"SEC001": {"TYPESCRIPT": "IMPLEMENTED_V2"}},
                source_hashes={r["case_id"] + "/src/Unit.ts": "0" * 64 for r in cases},
            )
        )
    )


@pytest.mark.parametrize(
    "extra",
    ["truth", "final_label", "reviewer_responses", "adjudication_responses", "construction_intent"],
)
def test_no_truth_or_review_fields_in_worker_manifest(tmp_path: Path, extra: str) -> None:
    value = manifest() | {extra: []}
    with pytest.raises(ValueError):
        SourceFence(tmp_path.resolve(), value)


@pytest.mark.parametrize(
    "path",
    [
        "../truth.json",
        "/truth.json",
        "DEV/truth.json",
        "FINAL/truth.json",
        "responses/A.json",
        "adjudication.json",
        "coordinator/intent.json",
    ],
)
def test_truth_review_intent_traversal_and_absolute_paths_denied(tmp_path: Path, path: str) -> None:
    fence = SourceFence(tmp_path.resolve(), manifest())
    with pytest.raises(ValueError):
        fence.source(path)
    with pytest.raises(PermissionError):
        fence.audit("open", (str(tmp_path.resolve() / path), "r", 0))


@pytest.mark.parametrize("field", ["final_label", "expected_label", "mutation", "rationale"])
def test_roster_extra_fields_rejected(tmp_path: Path, field: str) -> None:
    value = manifest()
    value.pop("fingerprint")
    value["cases"][0][field] = "forbidden"
    with pytest.raises(ValueError):
        SourceFence(tmp_path.resolve(), thesis.sealed(value))


@pytest.mark.parametrize("status", ["CONTRACT_ONLY", "SUPPORTED_PARTIAL_V2_SCOPE", "FAILED"])
def test_frozen_p030_adapter_never_makes_no_finding_tn(status: str) -> None:
    raw = dict(
        requested_rules=["SEC005"],
        findings=[],
        analysis_metadata=dict(
            coverage={"SEC005": dict(status=status, evaluated=status != "CONTRACT_ONLY")}
        ),
    )
    expected = {
        "CONTRACT_ONLY": Outcome.UNSUPPORTED,
        "SUPPORTED_PARTIAL_V2_SCOPE": Outcome.PARTIAL,
        "FAILED": Outcome.FAILED,
    }
    assert map_p029_outcome(raw, "SEC005") == expected[status]


def test_exact_protocol_arithmetic_and_undefined_denominators() -> None:
    pairs = [
        ("POSITIVE", "DEFINITIVE_POSITIVE"),
        ("NEGATIVE", "DEFINITIVE_POSITIVE"),
        ("NEGATIVE", "DEFINITIVE_NEGATIVE"),
        ("POSITIVE", "DEFINITIVE_NEGATIVE"),
        ("POSITIVE", "PARTIAL"),
        ("NEGATIVE", "PARTIAL"),
        ("UNCERTAIN", "DEFINITIVE_POSITIVE"),
        ("OUT_OF_SCOPE", "PARTIAL"),
    ]
    v = e.aggregate([dict(final_label=t, outcome=o) for t, o in pairs])
    assert [v[k] for k in ("TP", "FP", "TN", "FN")] == [1, 1, 1, 1]
    assert v["binary_eligible"] == 6 and v["excluded_truth"] == 2
    assert v["positive_nondefinitive"] == v["negative_nondefinitive"] == 1
    assert v["recall"] == v["precision"] == v["F1"] == 0.5
    assert v["effective_positive_recovery"] == 1 / 3
    empty = e.aggregate([])
    assert all(empty[k] is None for k in ("precision", "recall", "F1", "specificity", "FPR", "FNR"))
    assert tuple(TruthLabel) == tuple(
        TruthLabel(x) for x in ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
    )


def test_stable_join_rejects_unknown_duplicate_and_missing() -> None:
    cases = manifest()["cases"]
    truth = [dict(case_id=r["case_id"], final_label="UNCERTAIN") for r in cases]
    joined = e.stable_join(cases, truth)
    assert len(joined) == 100 and all(r["final_label"] == "UNCERTAIN" for r in joined)
    for malformed in (
        truth[:-1],
        truth[:-1] + [truth[0]],
        truth[:-1] + [dict(case_id="unknown", final_label="UNCERTAIN")],
    ):
        with pytest.raises(ValueError):
            e.stable_join(cases, malformed)


def test_truth_open_requires_closed_writer_before_any_truth_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = []

    def read(path: Path, expected: str | None = None) -> dict[str, Any]:
        seen.append(path)
        assert path != e.DEV_TRUTH
        return dict(
            worker_exited=False,
            prediction_writer_closed=False,
            prediction_registry_frozen=False,
            DEV_truth_reads_before_prediction_freeze=0,
        )

    monkeypatch.setattr(io, "read_seal", read)
    with pytest.raises(ValueError, match="INVALID_TRUTH_BLIND"):
        e.open_dev_truth()
    assert seen == [e.PRIVATE / "prediction-freeze.json"]


@pytest.mark.parametrize("event", ["socket.connect", "subprocess.Popen", "os.system"])
def test_prediction_fence_blocks_external_execution(tmp_path: Path, event: str) -> None:
    with pytest.raises(PermissionError):
        SourceFence(tmp_path.resolve(), manifest()).audit(event, ())


@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "remap"])
def test_actual_registry_faults_rejected_without_replacing_predictions(fault: str) -> None:
    if not (e.RUN / "registry.json").exists():
        pytest.skip("Private frozen P032 predictions are not mounted")
    raw = io.read_seal(e.RUN / "raw.json")
    registry = io.read_seal(e.RUN / "registry.json")
    original = digest(registry)
    changed = copy.deepcopy(registry)
    if fault == "missing":
        changed["rows"].pop()
    elif fault == "duplicate":
        changed["rows"][-1] = changed["rows"][0]
    elif fault == "unknown":
        changed["rows"][-1]["case_id"] = "unknown"
    else:
        changed["rows"][0]["outcome"] = "DEFINITIVE_NEGATIVE"
    with pytest.raises(ValueError):
        e.prediction_rows(raw, changed, io.read_seal(e.RUN / "input.json")["cases"])
    if digest(io.read_seal(e.RUN / "registry.json")) != original:
        pytest.fail("Frozen predictions were modified by validation")


def test_resource_labels_are_measured_whole_process_and_not_suite_runtime() -> None:
    v = e.resource_summary(
        dict(
            latency=[dict(seconds=1.0)] * 100,
            adapter_materialization_seconds=0.1,
            worker_wall_seconds=101.0,
            WHOLE_PROCESS_PEAK_RSS_bytes=123,
            source_bytes=1,
            source_chars=1,
        ),
        0,
        0.2,
        102.0,
    )
    assert v["analyzer_seconds"] == 100 and v["case_latency"]["p95"] == 1
    assert v["WHOLE_PROCESS_PEAK_RSS_bytes"] == 123 and v["timeouts"] == "NOT_MEASURED"
    assert not v["repeatable_timing_claim"]


def test_real_frozen_worker_on_unlabelled_nonbenchmark_sources(tmp_path: Path) -> None:
    root = tmp_path.resolve()
    data = manifest()
    data.pop("fingerprint")
    code = b"export const n=1;\n"
    import hashlib

    for row in data["cases"]:
        name = row["case_id"] + "/src/Unit.ts"
        path = root / "sources" / name
        path.parent.mkdir(parents=True)
        path.write_bytes(code)
        data["source_hashes"][name] = hashlib.sha256(code).hexdigest()
    (root / "input.json").write_text(canonical(thesis.sealed(data)))
    result = subprocess.run(
        [sys.executable, "-m", "archguard.infrastructure.security_dev_worker", str(root)],
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
    )
    assert result.returncode == 0, result.stderr.decode()
    raw, registry = (io.read_seal(root / name) for name in ("raw.json", "registry.json"))
    e.prediction_rows(raw, registry, data["cases"])
    assert all(r["outcome"] == "PARTIAL" for r in registry["rows"])
    audit = io.read_seal(root / "worker-audit.json")
    assert (
        audit["DEV_truth_reads"]
        == audit["FINAL_truth_reads"]
        == audit["provider_calls"]
        == audit["credential_reads"]
        == 0
    )
    assert (
        audit["APPLICATION_CAPABILITY_BOUNDARY"] == "VERIFIED"
        and audit["OS_LEVEL_ISOLATION"] == "NOT_CLAIMED"
    )
    safety.write_once(root / "immutable.json", dict(token=1))
    with pytest.raises(ValueError):
        safety.write_once(root / "immutable.json", dict(token=2))


def test_actual_frozen_dev_replay_and_privacy_without_reopening_truth() -> None:
    if not (e.PUBLIC / "security-dev-evaluation-receipt.json").exists():
        pytest.skip("P032 private execution is not mounted or not frozen yet")
    raw = io.read_seal(e.RUN / "raw.json")
    registry = io.read_seal(e.RUN / "registry.json")
    joined = io.read_seal(e.PRIVATE / "joined-dev.json")
    truth = dict(
        rows=[dict(case_id=r["case_id"], final_label=r["final_label"]) for r in joined["rows"]]
    )
    a, private = e.evaluate(registry, raw, truth)
    b, again = e.evaluate(registry, raw, truth)
    if canonical((a, private)) != canonical((b, again)):
        pytest.fail("Nondeterministic replay")
    assert a["primary"]["binary_eligible"] == 89
    assert a["receipt"]["FINAL_truth_reads"] == a["receipt"]["FINAL_prediction_rows"] == 0
    assert a["capabilities"]["groups"]["CONTRACT_ONLY"]["outcomes"]["UNSUPPORTED"] == 5
    assert len(a["rules"]["groups"]) == 10 and len(a["languages"]["groups"]) == 2
    assert io.read_seal(e.PUBLIC / "security-dev-baseline-metrics.json") == a["primary"]
    assert io.read_seal(e.PRIVATE / "errors-dev.json") == private["errors"]
    assert all(not (e.RUN / n).stat().st_mode & 0o222 for n in ("raw.json", "registry.json"))
    safety.privacy(tuple(e.PUBLIC / n for n in e.ARTIFACTS[:9]))
    assert (
        subprocess.run(
            ["git", "check-ignore", "-q", str(e.PRIVATE / "joined-dev.json")], capture_output=True
        ).returncode
        == 0
    )
    assert not subprocess.check_output(["git", "ls-files", "--", str(e.PRIVATE)])
