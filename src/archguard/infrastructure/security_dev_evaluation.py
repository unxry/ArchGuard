"""P032: frozen P029 DEV predictions first; only then open the sealed DEV labels."""

import math
import os
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_review_readiness as readiness
from archguard.infrastructure import security_review_recovery as safety
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import (
    Outcome,
    TruthLabel,
    map_p029_outcome,
    metric_protocol,
    metrics,
)

BASE = "6bbb0e93d353fafc8c9643b9ac66a0329e567fb8"
ROOT = Path("experiments/security/security-dev-baseline-v1")
PRIVATE, PUBLIC = ROOT / "private", ROOT / "public"
RUN = PRIVATE / "prediction-worker"
HUMAN_PUBLIC = Path("experiments/security/security-human-review-v1/public")
DEV_TRUTH = Path("experiments/security/security-human-review-v1/private/truth/DEV/truth.json")
DEV_FP = "bec967a2e197906cf3c7bd3e9b2cb74970ee0d0d20658b13d2c35ec5f1ce4319"
DOC = "docs/verification/PROMPT_032.md"
SOURCES = (
    "src/archguard/infrastructure/security_dev_evaluation.py",
    "src/archguard/infrastructure/security_dev_worker.py",
    "scripts/prompt032_security_dev.py",
    "tests/security/test_dev_evaluation.py",
    "src/archguard/infrastructure/security_dev_test_guard.py",
)
ARTIFACTS = (
    "security-dev-input-receipt.json",
    "security-dev-truth-blind-receipt.json",
    "security-dev-baseline-metrics.json",
    "security-dev-rule-metrics.json",
    "security-dev-language-metrics.json",
    "security-dev-capability-summary.json",
    "security-dev-error-summary.json",
    "security-dev-resource-summary.json",
    "security-dev-evaluation-receipt.json",
    "quality-verification.json",
    "freeze-index.json",
)
TRUTH_PINS = dict(
    adjudication_response_set="9682bbbbcaed4750faf2b240ac8ea6524ecebd5af44068e1ba6275829d431379",
    human_truth_300="4c60a98e2c2b0c77c5b30ed1356228028b5626f4a6ed4f1a786a58159e4f2fad",
    DEV_truth=DEV_FP,
    FINAL_truth="00fc038bff72a6ce0d5d7ccb72ff295938f02abf3ccd78c700397f3586150340",
    final_truth_custody="e04ac90be27e18a36058764df3d9e6bbeabd5f1a34ea015730e82d0f17f645d0",
)
CLOSURE_FP = "c7481bcafa5adb540777d7b507e13f6fcae50d6368bddaaa307b8a8a5c3d7528"
P030_PINS = {
    "SECURITY_BENCHMARK_CASE_INVENTORY_FINGERPRINT": (
        "db3f1e60dfeb644a12403b59a1205fe9f89973187699b5babc75901611e4d232"
    ),
    "SECURITY_DEV_COHORT_FINGERPRINT": (
        "75201588fa3ee94cf6226a5cbd0512f28995569ab4cb2c5f0c7371d60d1f19f3"
    ),
    "SECURITY_FINAL_COHORT_FINGERPRINT": (
        "57bb9c3a349c2cf85fe69546aafa1f10be8f05d56e5211fecb7c992e9febe307"
    ),
    "SECURITY_BENCHMARK_PROTOCOL_FINGERPRINT": (
        "96a226fd76b97ecb752f308200f33e65dae1688df7ef85b00d74994d284fe6c6"
    ),
    "SECURITY_DEV_FINAL_SEPARATION_FINGERPRINT": (
        "7b240db07b992893f65474c412f7cdd41c603546d0d9618f932a46e394f0d6b5"
    ),
    "SECURITY_HUMAN_REVIEW_PROTOCOL_FINGERPRINT": (
        "8ac81d1526f2c6077f90d6bb35c90e5a0030f194f110cf48e04f89e4fd965189"
    ),
    "SECURITY_METRIC_PROTOCOL_FINGERPRINT": (
        "389f190ee490c1eba54d7f80ebaee6c37fdaf7fbf4b6140edc0e3fd2e9435d92"
    ),
}
ZERO = dict(
    FINAL_analyzer_executions=0,
    FINAL_prediction_rows=0,
    FINAL_truth_reads=0,
    FINAL_review_response_reads=0,
    FINAL_adjudication_reads=0,
    construction_intent_reads=0,
    review_rationale_reads=0,
    adjudication_rationale_reads=0,
    provider_calls=0,
    connectivity_calls=0,
    credential_reads=0,
    paid_spend=0,
    AI_labels=0,
    AI_adjudication=0,
)


