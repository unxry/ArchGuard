"""P019 prospective design, independent truth, scope and process capabilities."""

import copy
import json
from pathlib import Path

import pytest

from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.hybrid.calibration import numeric_values
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.benchmark import component_holdout as domain
from archguard.benchmark.oss.models import digest
from archguard.infrastructure import component_holdout as infra
from archguard.infrastructure.calibration import load_policy
from archguard.infrastructure.semantic_positive_evaluation_freeze import evaluation_io

RULES = tuple(f"ARCH00{i}" for i in range(1, 6)) + tuple(f"ARCH10{i}" for i in range(1, 6))


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("positive", [False, True])
def test_independent_predicates(rule, positive):
    for index in range(5):
        facts = domain.topology(rule, index, positive)
        assert domain.oracle(rule, facts, domain.specification(rule)) is positive
        ArchitectureSpecification.model_validate(domain.specification(rule)["spec"])


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("language", ["JAVA", "TYPESCRIPT"])
def test_source_iam_adjacency_and_replay(tmp_path, rule, language):
    facts = domain.topology(rule, 0, True)
    files = domain.sources("abc123def456789", language, facts)
    for name, text in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    iam, receipt = infra.build(tmp_path, "p019-engineering-test-" + rule + language)
    observed = infra.normalized(iam)
    assert observed["edges"] == facts["edges"]
    assert observed["nodes"] == facts["nodes"]
    assert receipt["status"] == "VALID" and receipt["replay"]
    assert all(observed["methods"][i] == n for i, n in enumerate(facts["methods"]))


def design():
    result = []
    for r in domain.recipes(tuple(domain.TRAIN_FAMILIES)):
        parts = (r["track"], r["family"], r["language"], r["index"])
        result.append(
            r
            | dict(
                case_id=domain.identity("fixed", "case", *parts, r["positive"]),
                pair_id=domain.identity("fixed", "pair", *parts),
                truth=r["positive"],
            )
        )
    return result


def test_balanced_fresh_design_and_deterministic_ids():
    rows = design()
    domain.validate_design(rows, tuple(domain.TRAIN_FAMILIES))
    assert rows == design() and len(rows) == 180
    assert len({r["pair_id"] for r in rows}) == 90
    assert sum(r["truth"] for r in rows) == 90
    assert all("POSITIVE" not in r["case_id"] for r in rows)
    a = domain.sources("111111111111aaaa", "JAVA", domain.topology("ARCH101", 0, True))
    b = domain.sources("222222222222bbbb", "JAVA", domain.topology("ARCH101", 0, True))
    assert not set(a.values()) & set(b.values())


@pytest.mark.parametrize("defect", ["duplicate", "unbalanced", "missing", "pair"])
def test_reject_malformed_design(defect):
    rows = design()
    if defect == "duplicate":
        rows[0]["case_id"] = rows[1]["case_id"]
    elif defect == "unbalanced":
        rows[0]["truth"] = rows[1]["truth"]
    elif defect == "missing":
        rows.pop()
    else:
        rows[0]["language"] = "TYPESCRIPT"
    with pytest.raises(ValueError):
        domain.validate_design(rows, tuple(domain.TRAIN_FAMILIES))


def test_oracle_independence_and_no_detector_truth_imports():
    text = Path(domain.__file__).read_text()
    assert "from archguard.architecture" not in text
    assert "GraphAnalyzer" not in text and "StaticConformanceAnalyzer" not in text
    assert all(v is None for v in GraphAnalysisConfig().candidates.model_dump().values())
    facts = domain.topology("ARCH003", 0, True)
    assert domain.oracle("ARCH003", facts, domain.specification("ARCH003"))
    facts["edges"] = [e for e in facts["edges"] if e != (2, 0)]
    assert not domain.oracle("ARCH003", facts, domain.specification("ARCH003"))


def row(truth, prediction, scope="BINARY", error=None):
    return dict(truth=truth, prediction=prediction, scope=scope, error=error, seconds=0.25)


