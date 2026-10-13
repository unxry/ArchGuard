"""P023 orchestration helpers around the unchanged P020 fitting/selection methods."""

import copy
import math
from collections import Counter
from typing import Any

from archguard.benchmark import unified_hybrid as frozen
from archguard.benchmark.component_holdout import STATIC_RULES
from archguard.benchmark.oss.models import digest
from archguard.calibration.unified import fit_candidate

NAMES = tuple(n for c in frozen.COMPONENTS for n in frozen.FEATURES[c])
CATEGORIES = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
LLM_STATES = ("SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE")
ABLATIONS = {f"A{i}": c for i, c in enumerate(frozen.ABLATIONS, 1)}


def validate_rows(rows: list[dict[str, Any]], split: str) -> None:
    if not rows or len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("P023_MISSING_OR_DUPLICATE_ROW")
    for r in rows:
        expected = 1 if r["category"] == "POSITIVE" else 0 if r["category"] == "NEGATIVE" else None
        values = r["values"]
        if (
            r["split"] != split
            or r["cohort"] not in {"DEVELOPMENT", "SYNTHETIC"}
            or r["category"] not in CATEGORIES
            or r["label"] != expected
            or r["rule_id"] not in frozen.RULES
            or not r["llm_bound"]
            or r["llm_decision"] not in LLM_STATES
            or set(values) != set(NAMES)
            or any(
                v is not None and (type(v) not in {int, float} or not math.isfinite(v))
                for v in values.values()
            )
            or any(values[n] not in {0.0, 1.0} for n in frozen.FEATURES["LLM"])
            or sum(values[n] for n in frozen.FEATURES["LLM"][:4]) != 1
            or any(
                values[n] != float(r["llm_decision"] == state)
                for n, state in zip(frozen.FEATURES["LLM"][:4], LLM_STATES, strict=True)
            )
            or any(r["evidence"][c] not in frozen.STATES for c in frozen.COMPONENTS)
            or r["evidence"]["LLM"]
            != (
                "INSUFFICIENT_EVIDENCE"
                if r["llm_decision"] == "INSUFFICIENT_CONTEXT"
                else r["llm_decision"]
            )
        ):
            raise ValueError("P023_FEATURE_OR_LABEL_CONTRACT_DRIFT")


def development_contract(
    joined: list[dict[str, Any]],
    llm: list[dict[str, Any]],
    truth: list[dict[str, Any]],
) -> None:
    sets = [{r["case_id"] for r in records} for records in (joined, llm, truth)]
    if (
        any(len(records) != 280 for records in (joined, llm, truth))
        or any(len(ids) != 280 or ids != sets[0] for ids in sets)
        or any(r["cohort"] != "DEVELOPMENT" for r in joined)
        or Counter(r["source"] for r in llm) != {"P022.LIVE": 180, "P016": 100}
        or Counter(r["source"] for r in truth) != {"P019": 180, "P015": 100}
    ):
        raise ValueError("P023_INCOMPLETE_DEVELOPMENT_JOIN")
    train = [r for r in joined if r["split"] == "TRAIN"]
    val = [r for r in joined if r["split"] == "VALIDATION"]
    validate_rows(train, "TRAIN")
    validate_rows(val, "VALIDATION")
    if (
        len(train) != 196
        or len(val) != 84
        or len({r["project_id"] for r in train}) != 196
        or len({r["project_id"] for r in val}) != 84
        or {r["project_id"] for r in train} & {r["project_id"] for r in val}
    ):
        raise ValueError("P023_SPLIT_DRIFT")


def fitted_candidates(
    rows: list[dict[str, Any]], implementation_fp: str
) -> dict[str, dict[str, Any]]:
    validate_rows(rows, "TRAIN")
    binary = sorted((r for r in rows if r["label"] is not None), key=lambda r: digest(r["case_id"]))
    binding = digest(binary)
    result = {}
    for configuration, components in list(ABLATIONS.items())[3:]:
        for method in ("H0", "H1", "H2"):
            artifact: dict[str, Any] = (
                dict(method="H0", components=components, threshold=None)
                if method == "H0"
                else fit_candidate(binary, method, components)
            )
            columns = artifact.get("columns")
            parameters = {k: artifact.get(k) for k in ("coefficients", "intercept")}
            thresholds = []
            if method != "H0":
                for threshold in (0.25, 0.50, 0.75):
                    trial = copy.deepcopy(artifact)
                    trial["threshold"] = threshold
                    scores = frozen.metric_scores(
                        [r["label"] for r in binary], [frozen.predict(r, trial) for r in binary]
                    )
                    thresholds.append(dict(threshold=threshold, **scores))
            value = dict(
                version="p023-train-candidate-v1",
                configuration=configuration,
                method=method,
                artifact=artifact,
                train_binding_fingerprint=binding,
                train_binary_cases=len(binary),
                feature_schema_fingerprint=digest(frozen.FEATURES),
                preprocessing_fingerprint=digest(columns),
                parameter_fingerprint=digest(parameters),
                implementation_fingerprint=implementation_fp,
                precedence_fingerprint=digest(frozen.hybrid_protocol()["precedence"]),
                threshold_state=dict(
                    partition="TRAIN",
                    grid=[0.25, 0.5, 0.75] if method != "H0" else [],
                    selected=artifact["threshold"],
                    diagnostics=thresholds,
                    policy=frozen.hybrid_protocol()["threshold"] if method != "H0" else None,
                ),
                solver=dict(
                    name="H0"
                    if method == "H0"
                    else "weighted-ridge-pivot-v1"
                    if method == "H1"
                    else "weighted-logistic-newton-v1",
                    L2=1 if method != "H0" else None,
                    observation_weights="UNIT" if method != "H0" else None,
                    iterations=artifact.get("iterations"),
                    converged=True,
                    intercept_penalty=0,
                    max_iterations=200 if method == "H2" else None,
                    tolerance=1e-10 if method == "H2" else None,
                    line_search_steps=40 if method == "H2" else None,
                ),
            )
            result[f"{configuration}-{method}"] = value | {"fingerprint": digest(value)}
    return result