def gate() -> None:
    allowed = (*SOURCES, DOC, ".gitignore", *(str(PUBLIC / n) for n in ARTIFACTS))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for sha in (
        benchmark.IMPLEMENTATION_V2,
        benchmark.SOURCE,
        "624eb05609e4e24f0cedcc50ce7a3587de0dcf60",
        "eaaabe47781f63bcad5d83885a5d71b940f9d758",
        "6b26a8ba876106efe44d4067c710ea3cea4047a4",
        "d717017ecc2db2a1ec46c77b6149d5c48b41ff34",
        "18eb49759f260c9ce288f40d8f77ed14d852ed6d",
        "e4d5fc7427aae9acb1cdbef452d419f188edbfd7",
        "3cdfef62f683c9eb5000f39d84b0bb226b56af8d",
        BASE,
    ):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P032_LINEAGE_DRIFT")
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", BASE, "HEAD"]).decode().splitlines()
    )
    if set(changed) - set(allowed):
        raise ValueError("P032_COMMITTED_SCOPE_DRIFT")
    original = subprocess.check_output(["git", "show", f"{BASE}:.gitignore"]).decode()
    if Path(".gitignore").read_text() != original + (
        "\n# P032 private source-only inputs, predictions, joins and diagnostics.\n"
        "experiments/security/security-dev-baseline-v1/private/\n"
    ):
        raise ValueError("P032_IGNORE_DRIFT")
    if subprocess.check_output(["git", "ls-files", "--", str(PRIVATE)]):
        raise ValueError("P032_PRIVATE_TRACKED")
    if subprocess.run(
        ["git", "check-ignore", "-q", str(PRIVATE / "probe")], capture_output=True
    ).returncode:
        raise ValueError("P032_PRIVATE_NOT_IGNORED")


