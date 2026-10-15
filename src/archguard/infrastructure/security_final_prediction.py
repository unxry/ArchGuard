"""P034 blind prediction custody; no truth loading or effectiveness calculation."""

import ast
import hashlib
import json
import math
import os
import re
import statistics
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_dev_evaluation as baseline
from archguard.infrastructure import security_final_boundary as boundary
from archguard.infrastructure import security_foundation as foundation
from archguard.infrastructure import security_refinement as refinement
from archguard.infrastructure import unified_human_review as io
from archguard.security.completeness_v3 import map_v3_outcome
from archguard.security.domain import SecurityAnalysisResult
from archguard.security.summaries_v2 import V2Limits
from archguard.security_benchmark.protocol import Outcome

ROOT = Path("experiments/security/security-final-prediction-v1")
PUBLIC, PRIVATE = ROOT / "public", ROOT / "private"
BUNDLE, OUTPUT, TEMP = (PRIVATE / name for name in ("bundle", "output", "temporary"))
BASE = "05938c49ef0db278ccf067e916ad7d6201fe658c"
INDEX_FP = "2c3325e52a6b9205b8bff133988b336c4e4be145dfda575bceb92b36a4032381"
PINS = {
    "FINAL_INPUT": ("private", "bundle/input.json"),
    "OS_ISOLATION_PREFLIGHT": ("public", "security-final-os-isolation-receipt.json"),
    "FINAL_RAW_PREDICTION": ("private", "output/raw.json"),
    "FINAL_PREDICTION_REGISTRY": ("private", "output/registry.json"),
    "FINAL_PREDICTION_OUTCOME_SUMMARY": ("public", "security-final-prediction-outcomes.json"),
    "FINAL_RULE_SUMMARY": ("public", "security-final-prediction-rule-summary.json"),
    "FINAL_LANGUAGE_SUMMARY": ("public", "security-final-prediction-language-summary.json"),
    "FINAL_CAPABILITY_SUMMARY": ("public", "security-final-prediction-capability-summary.json"),
    "FINAL_RESOURCE_SUMMARY": ("public", "security-final-prediction-resource-summary.json"),
    "FINAL_BLINDNESS_RECEIPT": ("public", "security-final-blindness-receipt.json"),
    "FINAL_PREDICTION_FREEZE_RECEIPT": ("public", "security-final-prediction-freeze-receipt.json"),
    "CUSTODY_INVENTORY": ("private", "custody-inventory.json"),
}


def access_guard(event: str, args: tuple[Any, ...]) -> None:
    if event.startswith("socket."):
        raise PermissionError("P034_OFFLINE_BOUNDARY")
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.path.realpath(os.fsdecode(args[0])))
    root = Path.cwd()
    denied = (
        baseline.HUMAN_PUBLIC.parent / "private",
        baseline.PRIVATE,
        refinement.PRIVATE,
        benchmark.PRIVATE / "coordinator",
    )
    if any(path.is_relative_to((root / p).resolve()) for p in denied) or (
        path.name.startswith(".env") and path.name != ".env.example"
    ):
        raise PermissionError("P034_PROTECTED_CONTENT_DENIED")
    private = (root / benchmark.PRIVATE).resolve()
    if path.is_relative_to(private) and not (
        path == private / "freeze-index.json"
        or path == private / "prediction/FINAL/roster.json"
        or path.is_relative_to(private / "prediction/FINAL/sources")
    ):
        raise PermissionError("P034_NON_SOURCE_BENCHMARK_CONTENT_DENIED")


def _verify_candidate() -> dict[str, Any]:
    index = io.read_seal(refinement.PUBLIC / "freeze-index.json", INDEX_FP)
    io.verify_files(
        refinement.PUBLIC,
        index["files"]
        | {
            "freeze-index.json": io.sha(refinement.PUBLIC / "freeze-index.json"),
        },
    )
    for name, expected in (index["source_bindings"] | index["documents"]).items():
        if io.sha(Path(name)) != expected:
            raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT")
    candidate = io.read_seal(
        refinement.PUBLIC / "security-candidate-manifest.json",
        "fa9ff988ef6f46a342ccd5b4a6c24330abd4cd616935d88b5261732572f00e6f",
    )
    if (
        candidate["source_fingerprint"] != boundary.SOURCE_FP
        or digest({name: io.sha(Path(name)) for name in candidate["source_bindings"]})
        != boundary.SOURCE_FP
        or candidate["candidate"] != "iteration-004"
        or candidate["version"] != boundary.VERSION
        or not candidate["P033_SECURITY_CANDIDATE_FROZEN"]
    ):
        raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT")
    refinement.anti_memorization()
    return candidate


