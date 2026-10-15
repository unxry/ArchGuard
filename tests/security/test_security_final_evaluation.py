import copy
import hashlib
import inspect
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from archguard.infrastructure import security_final_evaluation as e
from archguard.security.completeness_v3 import map_v3_outcome
from archguard.security_benchmark.protocol import Outcome, TruthLabel


@pytest.fixture
def verification():
    return dict(
        prediction_registry_fingerprint=e.REGISTRY_FP,
        candidate_source_fingerprint=e.boundary.SOURCE_FP,
        prediction_registry_verified=True,
        prediction_writer_closed=True,
        prediction_registry_frozen=True,
        blindness_receipt_verified=True,
        candidate_verified=True,
    )


@pytest.fixture
def dataset():
    labels = ["POSITIVE"] * 85 + ["NEGATIVE"] * 106 + ["UNCERTAIN"] * 9
    predictions, truth, originals = [], [], []
    for i, label in enumerate(labels):
        case = "sc-" + f"{i:024x}"
        outcome = Outcome.DEFINITIVE_POSITIVE if i % 5 == 0 else Outcome.PARTIAL
        row = dict(
            case_id=case,
            language="JAVA" if i < 100 else "TYPESCRIPT",
            rule_id=f"SEC{i % 10 + 1:03d}",
            capability="PARTIAL_V3",
            outcome=outcome.value,
            raw_row_fingerprint="0" * 64,
        )
        predictions.append(row)
        truth.append(dict(case_id=case, final_label=label, truth_source="A_B_AGREEMENT"))
        originals.append(dict(case_id=case, result=dict(diagnostics=[], analysis_metadata={})))
    registry = e.boundary.seal(dict(rows=predictions))
    raw = e.boundary.seal(dict(rows=originals))
    truth_set = e.boundary.seal(
        dict(
            split="FINAL",
            rows=truth,
            human_truth_300_fingerprint="0" * 64,
            roster_fingerprint="0" * 64,
        )
    )
    return registry, raw, truth_set


@pytest.mark.parametrize(
    "field",
    [
        "prediction_writer_closed",
        "prediction_registry_frozen",
        "prediction_registry_verified",
        "blindness_receipt_verified",
        "candidate_verified",
        "prediction_registry_fingerprint",
        "candidate_source_fingerprint",
    ],
)
def test_truth_cannot_open_before_verified(verification, field, monkeypatch):
    verification[field] = False
    monkeypatch.setattr(Path, "read_bytes", lambda self: pytest.fail("truth opened too early"))
    with pytest.raises(ValueError, match="CHRONOLOGY"):
        e.open_truth(e.TruthGate(), verification, set())


def test_authorized_frozen_truth_open(tmp_path, monkeypatch, verification, dataset):
    truth = dataset[2]
    path, inventory = tmp_path / "truth.json", tmp_path / "inventory.json"
    path.write_text(json.dumps(truth))
    binding = e.boundary.seal(
        dict(files={"truth/FINAL/truth.json": hashlib.sha256(path.read_bytes()).hexdigest()})
    )
    inventory.write_text(json.dumps(binding))
    monkeypatch.setattr(e, "TRUTH", path)
    monkeypatch.setattr(e, "TRUTH_FP", truth["fingerprint"])
    monkeypatch.setattr(e, "TRUTH_INVENTORY", inventory)
    monkeypatch.setattr(e, "TRUTH_INVENTORY_FP", binding["fingerprint"])
    monkeypatch.setattr(e, "PRIVATE", tmp_path)
    gate = e.TruthGate()
    assert e.open_truth(gate, verification, {r["case_id"] for r in truth["rows"]}) == truth
    assert gate.ready


def test_truth_bytes_drift_rejected(tmp_path, monkeypatch, verification):
    path, inventory = tmp_path / "truth.json", tmp_path / "inventory.json"
    path.write_text("{}")
    binding = e.boundary.seal(dict(files={"truth/FINAL/truth.json": "0" * 64}))
    inventory.write_text(json.dumps(binding))
    for name, value in dict(
        TRUTH=path, TRUTH_INVENTORY=inventory, TRUTH_INVENTORY_FP=binding["fingerprint"]
    ).items():
        monkeypatch.setattr(e, name, value)
    with pytest.raises(ValueError, match="TRUTH_DRIFT"):
        e.open_truth(e.TruthGate(), verification, set())


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate_prediction",
        "duplicate_truth",
        "prediction_only",
        "truth_only",
        "missing_prediction",
        "missing_truth",
    ],
)
def test_stable_join_rejects_mismatch(dataset, problem):
    predictions, _, truth = dataset
    a, b = predictions["rows"], truth["rows"]
    if problem == "duplicate_prediction":
        a[1] = a[0]
    elif problem == "duplicate_truth":
        b[1] = b[0]
    elif problem == "prediction_only":
        a[0]["case_id"] = "sc-" + "f" * 24
    elif problem == "truth_only":
        b[0]["case_id"] = "sc-" + "f" * 24
    elif problem == "missing_prediction":
        a.pop()
    else:
        b.pop()
    with pytest.raises(ValueError, match="JOIN"):
        e.stable_join(a, b)


