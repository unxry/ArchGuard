"""Offline P018 only; freeze the committed plan before opening construction intent."""

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path

import prompt017_evaluation as p017

from archguard.benchmark.oss.models import canonical
from archguard.benchmark.semantic_construction_diagnostic import diagnostic_plan, sealed
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_construction_diagnostic import (
    freeze_diagnostic,
    load_construction,
    make_join,
    require_plan,
    verify_diagnostic,
    verify_p017,
)
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    append_sealed,
    evaluation_io,
    verify_truth,
)

BASE = Path("experiments/semantic-holdout")
CONSTRUCTION_PUBLIC = BASE / "semantic-positive-holdout-v1"
CONSTRUCTION_PRIVATE = BASE / "private/semantic-positive-holdout-v1"
DESTINATION = BASE / "private/p018-diagnostic-v1"
PLAN = BASE / "p018-analysis-plan-v1.json"
AGGREGATE = BASE / "p018-aggregate-diagnostic-v1.json"
RECEIPT = BASE / "p018-diagnostic-freeze-v1.json"
PUBLIC = BASE / "p018-verification-v1.json"
CONSTRUCTION = {
    "provenance": "91f66c7ec9c676da1840f9e3de5ecb383b1f023dd3d9536acfba87b3693d8ec2",
    "inventory": "9f505c22d5076f620b9a98a308e928f83edd4e42481111ce37d79a5f4aa79e39",
    "corpus": "15273b2f42c2d15e79d9632b25942f8e2c4e589af93dd6eed9663fa080eca2b3",
    "sample": "926cf3014e3c46f9c3a62df6421ce89886373559335411209f25780130e1f5fa",
    "freeze": "b291e47d6b5ed7ffcbbac967b221b5dee7366fa2d559031b19bc5b3d751b3dfb",
    "future_analysis": "956644650a27f886fc9f25d1820455b958a937a80e2214f8750946dbfd8bddde",
}
P017 = {
    "join": "fd83704fed70be3c462e1a4d43511476c7fe9b781898623962b0b475c16d1696",
    "binding": "70d1a38c4a0d888961f7f11ad11086fe04e0fbf132f9cfb8e85a7b27ed349478",
    "aggregate": "992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091",
    "receipt": "3e506e13ea5cdc20f57da4d5f420687c5bde87d5dcc23e1c1a003c49defe4d02",
    "verification": "1fe89f2b4f377043a49fa19c76de4a198ca30d93922a13acea16a1a3859990d2",
}
TRUTH = {k: v for k, v in p017.EXPECTED.items() if k.startswith("truth_")}
INPUTS = (
    {f"construction_{k}": v for k, v in CONSTRUCTION.items()}
    | TRUTH
    | {f"p017_{k}": v for k, v in P017.items()}
)
CONSTRUCTION_COMMIT = "e91e6c13e6cc7dff7b640f9a968e52dd07745f11"
FIRST_HUMAN_ACCEPTANCE_COMMIT = "091bbf1eade51d3c4915624d599c371f8df9df68"
COMMITS = (
    *p017.COMMITS,
    "7e96c87d2380dfa417f6df9cbf59d3f512bdb5fe",
    "8a11b012dadde660318053f2cb6845703cae7547",
)
IMPLEMENTATION = (
    "scripts/prompt018_diagnostic.py",
    "src/archguard/benchmark/semantic_construction_diagnostic.py",
    "src/archguard/infrastructure/semantic_construction_diagnostic.py",
)
INTENDED = {
    *IMPLEMENTATION,
    "tests/benchmark/test_semantic_construction_diagnostic.py",
    "docs/verification/PROMPT_018.md",
    *(str(p) for p in (PLAN, AGGREGATE, RECEIPT, PUBLIC)),
}
SAFE_INPUTS = (
    p017.DESTINATION,
    p017.BINDING,
    p017.AGGREGATE,
    p017.RECEIPT,
    p017.PUBLIC,
    p017.recovery.base.TRUTH,
    p017.TRUTH_PUBLIC,
    CONSTRUCTION_PUBLIC,
    PLAN,
    AGGREGATE,
    RECEIPT,
    PUBLIC,
)