def verify_candidate() -> dict[str, Any]:
    try:
        return _verify_candidate()
    except (ValueError, OSError) as error:
        raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT") from error


def verify_history() -> dict[str, Any]:
    for commit in (
        "ae99aa94c818f89a4d988bca99c73eb18b6a74cf",
        "3274504a80abe0ae688796c28322a87f7f5272c9",
        "624eb05609e4e24f0cedcc50ce7a3587de0dcf60",
        "eaaabe47781f63bcad5d83885a5d71b940f9d758",
        "6bbb0e93d353fafc8c9643b9ac66a0329e567fb8",
        "a2f8181a9d5cea11b29dab8ee406f37fb2eaa298",
        "7e2cf155038321115cc33bd7f42c84f2701bb6ec",
        "22fbcf6afacc96bd6e405e6ed89fea9512968f4e",
        BASE,
    ):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    with patch.object(v2, "gate", lambda: None):
        historical = v2.historical_audit()
    indexes = {}
    for root, name in (
        (v2.ROOT, "freeze-index.json"),
        (benchmark.PUBLIC, "freeze-index.json"),
        (baseline.HUMAN_PUBLIC, "truth-freeze-index.json"),
        (baseline.PUBLIC, "freeze-index.json"),
    ):
        index = io.read_seal(root / name)
        io.verify_files(root, index["files"] | {name: io.sha(root / name)})
        bindings = index.get("source_bindings", {}) | index.get("documents", {})
        if root == benchmark.PUBLIC:
            bindings |= io.read_seal(root / "benchmark-manifest.json")["source_bindings"]
        for path, expected in bindings.items():
            if io.sha(Path(path)) != expected:
                raise ValueError("P034_HISTORICAL_DRIFT")
        indexes[str(root)] = index["fingerprint"]
    for name, expected in benchmark.PINS.items():
        io.read_seal(v2.ROOT / name, expected)
    inventory = io.read_seal(
        benchmark.PRIVATE / "freeze-index.json",
        "8b3e8267e670e0eca932cd44354976de900f13f485ed0679e297e369a36ba2e1",
    )
    actual = {
        str(p.relative_to(benchmark.PRIVATE)) for p in benchmark.PRIVATE.rglob("*") if p.is_file()
    }
    expected_paths = set(inventory["files"]) | {"freeze-index.json"}
    if len(actual) != 927 or actual != expected_paths:
        raise ValueError("P034_P030_INVENTORY_DRIFT")
    verify_candidate()
    return boundary.seal(
        dict(
            status="PASS",
            closure=BASE,
            indexes=indexes,
            architecture={
                k: historical[k]
                for k in (
                    "P025_primary",
                    "P025_hypothesis",
                    "P025_receipt",
                    "P026_scientific_registry",
                )
            },
            current_import_firewall=foundation.import_firewall()["status"],
            P030_inventory=927,
            missing=0,
            unexpected=0,
            P030_byte_integrity="Public frozen bindings; FINAL source bytes checked at intake",
            protected_private_byte_rehash="NOT_PERFORMED; opaque historical seals only",
            P031="PUBLIC_OPAQUE_SEALS_ONLY",
            P032="PUBLIC_FREEZE_ONLY",
            P033="EXACT_FROZEN_CANDIDATE",
        )
    )


def runtime_sources() -> dict[str, Path]:
    pending = ["archguard.infrastructure.security_final_worker"]
    found: dict[str, Path] = {}
    while pending:
        module = pending.pop()
        relative = Path(*module.split("."))
        path = Path("src") / relative.with_suffix(".py")
        if not path.is_file():
            path = Path("src") / relative / "__init__.py"
        if not path.is_file() or str(path.relative_to("src")) in found:
            continue
        found[str(path.relative_to("src"))] = path
        for parent in relative.parents:
            if parent.parts:
                pending.append(".".join(parent.parts))
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("archguard")
            ):
                pending.append(node.module)
                pending.extend(node.module + "." + alias.name for alias in node.names)
            elif isinstance(node, ast.Import):
                pending.extend(n.name for n in node.names if n.name.startswith("archguard"))
    return found


