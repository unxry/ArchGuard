"""P035 evaluation of immutable predictions; exact FINAL labels are the only truth input."""

import hashlib
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from types import FrameType
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_dev_evaluation as baseline
from archguard.infrastructure import security_final_boundary as boundary
from archguard.infrastructure import security_final_prediction as prediction
from archguard.infrastructure import security_refinement as refinement
from archguard.infrastructure import unified_human_review as io
from archguard.security_benchmark.protocol import Outcome, TruthLabel, metric_protocol

ROOT = Path("experiments/security/security-final-evaluation-v1")
PUBLIC, PRIVATE = ROOT / "public", ROOT / "private"
BASE = "e17bb28ca832c59e12f75cc65c88b285051cf73f"
P034_INDEX = "26ef920afcde4180e831b48924f75dffa6cbf348a4edb2d1ff7b7ee55d4921c1"
TRUTH = Path("experiments/security/security-human-review-v1/private/truth/FINAL/truth.json")
TRUTH_FP = "00fc038bff72a6ce0d5d7ccb72ff295938f02abf3ccd78c700397f3586150340"
REGISTRY_FP = "f91cc15fe26ddfae51c4f1887cce80004c1ba02aeaa155b506b66eb52f8bb9f0"
TRUTH_INVENTORY = TRUTH.parents[1] / "freeze-index.json"
TRUTH_INVENTORY_FP = "40480bf4dbc494f850f501436cb0cc13d72aece93065dcc9fa2d80e924f49c4a"
DEFINITIVE = {Outcome.DEFINITIVE_POSITIVE, Outcome.DEFINITIVE_NEGATIVE}
ZERO = dict.fromkeys(
    (
        "FINAL_ANALYZER_EXECUTIONS_DURING_P035",
        "DETECTOR_CODE_CHANGES",
        "POST_FINAL_TUNING",
        "P034_PREDICTION_MUTATIONS",
        "CONSTRUCTION_INTENT_READS",
        "REVIEW_RATIONALE_READS",
        "ADJUDICATION_RATIONALE_READS",
        "HUMAN_TRUTH_300_READS",
        "DEV_TRUTH_READS",
        "PROVIDER_CALLS",
        "CREDENTIAL_READS",
        "NETWORK_CONNECTIONS",
        "PAID_SPEND",
    ),
    0,
)
ARTIFACTS = {
    "FINAL_TRUTH_OPEN_RECEIPT": ("public", "security-final-truth-open-receipt.json"),
    "FINAL_JOIN": ("private", "joined-final.json"),
    "FINAL_PRIMARY_METRICS": ("public", "security-final-metrics.json"),
    "FINAL_RULE_METRICS": ("public", "security-final-rule-metrics.json"),
    "FINAL_LANGUAGE_METRICS": ("public", "security-final-language-metrics.json"),
    "FINAL_CAPABILITY_METRICS": ("public", "security-final-capability-metrics.json"),
    "FINAL_OUTCOME_CROSSTAB": ("public", "security-final-outcome-cross-tab.json"),
    "FINAL_ERROR_INVENTORY": ("private", "error-inventory.json"),
    "DEV_FINAL_GENERALIZATION": ("public", "security-dev-final-generalization.json"),
    "FINAL_EVALUATION_RECEIPT": ("public", "security-final-evaluation-receipt.json"),
    "FINAL_CUSTODY_INVENTORY": ("private", "custody-inventory.json"),
    "FINAL_EFFECTIVENESS": ("public", "security-final-effectiveness.json"),
}