def prediction(row: dict[str, Any], model: dict[str, Any]) -> str:
    artifact = model["artifact"]
    components = tuple(artifact["components"])
    if frozen.precedence(row["evidence"], components):
        return "SUPPORTED"
    if model["method"] == "H0":
        return frozen.h0(row["evidence"], components)
    return frozen.predict(row, artifact)


def component_prediction(row: dict[str, Any], component: str) -> str:
    return str(row["evidence"][component])


def metrics(rows: list[dict[str, Any]], decisions: list[str]) -> dict[str, Any]:
    if len(rows) != len(decisions) or any(d not in frozen.STATES for d in decisions):
        raise ValueError("P023_METRIC_BINDING_DRIFT")
    pairs = [(r, d) for r, d in zip(rows, decisions, strict=True) if r["label"] is not None]
    labels = [r["label"] for r, _ in pairs]
    outputs = [d for _, d in pairs]
    tp = sum(y == 1 and d == "SUPPORTED" for y, d in zip(labels, outputs, strict=True))
    fp = sum(y == 0 and d == "SUPPORTED" for y, d in zip(labels, outputs, strict=True))
    tn = sum(y == 0 and d == "NOT_SUPPORTED" for y, d in zip(labels, outputs, strict=True))
    fn = sum(y == 1 and d != "SUPPORTED" for y, d in zip(labels, outputs, strict=True))

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    counts = Counter(outputs)
    return dict(
        N=len(pairs),
        TP=tp,
        FP=fp,
        TN=tn,
        FN=fn,
        **frozen.metric_scores(labels, outputs),
        Recall=ratio(tp, tp + fn),
        Specificity=ratio(tn, tn + fp),
        FPR=ratio(fp, tn + fp),
        FNR=ratio(fn, tp + fn),
        definitive_coverage=ratio(counts["SUPPORTED"] + counts["NOT_SUPPORTED"], len(pairs)),
        abstention=counts["INSUFFICIENT_EVIDENCE"],
        non_applicability=counts["NOT_APPLICABLE"],
        negative_nondefinitive=sum(
            r["label"] == 0 and d not in {"SUPPORTED", "NOT_SUPPORTED"} for r, d in pairs
        ),
    )


def views(
    rows: list[dict[str, Any]], decisions: list[str], components: tuple[str, ...]
) -> dict[str, Any]:
    def native(rule: str) -> bool:
        return (
            ("STATIC" in components and rule in STATIC_RULES)
            or ("GRAPH" in components and (rule == "ARCH003" or rule.startswith("ARCH1")))
            or "LLM" in components
        )

    definitive = [
        (r, d) for r, d in zip(rows, decisions, strict=True) if d in {"SUPPORTED", "NOT_SUPPORTED"}
    ]
    scoped = [(r, d) for r, d in zip(rows, decisions, strict=True) if native(r["rule_id"])]
    nonbinary = Counter(r["category"] for r in rows if r["label"] is None)
    return dict(
        cohort_total=len(rows),
        nonbinary=dict(nonbinary),
        primary=metrics(rows, decisions),
        definitive_only=metrics([r for r, _ in definitive], [d for _, d in definitive])
        if definitive
        else metrics([], []),
        scope_conditional_native=metrics([r for r, _ in scoped], [d for _, d in scoped])
        if scoped
        else metrics([], []),
    )


def validation_selection(
    rows: list[dict[str, Any]], models: dict[str, dict[str, Any]]
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    validate_rows(rows, "VALIDATION")
    if set(models) != {f"A{i}-{m}" for i in range(4, 8) for m in ("H0", "H1", "H2")}:
        raise ValueError("P023_UNFROZEN_CANDIDATE_SET")
    tables, predictions, selected = {}, {}, {}
    for configuration, components in ABLATIONS.items():
        keys = (
            [configuration]
            if len(components) == 1
            else [f"{configuration}-{m}" for m in ("H0", "H1", "H2")]
        )
        for key in keys:
            decisions = [
                component_prediction(r, components[0])
                if len(components) == 1
                else prediction(r, models[key])
                for r in rows
            ]
            predictions[key] = decisions
            tables[key] = views(rows, decisions, components)
        if len(components) > 1:
            winner = frozen.select_candidate(
                {m: tables[f"{configuration}-{m}"]["primary"] for m in ("H0", "H1", "H2")},
                "VALIDATION",
            )
            selected[configuration] = dict(
                family=winner,
                candidate_fingerprint=models[f"{configuration}-{winner}"]["fingerprint"],
            )
    return tables, predictions, selected