def prepare() -> dict[str, Any]:
    roster = json.loads((benchmark.PRIVATE / "prediction/FINAL/roster.json").read_text())
    if set(roster) != {"cases"}:
        raise ValueError("P034_FORBIDDEN_ROSTER_FIELDS")
    boundary.validate_roster(roster["cases"])
    inventory = io.read_seal(benchmark.PRIVATE / "freeze-index.json")
    roster_name = "prediction/FINAL/roster.json"
    if io.sha(benchmark.PRIVATE / roster_name) != inventory["files"][roster_name]:
        raise ValueError("P034_ROSTER_BYTE_DRIFT")
    hashes = {}
    for row in roster["cases"]:
        for relative in row["source_paths"]:
            name = row["case_id"] + "/" + relative
            source = benchmark.PRIVATE / "prediction/FINAL/sources" / name
            if source.resolve() != source.absolute() or any(
                p.is_symlink() for p in (source, *source.parents)
            ):
                raise ValueError("P034_SOURCE_SYMLINK_DENIED")
            blob = source.read_bytes()
            expected = inventory["files"]["prediction/FINAL/sources/" + name]
            if hashlib.sha256(blob).hexdigest() != expected:
                raise ValueError("P034_FINAL_SOURCE_BYTE_DRIFT")
            target = BUNDLE / "sources" / name
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("xb") as stream:
                stream.write(blob)
            hashes[name] = expected
    runtime = {}
    for name, source in runtime_sources().items():
        target = BUNDLE / "runtime" / name
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with target.open("xb") as stream:
            stream.write(source.read_bytes())
        runtime[name] = io.sha(source)
    site = Path(sys.prefix, "lib", "python3.13", "site-packages").resolve()
    bootstrap = BUNDLE / "runtime/launch.py"
    bootstrap.write_text(
        "import runpy,sys\n"
        f"sys.path.append({str(site)!r})\n"
        "runpy.run_module('archguard.infrastructure.security_final_worker',run_name='__main__')\n"
    )
    runtime["launch.py"] = io.sha(bootstrap)
    caps = io.read_seal(refinement.PUBLIC / "candidate-capability-matrix.json")["matrix"]
    manifest = boundary.seal(
        dict(
            cases=roster["cases"],
            source_hashes=hashes,
            runtime_hashes=runtime,
            capabilities=caps,
            limits=V2Limits().model_dump(mode="json"),
            candidate_source_fingerprint=boundary.SOURCE_FP,
        )
    )
    boundary.FinalFence(BUNDLE, OUTPUT, manifest)
    boundary.write_new(BUNDLE / "input.json", manifest)
    return manifest


