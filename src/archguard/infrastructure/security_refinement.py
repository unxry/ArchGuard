"""Offline DEV-only candidate engineering, immutable history and deterministic selection."""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_dev_evaluation as baseline
from archguard.infrastructure import security_foundation as foundation
from archguard.infrastructure import security_review_recovery as safety
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security.completeness_v3 import CompletenessCertificate, map_v3_outcome
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome

ROOT = Path("experiments/security/security-dev-refinement-v3")
PUBLIC, PRIVATE = ROOT / "public", ROOT / "private"
DETECTOR_SOURCES = tuple(
    "src/archguard/security/" + name + ".py"
    for name in ("analyzer_v3", "engine_v3", "completeness_v3")
)
BASE = "7e2cf155038321115cc33bd7f42c84f2701bb6ec"
RULES = tuple(f"SEC{i:03d}" for i in range(1, 11))
REFINEMENTS = {
    "SEC001": "Structured credentials and credential-role literals "
    "propagated through local aliases; "
    "placeholder rejection; inherited synthetic-marker branch removed",
    "SEC002": "Primitive String preserves taint; fully qualified Java API identity; "
    "Connection.createStatement returns Statement; bind proofs retained",
    "SEC003": "Primitive String transport; explicit POSIX shell -c argv payload is a command sink; "
    "ordinary argument vectors retain conservative argument-injection uncertainty",
    "SEC004": "Fully qualified Java filesystem identity and Path.of value transport; "
    "normalization alone never grants confinement",
    "SEC005": "Inherited Java stream/object-flow semantics; TS remains CONTRACT_ONLY",
    "SEC006": "Primitive String transport and fully qualified Java URL identity; "
    "same-target allowlist proof semantics retained; modern HttpClient not added",
    "SEC007": "Primitive String transport to existing DOM sinks; response writer context "
    "remains unsupported rather than assuming HTML",
    "SEC008": "Fully qualified crypto API identity; existing algorithm and security-context "
    "model retained; closed literal-only TS crypto completeness grammar",
    "SEC009": "Primitive String transports randomness origins through local calls and objects; "
    "unknown transformations cannot establish a security-purpose use; "
    "security-purpose evidence remains required",
    "SEC010": "Primitive String transport; ScriptEngineManager and getEngineByName return types; "
    "Class.forName remains outside eval semantics",
}


def access_guard(event: str, args: tuple[Any, ...]) -> None:
    if event.startswith("socket."):
        raise PermissionError("P033_OFFLINE_BOUNDARY")
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.path.realpath(os.fsdecode(args[0])))
    root = Path.cwd()
    forbidden = (
        root / "experiments/security/security-human-review-v1/private",
        root / "experiments/security/security-benchmark-v1/private",
    )
    if any(path.is_relative_to(p) for p in forbidden) or (
        path.name.startswith(".env") and path.name != ".env.example"
    ):
        raise PermissionError("P033_FORBIDDEN_TRUTH_REVIEW_INTENT_OR_CREDENTIAL_PATH")


def selection_receipt(
    attempt: str, fp: str, registry: dict[str, Any], primary: dict[str, Any], audit: dict[str, int]
) -> dict[str, Any]:
    return thesis.sealed(
        dict(
            candidate=attempt,
            source_fingerprint=fp,
            DEV_USED_FOR_REFINEMENT=True,
            FINAL_REMAINS_BLIND=True,
            primary_fingerprint=primary["fingerprint"],
            prediction_fingerprint=registry["fingerprint"],
            criterion="DEV precision preserved; effective recovery and coverage nondecreasing",
            anti_memorization=audit,
            acceptance_gates="A-K PASS",
            FP=primary["FP"],
        )
    )