def verify() -> dict[str, Any]:
    gate()
    with patch.object(v2, "gate", gate):
        historical = v2.verify()
    for name, fp in benchmark.PINS.items():
        io.read_seal(v2.ROOT / name, fp)
    p030 = io.read_seal(benchmark.PUBLIC / "freeze-index.json")
    io.verify_files(
        benchmark.PUBLIC,
        p030["files"] | {"freeze-index.json": io.sha(benchmark.PUBLIC / "freeze-index.json")},
    )
    inventory = io.read_seal(
        benchmark.PRIVATE / "freeze-index.json", p030["private_freeze_fingerprint"]
    )
    # Opaque byte-integrity pass only: never decode the construction ledger.
    io.verify_files(
        benchmark.PRIVATE,
        inventory["files"] | {"freeze-index.json": io.sha(benchmark.PRIVATE / "freeze-index.json")},
    )
    if len(inventory["files"]) + 1 != 927:
        raise ValueError("P032_P030_INVENTORY_DRIFT")
    manifest = io.read_seal(benchmark.PUBLIC / "benchmark-manifest.json")
    if any(manifest["fingerprints"][key] != fp for key, fp in P030_PINS.items()):
        raise ValueError("P032_P030_PIN_DRIFT")
    for name, h in (manifest["source_bindings"] | p030["documents"]).items():
        if io.sha(Path(name)) != h:
            raise ValueError("P032_P030_FREEZE_DRIFT")
    protocol = io.read_seal(
        benchmark.PUBLIC / "security-metric-protocol.json",
        "389f190ee490c1eba54d7f80ebaee6c37fdaf7fbf4b6140edc0e3fd2e9435d92",
    )
    if protocol != thesis.sealed(metric_protocol()):
        raise ValueError("P032_BLOCKED_METRIC_PROTOCOL_AMBIGUITY")
    p031 = io.read_seal(
        HUMAN_PUBLIC / "truth-freeze-index.json",
        "032ab3d9312ed11bc0226013940272257b782b02b0f91c3597d4cdc8c8bdf84f",
    )
    io.verify_files(
        HUMAN_PUBLIC,
        p031["files"]
        | {"truth-freeze-index.json": io.sha(HUMAN_PUBLIC / "truth-freeze-index.json")},
    )
    for name, h in (p031["source_bindings"] | p031["documents"]).items():
        if io.sha(Path(name)) != h:
            raise ValueError("P032_P031_FREEZE_DRIFT")
    closure = io.read_seal(HUMAN_PUBLIC / "security-human-truth-closure.json", CLOSURE_FP)
    if (
        closure["status"] != "P031_SECURITY_HUMAN_TRUTH_COMPLETE"
        or closure["P032"] != "NOT_STARTED"
        or closure["fingerprints"] != TRUTH_PINS
    ):
        raise ValueError("P032_P031_TRUTH_DRIFT")
    io.read_seal(
        HUMAN_PUBLIC / "security-final-truth-custody.json", TRUTH_PINS["final_truth_custody"]
    )
    # No P031 private store is opened here: FINAL truth and review bytes stay unread.
    return dict(
        P029="UNCHANGED",
        P030="UNCHANGED",
        P031="UNCHANGED",
        architecture="UNCHANGED",
        P030_expected=927,
        P030_missing=0,
        P030_mismatches=0,
        P030_unexpected=0,
        architecture_scientific_freeze=historical["historical_freeze"],
        truth_verification="OPAQUE_P031_PUBLIC_SEALS_ONLY",
    )


def prepare() -> dict[str, Any]:
    roster = safety.read_object(benchmark.PRIVATE / "prediction/DEV/roster.json")
    if set(roster) != {"cases"} or len(roster["cases"]) != 100:
        raise ValueError("P032_DEV_ROSTER_DRIFT")
    caps = io.read_seal(v2.ROOT / "security-capability-matrix-v2.json")
    hashes = {}
    for row in roster["cases"]:
        if set(row) != {"case_id", "rule_id", "language", "source_paths"}:
            raise ValueError("P032_FORBIDDEN_ROSTER_FIELDS")
        for relative in row["source_paths"]:
            source = benchmark.PRIVATE / "prediction/DEV/sources" / row["case_id"] / relative
            readiness.safe(source)
            if (
                ".." in Path(relative).parts
                or Path(relative).is_absolute()
                or source.suffix not in {".java", ".ts"}
            ):
                raise ValueError("P032_UNSAFE_SOURCE_PATH")
            name = f"{row['case_id']}/{relative}"
            blob = source.read_bytes()
            target = RUN / "sources" / name
            readiness.safe(target)
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if target.exists():
                if target.read_bytes() != blob:
                    raise ValueError("P032_INPUT_BYTE_DRIFT")
            else:
                with target.open("xb") as stream:
                    stream.write(blob)
            hashes[name] = io.sha(source)
    manifest = thesis.sealed(
        dict(
            cases=roster["cases"],
            source_hashes=hashes,
            limits=V2Limits().model_dump(mode="json"),
            capabilities={
                r["rule_id"]: {language: r[language] for language in ("JAVA", "TYPESCRIPT")}
                for r in caps["rows"]
            },
        )
    )
    safety.write_once(RUN / "input.json", manifest)
    receipt = thesis.sealed(
        dict(
            DEV_N=100,
            input_fingerprint=manifest["fingerprint"],
            detector_fingerprint=benchmark.PINS["security-analysis-v2.json"],
            source_only=True,
            forbidden_input_fields_rejected=True,
            traversal_rejected=True,
            absolute_paths_rejected=True,
            truth_paths_rejected=True,
            APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
            OS_LEVEL_ISOLATION="NOT_CLAIMED",
            **ZERO,
        )
    )
    safety.write_once(PUBLIC / "security-dev-input-receipt.json", receipt)
    return manifest