def test_200_truth_and_binary_eligibility(dataset):
    registry, _, truth = dataset
    e.validate_truth(truth, {r["case_id"] for r in registry["rows"]})
    joined = e.stable_join(registry["rows"], truth["rows"])
    values = e.aggregate(joined)
    assert len(joined) == 200
    assert values["truth_distribution"] == dict(
        POSITIVE=85, NEGATIVE=106, UNCERTAIN=9, OUT_OF_SCOPE=0
    )
    assert values["binary_eligible"] == 191


@pytest.mark.parametrize("label", list(TruthLabel))
def test_four_state_truth(label):
    value = e.aggregate([dict(final_label=label.value, outcome="DEFINITIVE_POSITIVE")])
    assert value["truth_distribution"][label.value] == 1
    assert value["TP"] == (label == TruthLabel.POSITIVE)
    assert value["FP"] == (label == TruthLabel.NEGATIVE)
    assert value["binary_eligible"] == int(label in {TruthLabel.POSITIVE, TruthLabel.NEGATIVE})


@pytest.mark.parametrize(
    "outcome",
    [
        Outcome.PARTIAL,
        Outcome.POTENTIAL,
        Outcome.UNSUPPORTED,
        Outcome.INSUFFICIENT_EVIDENCE,
        Outcome.FAILED,
    ],
)
def test_abstentions_never_become_false_negatives(outcome):
    value = e.aggregate([dict(final_label="POSITIVE", outcome=outcome.value)])
    assert value["FN"] == 0 and value["positive_nondefinitive"] == 1
    assert value["effective_positive_recovery"] == 0
    assert value["precision"] is value["recall"] is value["F1"] is None


def test_definitive_negative_and_metric_arithmetic():
    rows = [
        dict(final_label=t, outcome=o)
        for t, o in [
            ("POSITIVE", "DEFINITIVE_POSITIVE"),
            ("NEGATIVE", "DEFINITIVE_POSITIVE"),
            ("NEGATIVE", "DEFINITIVE_NEGATIVE"),
            ("POSITIVE", "DEFINITIVE_NEGATIVE"),
            ("POSITIVE", "PARTIAL"),
            ("UNCERTAIN", "DEFINITIVE_POSITIVE"),
        ]
    ]
    value = e.aggregate(rows)
    assert [value[k] for k in ["TP", "FP", "TN", "FN"]] == [1, 1, 1, 1]
    assert value["precision"] == value["recall"] == value["F1"] == 0.5
    assert value["effective_positive_recovery"] == 1 / 3
    assert value["definitive_coverage"] == 4 / 5
    assert value["unified_definitive_coverage"] == 5 / 6
    assert value["definitive_nonbinary"]["UNCERTAIN"]["DEFINITIVE_POSITIVE"] == 1


def test_ordinary_no_finding_retains_frozen_mapping():
    raw = dict(
        requested_rules=["SEC008"],
        findings=[],
        analysis_metadata=dict(
            coverage=dict(SEC008=dict(status="SUPPORTED_PARTIAL_V2_SCOPE", evaluated=True))
        ),
    )
    assert map_v3_outcome(raw, "SEC008", "TYPESCRIPT") == Outcome.PARTIAL


def test_undefined_denominators():
    value = e.aggregate([])
    assert all(
        value[k] is None
        for k in ["precision", "recall", "F1", "specificity", "FPR", "FNR", "nondefinitive_rate"]
    )


def test_build_strata_crosstab_privacy_and_replay(tmp_path, dataset):
    registry, raw, truth = dataset
    opened = e.boundary.seal(dict(verified=True))
    first = e.build(registry, raw, truth, opened)
    assert first == e.build(*copy.deepcopy((registry, raw, truth, opened)))
    public, private = first
    assert len(private["error-inventory.json"]["rows"]) == 200
    for name in ["rule", "language", "capability"]:
        groups = public[f"security-final-{name}-metrics.json"]["groups"]
        assert sum(v["N"] for v in groups.values()) == 200
        assert sum(v["TP"] for v in groups.values()) == public["security-final-metrics.json"]["TP"]
    tab = public["security-final-outcome-cross-tab.json"]["truth_by_outcome"]
    assert sum(sum(row.values()) for row in tab.values()) == 200
    for name, value in public.items():
        path = tmp_path / name
        path.write_text(json.dumps(value))
    e.prediction.privacy(list(tmp_path.glob("*.json")))