def verify_history() -> dict[str, Any]:
    for sha in (
        benchmark.IMPLEMENTATION_V2,
        benchmark.SOURCE,
        "624eb05609e4e24f0cedcc50ce7a3587de0dcf60",
        "eaaabe47781f63bcad5d83885a5d71b940f9d758",
        baseline.BASE,
        "a2f8181a9d5cea11b29dab8ee406f37fb2eaa298",
        BASE,
    ):
        subprocess.run(["git", "merge-base", "--is-ancestor", sha, "HEAD"], check=True)
    with patch.object(v2, "gate", lambda: None):
        historical = v2.historical_audit()
    firewall = foundation.import_firewall()
    frozen_v2 = io.read_seal(v2.ROOT / "freeze-index.json")
    io.verify_files(
        v2.ROOT, frozen_v2["files"] | {"freeze-index.json": io.sha(v2.ROOT / "freeze-index.json")}
    )
    for path, value in (frozen_v2["source_bindings"] | frozen_v2["documents"]).items():
        if io.sha(Path(path)) != value:
            raise ValueError("P033_BLOCKED_HISTORICAL_DRIFT")
    indexes = []
    for root, name in (
        (benchmark.PUBLIC, "freeze-index.json"),
        (baseline.HUMAN_PUBLIC, "truth-freeze-index.json"),
        (baseline.PUBLIC, "freeze-index.json"),
    ):
        index = io.read_seal(root / name)
        io.verify_files(root, index["files"] | {name: io.sha(root / name)})
        for path, value in (index.get("source_bindings", {}) | index.get("documents", {})).items():
            if io.sha(Path(path)) != value:
                raise ValueError("P033_BLOCKED_HISTORICAL_DRIFT")
        indexes.append(index)
    if indexes[-1]["status"] != "P032_SECURITY_DEV_EVALUATION_COMPLETE":
        raise ValueError("P033_BASELINE_NOT_COMPLETE")
    protocol = io.read_seal(
        PUBLIC / "security-dev-refinement-protocol.json",
        "8305a3dd7452c6c62d170a5a8e7bab344bf0deb11ed20e98b0ded95e042c7e4a",
    )
    if indexes[-1]["fingerprints"] != protocol["baseline"]:
        raise ValueError("P033_BLOCKED_HISTORICAL_DRIFT")
    custody = io.read_seal(
        baseline.PRIVATE / "freeze-index.json", indexes[-1]["private_custody_fingerprint"]
    )
    io.verify_files(
        baseline.PRIVATE,
        custody["files"] | {"freeze-index.json": io.sha(baseline.PRIVATE / "freeze-index.json")},
    )
    for name, fp in benchmark.PINS.items():
        io.read_seal(v2.ROOT / name, fp)
    return thesis.sealed(
        dict(
            architecture={
                k: historical[k]
                for k in (
                    "P025_primary",
                    "P025_hypothesis",
                    "P025_receipt",
                    "P026_scientific_registry",
                )
            },
            current_import_firewall=firewall["status"],
            historical_indexes=[i["fingerprint"] for i in indexes],
            P029="UNCHANGED",
            P030="UNCHANGED",
            P031="UNCHANGED",
            P032="UNCHANGED",
            private_truth_verification="Opaque P031 public seals only; private stores unopened",
            construction_verification="P030 public bindings only; construction files unopened",
        )
    )


def source_fingerprint() -> str:
    return digest({p: io.sha(Path(p)) for p in DETECTOR_SOURCES})


def anti_memorization() -> dict[str, int]:
    for name in DETECTOR_SOURCES:
        source = Path(name).read_text()
        if re.search(
            r"sc-[a-f0-9]{24}|Unit[a-f0-9]{8}|TEST_ONLY_SYNTHETIC|\bDEV\b|\bFINAL\b", source
        ):
            raise ValueError("P033_INVALID_BENCHMARK_MEMORIZATION")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in {
                "case_id",
                "ordinal",
                "final_label",
                "expected_label",
                "split",
                "source_hash",
            }:
                raise ValueError("P033_INVALID_BENCHMARK_MEMORIZATION")
            if isinstance(node, ast.Compare) and any(
                isinstance(n, ast.Constant)
                and isinstance(n.value, str)
                and re.fullmatch(r"[a-f0-9]{40,64}", n.value)
                for n in ast.walk(node)
            ):
                raise ValueError("P033_INVALID_BENCHMARK_MEMORIZATION")
    return dict(
        case_id_branches=0,
        filename_branches=0,
        source_hash_branches=0,
        DEV_split_branches=0,
        benchmark_specific_production_literals=0,
    )