def prediction_rows(
    raw: dict[str, Any], registry: dict[str, Any], cases: list[dict[str, Any]]
) -> None:
    expected = {r["case_id"] for r in cases}
    for data in (raw, registry):
        rows = data["rows"]
        if (
            len(rows) != 100
            or len({r["case_id"] for r in rows}) != 100
            or {r["case_id"] for r in rows} != expected
        ):
            raise ValueError("P032_DEV_PREDICTION_INCOMPLETE")
    if registry["raw_prediction_fingerprint"] != raw["fingerprint"]:
        raise ValueError("P032_RAW_BINDING_DRIFT")
    by_case = {r["case_id"]: r for r in raw["rows"]}
    for row in registry["rows"]:
        original = by_case[row["case_id"]]
        status = (
            map_p029_outcome(original["result"], row["rule_id"])
            if original["result"] is not None
            else Outcome.FAILED
        )
        if row["outcome"] != status.value or row["raw_row_fingerprint"] != digest(original):
            raise ValueError("P032_FROZEN_ADAPTER_DRIFT")


def freeze_predictions(manifest: dict[str, Any]) -> dict[str, Any]:
    frozen = PRIVATE / "prediction-freeze.json"
    if frozen.exists():
        receipt = io.read_seal(frozen)
        io.read_seal(RUN / "raw.json", receipt["raw_prediction_fingerprint"])
        io.read_seal(RUN / "registry.json", receipt["prediction_registry_fingerprint"])
        return receipt
    if (PRIVATE / "execution-started.json").exists():
        raise ValueError("P032_DEV_PREDICTION_INCOMPLETE; never silently rerun")
    safety.write_once(
        PRIVATE / "execution-started.json", dict(input_fingerprint=manifest["fingerprint"])
    )
    worker = subprocess.run(
        [sys.executable, "-m", "archguard.infrastructure.security_dev_worker", str(RUN)],
        capture_output=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"},
    )
    if worker.returncode:
        safety.write_once(
            PRIVATE / "worker-failure.json",
            dict(exit_code=worker.returncode, stderr=worker.stderr.decode(errors="replace")),
        )
        raise ValueError("P032_DEV_PREDICTION_INCOMPLETE; worker failure retained privately")
    raw, registry, audit = (
        io.read_seal(RUN / n) for n in ("raw.json", "registry.json", "worker-audit.json")
    )
    prediction_rows(raw, registry, manifest["cases"])
    if audit["DEV_cases_analyzed"] != 100 or any(
        audit[k] != 0
        for k in (
            "DEV_truth_reads",
            "FINAL_truth_reads",
            "review_reads",
            "adjudication_reads",
            "construction_intent_reads",
            "provider_calls",
            "credential_reads",
        )
    ):
        raise ValueError("P032_INVALID_TRUTH_BLIND_BASELINE")
    receipt = thesis.sealed(
        dict(
            DEV_requested=100,
            DEV_prediction_rows=100,
            missing=0,
            duplicates=0,
            raw_prediction_fingerprint=raw["fingerprint"],
            prediction_registry_fingerprint=registry["fingerprint"],
            input_fingerprint=manifest["fingerprint"],
            worker_audit_fingerprint=audit["fingerprint"],
            worker_exited=True,
            prediction_writer_closed=True,
            prediction_registry_frozen=True,
            DEV_truth_reads_before_prediction_freeze=0,
            review_response_reads=0,
            adjudication_reads=0,
            detector_fingerprint=benchmark.PINS["security-analysis-v2.json"],
            APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
            OS_LEVEL_ISOLATION="NOT_CLAIMED",
            **ZERO,
        )
    )
    for name in ("raw.json", "registry.json", "worker-audit.json", "resources.json", "input.json"):
        (RUN / name).chmod(0o400)
    safety.write_once(frozen, receipt)
    safety.write_once(PUBLIC / "security-dev-truth-blind-receipt.json", receipt)
    return receipt


