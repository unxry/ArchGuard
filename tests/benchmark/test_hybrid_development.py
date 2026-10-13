"""Synthetic P023 selection/fit/isolation tests; no real validation is queried."""

import copy
from pathlib import Path

import pytest

from archguard.benchmark import unified_hybrid as d
from archguard.benchmark.oss.models import canonical, digest
from archguard.calibration import hybrid_development as k
from archguard.infrastructure import hybrid_development as i
from archguard.infrastructure import unified_human_review as io


def rows(split="TRAIN", n=12):
    result = []
    for num in range(n):
        label = num % 2
        decision = "SUPPORTED" if label else "NOT_SUPPORTED"
        values = {name: float(label) for name in k.NAMES}
        values.update({name: 0.0 for name in d.FEATURES["LLM"]})
        values["llm.supported" if label else "llm.not_supported"] = 1.0
        values["llm.evidence_available"] = 1.0
        values["graph.Ca"] = None if num % 3 == 0 else float(num)
        result.append(
            dict(
                case_id=digest((split, num)),
                project_id=digest(("project", split, num)),
                rule_id="ARCH101",
                language="JAVA",
                cohort="SYNTHETIC",
                split=split,
                category="POSITIVE" if label else "NEGATIVE",
                label=label,
                llm_bound=True,
                llm_decision=decision,
                values=values,
                evidence=dict(
                    STATIC="NOT_APPLICABLE",
                    GRAPH=decision,
                    LLM=decision,
                    static_proof=False,
                    cycle_proof=False,
                ),
            )
        )
    return result


def test_frozen_protocol_sources_and_fingerprints():
    r = i.protocol_gate()
    assert (
        r["hybrid_feature_schema"]
        == digest(d.FEATURES)
        == "1febc401be51406691f4816557e504b0a5f3698b29473951c497adc9e12728f2"
    )
    assert (
        d.hybrid_protocol()["threshold"]
        == "TRAIN_INTERNAL_FIXED_GRID_0.25_0.5_0.75_MAX_F1_THEN_PRECISION_THEN_CLOSEST_TO_0.5"
    )


@pytest.mark.parametrize(
    "field",
    [
        "case_id",
        "project_id",
        "reviewer",
        "intent",
        "mutation",
        "control",
        "expected_label",
        "correctness",
        "TP",
        "FP",
        "TN",
        "FN",
        "final_membership",
        "cost",
        "latency",
        "response_id",
        "rule_id",
        "confidence",
        "severity",
    ],
)
def test_feature_whitelist_refuses_shortcuts(field):
    data = rows()
    data[0]["values"][field] = 1.0
    with pytest.raises(ValueError):
        k.fitted_candidates(data, digest("synthetic-code"))


@pytest.mark.parametrize("split", ["VALIDATION", "TEST"])
def test_training_never_uses_other_partitions(split):
    with pytest.raises(ValueError):
        k.fitted_candidates(rows(split), digest("synthetic-code"))


def test_missing_llm_never_imputed_negative():
    data = rows()
    data[0]["llm_bound"] = False
    with pytest.raises(ValueError):
        k.fitted_candidates(data, digest("synthetic-code"))


def test_independent_ablations_unit_weights_l2_solver_and_reproducibility(monkeypatch):
    original = k.fit_candidate
    calls = []

    def fit(data, method, components):
        calls.append((method, components))
        assert all(r["split"] == "TRAIN" for r in data)
        return original(data, method, components)

    monkeypatch.setattr(k, "fit_candidate", fit)
    models = k.fitted_candidates(rows(), digest("synthetic-code"))
    assert calls == [(m, c) for c in d.ABLATIONS[3:] for m in ("H1", "H2")]
    assert canonical(models) == canonical(
        k.fitted_candidates(list(reversed(rows())), digest("synthetic-code"))
    )
    for model in models.values():
        assert model["threshold_state"]["selected"] in (None, 0.25, 0.5, 0.75)
        if model["method"] != "H0":
            assert model["solver"]["observation_weights"] == "UNIT" and model["solver"]["L2"] == 1
            assert model["solver"]["converged"] is True
            assert len(model["artifact"]["coefficients"]) == 2 * sum(
                len(d.FEATURES[c]) for c in model["artifact"]["components"]
            )