def test_dev_final_delta_arithmetic():
    final = dict(
        precision=0.8,
        effective_positive_recovery=0.5,
        effective_negative_correctness=0,
        definitive_coverage=0.2,
        effective_correctness=0.2,
        nondefinitive_rate=0.8,
    )
    value = e.comparison(final)
    for key in final:
        assert value["deltas_FINAL_minus_DEV"][key] == pytest.approx(final[key] - value["DEV"][key])
    assert value["P029_FINAL_EFFECTIVENESS"] == "NOT_EVALUATED"


@pytest.mark.parametrize(
    "kind", ["truth", "review", "adjudication", "construction", "DEV", "credentials"]
)
def test_protected_inputs_stay_denied(kind):
    paths = {
        "truth": e.TRUTH.parents[1] / "human-truth-300.json",
        "review": e.TRUTH.parents[2] / "responses/A/denied.json",
        "adjudication": e.TRUTH.parents[2] / "adjudication/responses/denied.json",
        "construction": e.benchmark.PRIVATE / "coordinator/denied.json",
        "DEV": e.baseline.PRIVATE / "joined-dev.json",
        "credentials": Path(".env"),
    }
    with pytest.raises(PermissionError):
        e.TruthGate().audit("open", (str(paths[kind]), "r", 0))


def test_truth_direct_access_denied_before_gate():
    with pytest.raises(PermissionError, match="CHRONOLOGY"):
        e.TruthGate().audit("open", (str(e.TRUTH), "r", 0))


def test_provider_and_worker_execution_denied():
    for event, args in [("socket.connect", ()), ("subprocess.Popen", ("security_final_worker",))]:
        with pytest.raises(PermissionError):
            e.TruthGate().audit(event, args)
    assert set(e.ZERO.values()) == {0}


def test_no_analyzer_invocation_in_evaluation_source():
    source = inspect.getsource(e)
    assert ".analyze(" not in source
    assert "SecurityAnalyzerV" not in source
    assert "metric_protocol()" in source


def test_p034_exact_freeze_candidate_and_architecture():
    value = e.verify_inputs()
    assert value["prediction_registry_fingerprint"] == e.REGISTRY_FP
    assert value["candidate_verified"] is value["prediction_writer_closed"] is True
    assert value["history"]["status"] == "PASS"


def test_private_git_exclusion():
    assert not subprocess.check_output(["git", "ls-files", "--", str(e.PRIVATE)])
    assert subprocess.run(["git", "check-ignore", "-q", str(e.PRIVATE / "probe")]).returncode == 0


@pytest.mark.parametrize("problem", ["duplicate", "unknown", "distribution", "rationale"])
def test_invalid_truth_rejected(dataset, problem):
    registry, _, truth = dataset
    if problem == "duplicate":
        truth["rows"][1] = truth["rows"][0]
    elif problem == "unknown":
        truth["rows"][0]["case_id"] = "sc-" + "f" * 24
    elif problem == "distribution":
        truth["rows"][0]["final_label"] = "NEGATIVE"
    else:
        truth["rows"][0]["rationale"] = "forbidden"
    truth = e.boundary.seal({k: v for k, v in truth.items() if k != "fingerprint"})
    with pytest.raises(ValueError):
        e.validate_truth(truth, {r["case_id"] for r in registry["rows"]})


def test_analyzer_profile_blocks_entry():
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_name="analyze"),
        f_globals={"__name__": "archguard.security.analyzer_v3"},
    )
    with pytest.raises(PermissionError, match="REEXECUTION"):
        e.deny_analyzer(frame, "call", None)


def test_private_writer_closure(tmp_path, monkeypatch):
    monkeypatch.setattr(e, "PRIVATE", tmp_path)
    path = tmp_path / "joined-final.json"
    e.boundary.write_new(path, e.boundary.seal(dict(rows=[])))
    (tmp_path / "quality").mkdir()
    e.close_private()
    try:
        with pytest.raises(PermissionError):
            path.write_text("mutation")
        assert not path.stat().st_mode & 0o222
        assert not tmp_path.stat().st_mode & 0o222
    finally:
        tmp_path.chmod(0o700)
        path.chmod(0o600)


def test_profile_removed_before_interpreter_shutdown():
    code = """
import sys
from archguard.infrastructure import security_final_evaluation as e
sys.argv = ['p035', 'invalid-action']
try:
    e.main()
except ValueError:
    pass
else:
    raise AssertionError('unknown action accepted')
assert sys.getprofile() is None
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    assert result.returncode == 0, result.stderr.decode()
    assert not result.stderr