def registries() -> dict[str, dict[str, Any]]:
    old = io.read_seal(v2.ROOT / "security-analysis-v2.json")
    capability = {
        rule: {
            lang: "CONTRACT_ONLY"
            if rule == "SEC005" and lang == "TYPESCRIPT"
            else "IMPLEMENTED_V3"
            if rule == "SEC001"
            else "PARTIAL_V3"
            for lang in ("JAVA", "TYPESCRIPT")
        }
        for rule in RULES
    }
    entries = dict(
        summary_protocol=dict(
            reused_P029=old["summary_protocol_fingerprint"],
            changes="NONE; inherited summary extraction; V3 concrete invocation",
        ),
        call_resolution=dict(
            reused_P029=old["call_resolution_fingerprint"],
            additions="Unshadowed fully qualified platform names and typed API returns",
        ),
        framework_registry=dict(
            reused_P029=old["framework_registry_fingerprint"],
            additions=[
                "Primitive String",
                "JDBC createStatement",
                "Path.of",
                "ScriptEngineManager",
                "POSIX shell -c argv",
            ],
        ),
        proof_registry=dict(
            reused_P029=old["proof_registry_fingerprint"],
            additions="security-completeness-v3; closed TS SEC008 grammar only",
            invalidation=(
                "Any unresolved/unsupported construct, failure or new taint blocks completeness"
            ),
        ),
        detector_registry=dict(
            reused_P029=old["detector_registry_fingerprint"], refinements=REFINEMENTS
        ),
        capability_matrix=dict(
            matrix=capability, interpretation="Engineering semantics; never inferred from scores"
        ),
        limits=dict(limits=V2Limits().model_dump(mode="json"), changes="NONE"),
    )
    return {
        name: thesis.sealed(dict(version="security-bounded-v3", **value))
        for name, value in entries.items()
    }