@pytest.mark.parametrize("proof,component", [("static_proof", "STATIC"), ("cycle_proof", "GRAPH")])
@pytest.mark.parametrize("method", ["H0", "H1", "H2"])
def test_positive_precedence_respects_included_components(proof, component, method):
    models = k.fitted_candidates(rows(), digest("synthetic-code"))
    r = rows()[0]
    r["evidence"].update(STATIC="NOT_SUPPORTED", GRAPH="NOT_SUPPORTED", LLM="NOT_SUPPORTED")
    r["evidence"][proof] = True
    for config, parts in list(k.ABLATIONS.items())[3:]:
        model = copy.deepcopy(models[f"{config}-{method}"])
        if method != "H0":
            model["artifact"].update(
                coefficients=[0.0] * len(model["artifact"]["coefficients"]), intercept=-100.0
            )
        assert k.prediction(r, model) == ("SUPPORTED" if component in parts else "NOT_SUPPORTED")


@pytest.mark.parametrize("llm", ["INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"])
def test_abstention_and_non_applicability_not_negative(llm):
    data = rows()
    r = data[0]
    r["llm_decision"] = llm
    for name, state in zip(d.FEATURES["LLM"][:4], k.LLM_STATES, strict=True):
        r["values"][name] = float(state == llm)
    r["evidence"].update(
        STATIC="NOT_APPLICABLE",
        GRAPH="NOT_APPLICABLE",
        LLM="INSUFFICIENT_EVIDENCE" if llm == "INSUFFICIENT_CONTEXT" else llm,
    )
    models = k.fitted_candidates(data, digest("synthetic-code"))
    for model in models.values():
        out = k.prediction(r, model)
        assert out == (
            "INSUFFICIENT_EVIDENCE"
            if llm == "INSUFFICIENT_CONTEXT" and "LLM" in model["artifact"]["components"]
            else "NOT_APPLICABLE"
        )


def test_nonbinary_separate_and_primary_misses_abstaining_positives():
    data = rows()
    data[0].update(category="UNCERTAIN", label=None)
    m = k.fitted_candidates(data, digest("synthetic-code"))
    assert all(x["train_binary_cases"] == 11 for x in m.values())
    metrics = k.metrics(data, ["INSUFFICIENT_EVIDENCE"] * 12)
    assert metrics["N"] == 11 and metrics["FN"] == 6 and metrics["TN"] == 0
    assert (
        metrics["Precision"] is None and metrics["F1"] == 0 and metrics["definitive_coverage"] == 0
    )


def test_exact_selection_order_ties_nulls_and_reordered_dictionary():
    scores = {
        m: dict(
            F1=0.5, Precision=0.5, effective_correctness=0.5, Recall=1.0, definitive_coverage=1.0
        )
        for m in ("H0", "H1", "H2")
    }
    assert d.select_candidate(dict(reversed(list(scores.items()))), "VALIDATION") == "H0"
    scores["H2"].update(Recall=0.0, definitive_coverage=0.0)
    scores["H0"].update(Recall=None, definitive_coverage=None)
    assert d.select_candidate(scores, "VALIDATION") == "H0"
    scores["H2"]["F1"] += 1e-13
    assert d.select_candidate(scores, "VALIDATION") == "H0"
    scores["H1"]["Precision"] += 0.1
    assert d.select_candidate(scores, "VALIDATION") == "H1"
    scores["H2"]["Precision"] += 0.1
    scores["H2"]["effective_correctness"] += 0.1
    assert d.select_candidate(scores, "VALIDATION") == "H2"
    scores["H2"]["F1"] = None
    assert d.select_candidate(scores, "VALIDATION") == "H1"


def test_closed_root_train_phase_denies_validation_final_truth_and_credentials(tmp_path):
    inputs = tmp_path / "inputs"
    output = tmp_path / "output"
    inputs.mkdir()
    output.mkdir()
    for path in (
        inputs / "validation-labels.json",
        io.FINAL / "truth.json",
        io.PRIVATE / "human-intake/accepted/A/v0001/canonical-response.json",
        io.PRIVATE / "coordinator/construction-intent.json",
        Path(".env.ai.local"),
        tmp_path / "final-evidence.json",
    ):
        with i.training_scope(inputs, output, "FIT"), pytest.raises(PermissionError):
            i.audit_hook("open", (str(path), "r", 0))
    with i.training_scope(inputs, output, "FIT"), pytest.raises(PermissionError):
        i.audit_hook("socket.connect", ())