def repository_gate(clean: bool = False) -> None:
    for commit in (*COMMITS, CONSTRUCTION_COMMIT, FIRST_HUMAN_ACCEPTANCE_COMMIT):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P018_BLOCKED_REPOSITORY_DRIFT")
    for newer in (FIRST_HUMAN_ACCEPTANCE_COMMIT, *COMMITS):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", CONSTRUCTION_COMMIT, newer], capture_output=True
        ).returncode:
            raise ValueError("P018_BLOCKED_REPOSITORY_DRIFT")
    changed = set(
        subprocess.check_output(["git", "diff", "--name-only", "HEAD"], text=True).splitlines()
    )
    changed.update(
        subprocess.check_output(
            ["git", "ls-files", "--others", "--exclude-standard"], text=True
        ).splitlines()
    )
    if changed - INTENDED or (clean and subprocess.check_output(["git", "status", "--porcelain"])):
        raise ValueError("P018_BLOCKED_REPOSITORY_DRIFT")
    path = CONSTRUCTION_PUBLIC / "sample-freeze-v1.json"
    if (
        subprocess.check_output(["git", "show", f"{CONSTRUCTION_COMMIT}:{path}"])
        != path.read_bytes()
    ):
        raise ValueError("P018_BLOCKED_CONSTRUCTION_FREEZE_DRIFT")


def source_hashes() -> dict[str, str]:
    return {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in IMPLEMENTATION}


def frozen_reference():
    verify_p017(BASE, p017.DESTINATION, P017)
    truth, _ = verify_truth(p017.recovery.base.TRUTH, p017.TRUTH_PUBLIC, TRUTH)
    return truth