def diagnose(raw: dict[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_case = {r["case_id"]: r for r in raw["rows"]}
    inventory = []
    for row in rows:
        outcome, truth = row["outcome"], row["final_label"]
        categories = []
        if outcome == "DEFINITIVE_POSITIVE" and truth == "NEGATIVE":
            categories.append("FALSE_POSITIVE")
        if outcome == "DEFINITIVE_NEGATIVE" and truth == "POSITIVE":
            categories.append("FALSE_NEGATIVE")
        if outcome not in {"DEFINITIVE_POSITIVE", "DEFINITIVE_NEGATIVE"}:
            if truth in {"POSITIVE", "NEGATIVE"}:
                categories.append(truth + "_NONDEFINITIVE")
            result = by_case[row["case_id"]]["result"]
            codes = {d["code"] for d in result["diagnostics"]} if result else {"ANALYSIS_FAILURE"}
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
                elif "UNSUPPORTED" in code or "UNRESOLVED" in code or "FLOW" in code:
                    gaps.add("DATAFLOW_LIMIT")
            categories.extend(sorted(gaps or {"UNKNOWN_REASON"}))
            categories.append("COMPLETENESS_NOT_PROVEN")
        if categories:
            inventory.append(
                dict(
                    row,
                    categories=categories,
                    evidence="Recorded diagnostic/capability limitations; not a causal attribution",
                )
            )
    return thesis.sealed(dict(rows=inventory))


def evaluate(raw: dict[str, Any], registry: dict[str, Any]) -> dict[str, Any]:
    truth = io.read_seal(
        baseline.PRIVATE / "joined-dev.json",
        "6dade76354fa2bf1dd51e80339c3af0b3762f463f1f11c028ed9b2641d6f0ead",
    )
    rows = baseline.stable_join(registry["rows"], truth["rows"])
    originals = {r["case_id"]: r for r in raw["rows"]}
    if (
        len(originals) != 100
        or len(raw["rows"]) != 100
        or set(originals) != {r["case_id"] for r in rows}
    ):
        raise ValueError("P033_DEV_COHORT_DRIFT")
    certificates = 0
    for row in rows:
        original = originals[row["case_id"]]
        if row["raw_row_fingerprint"] != digest(original):
            raise ValueError("P033_RAW_BINDING_DRIFT")
        result = original["result"]
        expected = (
            map_v3_outcome(result, row["rule_id"], row["language"]) if result else Outcome.FAILED
        )
        if row["outcome"] != expected.value:
            raise ValueError("P033_ADAPTER_DRIFT")
        if expected == Outcome.DEFINITIVE_NEGATIVE:
            cert = CompletenessCertificate.model_validate(
                result["analysis_metadata"]["completeness_certificates"][row["rule_id"]]
            )
            if cert.certificate_status != "COMPLETE":
                raise ValueError("P033_INVALID_UNSOUND_NEGATIVE")
            certificates += 1
    primary = thesis.sealed(baseline.aggregate(rows))
    if (
        primary["binary_eligible"] != 89
        or primary["N"] != 100
        or primary["truth_distribution"]
        != {
            "POSITIVE": 37,
            "NEGATIVE": 52,
            "UNCERTAIN": 11,
            "OUT_OF_SCOPE": 0,
        }
    ):
        raise ValueError("P033_DEV_TRUTH_DRIFT")
    grouped = {
        field: thesis.sealed(
            dict(
                groups={
                    value: baseline.aggregate([r for r in rows if r[field] == value])
                    for value in sorted({r[field] for r in rows})
                }
            )
        )
        for field in ("rule_id", "language", "capability")
    }
    errors = diagnose(raw, rows)
    error_summary = thesis.sealed(
        dict(
            private_error_rows=len(errors["rows"]),
            category_counts=dict(
                sorted(Counter(c for r in errors["rows"] for c in r["categories"]).items())
            ),
            categories_are_nonexclusive=True,
            diagnosis="Recorded limitations only; human labels do not establish causes",
            error_inventory_fingerprint=errors["fingerprint"],
        )
    )
    return dict(
        primary=primary,
        rules=grouped["rule_id"],
        languages=grouped["language"],
        capabilities=grouped["capability"],
        errors=errors,
        error_summary=error_summary,
        join=thesis.sealed(dict(rows=rows)),
        certificate_audit=thesis.sealed(
            dict(
                definitive_negatives=certificates,
                valid_certificates=certificates,
                certificate_violations=0,
                noncomplete_certificates=sum(
                    c["certificate_status"] != "COMPLETE"
                    for r in raw["rows"]
                    if r["result"]
                    for c in r["result"]["analysis_metadata"]["completeness_certificates"].values()
                ),
                unresolved_invalidations=sum(
                    any("CALL_" in d["code"] for d in r["result"]["diagnostics"])
                    for r in raw["rows"]
                    if r["result"]
                ),
            )
        ),
    )


def execution(name: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    target = PRIVATE / name
    if target.exists():
        raise ValueError("P033_ITERATION_ALREADY_EXISTS; never overwrite attempts")
    target.mkdir(parents=True)
    shutil.copyfile(baseline.RUN / "input.json", target / "input.json")
    shutil.copytree(baseline.RUN / "sources", target / "sources")
    environment = {
        "PATH": "/usr/bin:/bin",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": str(Path("src").resolve()),
    }
    process = subprocess.run(
        [sys.executable, "-m", "archguard.infrastructure.security_refinement_worker", str(target)],
        env=environment,
        capture_output=True,
        text=True,
    )
    if process.returncode:
        safety.write_once(
            target / "failure.json",
            thesis.sealed(dict(returncode=process.returncode, stderr=process.stderr)),
        )
        raise ValueError("P033_WORKER_FAILED; retained private failure receipt")
    raw, registry, resources = (
        io.read_seal(target / n) for n in ("raw.json", "registry.json", "resources.json")
    )
    for n in ("raw.json", "registry.json", "resources.json", "worker-audit.json"):
        (target / n).chmod(0o400)
    return raw, registry, resources


def fingerprints() -> dict[str, str]:
    manifest = io.read_seal(PUBLIC / "security-candidate-manifest.json")
    mapping = {
        "REFINEMENT_PROTOCOL": "security-dev-refinement-protocol.json",
        "CANDIDATE_MANIFEST": "security-candidate-manifest.json",
        "DEV_PRIMARY_METRICS": "security-dev-candidate-primary.json",
        "DEV_RULE_METRICS": "security-dev-candidate-rules.json",
        "DEV_LANGUAGE_METRICS": "security-dev-candidate-languages.json",
        "DEV_RESOURCE_SUMMARY": "security-dev-candidate-resource-summary.json",
        "SELECTION_RECEIPT": "security-dev-selection-receipt.json",
        "FINAL_BLINDNESS_RECEIPT": "security-final-blindness-receipt.json",
    }
    values = {key: io.read_seal(PUBLIC / name)["fingerprint"] for key, name in mapping.items()}
    values["CANDIDATE_SOURCE"] = manifest["source_fingerprint"]
    values.update(
        {"CANDIDATE_" + key.upper(): value for key, value in manifest["registries"].items()}
    )
    values["DEV_PREDICTION"] = io.read_seal(PUBLIC / mapping["SELECTION_RECEIPT"])[
        "prediction_fingerprint"
    ]
    values["DEV_ERROR_INVENTORY"] = io.read_seal(
        PUBLIC / "security-dev-candidate-error-summary.json"
    )["error_inventory_fingerprint"]
    return {"SECURITY_P033_" + k + "_FINGERPRINT": v for k, v in values.items()}


def verify_selected() -> dict[str, Any]:
    manifest = io.read_seal(PUBLIC / "security-candidate-manifest.json")
    if source_fingerprint() != manifest["source_fingerprint"]:
        raise ValueError("P033_CANDIDATE_FREEZE_VIOLATION")
    for key, fp in manifest["registries"].items():
        io.read_seal(PUBLIC / ("candidate-" + key.replace("_", "-") + ".json"), fp)
    first = PRIVATE / manifest["candidate"]
    replay = PRIVATE / "selected-replay"
    pairs = [
        (io.read_seal(root / "raw.json"), io.read_seal(root / "registry.json"))
        for root in (first, replay)
    ]
    a, b = (evaluate(raw, registry) for raw, registry in pairs)
    if canonical((pairs[0], a)) != canonical((pairs[1], b)):
        raise ValueError("P033_NONDETERMINISTIC_CANDIDATE")
    selection = io.read_seal(
        PUBLIC / "security-dev-selection-receipt.json", manifest["selection_fingerprint"]
    )
    for _, registry in pairs:
        if (
            selection_receipt(
                manifest["candidate"],
                source_fingerprint(),
                registry,
                a["primary"],
                anti_memorization(),
            )
            != selection
        ):
            raise ValueError("P033_SELECTION_DRIFT")
    if a["primary"] != io.read_seal(PUBLIC / "security-dev-candidate-primary.json"):
        raise ValueError("P033_METRIC_DRIFT")
    history = verify_history()
    receipt = io.read_seal(PUBLIC / "security-dev-refinement-receipt.json")
    if receipt["history"] != history:
        raise ValueError("P033_BLOCKED_HISTORICAL_DRIFT")
    if (PUBLIC / "freeze-index.json").exists():
        index = io.read_seal(PUBLIC / "freeze-index.json")
        io.verify_files(
            PUBLIC, index["files"] | {"freeze-index.json": io.sha(PUBLIC / "freeze-index.json")}
        )
        for path, value in (index["source_bindings"] | index["documents"]).items():
            if io.sha(Path(path)) != value:
                raise ValueError("P033_CLOSURE_DRIFT")
    safety.privacy(tuple(PUBLIC.glob("*.json")))
    return dict(status="P033_SECURITY_DEV_REFINEMENT_COMPLETE", fingerprints=fingerprints())


def run(reason: str) -> dict[str, Any]:
    if (PUBLIC / "security-candidate-manifest.json").exists():
        raise ValueError("P033_CANDIDATE_ALREADY_FROZEN")
    before = verify_history()
    audit = anti_memorization()
    protocol = io.read_seal(PUBLIC / "security-dev-refinement-protocol.json")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    attempt = f"iteration-{len(list(PRIVATE.glob('iteration-*'))) + 1:03}"
    fp = source_fingerprint()
    safety.write_once(
        PRIVATE / (attempt + "-started.json"),
        thesis.sealed(
            dict(
                candidate=attempt,
                source_fingerprint=fp,
                reason=reason,
                protocol=protocol["fingerprint"],
            )
        ),
    )
    raw, registry, resources = execution(attempt)
    results = evaluate(raw, registry)
    primary = results["primary"]
    receipt = thesis.sealed(
        dict(
            candidate=attempt,
            source_fingerprint=fp,
            prediction_fingerprint=registry["fingerprint"],
            metrics=primary,
            reason=reason,
        )
    )
    safety.write_once(PRIVATE / (attempt + "-receipt.json"), receipt)
    if (
        primary["effective_positive_recovery"] < 7 / 37
        or primary["definitive_coverage"] < 7 / 89
        or primary["FP"] != 0
    ):
        raise ValueError("P033_CANDIDATE_REJECTED; iteration retained")
    if fp != source_fingerprint():
        raise ValueError("P033_CANDIDATE_SOURCE_CHANGED_DURING_EVALUATION")
    bundle = registries()
    selection = selection_receipt(attempt, fp, registry, primary, audit)
    # Freeze before a second fresh-process evaluation; no detector edits follow.
    manifest = thesis.sealed(
        dict(
            version="security-bounded-v3",
            candidate=attempt,
            P033_SECURITY_CANDIDATE_FROZEN=True,
            source_fingerprint=fp,
            source_bindings={p: io.sha(Path(p)) for p in DETECTOR_SOURCES},
            P029_manifest=benchmark.PINS["security-analysis-v2.json"],
            registries={k: v["fingerprint"] for k, v in bundle.items()},
            protocol_fingerprint=protocol["fingerprint"],
            selection_fingerprint=selection["fingerprint"],
        )
    )
    for key, value in bundle.items():
        safety.write_once(PUBLIC / ("candidate-" + key.replace("_", "-") + ".json"), value)
    safety.write_once(PUBLIC / "security-candidate-manifest.json", manifest)
    raw2, registry2, _ = execution("selected-replay")
    replay = evaluate(raw2, registry2)
    if canonical((raw, registry, results)) != canonical((raw2, registry2, replay)):
        raise ValueError("P033_NONDETERMINISTIC_CANDIDATE")
    if fp != source_fingerprint() or verify_history() != before:
        raise ValueError("P033_CANDIDATE_FREEZE_OR_HISTORICAL_DRIFT")
    replay_selection = selection_receipt(attempt, fp, registry2, replay["primary"], audit)
    if replay_selection != selection:
        raise ValueError("P033_NONDETERMINISTIC_SELECTION")
    baseline_raw = io.read_seal(baseline.RUN / "raw.json")
    baseline_rows = io.read_seal(baseline.PRIVATE / "joined-dev.json")["rows"]
    diagnosis = diagnose(baseline_raw, baseline_rows)
    safety.write_once(PRIVATE / "baseline-diagnosis.json", diagnosis)
    safety.write_once(PRIVATE / "selected-errors.json", results["errors"])
    safety.write_once(PRIVATE / "selected-join.json", results["join"])
    for key in (
        "primary",
        "rules",
        "languages",
        "capabilities",
        "error_summary",
        "certificate_audit",
    ):
        safety.write_once(
            PUBLIC / ("security-dev-candidate-" + key.replace("_", "-") + ".json"), results[key]
        )
    summary = baseline.resource_summary(resources, primary["outcomes"]["FAILED"], 0.0, 0.0)
    summary.pop("fingerprint")
    summary.update(
        timing_authority="First selected-candidate execution; replay timing excluded",
        evaluation_join_seconds="NOT_MEASURED",
        orchestration_seconds="NOT_MEASURED",
        deltas=dict(
            analyzer_seconds=summary["analyzer_seconds"] - 0.3217300850956235,
            worker_wall_seconds=summary["worker_wall_seconds"] - 0.3565061669796705,
            WHOLE_PROCESS_PEAK_RSS_bytes=summary["WHOLE_PROCESS_PEAK_RSS_bytes"] - 50937856,
        ),
    )
    safety.write_once(
        PUBLIC / "security-dev-candidate-resource-summary.json", thesis.sealed(summary)
    )
    safety.write_once(PUBLIC / "security-dev-selection-receipt.json", selection)
    blindness = thesis.sealed(
        dict(
            **baseline.ZERO,
            candidate_selected_using="DEV_ONLY",
            FINAL_metrics="NOT_COMPUTED",
            FINAL_effectiveness="NOT_EVALUATED",
            custody=(
                "Only frozen DEV source/labels/raw diagnostics and opaque public historical seals"
            ),
            worker_boundary=(
                "Frozen DEV input seal; deny-by-default file/network/process audit fence"
            ),
            OS_LEVEL_ISOLATION="NOT_CLAIMED",
        )
    )
    safety.write_once(PUBLIC / "security-final-blindness-receipt.json", blindness)
    safety.write_once(
        PUBLIC / "security-dev-refinement-receipt.json",
        thesis.sealed(
            dict(
                status="P033_SECURITY_DEV_REFINEMENT_COMPLETE",
                selected_candidate=manifest["fingerprint"],
                history=before,
                determinism=(
                    "Two fresh analyzer processes: raw/registry/outcomes/metrics/"
                    "diagnostics identical"
                ),
                DEV_USED_FOR_REFINEMENT=True,
                FINAL_REMAINS_BLIND=True,
                baseline_diagnosis_counts=dict(
                    Counter(c for r in diagnosis["rows"] for c in r["categories"])
                ),
                candidate_source_fingerprint=fp,
                next_stage="READY_FOR_P034_SECURITY_FINAL_BLIND_PREDICTION; not executed",
            )
        ),
    )
    safety.privacy(tuple(PUBLIC.glob("*.json")))
    return dict(primary)


if __name__ == "__main__":
    os.umask(0o077)
    sys.addaudithook(access_guard)
    print(json.dumps(run(sys.argv[1]), sort_keys=True))