def test_scope_and_confusion_counts():
    rows = [
        row(True, True),
        row(False, True),
        row(False, False),
        row(True, False),
        row(True, None, "UNSUPPORTED"),
        row(True, None, "CANDIDATE_ONLY"),
        row(True, None, error="PARTIAL"),
    ]
    values = domain.metrics(rows)
    assert [values[k] for k in ("TP", "FP", "TN", "FN")] == [1, 1, 1, 1]
    assert values["coverage"] == 4 / 5 and values["errors"] == 1
    assert values["F1"] == 0.5 and values["applicability_coverage"] == 5 / 7


@pytest.mark.parametrize(
    "key", ["Precision", "Recall", "F1", "Specificity", "FPR", "FNR", "coverage"]
)
def test_empty_denominators_are_null(key):
    assert domain.metrics([])[key] is None


@pytest.mark.parametrize(
    "forbidden",
    ["human-truth.json", "p017/result.json", "p018/intent.json", "pair-map.json", ".env.ai.local"],
)
def test_worker_truth_and_secret_firewall(tmp_path, forbidden):
    experiments = tmp_path / "experiments"
    allowed, output = experiments / "iam", experiments / "output"
    allowed.mkdir(parents=True)
    target = experiments / forbidden
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("sensitive fixture")
    with evaluation_io(experiments, (allowed,), output), pytest.raises(PermissionError):
        target.read_bytes()