def open_dev_truth() -> dict[str, Any]:
    receipt = io.read_seal(PRIVATE / "prediction-freeze.json")
    if (
        not receipt["worker_exited"]
        or not receipt["prediction_writer_closed"]
        or not receipt["prediction_registry_frozen"]
        or receipt["DEV_truth_reads_before_prediction_freeze"] != 0
    ):
        raise ValueError("P032_INVALID_TRUTH_BLIND_BASELINE")
    registry = RUN / "registry.json"
    if registry.stat().st_mode & 0o222:
        raise ValueError("P032_PREDICTION_WRITER_NOT_CLOSED")
    io.read_seal(registry, receipt["prediction_registry_fingerprint"])
    io.read_seal(RUN / "raw.json", receipt["raw_prediction_fingerprint"])
    return io.read_seal(DEV_TRUTH, DEV_FP)


def stable_join(
    predictions: list[dict[str, Any]], truth: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    a = {r["case_id"]: r for r in predictions}
    b = {r["case_id"]: r for r in truth}
    if (
        len(a) != 100
        or len(b) != 100
        or len(predictions) != 100
        or len(truth) != 100
        or set(a) != set(b)
    ):
        raise ValueError("P032_INVALID_DEV_JOIN")
    return [dict(a[c], final_label=TruthLabel(b[c]["final_label"]).value) for c in sorted(a)]


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = tuple((TruthLabel(r["final_label"]), Outcome(r["outcome"])) for r in rows)
    result = metrics(values)
    definitive = {Outcome.DEFINITIVE_POSITIVE, Outcome.DEFINITIVE_NEGATIVE}
    return dict(
        N=len(rows),
        truth_distribution={t.value: sum(x == t for x, _ in values) for t in TruthLabel},
        negative_nondefinitive=sum(
            t == TruthLabel.NEGATIVE and o not in definitive for t, o in values
        ),
        positive_nondefinitive=sum(
            t == TruthLabel.POSITIVE and o not in definitive for t, o in values
        ),
        nondefinitive_rate=sum(o not in definitive for _, o in values) / len(values)
        if values
        else None,
        **result,
    )


def evaluate(
    registry: dict[str, Any], raw: dict[str, Any], truth: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = stable_join(registry["rows"], truth["rows"])
    join = thesis.sealed(
        dict(
            rows=rows,
            prediction_registry_fingerprint=registry["fingerprint"],
            DEV_truth_fingerprint=DEV_FP,
        )
    )
    primary = thesis.sealed(aggregate(rows))
    if (
        primary["truth_distribution"]
        != {"POSITIVE": 37, "NEGATIVE": 52, "UNCERTAIN": 11, "OUT_OF_SCOPE": 0}
        or primary["binary_eligible"] != 89
    ):
        raise ValueError("P032_DEV_TRUTH_DISTRIBUTION_DRIFT")

    def grouped(field: str) -> dict[str, Any]:
        return {
            key: aggregate([r for r in rows if r[field] == key])
            for key in sorted({r[field] for r in rows})
        }

    rules = thesis.sealed(dict(groups=grouped("rule_id")))
    languages = thesis.sealed(dict(groups=grouped("language")))
    capabilities = thesis.sealed(dict(groups=grouped("capability")))
    raw_by_case = {r["case_id"]: r for r in raw["rows"]}
    errors = []
    for row in rows:
        label, outcome = row["final_label"], row["outcome"]
        positive = outcome == "DEFINITIVE_POSITIVE"
        negative = outcome == "DEFINITIVE_NEGATIVE"
        categories = []
        if label == "POSITIVE" and negative:
            categories.append("FALSE_NEGATIVE")
        if label == "NEGATIVE" and positive:
            categories.append("FALSE_POSITIVE")
        if not positive and not negative:
            if label in {"POSITIVE", "NEGATIVE"}:
                categories.append(label + "_NONDEFINITIVE")
            if outcome == "UNSUPPORTED":
                categories.append("UNSUPPORTED")
            if outcome == "FAILED":
                categories.append("ANALYSIS_FAILED")
            if row["capability"] == "CONTRACT_ONLY":
                categories.append("CAPABILITY_GAP")
        if not categories:
            continue
        result = raw_by_case[row["case_id"]]["result"]
        codes = (
            sorted({d["code"] for d in result["diagnostics"]})
            if result is not None
            else ["ANALYSIS_EXCEPTION"]
        )
        errors.append(
            dict(
                row,
                categories=categories,
                diagnostic_codes=codes,
                cause="CAPABILITY_GAP"
                if row["capability"] == "CONTRACT_ONLY"
                else "UNKNOWN_REASON",
            )
        )
    inventory = thesis.sealed(dict(rows=errors, join_fingerprint=join["fingerprint"]))
    error_summary = thesis.sealed(
        dict(
            private_error_rows=len(errors),
            category_counts=dict(
                sorted(Counter(c for r in errors for c in r["categories"]).items())
            ),
            categories_are_nonexclusive=True,
            groups={
                field: {
                    key: dict(
                        sorted(
                            Counter(
                                c for r in errors if r[field] == key for c in r["categories"]
                            ).items()
                        )
                    )
                    for key in sorted({r[field] for r in rows})
                }
                for field in ("rule_id", "language", "capability")
            },
            causal_analysis="Recorded diagnostic codes only; no causal inference",
            error_inventory_fingerprint=inventory["fingerprint"],
        )
    )
    cross = {
        t.value: {
            o.value: sum(r["final_label"] == t.value and r["outcome"] == o.value for r in rows)
            for o in Outcome
        }
        for t in TruthLabel
    }
    receipt = thesis.sealed(
        dict(
            status="P032_SECURITY_DEV_EVALUATION_COMPLETE",
            DEV_N=100,
            DEV_binary_eligible=89,
            DEV_truth_reads_before_prediction_freeze=0,
            DEV_truth_first_read_after_prediction_freeze=True,
            prediction_writer_closed=True,
            joined=100,
            prediction_only=0,
            truth_only=0,
            Security_DEV_effectiveness="EVALUATED",
            Security_FINAL_effectiveness="NOT_EVALUATED",
            FINAL_metrics="NOT_COMPUTED",
            detector_code_changes=0,
            detector_tuning=0,
            APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
            OS_LEVEL_ISOLATION="NOT_CLAIMED",
            strict_confusion="P030: FN excludes abstention; no-finding PARTIAL never TN",
            supplemental_view="NOT_COMPUTED; primary frozen P030 formulas unchanged",
            truth_outcome_crosstab=cross,
            fingerprints=dict(
                raw=raw["fingerprint"],
                prediction_registry=registry["fingerprint"],
                join=join["fingerprint"],
                primary=primary["fingerprint"],
                rules=rules["fingerprint"],
                languages=languages["fingerprint"],
                capabilities=capabilities["fingerprint"],
                errors=inventory["fingerprint"],
            ),
            **ZERO,
        )
    )
    return dict(
        primary=primary,
        rules=rules,
        languages=languages,
        capabilities=capabilities,
        error_summary=error_summary,
        receipt=receipt,
    ), dict(join=join, errors=inventory)


def resource_summary(
    data: dict[str, Any], failed: int, evaluation_seconds: float, orchestration_seconds: float
) -> dict[str, Any]:
    seconds = sorted(r["seconds"] for r in data["latency"])
    if len(seconds) != 100:
        raise ValueError("P032_RESOURCE_COUNT_DRIFT")
    return thesis.sealed(
        dict(
            analyzer_seconds=sum(seconds),
            case_latency=dict(
                count=len(seconds),
                sum=sum(seconds),
                mean=statistics.mean(seconds),
                median=statistics.median(seconds),
                p95=seconds[math.ceil(0.95 * len(seconds)) - 1],
                maximum=max(seconds),
            ),
            analyzer_time_scope=(
                "Fresh analyzer initialization and analyze per case; excludes source intake/adapter"
            ),
            adapter_materialization_seconds=data["adapter_materialization_seconds"],
            worker_wall_seconds=data["worker_wall_seconds"],
            evaluation_join_seconds=evaluation_seconds,
            orchestration_seconds=orchestration_seconds,
            orchestration_scope="Through post-run verification; excludes tests/Git publication",
            WHOLE_PROCESS_PEAK_RSS_bytes=data["WHOLE_PROCESS_PEAK_RSS_bytes"],
            memory_scope="Prediction child whole-process high-water mark, not per case/detector",
            source_bytes=data["source_bytes"],
            source_chars=data["source_chars"],
            analysis_failures=failed,
            timeouts="NOT_MEASURED",
            per_method_memory="NOT_MEASURED",
            p95_method="nearest rank",
            repeatable_timing_claim=False,
        )
    )


def run() -> dict[str, Any]:
    os.umask(0o077)
    started = time.perf_counter()
    before = verify()
    manifest = prepare()
    frozen = freeze_predictions(manifest)
    raw = io.read_seal(RUN / "raw.json", frozen["raw_prediction_fingerprint"])
    registry = io.read_seal(RUN / "registry.json", frozen["prediction_registry_fingerprint"])
    prediction_rows(raw, registry, manifest["cases"])
    began = time.perf_counter()
    truth = open_dev_truth()
    public, private = evaluate(registry, raw, truth)
    elapsed = time.perf_counter() - began
    again, again_private = evaluate(registry, raw, truth)
    if canonical((public, private)) != canonical((again, again_private)):
        raise ValueError("P032_NONDETERMINISTIC_EVALUATION")
    for key, path in (
        ("join", PRIVATE / "joined-dev.json"),
        ("errors", PRIVATE / "errors-dev.json"),
    ):
        safety.write_once(path, private[key])
    names = dict(
        primary="security-dev-baseline-metrics.json",
        rules="security-dev-rule-metrics.json",
        languages="security-dev-language-metrics.json",
        capabilities="security-dev-capability-summary.json",
        error_summary="security-dev-error-summary.json",
        receipt="security-dev-evaluation-receipt.json",
    )
    for key, name in names.items():
        safety.write_once(PUBLIC / name, public[key])
    if verify() != before:
        raise ValueError("P032_HISTORICAL_FREEZE_DRIFT")
    if not (PUBLIC / "security-dev-resource-summary.json").exists():
        measured = io.read_seal(RUN / "resources.json")
        safety.write_once(
            PUBLIC / "security-dev-resource-summary.json",
            resource_summary(
                measured,
                public["primary"]["outcomes"]["FAILED"],
                elapsed,
                time.perf_counter() - started,
            ),
        )
    io.read_seal(RUN / "raw.json", raw["fingerprint"])
    io.read_seal(RUN / "registry.json", registry["fingerprint"])
    io.read_seal(DEV_TRUTH, DEV_FP)
    safety.privacy(tuple(PUBLIC / name for name in ARTIFACTS[:9]))
    return dict(public["receipt"])