def prediction_rows(
    raw: dict[str, Any],
    registry: dict[str, Any],
    cases: list[dict[str, Any]],
    capabilities: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if set(raw) != {"input_fingerprint", "rows", "fingerprint"} or set(registry) != {
        "raw_prediction_fingerprint",
        "rows",
        "fingerprint",
    }:
        raise ValueError("P034_INVALID_REGISTRY_SCHEMA")
    for value in (raw, registry):
        if digest({k: v for k, v in value.items() if k != "fingerprint"}) != value["fingerprint"]:
            raise ValueError("P034_REGISTRY_SEAL_DRIFT")
        ids = [r["case_id"] for r in value["rows"]]
        if len(ids) != 200 or len(set(ids)) != 200 or set(ids) != {r["case_id"] for r in cases}:
            raise ValueError("P034_FINAL_PREDICTION_INCOMPLETE")
    if registry["raw_prediction_fingerprint"] != raw["fingerprint"]:
        raise ValueError("P034_RAW_BINDING_DRIFT")
    route = {r["case_id"]: r for r in cases}
    expected = []
    for row in raw["rows"]:
        if set(row) != {
            "case_id",
            "language",
            "rule_id",
            "capability",
            "candidate_version",
            "candidate_source_fingerprint",
            "execution_status",
            "result",
            "analysis_exception",
        }:
            raise ValueError("P034_FORBIDDEN_RAW_FIELDS")
        case = route[row["case_id"]]
        if (
            capabilities is not None
            and row["capability"] != capabilities[row["rule_id"]][row["language"]]
        ):
            raise ValueError("P034_CAPABILITY_DRIFT")
        if any(row[k] != case[k] for k in ("language", "rule_id")) or (
            row["candidate_version"] != boundary.VERSION
            or row["candidate_source_fingerprint"] != boundary.SOURCE_FP
        ):
            raise ValueError("P034_RAW_IDENTITY_DRIFT")
        result = row["result"]
        if result is not None:
            SecurityAnalysisResult.model_validate(result)
            if (
                result["requested_rules"] != [row["rule_id"]]
                or result["analyzer_version"] != boundary.VERSION
            ):
                raise ValueError("P034_TARGET_RULE_OR_ANALYZER_DRIFT")
        outcome = (
            map_v3_outcome(result, row["rule_id"], row["language"]) if result else Outcome.FAILED
        )
        if row["execution_status"] != ("ANALYZED" if result else "FAILED"):
            raise ValueError("P034_EXECUTION_STATUS_DRIFT")
        expected.append(
            dict(
                case_id=row["case_id"],
                language=row["language"],
                rule_id=row["rule_id"],
                capability=row["capability"],
                outcome=outcome.value,
                raw_row_fingerprint=digest(row),
            )
        )
    if expected != registry["rows"]:
        raise ValueError("P034_FROZEN_ADAPTER_REPLAY_DRIFT")
    return expected


def counts(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tally = Counter(r["outcome"] for r in rows)
    return dict(N=len(rows), outcomes={o.value: tally[o.value] for o in Outcome})


def summaries(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {"security-final-prediction-outcomes.json": boundary.seal(counts(rows))}
    for field, name, values in (
        ("rule_id", "rule", [f"SEC{i:03d}" for i in range(1, 11)]),
        ("language", "language", ["JAVA", "TYPESCRIPT"]),
        ("capability", "capability", ["IMPLEMENTED_V3", "PARTIAL_V3", "CONTRACT_ONLY"]),
    ):
        result[f"security-final-prediction-{name}-summary.json"] = boundary.seal(
            dict(
                groups={value: counts([r for r in rows if r[field] == value]) for value in values},
            )
        )
    return result


def readonly(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_relative_to(PRIVATE / "quality"):
            continue
        if path.is_file():
            path.chmod(0o400)
    for path in sorted(root.rglob("*"), reverse=True):
        if path.is_relative_to(PRIVATE / "quality"):
            continue
        if path.is_dir():
            path.chmod(0o500)
    root.chmod(0o500)


def verify_frozen() -> dict[str, Any]:
    verify_candidate()
    frozen = io.read_seal(PUBLIC / "security-final-prediction-freeze-receipt.json")
    custody = io.read_seal(PRIVATE / "custody-inventory.json", frozen["custody_fingerprint"])
    for name, expected in custody["files"].items():
        path = PRIVATE / name
        if io.sha(path) != expected or path.stat().st_mode & 0o222:
            raise ValueError("P034_FROZEN_CUSTODY_DRIFT")
    manifest = io.read_seal(BUNDLE / "input.json")
    raw, registry = (io.read_seal(OUTPUT / name) for name in ("raw.json", "registry.json"))
    if raw["input_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("P034_INPUT_BINDING_DRIFT")
    if (
        raw["fingerprint"] != frozen["raw_prediction_fingerprint"]
        or registry["fingerprint"] != frozen["prediction_fingerprint"]
        or manifest["fingerprint"] != frozen["input_fingerprint"]
        or (PRIVATE / "custody-inventory.json").stat().st_mode & 0o222
    ):
        raise ValueError("P034_PUBLIC_FREEZE_BINDING_DRIFT")
    rows = prediction_rows(raw, registry, manifest["cases"], manifest["capabilities"])
    for name, expected_summary in summaries(rows).items():
        if io.read_seal(PUBLIC / name) != expected_summary:
            raise ValueError("P034_AGGREGATE_REPLAY_DRIFT")
    return dict(
        status="PASS",
        rows=len(rows),
        analyzer_reexecutions=0,
        registry_fingerprint=registry["fingerprint"],
    )


def fingerprints() -> dict[str, str]:
    return {
        "SECURITY_P034_" + name + "_FINGERPRINT": io.read_seal(ROOT / area / path)["fingerprint"]
        for name, (area, path) in PINS.items()
    }


def run() -> dict[str, Any]:
    if (PRIVATE / "execution-reservation.json").exists():
        raise ValueError("P034_AUTHORITATIVE_EXECUTION_ALREADY_RESERVED_WRITER_CLOSED")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    origin = subprocess.check_output(["git", "rev-parse", "origin/main"], text=True).strip()
    if head != BASE or head != origin:
        raise ValueError("P034_LINEAGE_PRECONDITION")
    boundary.mechanism()
    candidate = verify_candidate()
    history = verify_history()
    for path in (PUBLIC, PRIVATE, BUNDLE, OUTPUT, TEMP, PRIVATE / "quality"):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    boundary.write_new(
        PRIVATE / "candidate-writer-closed.json",
        boundary.seal(
            dict(
                CANDIDATE_WRITER_CLOSED=True,
                candidate_source_fingerprint=boundary.SOURCE_FP,
                HEAD_before_execution=head,
                origin_main_before_execution=origin,
                history_fingerprint=history["fingerprint"],
                candidate_manifest=candidate["fingerprint"],
                technical_retry_policy="Zero retries; any infrastructure failure stops acquisition",
            )
        ),
    )
    boundary.write_new(PRIVATE / "history-verification.json", history)
    manifest = prepare()
    policy = (PRIVATE / "sandbox.sb").resolve()
    policy.write_text(boundary.profile(BUNDLE, OUTPUT, TEMP))
    preflight = boundary.preflight(BUNDLE.resolve(), OUTPUT.resolve(), TEMP.resolve(), policy)
    boundary.write_new(PUBLIC / "security-final-os-isolation-receipt.json", preflight)
    readonly(BUNDLE)
    before = {name: io.sha(Path(name)) for name in candidate["source_bindings"]}
    boundary.write_new(
        PRIVATE / "execution-reservation.json",
        boundary.seal(
            dict(
                invocation=1,
                input_fingerprint=manifest["fingerprint"],
                preflight_fingerprint=preflight["fingerprint"],
                no_semantic_retries=True,
                runtime_hashes=manifest["runtime_hashes"],
            )
        ),
    )
    started = time.perf_counter()
    completed = subprocess.run(
        boundary.command(
            policy,
            str((BUNDLE / "runtime/launch.py").resolve()),
            str(BUNDLE.resolve()),
            str(OUTPUT.resolve()),
        ),
        env=boundary.environment(BUNDLE.resolve(), TEMP.resolve()),
        cwd=BUNDLE.resolve(),
        capture_output=True,
    )
    process_wall = time.perf_counter() - started
    (PRIVATE / "worker-stderr.log").write_bytes(completed.stderr)
    if completed.returncode:
        raise ValueError("P034_FINAL_PREDICTION_INCOMPLETE")
    if before != {name: io.sha(Path(name)) for name in before}:
        raise ValueError("P034_BLOCKED_CANDIDATE_DRIFT")
    verify_candidate()
    raw, registry = (io.read_seal(OUTPUT / name) for name in ("raw.json", "registry.json"))
    rows = prediction_rows(raw, registry, manifest["cases"], manifest["capabilities"])
    if raw["input_fingerprint"] != manifest["fingerprint"]:
        raise ValueError("P034_INPUT_BINDING_DRIFT")
    readonly(OUTPUT)
    audit = io.read_seal(OUTPUT / "worker-audit.json")
    if any(audit[key] != 0 for key in boundary.ZERO) or audit["FINAL_cases_analyzed"] != 200:
        raise ValueError("P034_INVALID_FINAL_BLINDNESS")
    for name, value in summaries(rows).items():
        boundary.write_new(PUBLIC / name, value)
    resources = io.read_seal(OUTPUT / "resources.json")
    latency = sorted(r["seconds"] for r in resources["latency"])
    resource_summary = boundary.seal(
        dict(
            analyzer_seconds=sum(latency),
            worker_wall_seconds=resources["worker_wall_seconds"],
            process_wall_seconds=process_wall,
            case_latency=dict(
                count=len(latency),
                sum=sum(latency),
                mean=statistics.mean(latency),
                median=statistics.median(latency),
                p95=latency[math.ceil(0.95 * len(latency)) - 1],
                max=max(latency),
            ),
            **{
                key: resources[key]
                for key in (
                    "adapter_materialization_seconds",
                    "WHOLE_PROCESS_PEAK_RSS_bytes",
                    "source_bytes",
                    "source_chars",
                    "timeouts",
                )
            },
            analysis_failures=sum(r["result"] is None for r in raw["rows"]),
            infrastructure_failures=0,
            technical_retries=0,
            authoritative_invocations=1,
        )
    )
    boundary.write_new(PUBLIC / "security-final-prediction-resource-summary.json", resource_summary)
    blindness = boundary.seal(
        dict(
            **boundary.ZERO,
            FINAL_cases_requested=200,
            FINAL_prediction_rows=200,
            OS_LEVEL_ISOLATION="VERIFIED",
            APPLICATION_CAPABILITY_BOUNDARY="VERIFIED",
            FINAL_PREDICTION_WRITER_CLOSED=True,
            FINAL_PREDICTION_REGISTRY_FROZEN=True,
            CANDIDATE_WRITER_CLOSED=True,
            FINAL_TRUTH_JOIN="NOT_STARTED",
            FINAL_METRICS="NOT_COMPUTED",
            SECURITY_FINAL_EFFECTIVENESS="NOT_EVALUATED",
            readonly_mechanism="owner read-only custody; exclusive create; no overwrite",
            limitation="Owner can deliberately chmod; no privileged filesystem lock",
        )
    )
    boundary.write_new(PUBLIC / "security-final-blindness-receipt.json", blindness)
    boundary.write_new(PRIVATE / "technical-retries.json", boundary.seal(dict(count=0, reasons=[])))
    custody = boundary.seal(
        dict(
            files={
                str(p.relative_to(PRIVATE)): io.sha(p)
                for p in sorted(PRIVATE.rglob("*"))
                if p.is_file()
            },
            contains_truth=False,
            contains_reviews=False,
            contains_construction=False,
        )
    )
    boundary.write_new(PRIVATE / "custody-inventory.json", custody)
    readonly(PRIVATE)
    frozen = boundary.seal(
        dict(
            status="P034_SECURITY_FINAL_BLIND_PREDICTION_COMPLETE",
            candidate=boundary.VERSION,
            iteration="iteration-004",
            candidate_source_fingerprint=boundary.SOURCE_FP,
            candidate_manifest_fingerprint=candidate["fingerprint"],
            input_fingerprint=manifest["fingerprint"],
            raw_prediction_fingerprint=raw["fingerprint"],
            prediction_fingerprint=registry["fingerprint"],
            blindness_fingerprint=blindness["fingerprint"],
            isolation_fingerprint=preflight["fingerprint"],
            custody_fingerprint=custody["fingerprint"],
            history_fingerprint=history["fingerprint"],
            FINAL_cases_requested=200,
            FINAL_cases_analyzed=200,
            FINAL_prediction_rows=200,
            missing=0,
            duplicates=0,
            unknown=0,
            FINAL_PREDICTION_WRITER_CLOSED=True,
            FINAL_PREDICTION_REGISTRY_FROZEN=True,
            P033_SECURITY_CANDIDATE_UNCHANGED=True,
            READY_FOR_P035_SECURITY_FINAL_TRUTH_JOIN=True,
            P035="NOT_STARTED",
            FINAL_TRUTH_JOIN="NOT_STARTED",
            FINAL_METRICS="NOT_COMPUTED",
            SECURITY_FINAL_EFFECTIVENESS="NOT_EVALUATED",
        )
    )
    boundary.write_new(PUBLIC / "security-final-prediction-freeze-receipt.json", frozen)
    boundary.write_new(
        PUBLIC / "security-p035-opaque-handoff.json",
        boundary.seal(
            dict(
                candidate=boundary.VERSION,
                candidate_fingerprints=candidate["registries"],
                source_fingerprint=boundary.SOURCE_FP,
                prediction_registry_fingerprint=registry["fingerprint"],
                N=200,
                writer_closed=True,
                blindness_receipt_fingerprint=blindness["fingerprint"],
                OS_isolation_receipt_fingerprint=preflight["fingerprint"],
                custody_fingerprint=custody["fingerprint"],
                READY_FOR_P035_SECURITY_FINAL_TRUTH_JOIN=True,
            )
        ),
    )
    verify_frozen()
    verify_history()
    return frozen


def privacy(paths: list[Path]) -> None:
    for path in paths:
        text = path.read_text()
        pattern = r"sc-[a-f0-9]{24}|/Us" + r"ers/|Unit[a-f0-9]{8}|sk-[A-Za-z0-9]{16,}"
        if re.search(pattern, text):
            raise ValueError("P034_PUBLIC_PRIVACY_FAILURE")


def main() -> None:
    os.umask(0o077)
    sys.addaudithook(access_guard)
    action = sys.argv[1]
    if action == "run":
        result = run()
    elif action == "verify":
        result = verify_frozen()
    else:
        raise ValueError("P034_UNKNOWN_ACTION")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