class TruthGate:
    def __init__(self) -> None:
        self.ready = False
        self.original_truth_reads = 0

    def authorize(self, verification: dict[str, Any]) -> None:
        if (
            verification.get("prediction_registry_fingerprint") != REGISTRY_FP
            or verification.get("candidate_source_fingerprint") != boundary.SOURCE_FP
            or any(
                verification.get(k) is not True
                for k in (
                    "prediction_registry_verified",
                    "prediction_writer_closed",
                    "prediction_registry_frozen",
                    "blindness_receipt_verified",
                    "candidate_verified",
                )
            )
        ):
            raise ValueError("P035_INVALID_EVALUATION_CHRONOLOGY")
        self.ready = True

    def audit(self, event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket."):
            raise PermissionError("P035_PROVIDER_NETWORK_DENIED")
        if event == "subprocess.Popen" and any(
            word in str(args)
            for word in (
                "security_final_worker",
                "security_dev_worker",
                "security_refinement_worker",
                "runtime/launch.py",
            )
        ):
            raise PermissionError("P035_SCOPE_VIOLATION_ANALYZER_REEXECUTION")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.path.realpath(os.fsdecode(args[0])))
        mode, flags = args[1:3]
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)
        )
        if path == TRUTH.resolve():
            if not self.ready or writing:
                raise PermissionError("P035_INVALID_EVALUATION_CHRONOLOGY")
            self.original_truth_reads += 1
            return
        if path == TRUTH_INVENTORY.resolve() and not writing:
            if not self.ready:
                raise PermissionError("P035_INVALID_EVALUATION_CHRONOLOGY")
            return
        protected = (
            baseline.HUMAN_PUBLIC.parent / "private",
            baseline.PRIVATE,
            refinement.PRIVATE,
            benchmark.PRIVATE / "coordinator",
        )
        if any(path.is_relative_to(p.resolve()) for p in protected) or (
            path.name.startswith(".env") and path.name != ".env.example"
        ):
            raise PermissionError("P035_UNRELATED_PRIVATE_INPUT_DENIED")
        if writing and (
            path.is_relative_to(prediction.ROOT.resolve())
            or path.is_relative_to(Path("src/archguard/security").resolve())
        ):
            raise PermissionError("P035_INVALID_POST_TRUTH_MUTATION")
        parent = benchmark.PRIVATE.resolve()
        if path.is_relative_to(parent) and path != parent / "freeze-index.json":
            raise PermissionError("P035_BENCHMARK_SOURCE_OR_INTENT_DENIED")


def deny_analyzer(frame: FrameType, event: str, arg: Any) -> None:
    if (
        event == "call"
        and frame.f_code.co_name == "analyze"
        and str(frame.f_globals.get("__name__", "")).startswith("archguard.security.analyzer_")
    ):
        raise PermissionError("P035_SCOPE_VIOLATION_ANALYZER_REEXECUTION")


