from collections import defaultdict
from uuid import UUID

from archguard import __version__
from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.benchmark.identity import digest, resolved_key, subject_key
from archguard.benchmark.models import (
    BenchmarkDataset,
    BenchmarkPrediction,
    BenchmarkRun,
    Confusion,
    EvaluationGroup,
    GroundTruthCase,
    Label,
    Metrics,
    Mode,
    PredictionState,
    Split,
    Task,
)
from archguard.benchmark.resolver import LocatorResolver
from archguard.benchmark.splits import validate_leakage
from archguard.iam.model import ArchitectureModel


def ratio(a: int | float, b: int | float) -> float | None:
    return a / b if b else None


def metrics(c: Confusion) -> Metrics:
    p, r = ratio(c.tp, c.tp + c.fp), ratio(c.tp, c.tp + c.fn)
    return Metrics(
        precision=p,
        recall=r,
        f1=ratio(2 * c.tp, 2 * c.tp + c.fp + c.fn) if p is not None and r is not None else None,
        fpr=ratio(c.fp, c.fp + c.tn) if c.explicit_negatives and not c.scoped_extra_fp else None,
        fnr=ratio(c.fn, c.fn + c.tp),
        abstention_rate=ratio(c.abstain, c.eligible),
        prediction_coverage=ratio(c.tp + c.fp - c.scoped_extra_fp + c.fn + c.tn, c.eligible),
    )


def macro(groups: tuple[EvaluationGroup, ...]) -> Metrics:
    values: dict[str, float | None] = {}
    for name in Metrics.model_fields:
        available = [v for g in groups if (v := getattr(g.metrics, name)) is not None]
        values[name] = sum(available) / len(available) if available else None
    return Metrics.model_validate(values)