def test_fit_freeze_precedes_validation_no_refit_and_double_reproduction(tmp_path, monkeypatch):
    inputs = tmp_path / "inputs"
    out = tmp_path / "out"
    inputs.mkdir()
    out.mkdir()
    train = rows()
    val = rows("VALIDATION", 6)
    features = [{k: v for k, v in r.items() if k not in {"label", "category"}} for r in val]
    labels = [{k: r[k] for k in ("case_id", "label", "category")} for r in reversed(val)]
    data = {
        "train.json": dict(rows=train),
        "validation-features.json": dict(rows=features),
        "validation-labels.json": dict(rows=labels),
    }
    for name, payload in data.items():
        io.append_seal(inputs / name, payload)
    metadata = dict(
        data_files={n: digest(p) for n, p in data.items()},
        implementation_fingerprint=digest("synthetic-code"),
        selection_rule_fingerprint=digest("selection"),
        split_fingerprint=digest("split"),
        llm_evidence_fingerprint=digest("llm"),
        truth_binding_fingerprint=digest("truth"),
        join_fingerprint=digest("join"),
        component_fingerprint=digest("components"),
        feature_schema_fingerprint=digest(d.FEATURES),
        hybrid_protocol_fingerprint=digest(d.hybrid_protocol()),
        ablation_protocol_fingerprint=digest(d.ABLATIONS),
        development_cases=18,
        structural=12,
        semantic=6,
        TRAIN=12,
        VALIDATION=6,
        train_projects=12,
        validation_projects=6,
        project_overlap=0,
        final_overlap=0,
    )
    original = k.validation_selection

    def select(validation, models):
        assert (out / "primary/train-candidates-freeze.json").exists() and (
            out / "reproduction/train-candidates-freeze.json"
        ).exists()
        assert i._VALIDATION_OPENS.get() == 1
        return original(validation, models)

    monkeypatch.setattr(k, "validation_selection", select)
    result = i.fit_runs(inputs, out, metadata)
    assert (
        result["validation_opens"] == 1
        and not result["post_selection_refit"]
        and not result["final_truth_reads"]
    )
    for config, entry in result["selected_models"].items():
        assert io.read_seal(out / "selected" / f"{config}.json") == io.read_seal(
            out / "primary/candidates" / f"{config}-{entry['selected_family']}.json"
        )
    receipt = io.read_seal(out / "reproducibility.json")
    assert all(
        receipt[k]
        for k in ("candidate_equal", "metrics_equal", "selected_equal", "preprocessing_equal")
    )


def test_validation_changes_do_not_affect_train_preprocessing():
    train = rows()
    first = k.fitted_candidates(train, digest("code"))
    val = rows("VALIDATION")
    val[0]["values"]["graph.Ca"] = 1e12
    k.validation_selection(val, first)
    assert canonical(first) == canonical(k.fitted_candidates(train, digest("code")))


def development_bundle():
    data = rows("TRAIN", 196) + rows("VALIDATION", 84)
    for row in data:
        row["cohort"] = "DEVELOPMENT"
    llm = [
        dict(case_id=r["case_id"], source="P022.LIVE" if n < 180 else "P016")
        for n, r in enumerate(data)
    ]
    truth = [
        dict(case_id=r["case_id"], source="P019" if n < 180 else "P015") for n, r in enumerate(data)
    ]
    return data, llm, truth


def test_280_case_development_join_coverage_and_stable_ids():
    data, llm, truth = development_bundle()
    k.development_contract(data, list(reversed(llm)), truth[100:] + truth[:100])
    assert len(data) == len(llm) == len(truth) == 280


@pytest.mark.parametrize(
    "corruption", ["missing_llm", "missing_truth", "duplicate", "final", "overlap", "split"]
)
def test_development_join_refuses_missing_duplicate_final_or_cross_split(corruption):
    data, llm, truth = development_bundle()
    if corruption == "missing_llm":
        llm.pop()
    elif corruption == "missing_truth":
        truth.pop()
    elif corruption == "duplicate":
        data[-1]["case_id"] = data[0]["case_id"]
    elif corruption == "final":
        data[-1]["cohort"] = "FINAL"
    elif corruption == "overlap":
        data[-1]["project_id"] = data[0]["project_id"]
    else:
        data[0]["split"] = "VALIDATION"
    with pytest.raises(ValueError):
        k.development_contract(data, llm, truth)


@pytest.mark.parametrize("field", ["llm_decision", "llm.supported", "evidence"])
def test_raw_llm_decision_feature_and_fusion_state_cannot_disagree(field):
    data = rows()
    if field == "llm_decision":
        data[0][field] = "INSUFFICIENT_CONTEXT"
    elif field == "evidence":
        data[0][field]["LLM"] = "NOT_APPLICABLE"
    else:
        data[0]["values"][field] = 1.0
    with pytest.raises(ValueError):
        k.fitted_candidates(data, digest("code"))


