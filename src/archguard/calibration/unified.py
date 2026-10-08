"""TRAIN-only interpretable candidate fitting; benchmark contracts stay solver-free."""

from statistics import mean, median, pstdev
from typing import Any

from archguard.benchmark.unified_hybrid import (
    ABLATIONS,
    FEATURES,
    metric_scores,
    predict,
    transform,
)
from archguard.calibration.numeric import fit_coefficients


def fit_candidate(
    rows: list[dict[str, Any]], method: str, components: tuple[str, ...]
) -> dict[str, Any]:
    if method not in {"H1", "H2"} or components not in ABLATIONS:
        raise ValueError("unregistered candidate/ablation")
    if any(r["split"] != "TRAIN" or r.get("cohort") == "FINAL" for r in rows):
        raise ValueError("TRAIN-only fitting")
    if any(not r.get("llm_bound", False) for r in rows) or not rows:
        raise ValueError("missing accepted development LLM evidence")
    names = tuple(n for c in components for n in FEATURES[c])
    columns = []
    for name in names:
        values = [float(r["values"][name]) for r in rows if r["values"].get(name) is not None]
        mid = median(values) if values else 0.0
        all_values = [
            float(r["values"].get(name) if r["values"].get(name) is not None else mid) for r in rows
        ]
        columns.append(
            dict(name=name, median=mid, mean=mean(all_values), scale=pstdev(all_values) or 1.0)
        )
    artifact: dict[str, Any] = {"method": method, "components": components, "columns": columns}
    x = tuple(transform(r["values"], artifact) for r in rows)
    y = tuple(int(r["label"]) for r in rows)
    coef, intercept, iterations = fit_coefficients(
        x, y, tuple(1.0 for _ in y), 1.0, logistic=method == "H2"
    )
    artifact.update(coefficients=coef, intercept=intercept, iterations=iterations, threshold=0.5)
    ranks = []
    for threshold in (0.25, 0.5, 0.75):
        artifact["threshold"] = threshold
        s = metric_scores(list(y), [predict(r, artifact) for r in rows])
        ranks.append(((s["F1"] or 0.0, s["Precision"] or 0.0, -abs(threshold - 0.5)), threshold))
    artifact["threshold"] = max(ranks)[1]
    return artifact