def evaluate(
    dataset: BenchmarkDataset,
    truths: tuple[GroundTruthCase, ...],
    predictions: tuple[BenchmarkPrediction, ...],
    iams: dict[str, ArchitectureModel],
    fingerprint: str,
    *,
    task: Task,
    mode: Mode,
    splits: tuple[Split, ...] = tuple(Split),
) -> BenchmarkRun:
    validate_leakage(dataset)
    if task == Task.CALIBRATED_HYBRID_DETECTION:
        raise ValueError("calibrated Hybrid evaluation is reserved for a later stage")
    repositories = {r.repository_id: r for r in dataset.repositories if r.dataset_split in splits}
    resolvers = {r: LocatorResolver(iams[r]) for r in repositories}
    rows: list[tuple[str, str, dict[str, int]]] = []
    diagnostics: list[str] = []
    seen_truth: set[tuple[str, str, str]] = set()
    selected: dict[tuple[str, str, str], list[BenchmarkPrediction]] = defaultdict(list)
    unique: dict[tuple[str, str, str, PredictionState], BenchmarkPrediction] = {}
    for p in predictions:
        if p.repository_id not in {r.repository_id for r in dataset.repositories}:
            raise ValueError("unknown prediction repository")
        if p.source != mode or p.task != task:
            raise ValueError("prediction mode/task mismatch")
        if p.repository_id not in repositories:
            continue
        resolved = resolvers[p.repository_id].subjects(p.subjects)
        if resolved is None or (p.subject_ids and p.subject_ids != resolved):
            raise ValueError("prediction locator/ID mismatch or unresolved prediction")
        prediction_key = (p.repository_id, p.rule_id, resolved_key(p.subjects, resolved), p.state)
        if prediction_key in unique:
            diagnostics.append("DUPLICATE_PREDICTION")
            if str(p.prediction_id) >= str(unique[prediction_key].prediction_id):
                continue
        unique[prediction_key] = p
    for prediction_key, p in unique.items():
        selected[prediction_key[:3]].append(p)
    case_ids: set[UUID] = set()
    for truth in truths:
        if truth.case_id in case_ids:
            raise ValueError("duplicate truth ID")
        case_ids.add(truth.case_id)
        if truth.repository_id not in repositories or truth.rule_family != task.family:
            continue
        truth_ids = resolvers[truth.repository_id].subjects(truth.subjects)
        key = (
            truth.repository_id,
            truth.rule_id,
            resolved_key(truth.subjects, truth_ids)
            if truth_ids is not None
            else subject_key(truth.subjects),
        )
        if key in seen_truth:
            raise ValueError("duplicate/conflicting logical truth")
        seen_truth.add(key)
        counts: dict[str, int] = {}
        matched = selected.pop(key, [])
        if truth_ids is None:
            counts["unresolved_truth"] = 1
            diagnostics.append("UNRESOLVED_TRUTH:" + str(truth.case_id))
        elif truth.label == Label.UNKNOWN:
            counts["unknown_truth"] = 1
            counts["out_of_scope"] = len(matched)
        else:
            counts["eligible"] = 1
            counts["explicit_negatives"] = int(truth.label == Label.NEGATIVE)
            states = {p.state for p in matched}
            if PredictionState.CANDIDATE in states:
                states.remove(PredictionState.CANDIDATE)
                states.add(PredictionState.POSITIVE)
            if len(states) > 1:
                counts["abstain"] = 1
                diagnostics.append("CONFLICTING_PREDICTIONS:" + str(truth.case_id))
            elif states == {PredictionState.ABSTAIN}:
                counts["abstain"] = 1
            elif not states and mode in {Mode.LLM_ONLY, Mode.HYBRID}:
                counts["no_prediction"] = 1
            else:
                positive = PredictionState.POSITIVE in states
                outcome = (
                    ("tp" if positive else "fn")
                    if truth.label == Label.POSITIVE
                    else ("fp" if positive else "tn")
                )
                counts[outcome] = 1
        rows.append((truth.repository_id, truth.rule_id, counts))
    for (repo, rule, _), unmatched in selected.items():
        positive = any(
            p.state in {PredictionState.POSITIVE, PredictionState.CANDIDATE} for p in unmatched
        )
        inside = repositories[repo].annotation_scope.contains(rule, unmatched[0].subjects)
        counts = {"fp": 1, "scoped_extra_fp": 1} if inside and positive else {"out_of_scope": 1}
        rows.append((repo, rule, counts))

    def aggregate(group: str) -> tuple[EvaluationGroup, ...]:
        buckets: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for repo, rule, counts in rows:
            languages = repositories[repo].languages
            key = (
                rule
                if group == "rule"
                else repo
                if group == "repo"
                else languages[0].value
                if len(languages) == 1
                else "MIXED"
            )
            for name, value in counts.items():
                buckets[key][name] += value
        return tuple(
            EvaluationGroup(
                key=k, confusion=(c := Confusion.model_validate(buckets[k])), metrics=metrics(c)
            )
            for k in sorted(buckets)
        )

    total: dict[str, int] = defaultdict(int)
    for _, _, counts in rows:
        for name, value in counts.items():
            total[name] += value
    confusion = Confusion.model_validate(total)
    rule_groups, repo_groups = aggregate("rule"), aggregate("repo")
    return BenchmarkRun(
        dataset_id=dataset.dataset_id,
        dataset_version=dataset.dataset_version,
        dataset_fingerprint=fingerprint,
        splits=splits,
        mode=mode,
        task=task,
        status="PARTIAL" if confusion.unresolved_truth else "VALID",
        predictions=tuple(
            sorted(
                unique.values(),
                key=lambda p: (
                    p.repository_id,
                    p.rule_id,
                    subject_key(p.subjects),
                    p.state,
                    str(p.prediction_id),
                ),
            )
        ),
        confusion=confusion,
        metrics=metrics(confusion),
        per_rule=rule_groups,
        per_language=aggregate("language"),
        per_repository=repo_groups,
        macro_rule=macro(rule_groups),
        macro_repository=macro(repo_groups),
        diagnostics=tuple(sorted(diagnostics)),
        tool_versions={"archguard": __version__, "evaluator": "1.0"},
        reproducibility={
            "matching": "exact-resolved-locators-v1",
            "iam_fingerprints": digest(
                {repo: iam_fingerprint(iams[repo]) for repo in sorted(repositories)}
            ),
            "negative_universe": "explicit-controls-only",
            "missing_prediction": "closed-world-static-graph; coverage-miss-llm-hybrid",
        },
    )
