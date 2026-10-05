import argparse
from pathlib import Path

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.adapters import graph_predictions, static_predictions, training_records
from archguard.benchmark.evaluation import evaluate
from archguard.benchmark.models import (
    BenchmarkPrediction,
    HybridTrainingRecord,
    Mode,
    PredictionArtifact,
    Split,
    Task,
)
from archguard.benchmark.mutations import MutationConfig
from archguard.benchmark.splits import plan_splits
from archguard.infrastructure.benchmark import (
    BenchmarkLimits,
    generate_mutation,
    load_dataset,
    prepared,
    read_manifest,
    validate_dataset,
)


def benchmark_arguments(group: argparse.ArgumentParser) -> None:
    commands = group.add_subparsers(dest="command", required=True)
    for name in ("validate", "split", "mutate", "evaluate", "smoke", "export-features"):
        child = commands.add_parser(name)
        child.add_argument("dataset", type=Path)
        child.add_argument("--output", type=Path)
        child.add_argument("--json", action="store_true")
        child.add_argument("--limits", type=Path, help="Bounded loader budgets JSON")
        if name == "mutate":
            child.add_argument("--base", required=True)
            child.add_argument(
                "--operator", choices=[f"ARCH00{i}" for i in range(1, 6)], required=True
            )
            child.add_argument("--config", type=Path, required=True)
        if name in {"evaluate", "smoke"}:
            child.add_argument("--task", choices=[t.value for t in Task], required=True)
            child.add_argument("--mode", choices=[m.value for m in Mode], required=True)
            child.add_argument("--split", choices=[s.value for s in Split], action="append")
        if name == "evaluate":
            child.add_argument("--predictions", type=Path, required=True)


def execute_benchmark(arguments: argparse.Namespace) -> int:
    limits = (
        BenchmarkLimits.model_validate(read_manifest(arguments.limits))
        if arguments.limits
        else None
    )
    loaded = load_dataset(arguments.dataset, limits)
    if arguments.command == "split":
        result: object = {
            "algorithm": loaded.dataset.split_algorithm,
            "seed": loaded.dataset.split_seed,
            "families": {
                k: v.value
                for k, v in sorted(
                    plan_splits(
                        tuple(r.repository_family_id for r in loaded.dataset.repositories),
                        loaded.dataset.split_seed,
                    ).items()
                )
            },
        }
    elif arguments.command == "mutate":
        if arguments.output is None:
            raise ValueError("mutate requires a new --output directory")
        mutation = generate_mutation(
            loaded,
            arguments.base,
            arguments.operator,
            MutationConfig.model_validate(read_manifest(arguments.config)),
            arguments.output,
        )
        print(canonical(mutation))
        return 0
    elif arguments.command == "validate":
        result, _ = validate_dataset(loaded)
    elif arguments.command == "export-features":
        if arguments.output is None or arguments.output.exists():
            raise ValueError("export requires a new --output directory")
        records: dict[Split, list[HybridTrainingRecord]] = {split: [] for split in Split}
        omitted = 0
        for repo in loaded.dataset.repositories:
            pipeline, inputs = prepared(loaded, repo.repository_id)
            hybrid = pipeline.execute_prepared(inputs)
            joined = training_records(inputs.iam, repo, loaded.truths, hybrid)
            omitted += len(hybrid.cases) - len(joined)
            records[repo.dataset_split].extend(joined)
        arguments.output.mkdir(parents=True)
        for split, items in records.items():
            (arguments.output / (split.value.lower() + ".jsonl")).write_text(
                "".join(
                    canonical(r) + "\n"
                    for r in sorted(items, key=lambda r: (r.repository_id, str(r.case_id)))
                ),
                encoding="utf-8",
            )
        result = {
            "dataset_fingerprint": loaded.fingerprint,
            "records": {s.value: len(v) for s, v in records.items()},
            "unmatched_cases_omitted": omitted,
            "fitting": False,
            "selection_bias": (
                "only cases proposed by current channels; no features fabricated f"
                "or missing negatives"
            ),
        }
    else:
        mode, task = Mode(arguments.mode), Task(arguments.task)
        splits = tuple(Split(s) for s in arguments.split) if arguments.split else tuple(Split)
        if arguments.command == "evaluate":
            artifact = PredictionArtifact.model_validate(read_manifest(arguments.predictions))
            if artifact.dataset_fingerprint != loaded.fingerprint:
                raise ValueError("prediction dataset fingerprint mismatch")
            if mode in {Mode.STATIC_ONLY, Mode.GRAPH_ONLY} and not artifact.closed_world_complete:
                raise ValueError(
                    "positive-only artifact must declare complete closed-world execution"
                )
            predictions = artifact.predictions
            _, iams = validate_dataset(loaded)
        else:
            if mode not in {Mode.STATIC_ONLY, Mode.GRAPH_ONLY}:
                raise ValueError(
                    "smoke executes only static/graph channels; use saved artifacts for AI/Hybrid"
                )
            values: list[BenchmarkPrediction] = []
            iams = {}
            for repo in loaded.dataset.repositories:
                pipeline, inputs = prepared(loaded, repo.repository_id)
                iams[repo.repository_id] = inputs.iam
                if not inputs.graph.is_valid or not inputs.graph.is_complete:
                    raise ValueError("incomplete graph cannot be scored as negative")
                if (
                    mode == Mode.GRAPH_ONLY
                    and task == Task.STRUCTURAL_SIGNAL_RETRIEVAL
                    and inputs.graph.statistics.metrics_skipped
                ):
                    raise ValueError("skipped metrics cannot be scored as absent signals")
                if inputs.static is not None and not inputs.static.is_complete:
                    raise ValueError("incomplete static channel cannot be scored as negative")
                if mode == Mode.STATIC_ONLY:
                    if task != Task.CONFIRMED_VIOLATION_DETECTION:
                        raise ValueError("static smoke requires confirmed-violation task")
                    if inputs.static:
                        values.extend(
                            static_predictions(
                                inputs.iam, repo.repository_id, inputs.static.findings
                            )
                        )
                elif task == Task.STRUCTURAL_SIGNAL_RETRIEVAL:
                    values.extend(graph_predictions(inputs.iam, repo.repository_id, inputs.graph))
                elif task == Task.CONFIRMED_VIOLATION_DETECTION:
                    values.extend(
                        graph_predictions(
                            inputs.iam,
                            repo.repository_id,
                            inputs.graph,
                            inputs.graph_conformance,
                            task=task,
                        )
                    )
                else:
                    raise ValueError("unsupported graph smoke task")
            predictions = tuple(values)
        result = evaluate(
            loaded.dataset,
            loaded.truths,
            predictions,
            iams,
            loaded.fingerprint,
            mode=mode,
            task=task,
            splits=splits,
        )
    rendered = canonical(result) + "\n"
    if arguments.output and arguments.command != "export-features":
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    status = result.get("status") if isinstance(result, dict) else getattr(result, "status", None)
    return 2 if status == "PARTIAL" else 0
