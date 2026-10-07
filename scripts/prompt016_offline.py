"""Offline coordinator: verify truth externally, pass only hashes to the blind builder."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from archguard.architecture.intelligence.models import ContextSelectionConfig
from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.semantic_positive_experiment import (
    STRATEGIES,
    PositiveProtocol,
    analysis_plan,
    preflight_cost,
    prompt_contract,
)
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_positive_offline import (
    freeze_execution_bundle,
    prepare_material,
    verify_execution_bundle,
)

STAGE_A = "08082d793d5962cee1bdc51dccc54ca79ac46bfd"
TRUTH_PUBLIC_FP = "8d2af0804bbc208662818f58618f246c200976f74b8a98ebbe47e57938cfa46d"
FROZEN_PUBLIC_VERIFICATION = "a9ac2b5f1ffe8946c76bd1bfcdeae135324adf212a8b912ea63ab279487bc4ca"
PUBLIC = Path("experiments/semantic-holdout/p016-offline-v1")
PRIVATE = Path("experiments/semantic-holdout/private")
EXECUTION = PRIVATE / "p016-execution-v1"
COORDINATOR = PRIVATE / "p016-coordinator-v1"
PRICING = Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json")


def protocol():
    subprocess.run(["git", "merge-base", "--is-ancestor", STAGE_A, "HEAD"], check=True)
    subprocess.run(
        [sys.executable, "scripts/prompt015f_ground_truth.py", "--verify"],
        check=True,
        capture_output=True,
    )
    # Coordinator-only public aggregate receipt; only whitelisted fingerprints cross boundary.
    truth = json.loads(
        verify_opaque_seal(
            Path("experiments/semantic-holdout/final-human-ground-truth-verification-v1.json"),
            TRUTH_PUBLIC_FP,
        )
    )
    return seal(
        PositiveProtocol,
        sample_fingerprint=truth["lineage"]["sample_fingerprint"],
        source_freeze_fingerprint=truth["lineage"]["sample_freeze_fingerprint"],
        truth_fingerprint=truth["ground_truth_fingerprint"],
        truth_freeze_fingerprint=truth["freeze_receipt_fingerprint"],
        stage_a_commit=STAGE_A,
        strategies=tuple(
            ContextSelectionConfig(
                strategy=s, include_spec=False, include_discovery=False, include_metrics=False
            )
            for s in STRATEGIES
        ),
        prompt_schema_fingerprint=digest(prompt_contract()),
        analysis_plan_fingerprint=digest(analysis_plan()),
    )


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    manifest = protocol()
    files, rows, mapping = prepare_material(manifest)
    pricing = PricingAssumption.model_validate_json(PRICING.read_bytes())
    report = preflight_cost(manifest, rows, pricing)
    coordinator = {
        "schema_version": "p016-evaluation-identity-map-v1",
        "sample_fingerprint": manifest.sample_fingerprint,
        "execution_case_mapping": mapping,
    }
    coordinator["fingerprint"] = digest(coordinator)
    for path in (EXECUTION / "execution-freeze.json", COORDINATOR / "identity-map.json"):
        subprocess.run(["git", "check-ignore", "-q", str(path)], check=True)
    if args.freeze:
        if (
            PUBLIC.exists()
            or PUBLIC.is_symlink()
            or COORDINATOR.exists()
            or COORDINATOR.is_symlink()
        ):
            raise ValueError("P016 offline outputs append-only")
        frozen = freeze_execution_bundle(EXECUTION, files)

        def coordinator_build(stage):
            stage.chmod(0o700)
            write_new(stage / "identity-map.json", coordinator)
            (stage / "identity-map.json").chmod(0o600)

        atomic_directory(COORDINATOR, coordinator_build)
        verification = {
            "schema_version": "p016-offline-verification-v1",
            "status": "P016_OFFLINE_PREPARED",
            "next_state": "WAITING_FOR_PAID_AI_EXECUTION_APPROVAL",
            "cases": 100,
            "logical_requests": 300,
            "by_strategy": {s.value: 100 for s in STRATEGIES},
            "protocol_fingerprint": manifest.fingerprint,
            "execution_freeze_fingerprint": frozen["fingerprint"],
            "execution_case_manifest_fingerprint": digest(files["execution-cases.json"]),
            "context_manifest_fingerprint": files["context-manifest.json"]["fingerprint"],
            "request_manifest_fingerprint": files["request-manifest.json"]["fingerprint"],
            "prompt_schema_fingerprint": manifest.prompt_schema_fingerprint,
            "strategy_configuration_fingerprint": digest(files["strategy-config.json"]),
            "analysis_plan_fingerprint": manifest.analysis_plan_fingerprint,
            "truth_fingerprint": manifest.truth_fingerprint,
            "coordinator_mapping_fingerprint": coordinator["fingerprint"],
            "truth_leakage_findings": 0,
            "construction_leakage_findings": 0,
            "reviewer_leakage_findings": 0,
            "duplicates": 0,
            "missing_context_combinations": 0,
            "paid_execution_approved": False,
            "live_ai_calls": 0,
            "connectivity_calls": 0,
            "credentials_read": False,
            "provider_usage": None,
            "evaluation_executed": False,
            "effectiveness_metrics_calculated": False,
        }
        verification["fingerprint"] = digest(verification)
        public_files = {
            "protocol-v1.json": manifest,
            "verification-v1.json": verification,
            "cost-preflight-v1.json": report,
            "prompt-schema-v1.json": prompt_contract(),
            "analysis-plan-v1.json": analysis_plan(),
            "strategy-config-v1.json": files["strategy-config.json"],
        }

        def public_build(stage):
            for name, value in public_files.items():
                write_new(stage / name, value)

        atomic_directory(PUBLIC, public_build)
    public = json.loads(
        verify_opaque_seal(PUBLIC / "verification-v1.json", FROZEN_PUBLIC_VERIFICATION)
    )
    frozen = verify_execution_bundle(EXECUTION, public["execution_freeze_fingerprint"])
    if set(files) != set(frozen["files"]) or any(
        hashlib.sha256((canonical(value) + "\n").encode()).hexdigest() != frozen["files"][name]
        for name, value in files.items()
    ):
        raise ValueError("deterministic regeneration differs from frozen P016 inputs")
    if (
        COORDINATOR.is_symlink()
        or {p.name for p in COORDINATOR.iterdir()} != {"identity-map.json"}
        or (COORDINATOR / "identity-map.json").read_bytes()
        != (canonical(coordinator) + "\n").encode()
    ):
        raise ValueError("evaluation-only scientific identity mapping drift")
    if public["coordinator_mapping_fingerprint"] != coordinator["fingerprint"]:
        raise ValueError("evaluation mapping fingerprint drift")
    expected_public = {
        "protocol-v1.json": manifest,
        "cost-preflight-v1.json": report,
        "prompt-schema-v1.json": prompt_contract(),
        "analysis-plan-v1.json": analysis_plan(),
        "strategy-config-v1.json": files["strategy-config.json"],
    }
    if {p.name for p in PUBLIC.iterdir()} != {*expected_public, "verification-v1.json"}:
        raise ValueError("public P016 inventory drift")
    for name, value in expected_public.items():
        if (PUBLIC / name).read_bytes() != (canonical(value) + "\n").encode():
            raise ValueError("public P016 deterministic bytes drift")
    if any(
        public[key] != value
        for key, value in {
            "protocol_fingerprint": manifest.fingerprint,
            "context_manifest_fingerprint": files["context-manifest.json"]["fingerprint"],
            "request_manifest_fingerprint": files["request-manifest.json"]["fingerprint"],
            "logical_requests": 300,
            "paid_execution_approved": False,
            "live_ai_calls": 0,
        }.items()
    ):
        raise ValueError("public P016 verification binding drift")
    print(json.dumps({"verification": public, "preflight": report}, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "MACRO_BLOCKED_P016_OFFLINE: frozen lineage, context, manifest or privacy gate failed"
        ) from None