def committed_plan():
    plan = json.loads(PLAN.read_bytes())
    require_plan(PLAN, plan["fingerprint"], INPUTS)
    if (
        plan["implementation_sha256"] != source_hashes()
        or subprocess.check_output(["git", "show", f"HEAD:{PLAN}"]) != PLAN.read_bytes()
    ):
        raise ValueError("P018_BLOCKED_DIAGNOSTIC_PLAN_DRIFT")
    return plan


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare-plan", "run", "verify"):
        group.add_argument("--" + action, action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    repository_gate(clean=args.run)
    if args.prepare_plan:
        with evaluation_io(Path("experiments"), SAFE_INPUTS, DESTINATION):
            frozen_reference()
        definition = diagnostic_plan(INPUTS)
        plan = sealed(
            {k: v for k, v in definition.items() if k != "fingerprint"}
            | {"implementation_sha256": source_hashes()}
        )
        append_sealed(PLAN, plan)
        print(
            canonical(
                {
                    "status": "P018_DIAGNOSTIC_PLAN_FROZEN_BEFORE_INTENT",
                    "plan_fingerprint": plan["fingerprint"],
                    "construction_intent_opened": False,
                    "provider_calls": 0,
                }
            )
        )
        return
    plan = committed_plan()
    with evaluation_io(Path("experiments"), (*SAFE_INPUTS, CONSTRUCTION_PRIVATE), DESTINATION):
        truth = frozen_reference()
        try:
            intent_input = load_construction(
                CONSTRUCTION_PUBLIC,
                CONSTRUCTION_PRIVATE,
                CONSTRUCTION,
                PLAN,
                plan["fingerprint"],
                INPUTS,
            )
        except ValueError as exc:
            code = (
                "P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH"
                if "DESIGN_MISMATCH" in str(exc)
                else "P018_BLOCKED_CONSTRUCTION_FREEZE_DRIFT"
            )
            raise ValueError(code) from None
        joined = make_join(intent_input, truth, plan["fingerprint"], INPUTS)
        if args.run:
            aggregate, receipt = freeze_diagnostic(DESTINATION, intent_input, joined)
        else:
            public = json.loads(PUBLIC.read_bytes())
            verify_opaque_seal(PUBLIC, public["fingerprint"])
            aggregate, receipt = verify_diagnostic(
                DESTINATION, public["freeze_receipt_fingerprint"]
            )
            if (
                json.loads((DESTINATION / "intent-input-v1.json").read_bytes()) != intent_input
                or json.loads((DESTINATION / "construction-truth-join-v1.json").read_bytes())
                != joined
                or json.loads(verify_opaque_seal(AGGREGATE, aggregate["fingerprint"])) != aggregate
                or json.loads(verify_opaque_seal(RECEIPT, receipt["fingerprint"])) != receipt
                or public != verification(aggregate, receipt)
            ):
                raise ValueError("P018 deterministic public/private binding drift")
            print(
                canonical(
                    {
                        "status": "P018_DIAGNOSTIC_VERIFIED",
                        "aggregate_fingerprint": aggregate["fingerprint"],
                        "provider_calls": 0,
                    }
                )
            )
            return
        frozen_reference()
    public = verification(aggregate, receipt)
    for path, value in ((AGGREGATE, aggregate), (RECEIPT, receipt), (PUBLIC, public)):
        append_sealed(path, value)
    print(
        canonical(
            {
                "status": public["status"],
                "aggregate_fingerprint": aggregate["fingerprint"],
                "provider_calls": 0,
            }
        )
    )


def verification(aggregate, receipt):
    return sealed(
        {
            "schema_version": "p018-public-verification-v1",
            "status": "CONSTRUCTION_INTENT_DIAGNOSTIC_FROZEN",
            "next_state": "READY_FOR_COMPONENT_BASELINE_EXPERIMENT",
            "frozen_inputs": INPUTS,
            "analysis_plan_fingerprint": aggregate["plan_fingerprint"],
            "plan_frozen_before_intent_join": True,
            "construction_origin_commit": CONSTRUCTION_COMMIT,
            "first_human_acceptance_commit": FIRST_HUMAN_ACCEPTANCE_COMMIT,
            "construction_predates_human_acceptance_truth_ai_and_p017": True,
            "construction_intent_input_fingerprint": receipt[
                "construction_intent_input_fingerprint"
            ],
            "construction_truth_join_fingerprint": receipt["join_fingerprint"],
            "private_join_sha256": receipt["files"]["construction-truth-join-v1.json"],
            "private_diagnostic_fingerprint": receipt["private_diagnostic_fingerprint"],
            "private_diagnostic_sha256": receipt["files"]["private-diagnostic-v1.json"],
            "aggregate_fingerprint": aggregate["fingerprint"],
            "freeze_receipt_fingerprint": receipt["fingerprint"],
            "construction_freeze_verified": True,
            "human_truth_freeze_verified": True,
            "p017_freeze_verified": True,
            "cases": 100,
            "pairs": 50,
            "mutation_cases": 50,
            "control_cases": 50,
            "malformed_pairs": 0,
            "missing_construction_cases": 0,
            "human_labels_changed": False,
            "cases_removed": False,
            "cases_replaced": False,
            "pair_membership_changed": False,
            "mutation_operators_changed": False,
            "p017_metrics_altered": False,
            "provider_calls": 0,
            "credentials_read": False,
            "static_graph_v2_hybrid_executed": False,
            "security_or_ablation_executed": False,
            "construction_intent_diagnostic_frozen": True,
            "mutation_validity_evidence_available": True,
        }
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, PermissionError, OSError, KeyError, TypeError) as exc:
        code = (
            str(exc)
            if str(exc).startswith("P018_BLOCKED_")
            else "P018_BLOCKED_INPUT_OR_FREEZE_DRIFT"
        )
        print(canonical({"status": code, "error_type": type(exc).__name__, "provider_calls": 0}))
        raise SystemExit(1) from None