def test_solver_receives_unit_weights_l2_and_missing_indicator_order(monkeypatch):
    from archguard.calibration import unified

    original = unified.fit_coefficients
    calls = []

    def fit(x, y, weights, penalty, *, logistic):
        assert weights == (1.0,) * len(y) and penalty == 1.0
        calls.append(logistic)
        return original(x, y, weights, penalty, logistic=logistic)

    monkeypatch.setattr(unified, "fit_coefficients", fit)
    models = k.fitted_candidates(rows(), digest("code"))
    assert calls == [False, True] * 4
    artifact = models["A7-H2"]["artifact"]
    assert tuple(c["name"] for c in artifact["columns"]) == k.NAMES
    encoded = d.transform(rows()[0]["values"], artifact)
    missing_index = k.NAMES.index("graph.Ca")
    assert encoded[2 * missing_index + 1] == 1.0
    assert all(encoded[2 * n + 1] == 0.0 for n in range(len(k.NAMES)) if n != missing_index)
    final = rows()
    final[0].update(cohort="FINAL")
    final[0]["values"]["graph.Ca"] = 1e12
    with pytest.raises(ValueError):
        k.fitted_candidates(final, digest("code"))


def test_interrupted_execution_cannot_restart_or_refit(tmp_path, monkeypatch):
    marker = tmp_path / "control/start.json"
    monkeypatch.setattr(i, "RUN_CONTROL", marker)
    monkeypatch.setattr(i, "OUTPUT", tmp_path / "output")
    monkeypatch.setattr(i, "prepare", lambda: dict(implementation_fingerprint=digest("code")))
    calls = []

    def interrupted(destination, build):
        calls.append(destination)
        raise ValueError("synthetic interruption")

    monkeypatch.setattr(i, "atomic_directory", interrupted)
    with pytest.raises(ValueError, match="synthetic interruption"):
        i.execute()
    with pytest.raises(ValueError, match="P023_BLOCKED_INTERRUPTED_RUN_NO_AUTOMATIC_REFIT"):
        i.execute()
    assert len(calls) == 1 and io.read_seal(marker)["automatic_restart_allowed"] is False


@pytest.mark.parametrize("drift", [None, "calibration", "fitting", "legacy"])
def test_boundary_correction_preserves_execution_source_and_methods(tmp_path, monkeypatch, drift):
    monkeypatch.chdir(tmp_path)
    sources = (
        "src/archguard/calibration/hybrid_development.py",
        "src/archguard/infrastructure/hybrid_development.py",
        "scripts/prompt023_hybrid_development.py",
        "tests/benchmark/test_hybrid_development.py",
    )
    old_kernel = "src/archguard/benchmark/hybrid_development.py"
    legacy = "legacy.py"
    archive = tmp_path / "execution-source"
    correction = tmp_path / "correction.json"
    monkeypatch.setattr(i, "SOURCES", sources)
    monkeypatch.setattr(i, "LEGACY", (legacy,))
    monkeypatch.setattr(i, "EXECUTION_SOURCE", archive)
    monkeypatch.setattr(i, "CORRECTION", correction)
    original = {
        old_kernel: "def model():\n    return 1\n",
        sources[1]: "def fit_runs():\n    return 1\ndef verify_outputs():\n    return 1\n",
        sources[2]: "# offline runner\n",
        sources[3]: "# synthetic tests\n",
    }
    for name, text in original.items():
        path = archive / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        dest = Path(sources[0] if name == old_kernel else name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(text)
    Path(legacy).write_text("# immutable P020 solver\n")
    bindings = {n: io.sha(archive / n) for n in original} | {legacy: io.sha(Path(legacy))}
    metadata = dict(source_bindings=bindings, implementation_fingerprint=digest(bindings))
    io.append_seal(
        archive / "execution-source-freeze.json",
        dict(
            implementation_fingerprint=metadata["implementation_fingerprint"],
            source_bindings={n: bindings[n] for n in original},
        ),
    )
    if drift == "calibration":
        Path(sources[0]).write_text("def model():\n    return 2\n")
    elif drift == "fitting":
        Path(sources[1]).write_text(original[sources[1]].replace("return 1", "return 2"))
    elif drift == "legacy":
        Path(legacy).write_text("# changed penalty\n")
    io.append_seal(
        correction,
        dict(
            original_source_bindings=bindings,
            corrected_source_bindings={n: io.sha(Path(n)) for n in (*sources, legacy)},
            original_implementation_fingerprint=metadata["implementation_fingerprint"],
            scientific_refit=False,
        ),
    )
    if drift:
        with pytest.raises(ValueError):
            i.verify_implementation(metadata)
    else:
        i.verify_implementation(metadata)