def test_frozen_input_writes_and_network_denied(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text("frozen")
    with (
        evaluation_io(tmp_path, (input_path,), tmp_path / "output"),
        pytest.raises(PermissionError),
    ):
        input_path.write_text("changed")
    for action in ("socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"):
        with pytest.raises(PermissionError):
            infra.offline(action, ())


def test_v2_exact_artifact_fixed_transform_no_leakage():
    if not infra.POLICY.exists():
        pytest.skip("local frozen V2 artifact not present")
    artifact = load_policy(infra.POLICY)
    assert artifact.fingerprint == domain.V2
    assert artifact.threshold == 0.398762395289
    assert len(artifact.train_families) == 4
    assert (
        artifact.preprocessor.fingerprint
        == "9f9493e70cf7cf21f259fd020471db698834fc6b5be7601bead87eb980461ae7"
    )
    assert not any(
        "selection" in name or "ARCH" in name for name in artifact.preprocessor.selected_features
    )
    values = {name: None for name in artifact.preprocessor.selected_features}
    ordered = numeric_values(values, artifact.preprocessor.feature_spec)
    assert artifact.preprocessor.transform(ordered) == artifact.preprocessor.transform(ordered)
    assert len(artifact.model.coefficients) == len(artifact.preprocessor.output_features)


@pytest.mark.parametrize(
    "field", ["case_id", "pair_id", "rationale", "reviewer_id", "source_text", "api_key"]
)
def test_public_private_separation(tmp_path, field):
    path = tmp_path / "aggregate.json"
    path.write_text(json.dumps({field: "private"}))
    with pytest.raises(ValueError):
        infra.public_privacy([path])


def test_public_credentials_rejected(tmp_path):
    path = tmp_path / "aggregate.json"
    path.write_text(json.dumps({"credential": "sk-" + "fake_fixture_value_" * 3}))
    with pytest.raises(ValueError):
        infra.public_privacy([path])
    path.write_text(json.dumps({"cases": 180, "fingerprint": "a" * 64}))
    infra.public_privacy([path])


def test_audit_output_before_join_and_tamper(tmp_path, monkeypatch):
    monkeypatch.setattr(infra, "AUDIT", tmp_path / "audit.jsonl")
    monkeypatch.setattr(infra, "read", lambda _: {"capability": {"v2_allowed": True}})
    for name in (
        "PLAN_FROZEN",
        "HOLDOUT_FROZEN",
        "LABELS_SEALED",
        "STATIC_EXECUTION",
        "STATIC_OUTPUT_FROZEN",
        "GRAPH_EXECUTION",
        "GRAPH_OUTPUT_FROZEN",
        "V2_EXECUTION",
        "V2_OUTPUT_FROZEN",
        "FIRST_TRUTH_JOIN",
        "METRICS",
    ):
        infra.event(name)
    assert len(infra.chronology()) == 11
    with pytest.raises(ValueError):
        infra.event("STATIC_EXECUTION")
    rows = [json.loads(line) for line in infra.AUDIT.read_text().splitlines()]
    rows[5]["event"] = "FIRST_TRUTH_JOIN"
    infra.AUDIT.write_text("\n".join(json.dumps(r) for r in rows))
    with pytest.raises(ValueError):
        infra.chronology()


def test_early_truth_join_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(infra, "AUDIT", tmp_path / "audit.jsonl")
    monkeypatch.setattr(infra, "read", lambda _: {"capability": {"v2_allowed": True}})
    infra.event("PLAN_FROZEN")
    infra.event("FIRST_TRUTH_JOIN")
    with pytest.raises(ValueError):
        infra.chronology()


def test_plan_is_sealed_before_data_and_private_membership_absent():
    capability = dict(v2_allowed=True, train_families=list(domain.TRAIN_FAMILIES))
    value = domain.plan(digest("seed"), capability)
    assert value["fingerprint"] == digest({k: v for k, v in value.items() if k != "fingerprint"})
    assert value["track_a"]["cases"] == 100 and value["track_b"]["cases"] == 80
    assert "case_id" not in json.dumps(value) and "pair_id" not in json.dumps(value)
    assert domain.plan(digest("seed"), copy.deepcopy(capability)) == value


@pytest.mark.parametrize("field", ["truth", "rationale", "positive", "family", "pair_id"])
def test_blind_manifest_rejects_truth_or_membership(field):
    row = dict(
        case_id="opaque",
        rule="ARCH003",
        language="JAVA",
        iam_file="opaque.json",
        subjects={},
        spec={},
        iam_fingerprint="a" * 64,
    )
    infra.blind_manifest(dict(rows=[row], fingerprint="b" * 64))
    row[field] = "forbidden"
    with pytest.raises(ValueError):
        infra.blind_manifest(dict(rows=[row], fingerprint="b" * 64))


def test_missing_v2_continues_direct_baselines(monkeypatch):
    def missing():
        raise FileNotFoundError("fixture")

    monkeypatch.setattr(infra, "_v2_capability", missing)
    value = infra.capability()
    assert not value["v2_allowed"] and not value["train_families"]
    assert domain.plan(digest("seed"), value)["track_a"]["cases"] == 100


def test_completed_local_freezes_and_exact100_evidence():
    if not (infra.BASE / "p019-component-registry-v1.json").exists():
        pytest.skip("local private P019 data not present")
    assert infra.verify_results()["verification"] == "PASS"
    artifact = infra.read(infra.OUTPUT / "semantic-evidence/evidence-v1.json")
    assert len(artifact["records"]) == 100
    assert not artifact["human_truth_accessed"] and not artifact["p017_correctness_accessed"]
    assert not artifact["p018_intent_accessed"] and not artifact["semantic_decisions_created"]


def test_plan_freezes_existing_engine_paths_and_rejects_repeat(tmp_path, monkeypatch):
    monkeypatch.setattr(infra, "PRIVATE", tmp_path / "private")
    monkeypatch.setattr(infra, "PLAN", tmp_path / "plan.json")
    monkeypatch.setattr(infra, "AUDIT", tmp_path / "audit.jsonl")
    monkeypatch.setattr(infra.subprocess, "check_output", lambda *args, **kwargs: "")
    monkeypatch.setattr(infra, "old_guards", lambda: {})
    monkeypatch.setattr(infra, "lineage", lambda: ["verified"])
    monkeypatch.setattr(infra, "capability", lambda: dict(v2_allowed=False, train_families=[]))
    result = infra.prepare_plan()
    assert infra.read(infra.PLAN)["fingerprint"] == result["plan"]
    assert len(infra.read(infra.PLAN)["capability"]["engine_source_hashes"]) == 10
    with pytest.raises(ValueError, match="already frozen"):
        infra.prepare_plan()