def verify_inputs() -> dict[str, Any]:
    for commit in (prediction.BASE, "ef2cf4927565606e8d88031c20abc43e5a477637", BASE):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    index = io.read_seal(prediction.PUBLIC / "freeze-index.json", P034_INDEX)
    io.verify_files(
        prediction.PUBLIC,
        index["files"]
        | {
            "freeze-index.json": io.sha(prediction.PUBLIC / "freeze-index.json"),
        },
    )
    for name, expected in (index["source_bindings"] | index["documents"]).items():
        if io.sha(Path(name)) != expected:
            raise ValueError("P035_BLOCKED_P034_PREDICTION_DRIFT")
    if prediction.fingerprints() != index["fingerprints"]:
        raise ValueError("P035_BLOCKED_P034_PREDICTION_DRIFT")
    frozen = io.read_seal(prediction.PUBLIC / "security-final-prediction-freeze-receipt.json")
    blind = io.read_seal(
        prediction.PUBLIC / "security-final-blindness-receipt.json", frozen["blindness_fingerprint"]
    )
    if (
        frozen["status"] != "P034_SECURITY_FINAL_BLIND_PREDICTION_COMPLETE"
        or not frozen["READY_FOR_P035_SECURITY_FINAL_TRUTH_JOIN"]
        or frozen["prediction_fingerprint"] != REGISTRY_FP
        or frozen["FINAL_prediction_rows"] != 200
        or not frozen["FINAL_PREDICTION_WRITER_CLOSED"]
        or not frozen["FINAL_PREDICTION_REGISTRY_FROZEN"]
        or any(blind[k] != 0 for k in boundary.ZERO)
    ):
        raise ValueError("P035_BLOCKED_P034_PREDICTION_DRIFT")
    prediction.verify_frozen()
    candidate = prediction.verify_candidate()
    history = prediction.verify_history()
    benchmark_manifest = io.read_seal(benchmark.PUBLIC / "benchmark-manifest.json")
    if any(
        benchmark_manifest["fingerprints"][key] != value
        for key, value in baseline.P030_PINS.items()
    ):
        raise ValueError("P035_BLOCKED_METRIC_PROTOCOL_DRIFT")
    metric = io.read_seal(
        benchmark.PUBLIC / "security-metric-protocol.json",
        "389f190ee490c1eba54d7f80ebaee6c37fdaf7fbf4b6140edc0e3fd2e9435d92",
    )
    if metric != boundary.seal(metric_protocol()):
        raise ValueError("P035_BLOCKED_METRIC_PROTOCOL_DRIFT")
    truth_index = io.read_seal(
        baseline.HUMAN_PUBLIC / "truth-freeze-index.json",
        "032ab3d9312ed11bc0226013940272257b782b02b0f91c3597d4cdc8c8bdf84f",
    )
    for key, expected in baseline.TRUTH_PINS.items():
        if truth_index["fingerprints"][key] != expected:
            raise ValueError("P035_BLOCKED_FINAL_TRUTH_DRIFT")
    io.read_seal(
        baseline.HUMAN_PUBLIC / "security-human-truth-closure.json",
        baseline.CLOSURE_FP,
    )
    return boundary.seal(
        dict(
            prediction_registry_fingerprint=REGISTRY_FP,
            prediction_registry_verified=True,
            prediction_writer_closed=True,
            prediction_registry_frozen=True,
            blindness_receipt_verified=True,
            candidate_verified=True,
            candidate_source_fingerprint=candidate["source_fingerprint"],
            P034_index=P034_INDEX,
            metric_protocol_fingerprint=metric["fingerprint"],
            history=history,
        )
    )


def validate_truth(truth: dict[str, Any], expected_ids: set[str]) -> None:
    if (
        set(truth)
        != {"split", "rows", "human_truth_300_fingerprint", "roster_fingerprint", "fingerprint"}
        or truth["split"] != "FINAL"
    ):
        raise ValueError("P035_INVALID_TRUTH_SCHEMA")
    if digest({k: v for k, v in truth.items() if k != "fingerprint"}) != truth["fingerprint"]:
        raise ValueError("P035_BLOCKED_FINAL_TRUTH_DRIFT")
    ids = [r["case_id"] for r in truth["rows"]]
    if len(ids) != 200 or len(set(ids)) != 200 or set(ids) != expected_ids:
        raise ValueError("P035_INVALID_FINAL_TRUTH_COHORT")
    for row in truth["rows"]:
        if set(row) != {"case_id", "final_label", "truth_source"} or row["truth_source"] not in {
            "A_B_AGREEMENT",
            "HUMAN_ADJUDICATION",
        }:
            raise ValueError("P035_FORBIDDEN_TRUTH_FIELDS")
        TruthLabel(row["final_label"])
    distribution = Counter(r["final_label"] for r in truth["rows"])
    if distribution != {"POSITIVE": 85, "NEGATIVE": 106, "UNCERTAIN": 9}:
        raise ValueError("P035_BLOCKED_FINAL_TRUTH_DISTRIBUTION_DRIFT")


