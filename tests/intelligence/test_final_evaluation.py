"""Synthetic final chronology, selected-only prediction and all-case metric semantics."""

import ast
from collections import Counter
from pathlib import Path

import pytest

from archguard.benchmark import final_evaluation as stats
from archguard.benchmark import unified_hybrid as domain
from archguard.benchmark.oss.models import digest
from archguard.infrastructure import final_evaluation as final
from archguard.infrastructure import final_llm_continuation as guard
from archguard.infrastructure import final_llm_preflight as seal
from archguard.infrastructure import unified_human_review as io


def row(label, decision, index=0):
    return dict(
        case_id=digest(("synthetic-final", index)),
        label=label,
        rule="ARCH201",
        family="SEMANTIC",
        language="JAVA",
        predictions={
            method: dict(
                decision=decision,
                binary=1 if decision == "SUPPORTED" else 0 if decision == "NOT_SUPPORTED" else None,
            )
            for method in stats.METHODS
        },
    )


@pytest.mark.parametrize("decision", stats.DECISIONS)
@pytest.mark.parametrize("label", [0, 1])
def test_every_categorical_primary_outcome(label, decision):
    m = stats.metrics([row(label, decision)], "A3")
    assert m["N"] == 1 and m["TP"] == int(label == 1 and decision == "SUPPORTED")
    assert m["FP"] == int(label == 0 and decision == "SUPPORTED")
    assert m["TN"] == int(label == 0 and decision == "NOT_SUPPORTED")
    assert m["FN"] == int(label == 1 and decision != "SUPPORTED")
    assert m["negative_nondefinitive"] == int(
        label == 0 and decision not in {"SUPPORTED", "NOT_SUPPORTED"}
    )
    assert m["technical_missing"] == int(decision in stats.MISSING)
    assert m["definitive_coverage"] == float(decision in {"SUPPORTED", "NOT_SUPPORTED"})


def test_exact_metrics_zero_denominators_and_no_new_accuracy():
    rows = [
        row(1, "SUPPORTED", 0),
        row(1, "NOT_SUPPORTED", 1),
        row(0, "SUPPORTED", 2),
        row(0, "NOT_SUPPORTED", 3),
        row(0, stats.MISSING[0], 4),
    ]
    m = stats.metrics(rows, "A3")
    assert (m["TP"], m["FP"], m["TN"], m["FN"]) == (1, 1, 1, 1)
    assert (
        m["Precision"] == m["Recall"] == m["F1"] == m["Specificity"] == m["FPR"] == m["FNR"] == 0.5
    )
    assert m["effective_correctness"] == 0.4 and m["definitive_coverage"] == 0.8
    assert m["applicability_rate"] is None and m["applicability_unknown"] == 1
    assert "Accuracy" not in m
    assert stats.metrics([], "A3")["F1"] is None
    assert stats.metrics([row(0, "INSUFFICIENT_CONTEXT")], "A3")["Specificity"] is None


