import argparse
from pathlib import Path

from archguard.architecture.hybrid.calibration import (
    FrozenStructuralHybridPolicyArtifact,
    StructuralCalibrationError,
)
from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.models import Split
from archguard.calibration.models import (
    DirectGraphBaselineResult,
    HeldoutEvaluationResult,
    ModelSelectionReport,
    TrainingRunResult,
)
from archguard.calibration.workflow import (
    assert_evaluation_allowed,
    direct_graph_baseline,
    evaluate_frozen,
    freeze,
    rank,
    select_model,
    train_models,
)
from archguard.infrastructure.calibration import (
    load_experiment,
    load_policy,
    load_primary,
    save_new,
)
from archguard.infrastructure.hybrid_configuration import _read


def calibration_arguments(parser: argparse.ArgumentParser) -> None:
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("train", "select", "freeze", "evaluate", "baseline"):
        child = commands.add_parser(name)
        child.add_argument("--output", type=Path, required=True, help="New artifact file")
        child.add_argument("--json", action="store_true")
        if name in {"train", "evaluate", "baseline"}:
            child.add_argument("--manifest", type=Path, required=True)
        if name == "baseline":
            child.add_argument("--train", type=Path, required=True)
            child.add_argument("--validation", type=Path, required=True)
        elif name == "train":
            child.add_argument("--train", type=Path, required=True)
            child.add_argument("--channels", default="static,graph")
        elif name == "select":
            child.add_argument("--training", type=Path, required=True)
            child.add_argument("--validation", type=Path, required=True)
        elif name == "freeze":
            child.add_argument("--selection", type=Path, required=True)
        else:
            child.add_argument("--artifact", type=Path, required=True)
            child.add_argument("--test", type=Path, required=True)


def execute_calibration(args: argparse.Namespace) -> int:
    result: (
        TrainingRunResult
        | ModelSelectionReport
        | FrozenStructuralHybridPolicyArtifact
        | HeldoutEvaluationResult
        | DirectGraphBaselineResult
    )
    if args.output.exists():
        raise StructuralCalibrationError("output already exists; frozen runs cannot be overwritten")
    if args.command == "baseline":
        experiment = load_experiment(args.manifest)
        train = load_primary(args.train, Split.TRAIN, experiment)
        validation = load_primary(args.validation, Split.VALIDATION, experiment)
        result = direct_graph_baseline(train, validation, experiment)
        summary = (
            f"Direct Graph Rule Baseline: TRAIN F1={result.train_metrics.macro_family.f1}; "
            f"VALIDATION F1={result.validation_metrics.macro_family.f1}; descriptive rule replay"
        )
    elif args.command == "train":
        if args.channels != "static,graph":
            raise StructuralCalibrationError(
                "FULL_HYBRID_NOT_READY: real AI assessments and semantic review required"
            )
        experiment = load_experiment(args.manifest)
        train = load_primary(args.train, Split.TRAIN, experiment)
        result = train_models(train, experiment)
        summary = (
            f"TRAIN families={len(train.families)}; cases={result.train_cases}; "
            f"P/N={result.train_positive}/{result.train_negative}; "
            f"{len(result.candidates)} fitted candidates"
        )
    elif args.command == "select":
        training = TrainingRunResult.model_validate(_read(args.training, 1048576))
        validation = load_primary(args.validation, Split.VALIDATION, training.experiment)
        result = select_model(training, validation)
        summary = (
            f"VALIDATION families={len(validation.families)}; cases={result.validation_cases}; "
            f"P/N={result.validation_positive}/{result.validation_negative}"
        )
        for family in ("WEIGHTED_LINEAR", "LOGISTIC_REGRESSION"):
            best = max(
                (c for c in result.candidates if c.model.family == family),
                key=rank,
            )
            summary += (
                f"\n{family}: L2={best.model.regularization}; threshold={best.threshold}; "
                f"macro-family-F1={best.metrics.macro_family.f1}"
            )
        summary += (
            f"\nChosen={result.candidates[result.chosen_index].model.family}; "
            f"{result.tie_break_reason}"
        )
    elif args.command == "freeze":
        selection = ModelSelectionReport.model_validate(_read(args.selection, 1048576))
        result = freeze(selection)
        summary = result.status + " artifact=" + result.fingerprint
    else:
        artifact = load_policy(args.artifact)
        experiment = load_experiment(args.manifest)
        assert_evaluation_allowed(artifact, experiment)
        receipt = args.artifact.parent / (artifact.fingerprint + ".heldout-receipt.json")
        if receipt.exists():
            raise StructuralCalibrationError(
                "held-out evaluation already claimed for this artifact"
            )
        test = load_primary(args.test, Split.TEST, experiment)
        with receipt.open("x", encoding="utf-8") as stream:
            stream.write(
                canonical(
                    {
                        "artifact_fingerprint": artifact.fingerprint,
                        "status": "CLAIMED_BEFORE_EVALUATION",
                    }
                )
                + "\n"
            )
        result = evaluate_frozen(artifact, test, experiment)
        summary = (
            f"ENGINEERING_SEED_HELDOUT_EVALUATION; F1={result.metrics.micro.f1}; "
            f"artifact={artifact.fingerprint}"
        )
    save_new(args.output, result)
    print(
        canonical(result)
        if args.json
        else summary + "\nSMALL ENGINEERING SEED; no final thesis or probability calibration claim"
    )
    return 0