def open_truth(gate: TruthGate, verification: dict[str, Any], ids: set[str]) -> dict[str, Any]:
    gate.authorize(verification)
    inventory = io.read_seal(TRUTH_INVENTORY, TRUTH_INVENTORY_FP)
    expected = inventory["files"].get("truth/FINAL/truth.json")
    if expected is None:
        raise ValueError("P035_FINAL_TRUTH_BYTE_BINDING_MISSING")
    raw = TRUTH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("P035_BLOCKED_FINAL_TRUTH_DRIFT")
    truth = json.loads(raw)
    if not isinstance(truth, dict):
        raise ValueError("P035_INVALID_TRUTH_SCHEMA")
    if truth.get("fingerprint") != TRUTH_FP:
        raise ValueError("P035_BLOCKED_FINAL_TRUTH_DRIFT")
    validate_truth(truth, ids)
    boundary.write_new(PRIVATE / "truth-source.json", truth)
    return truth


def stable_join(
    predictions: list[dict[str, Any]], truth: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    a, b = ({r["case_id"]: r for r in rows} for rows in (predictions, truth))
    if (
        len(a) != 200
        or len(b) != 200
        or len(predictions) != 200
        or len(truth) != 200
        or set(a) != set(b)
    ):
        raise ValueError("P035_INVALID_FINAL_JOIN")
    return [dict(a[c], final_label=TruthLabel(b[c]["final_label"]).value) for c in sorted(a)]


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = baseline.aggregate(rows)
    return result | dict(
        definitive_nonbinary={
            label.value: {
                o.value: sum(r["final_label"] == label and r["outcome"] == o for r in rows)
                for o in (Outcome.DEFINITIVE_POSITIVE, Outcome.DEFINITIVE_NEGATIVE)
            }
            for label in (TruthLabel.UNCERTAIN, TruthLabel.OUT_OF_SCOPE)
        },
    )


def correctness(row: dict[str, Any]) -> str:
    truth, outcome = TruthLabel(row["final_label"]), Outcome(row["outcome"])
    if truth in {TruthLabel.UNCERTAIN, TruthLabel.OUT_OF_SCOPE}:
        return "TRUTH_" + truth.value
    if outcome == Outcome.DEFINITIVE_POSITIVE:
        return "TRUE_POSITIVE" if truth == TruthLabel.POSITIVE else "FALSE_POSITIVE"
    if outcome == Outcome.DEFINITIVE_NEGATIVE:
        return "TRUE_NEGATIVE" if truth == TruthLabel.NEGATIVE else "FALSE_NEGATIVE"
    return truth.value + "_NONDEFINITIVE"


def diagnostics(row: dict[str, Any], raw: dict[str, Any]) -> dict[str, Any]:
    result = raw["result"] or {}
    codes = sorted({d["code"] for d in result.get("diagnostics", [])})
    gaps = set()
    if row["capability"] == "CONTRACT_ONLY":
        gaps.add("CAPABILITY_GAP")
    for code in codes:
        if "CALL_" in code or "INTERPROCEDURAL" in code:
            gaps.add("CALL_RESOLUTION_LIMIT")
        elif "SUMMARY" in code:
            gaps.add("SUMMARY_LIMIT")
        elif "FRAMEWORK" in code:
            gaps.add("FRAMEWORK_PACK_LIMIT")
        elif "OBJECT_FLOW" in code:
            gaps.add("OBJECT_FLOW_LIMIT")
        elif "UNSUPPORTED" in code or "UNRESOLVED" in code or "FLOW" in code:
            gaps.add("DATAFLOW_LIMIT")
    cert = (
        result.get("analysis_metadata", {}).get("completeness_certificates", {}).get(row["rule_id"])
    )
    if cert and cert["certificate_status"] == "NOT_PROVEN":
        gaps.add("COMPLETENESS_NOT_PROVEN")
    return dict(
        diagnostic_codes=codes,
        gap_categories=sorted(gaps or {"UNKNOWN_REASON"}),
        evidence_scope="Recorded frozen diagnostics/capability only; no causal attribution",
    )


def comparison(final: dict[str, Any]) -> dict[str, Any]:
    dev = io.read_seal(
        refinement.PUBLIC / "security-dev-candidate-primary.json",
        "0e6f07c86c8b4932d896dbe72dcea89af868357083e91ac21662f1dd13122873",
    )
    fields = (
        "precision",
        "effective_positive_recovery",
        "effective_negative_correctness",
        "definitive_coverage",
        "effective_correctness",
        "nondefinitive_rate",
    )
    return boundary.seal(
        dict(
            DEV_scope="development/refinement data; selected candidate",
            DEV=dev,
            FINAL_scope="blind held-out evaluation",
            FINAL={k: final[k] for k in fields},
            deltas_FINAL_minus_DEV={
                k: None if dev[k] is None or final[k] is None else final[k] - dev[k] for k in fields
            },
            deltas_percentage_points={
                k: None if dev[k] is None or final[k] is None else 100 * (final[k] - dev[k])
                for k in fields
            },
            population_assumption="Controlled splits; no identical-distribution inference",
            P029_FINAL_EFFECTIVENESS="NOT_EVALUATED",
            POST_FINAL_TUNING=0,
        )
    )


def build(
    registry: dict[str, Any], raw: dict[str, Any], truth: dict[str, Any], opened: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = stable_join(registry["rows"], truth["rows"])
    join = boundary.seal(
        dict(
            rows=rows, prediction_registry_fingerprint=REGISTRY_FP, FINAL_truth_fingerprint=TRUTH_FP
        )
    )
    primary = boundary.seal(aggregate(rows))
    public = {"security-final-metrics.json": primary}
    for field, name, values in (
        ("rule_id", "rule", [f"SEC{i:03d}" for i in range(1, 11)]),
        ("language", "language", ["JAVA", "TYPESCRIPT"]),
        ("capability", "capability", ["IMPLEMENTED_V3", "PARTIAL_V3", "CONTRACT_ONLY"]),
    ):
        public[f"security-final-{name}-metrics.json"] = boundary.seal(
            dict(
                groups={v: aggregate([r for r in rows if r[field] == v]) for v in values},
                frozen_capabilities=io.read_seal(
                    refinement.PUBLIC / "candidate-capability-matrix.json"
                )["matrix"],
            )
        )
    public["security-final-outcome-cross-tab.json"] = boundary.seal(
        dict(
            truth_by_outcome={
                t.value: {
                    o.value: sum(r["final_label"] == t and r["outcome"] == o for r in rows)
                    for o in Outcome
                }
                for t in TruthLabel
            },
        )
    )
    originals = {r["case_id"]: r for r in raw["rows"]}
    errors = boundary.seal(
        dict(
            rows=[
                dict(
                    row,
                    correctness_category=correctness(row),
                    execution_category=row["outcome"]
                    if row["outcome"] in {"FAILED", "UNSUPPORTED"}
                    else None,
                    **diagnostics(row, originals[row["case_id"]]),
                )
                for row in rows
            ]
        )
    )
    error_rows = errors["rows"]
    public["security-final-error-summary.json"] = boundary.seal(
        dict(
            N=200,
            private_inventory_fingerprint=errors["fingerprint"],
            correctness_categories=dict(
                sorted(Counter(r["correctness_category"] for r in error_rows).items())
            ),
            execution_categories=dict(
                sorted(
                    Counter(
                        r["execution_category"] for r in error_rows if r["execution_category"]
                    ).items()
                )
            ),
            gap_categories=dict(
                sorted(Counter(g for r in error_rows for g in r["gap_categories"]).items())
            ),
            strata={
                field: {
                    value: dict(
                        N=len(group),
                        correctness_categories=dict(
                            Counter(r["correctness_category"] for r in group)
                        ),
                        gap_categories=dict(Counter(g for r in group for g in r["gap_categories"])),
                    )
                    for value in sorted({r[field] for r in error_rows})
                    if (group := [r for r in error_rows if r[field] == value])
                }
                for field in ("rule_id", "language", "capability")
            },
            interpretation="Recorded diagnostic gaps may overlap; no causal attribution from truth",
        )
    )
    generalization = comparison(primary)
    public["security-dev-final-generalization.json"] = generalization
    receipt = boundary.seal(
        dict(
            status="P035_SECURITY_FINAL_EVALUATION_COMPLETE",
            candidate=boundary.VERSION,
            source_fingerprint=boundary.SOURCE_FP,
            prediction_registry_fingerprint=REGISTRY_FP,
            FINAL_truth_fingerprint=TRUTH_FP,
            join_fingerprint=join["fingerprint"],
            truth_open_receipt_fingerprint=opened["fingerprint"],
            public_fingerprints={k: v["fingerprint"] for k, v in sorted(public.items())},
            FINAL_predictions=200,
            FINAL_truth_rows=200,
            FINAL_join_rows=200,
            FINAL_binary_eligible=191,
            prediction_only=0,
            truth_only=0,
            duplicates=0,
            unknown=0,
            SECURITY_FINAL_EFFECTIVENESS="EVALUATED",
            SECURITY_DEV_EFFECTIVENESS="EVALUATED",
            P034_FINAL_PREDICTION_REGISTRY_UNCHANGED=True,
            P033_SECURITY_CANDIDATE_UNCHANGED=True,
            FINAL_TRUTH_OPENED_AFTER_PREDICTION_FREEZE=True,
            **ZERO,
            READY_FOR_P036_SECURITY_EXTENSION_CLOSURE=True,
            P036="NOT_STARTED",
        )
    )
    public["security-final-evaluation-receipt.json"] = receipt
    public["security-final-effectiveness.json"] = boundary.seal(
        dict(
            SECURITY_FINAL_EFFECTIVENESS="EVALUATED",
            primary_metrics_fingerprint=primary["fingerprint"],
            evaluation_receipt_fingerprint=receipt["fingerprint"],
            interpretation="P/R/F1 describe definitive P030 outcomes, not complete recall; "
            "effective positive recovery and definitive coverage are companion measures",
            SECURITY_EXTENSION_COMPLETE="NOT_DECLARED; reserved for P036",
        )
    )
    return public, {"joined-final.json": join, "error-inventory.json": errors}


def fingerprints() -> dict[str, str]:
    return {
        "SECURITY_P035_" + name + "_FINGERPRINT": io.read_seal(ROOT / area / path)["fingerprint"]
        for name, (area, path) in ARTIFACTS.items()
    }


def close_private() -> None:
    for path in PRIVATE.rglob("*"):
        if path.is_file() and not path.is_relative_to(PRIVATE / "quality"):
            path.chmod(0o400)
    for path in sorted(PRIVATE.rglob("*"), reverse=True):
        if path.is_dir() and not path.is_relative_to(PRIVATE / "quality"):
            path.chmod(0o500)
    PRIVATE.chmod(0o500)


def run(gate: TruthGate) -> dict[str, Any]:
    if (PRIVATE / "truth-open-preconditions.json").exists():
        raise ValueError("P035_ALREADY_STARTED; use verify; never replace evaluation")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    origin = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip()
    if head != BASE or head != origin:
        raise ValueError("P035_LINEAGE_PRECONDITION")
    verification = verify_inputs()
    for path in (PUBLIC, PRIVATE, PRIVATE / "quality"):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    boundary.write_new(PRIVATE / "truth-open-preconditions.json", verification)
    registry, raw = (
        io.read_seal(prediction.OUTPUT / name) for name in ("registry.json", "raw.json")
    )
    started = time.perf_counter()
    truth = open_truth(gate, verification, {r["case_id"] for r in registry["rows"]})
    truth_load_seconds = time.perf_counter() - started
    opened = boundary.seal(
        dict(
            prediction_registry_verified_first=True,
            prediction_writer_closed_first=True,
            candidate_verified_first=True,
            FINAL_truth_first_opened_in_P035=True,
            FINAL_TRUTH_FIRST_READ_AFTER_PREDICTION_FREEZE=True,
            preconditions_fingerprint=verification["fingerprint"],
            FINAL_truth_fingerprint=TRUTH_FP,
            original_FINAL_truth_reads=gate.original_truth_reads,
            **ZERO,
        )
    )
    boundary.write_new(PUBLIC / "security-final-truth-open-receipt.json", opened)
    started = time.perf_counter()
    public, private = build(registry, raw, truth, opened)
    evaluation_seconds = time.perf_counter() - started
    again_public, again_private = build(registry, raw, truth, opened)
    if canonical((public, private)) != canonical((again_public, again_private)):
        raise ValueError("P035_NONDETERMINISTIC_EVALUATION")
    for name, value in private.items():
        boundary.write_new(PRIVATE / name, value)
    for name, value in public.items():
        boundary.write_new(PUBLIC / name, value)
    boundary.write_new(
        PUBLIC / "security-final-evaluation-resources.json",
        boundary.seal(
            dict(
                P034_resource_fingerprint="5c95f45c3d520b8a826d536822000d658d9a57ad638d576fd26a7014de1513c1",
                P034=io.read_seal(
                    prediction.PUBLIC / "security-final-prediction-resource-summary.json"
                ),
                truth_load_seconds=truth_load_seconds,
                join_and_metric_aggregation_seconds=evaluation_seconds,
                timing_scope="P035 timings are separate from P034 authoritative prediction runtime",
            )
        ),
    )
    verify_inputs()
    custody = boundary.seal(
        dict(
            files={
                str(p.relative_to(PRIVATE)): io.sha(p)
                for p in sorted(PRIVATE.rglob("*"))
                if p.is_file() and not p.is_relative_to(PRIVATE / "quality")
            },
            contains_human_prose=False,
            contains_construction=False,
        )
    )
    boundary.write_new(PRIVATE / "custody-inventory.json", custody)
    close_private()
    prediction.privacy(list(PUBLIC.glob("*.json")))
    return dict(public["security-final-metrics.json"])


def verify() -> dict[str, Any]:
    verify_inputs()
    opened = io.read_seal(PUBLIC / "security-final-truth-open-receipt.json")
    truth = io.read_seal(PRIVATE / "truth-source.json", TRUTH_FP)
    registry, raw = (
        io.read_seal(prediction.OUTPUT / name) for name in ("registry.json", "raw.json")
    )
    validate_truth(truth, {r["case_id"] for r in registry["rows"]})
    public, private = build(registry, raw, truth, opened)
    for area, values in ((PUBLIC, public), (PRIVATE, private)):
        for name, expected in values.items():
            if io.read_seal(area / name) != expected:
                raise ValueError("P035_FROZEN_EVALUATION_DRIFT")
    custody = io.read_seal(PRIVATE / "custody-inventory.json")
    for name, expected in custody["files"].items():
        path = PRIVATE / name
        if io.sha(path) != expected or path.stat().st_mode & 0o222:
            raise ValueError("P035_PRIVATE_CUSTODY_DRIFT")
    return dict(
        status="PASS",
        joined_rows=200,
        original_truth_reopens=0,
        analyzer_executions=0,
        primary_fingerprint=public["security-final-metrics.json"]["fingerprint"],
    )


def main() -> None:
    os.umask(0o077)
    gate = TruthGate()
    sys.addaudithook(gate.audit)
    sys.setprofile(deny_analyzer)
    try:
        action = sys.argv[1]
        if action == "run":
            result = run(gate)
        elif action == "verify":
            result = verify()
        else:
            raise ValueError("P035_UNKNOWN_ACTION")
    finally:
        sys.setprofile(None)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