@pytest.fixture
def closed(tmp_path, monkeypatch):
    for name in ("INPUT", "PRED", "RECEIPTS", "TRUTH", "JOIN", "RESULT"):
        monkeypatch.setattr(final, name, tmp_path / name.lower())
    for name in ("COHORT", "HUMAN_PUBLIC", "STRUCTURAL", "SEMANTIC", "PUBLIC"):
        monkeypatch.setattr(final, name, tmp_path / (name.lower() + ".json"))
    original = {
        method: tmp_path / "original-models" / (method + ".json") for method in stats.METHODS[3:]
    }
    monkeypatch.setattr(final, "models", lambda: original)
    matrix = []
    features = {name: 0.0 for names in domain.FEATURES.values() for name in names}
    for index in range(300):
        rule = domain.RULES[index // 20]
        missing = index in (298, 299)
        matrix.append(
            dict(
                case_id=digest(("synthetic", index)),
                execution_id=digest(("synthetic-execution", index)),
                rule=rule,
                family="NORMATIVE" if index < 100 else "GRAPH" if index < 200 else "SEMANTIC",
                language="JAVA" if index % 2 == 0 else "TYPESCRIPT",
                llm_decision=None if missing else "NOT_SUPPORTED",
                llm_technical_status=stats.MISSING[index - 298] if missing else "ACCEPTED",
                evidence=dict(
                    STATIC="NOT_SUPPORTED" if index < 100 else "NOT_APPLICABLE",
                    GRAPH="NOT_SUPPORTED" if index < 200 else "NOT_APPLICABLE",
                    LLM="INSUFFICIENT_EVIDENCE" if missing else "NOT_SUPPORTED",
                    static_proof=False,
                    cycle_proof=False,
                ),
                values=features
                | {name: None if missing else 0.0 for name in domain.FEATURES["LLM"]},
            )
        )
    parts = {
        "matrix.json": dict(rows=matrix),
        "analysis.json": dict(
            scope_conditional=dict(
                STATIC=["ARCH001", "ARCH002", "ARCH004", "ARCH005"],
                GRAPH=["ARCH003", *domain.RULES[5:10]],
            )
        ),
    }
    components = {
        "A4": ["STATIC", "GRAPH"],
        "A5": ["STATIC", "LLM"],
        "A6": ["GRAPH", "LLM"],
        "A7": ["STATIC", "GRAPH", "LLM"],
    }
    for method in stats.METHODS[3:]:
        artifact = dict(
            components=components[method],
            method="H0" if method == "A4" else "H2",
            threshold=None if method == "A4" else 0.75 if method == "A7" else 0.5,
        )
        if method != "A4":
            artifact.update(columns=[], coefficients=[], intercept=0)
        model = dict(configuration=method, method=artifact["method"], artifact=artifact)
        seal.seal(original[method], model)
        parts[f"models/{method}.json"] = model
    parts["metadata.json"] = dict(
        original_model_hashes={key: io.sha(path) for key, path in original.items()},
        model_lock_fingerprint=digest("synthetic-lock"),
        source_bindings={},
        truth_mounted=False,
        final_truth_reads=0,
    )
    final.freeze_directory(final.INPUT, parts)
    structural = seal.seal(
        final.STRUCTURAL,
        dict(
            rows=[
                dict(
                    scientific_case_id=r["case_id"],
                    category="POSITIVE" if i % 2 == 0 else "NEGATIVE",
                )
                for i, r in enumerate(matrix[:200])
            ]
        ),
    )
    semantic = seal.seal(
        final.SEMANTIC,
        dict(
            cases=[
                dict(
                    scientific_case_id=r["case_id"],
                    final_category="POSITIVE" if i % 2 == 0 else "NEGATIVE",
                )
                for i, r in enumerate(matrix[200:])
            ]
        ),
    )
    seal.seal(final.COHORT, dict(fingerprints=dict(structural_truth=structural["fingerprint"])))
    pub = seal.seal(
        final.HUMAN_PUBLIC,
        dict(truth_fingerprint=semantic["fingerprint"], truth_raw_sha256=io.sha(final.SEMANTIC)),
    )
    monkeypatch.setattr(final, "HUMAN_PUBLIC_FP", pub["fingerprint"])
    yield matrix, original
    if final.PRED.exists():
        final.PRED.chmod(0o700)


def test_truth_denied_until_full_prediction_receipt(closed):
    with pytest.raises((OSError, PermissionError)):
        final.open_truth()
    assert not final.TRUTH.exists()
    with guard.scope((final.INPUT,), (final.PRED,)):
        for path in (final.STRUCTURAL, final.SEMANTIC, Path(".env.ai.local")):
            with pytest.raises(PermissionError):
                path.read_bytes()
        with pytest.raises(PermissionError):
            guard.core.audit_hook("socket.connect", ())
        for path in closed[1].values():
            with pytest.raises(PermissionError):
                path.write_text("mutation")


def test_prediction_freeze_selected_models_no_truth_and_no_reprediction(closed, monkeypatch):
    monkeypatch.setattr(final.selected, "fitted_candidates", lambda *_: pytest.fail("fit"))
    monkeypatch.setattr(final.selected, "validation_selection", lambda *_: pytest.fail("selection"))
    before = {key: io.sha(path) for key, path in closed[1].items()}
    result = final.predict()
    assert result["final_truth_reads"] == 0 and final.prediction_gate()["writer_closed"]
    assert before == {key: io.sha(path) for key, path in closed[1].items()}
    predictions = io.read_seal(final.PRED / "A3.json")["rows"]
    assert sum(r["decision"] in stats.MISSING for r in predictions) == 2
    assert all(r["binary"] is None for r in predictions if r["decision"] in stats.MISSING)
    with pytest.raises(PermissionError):
        final.predict()
    final.open_truth()
    with pytest.raises(PermissionError):
        final.predict()
    with (
        guard.scope((final.PRED, final.TRUTH), (final.RESULT,)),
        pytest.raises(PermissionError),
    ):
        (final.PRED / "A7.json").write_text("changed")


def test_model_mutation_stops_before_truth_open(closed):
    final.predict()
    next(iter(closed[1].values())).write_text("mutation")
    with pytest.raises(io.ReviewBlocked):
        final.open_truth()
    assert not final.TRUTH.exists()


def test_blind_matrix_cannot_contain_truth_or_semantic_missing_imputation(closed):
    rows = closed[0]
    rows[0]["label"] = 1
    with pytest.raises(ValueError):
        final.blind_matrix(rows)
    del rows[0]["label"]
    rows[-1]["llm_decision"] = "NOT_SUPPORTED"
    with pytest.raises(ValueError):
        final.blind_matrix(rows)


def test_join_is_stable_and_reordering_invariant(closed):
    final.predict()
    final.open_truth()
    truth = io.read_seal(final.TRUTH / "truth.json")["rows"]
    predictions = {
        method: io.read_seal(final.PRED / f"{method}.json")["rows"] for method in stats.METHODS
    }
    a = final.join_predictions(truth, predictions)
    b = final.join_predictions(
        list(reversed(truth)), {key: list(reversed(rows)) for key, rows in predictions.items()}
    )
    assert a == b and len(a) == 300
    assert Counter(r["rule"] for r in a) == {rule: 20 for rule in domain.RULES}
    results = stats.aggregate(
        a, ["ARCH001", "ARCH002", "ARCH004", "ARCH005"], ["ARCH003", *domain.RULES[5:10]]
    )
    assert results["final-native-scope-metrics.json"]["methods"]["A3_AVAILABLE_ONLY"]["N"] == 298
    missing = results["final-coverage-metrics.json"]["missingness"]
    assert missing["N"] == 2 and missing["positive"] == missing["negative"] == 1
    for group in results["final-paired-comparisons.json"]["comparisons"].values():
        assert (
            sum(group[key] for key in ("both_correct", "A7_only", "comparator_only", "neither"))
            == 300
        )
    assert stats.paired(a, "A3") == stats.paired(list(reversed(a)), "A3")
    predictions["A3"].pop()
    with pytest.raises(ValueError):
        final.join_predictions(truth, predictions)


def test_full_offline_reproducibility_no_predict_after_truth(closed, monkeypatch):
    final.predict()
    final.open_truth()
    measurements = io.read_seal(final.RECEIPTS / "resource-measurements.json")
    rq5 = dict(
        input_tokens=dict(paired_N=99, relative_reduction_first_vs_second=0.5),
        cost_usd=dict(relative_reduction_first_vs_second=0.3),
        effectiveness_difference=dict(precision=-0.03, F1_definitive=-0.02),
    )
    monkeypatch.setattr(
        final,
        "prior_evidence",
        lambda: dict(
            rq5=rq5,
            rq5_fingerprint=digest("synthetic-rq5"),
            graph_prior_fingerprint=digest("synthetic-graph"),
            resource={key: value for key, value in measurements.items() if key != "fingerprint"},
        ),
    )
    monkeypatch.setattr(final, "prediction_row", lambda *_: pytest.fail("repredict"))
    before = final.inventory(final.PRED)
    first = final.evaluate()
    second = final.evaluate()
    assert first == second and final.inventory(final.PRED) == before
    assert first["provider_calls"] == first["credential_reads"] == first["model_fitting"] == 0
    assert first["status"] == "P025_FINAL_ARCHITECTURE_EVALUATION_COMPLETE"


@pytest.mark.parametrize("kind", ["supported", "mixed", "unsupported"])
def test_predeclared_hypothesis_rule_exact_no_tolerance(kind):
    raw = [row(1, "SUPPORTED", 0), row(1, "NOT_SUPPORTED", 1), row(0, "NOT_SUPPORTED", 2)]
    base = stats.metrics(raw, "A1")
    perfect = stats.metrics(
        [row(1, "SUPPORTED", 0), row(1, "SUPPORTED", 1), row(0, "NOT_SUPPORTED", 2)], "A7"
    )
    primary = {method: base for method in stats.METHODS}
    if kind != "unsupported":
        primary["A7"] = perfect
    if kind == "mixed":
        primary["A3"] = perfect
    result = stats.hypothesis(primary)
    assert (
        result["final_status"]
        == {
            "supported": "SUPPORTED",
            "mixed": "PARTIALLY_SUPPORTED",
            "unsupported": "NOT_SUPPORTED",
        }[kind]
    )
    assert result["input_metric_fingerprint"] == digest(primary)


def test_final_path_has_no_fitting_selection_provider_or_credential_constructor():
    forbidden = {
        "fit",
        "fit_candidate",
        "fitted_candidates",
        "validation_selection",
        "select_candidate",
        "AIProviderSettings",
        "OpenAITransport",
    }
    for source in final.SOURCES[:3]:
        tree = ast.parse(Path(source).read_text())
        assert not any(
            isinstance(n, ast.Call)
            and (
                (isinstance(n.func, ast.Attribute) and n.func.attr in forbidden)
                or (isinstance(n.func, ast.Name) and n.func.id in forbidden)
            )
            for n in ast.walk(tree)
        )


@pytest.mark.parametrize("proof", ["static_proof", "cycle_proof"])
def test_frozen_unconditional_precedence(closed, proof):
    sample = closed[0][0]
    sample["evidence"][proof] = True
    model = io.read_seal(final.INPUT / "models/A7.json")
    model["artifact"]["intercept"] = -100
    assert final.prediction_row(sample, "A7", model)["decision"] == "SUPPORTED"


def test_duplicate_or_cross_method_rule_join_rejected(closed):
    final.predict()
    final.open_truth()
    truth = io.read_seal(final.TRUTH / "truth.json")["rows"]
    predictions = {
        method: io.read_seal(final.PRED / f"{method}.json")["rows"] for method in stats.METHODS
    }
    predictions["A7"][0]["rule"] = "ARCH205"
    with pytest.raises(ValueError):
        final.join_predictions(truth, predictions)
    with pytest.raises(ValueError):
        final.join_predictions(truth + [truth[0]], predictions)
