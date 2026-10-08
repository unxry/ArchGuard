"""P017 offline evaluation; credentials, construction files and network are unavailable."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import prompt016_recovery as recovery

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_positive_experiment import analysis_plan
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    aggregate_results,
    append_sealed,
    evaluation_io,
    freeze_evaluation,
    prepare_join,
    validate_join,
    verify_evaluation,
    verify_truth,
)
from archguard.infrastructure.semantic_positive_evaluator import join_frozen_positive
from archguard.infrastructure.semantic_positive_execution import verify_assessments

BASE = recovery.base.BASE
DESTINATION = BASE / "private/p017-evaluation-v1"
MAPPING = BASE / "private/p016-coordinator-v1/identity-map.json"
TRUTH_PUBLIC = BASE / "final-human-ground-truth-verification-v1.json"
BINDING = BASE / "p017-input-binding-v1.json"
AGGREGATE = BASE / "p017-aggregate-evaluation-v1.json"
RECEIPT = BASE / "p017-evaluation-freeze-v1.json"
PUBLIC = BASE / "p017-verification-v1.json"
EXPECTED = {
    "truth_sha256": "db4872615247e856d416e76653d0396a3aee1c430b5fdd8de33bc5e39afabfd1",
    "truth_fingerprint": "1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276",
    "truth_lineage_fingerprint": "5060d5144a84da8dc03d2175b6d661259769afc050051aed30188deb147b75b3",
    "truth_receipt_fingerprint": "3e8596e27f968df9ed6ca3a74d9592d53409da1f1bfa624852077c63ed0da62d",
    "truth_public_fingerprint": "8d2af0804bbc208662818f58618f246c200976f74b8a98ebbe47e57938cfa46d",
    "raw_ledger_fingerprint": "3da8f912c440da854d08df6a248cf6986f699c503a38d041b20fdad60d5cb219",
    "normalized_assessment_fingerprint": (
        "a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273"
    ),
    "usage_ledger_fingerprint": "bce262982fbaa9a70193599d1488a3b266099caabea591238099448e20b5c3b6",
    "execution_lineage_fingerprint": (
        "50bc6bc4ee363f18eedfcbdc8f0b7f27ea0f1be046bbaa0e30939cfa735c5d3e"
    ),
    "recovery_amendment_fingerprint": (
        "4ec308447a8208573e0a4644f67c4a754a68e8d2b280ae66ed05696bd60326aa"
    ),
    "ai_freeze_receipt_fingerprint": (
        "3ff09ed8f27012929412e9c801084ecc552feb2edd1d355a421c9cf58280a4eb"
    ),
    "ai_public_fingerprint": "67d3a635a649789bbfd4dc23e64a8a05dc3d3013de71b02b6fe1beb57e1faebe",
    "mapping_fingerprint": "616f8861220a384c1e7c4b0c710601b76c1c188a79f9ee627e44949b3cbbee67",
    "analysis_plan_fingerprint": "8659f3683603e60218e8baf2d14104f50b86d722caf4d491770e199614739bf5",
}
COMMITS = (
    "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
    "c4e2ed358568e8b0992f8cc3838e688443bbfb5d",
    "c34ac13caf5e77ffb37ac7417366dd866664c412",
    "9b675f50eb06c81fef92b83cf2c69a5e36553bdd",
    "802257d1211e519ae174736c8d83c3614f2678ea",
)
IMPLEMENTATION = (
    "scripts/prompt017_evaluation.py",
    "src/archguard/benchmark/semantic_positive_evaluation.py",
    "src/archguard/infrastructure/semantic_positive_evaluator.py",
    "src/archguard/infrastructure/semantic_positive_evaluation_freeze.py",
)
INTENDED = {
    *IMPLEMENTATION,
    "tests/intelligence/test_semantic_positive_evaluation_freeze.py",
    "tests/intelligence/test_semantic_positive_evaluation.py",
    "docs/verification/PROMPT_017.md",
    *(str(p) for p in (BINDING, AGGREGATE, RECEIPT, PUBLIC)),
}
INPUT_PATHS = (
    recovery.base.ROOT,
    recovery.base.LEDGER,
    recovery.base.TRUTH,
    MAPPING,
    TRUTH_PUBLIC,
    BASE / "p016-offline-v1",
    BASE / "p016-offline-safety-verification-v1.json",
    recovery.base.PUBLIC,
    recovery.PUBLIC,
    recovery.AMENDMENT,
    recovery.AUDIT,
    recovery.base.PRICING,
    BINDING,
    AGGREGATE,
    RECEIPT,
    PUBLIC,
)


def gates():
    for commit in COMMITS:
        if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"]).returncode:
            raise ValueError("P017_BLOCKED_REPOSITORY_DRIFT")
    recovery.base.INTENDED.update(INTENDED)
    recovery.gates()
    public = json.loads(verify_opaque_seal(recovery.PUBLIC, EXPECTED["ai_public_fingerprint"]))
    if (
        public["status"] != "P016_LIVE_EXECUTION_COMPLETE"
        or not public["ai_assessment_ledger_frozen"]
    ):
        raise ValueError("P017_BLOCKED_AI_FREEZE_DRIFT")
    verify_assessments(
        recovery.base.LEDGER, recovery.base.BINDINGS, EXPECTED["ai_freeze_receipt_fingerprint"]
    )
    for name, key in (
        ("raw-ledger.json", "raw_ledger_fingerprint"),
        ("normalized-assessments.json", "normalized_assessment_fingerprint"),
        ("attempt-usage-ledger.json", "usage_ledger_fingerprint"),
        ("execution-lineage.json", "execution_lineage_fingerprint"),
    ):
        verify_opaque_seal(recovery.base.LEDGER / name, EXPECTED[key])
    verify_opaque_seal(recovery.AMENDMENT, EXPECTED["recovery_amendment_fingerprint"])
    plan = json.loads((recovery.base.ROOT / "analysis-plan.json").read_bytes())
    if digest(plan) != EXPECTED["analysis_plan_fingerprint"] or plan != analysis_plan():
        raise ValueError("P017_BLOCKED_AI_FREEZE_DRIFT")
    truth, receipt = verify_truth(recovery.base.TRUTH, TRUTH_PUBLIC, EXPECTED)
    verify_opaque_seal(MAPPING, EXPECTED["mapping_fingerprint"])
    return public, truth, receipt


def regenerate_join():
    return join_frozen_positive(
        recovery.base.ROOT,
        recovery.base.LEDGER,
        recovery.base.BINDINGS,
        EXPECTED["ai_freeze_receipt_fingerprint"],
        recovery.base.TRUTH,
        EXPECTED["truth_sha256"],
        EXPECTED["truth_receipt_fingerprint"],
        MAPPING,
        EXPECTED["mapping_fingerprint"],
        EXPECTED["normalized_assessment_fingerprint"],
    )


def source_hashes():
    return {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in IMPLEMENTATION}


def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    for action in ("prepare", "run", "verify", "verify-inputs"):
        group.add_argument("--" + action, action="store_true")
    args = parser.parse_args()
    os.umask(0o077)
    with evaluation_io(Path("experiments"), INPUT_PATHS, DESTINATION):
        public, truth, truth_receipt = gates()
        distributions = {
            s: g["response_distribution"]
            for s, g in public["operational_statistics"]["by_strategy"].items()
        }
        if args.verify_inputs:
            print(
                canonical(
                    {"status": "P017_P015_TRUTH_P016_AI_INPUTS_VERIFIED", "provider_calls": 0}
                )
            )
            return
        if args.prepare:
            joined = regenerate_join()
            binding = prepare_join(DESTINATION, joined, EXPECTED, distributions)
            del binding["fingerprint"]
            binding["implementation_sha256"] = source_hashes()
            binding["fingerprint"] = digest(binding)
        else:
            binding = json.loads(BINDING.read_bytes())
            verify_opaque_seal(BINDING, binding["fingerprint"])
            if binding["inputs"] != EXPECTED or binding["implementation_sha256"] != source_hashes():
                raise ValueError("P017_BLOCKED_EVALUATOR_BINDING_DRIFT")
            join_raw = verify_opaque_seal(
                DESTINATION / "input-join-v1.json", binding["input_join_fingerprint"]
            )
            if hashlib.sha256(join_raw).hexdigest() != binding["private_join_sha256"]:
                raise ValueError("P017_BLOCKED_JOIN_DRIFT")
            joined = json.loads(join_raw)
            validate_join(joined, distributions)
            if joined != regenerate_join():
                raise ValueError("P017_BLOCKED_JOIN_DRIFT")
            if args.run:
                if subprocess.check_output(["git", "status", "--porcelain"]):
                    raise ValueError("P017_BLOCKED_REPOSITORY_DRIFT")
                if (
                    subprocess.check_output(["git", "show", f"HEAD:{BINDING}"])
                    != BINDING.read_bytes()
                ):
                    raise ValueError("input binding must be committed before metrics")
                aggregate = aggregate_results(joined, binding, public["operational_statistics"])
                receipt = freeze_evaluation(DESTINATION, joined, binding, aggregate)
            else:
                receipt = json.loads(RECEIPT.read_bytes())
                verify_opaque_seal(RECEIPT, receipt["fingerprint"])
                verify_evaluation(DESTINATION, receipt["fingerprint"])
                aggregate = json.loads(
                    verify_opaque_seal(AGGREGATE, receipt["aggregate_fingerprint"])
                )
                if aggregate != aggregate_results(
                    joined, binding, public["operational_statistics"]
                ):
                    raise ValueError("P017 deterministic aggregate drift")
                verification = json.loads(PUBLIC.read_bytes())
                verify_opaque_seal(PUBLIC, verification["fingerprint"])
                if verification["freeze_receipt_fingerprint"] != receipt["fingerprint"]:
                    raise ValueError("P017 public freeze binding drift")
                print(
                    canonical(
                        {
                            "status": "P017_EVALUATION_FREEZE_VERIFIED",
                            "aggregate_fingerprint": aggregate["fingerprint"],
                            "provider_calls": 0,
                        }
                    )
                )
                return
    if args.prepare:
        append_sealed(BINDING, binding)
        print(
            canonical(
                {
                    "status": binding["status"],
                    "input_join_fingerprint": joined["fingerprint"],
                    "binding_fingerprint": binding["fingerprint"],
                    "provider_calls": 0,
                }
            )
        )
        return
    append_sealed(AGGREGATE, aggregate)
    append_sealed(RECEIPT, receipt)
    verification = {
        "schema_version": "p017-public-verification-v1",
        "status": "P017_EVALUATION_COMPLETE",
        "semantic_effectiveness_results_frozen": True,
        "next_state": "READY_FOR_POST_SEMANTIC_ANALYSIS",
        "frozen_inputs": EXPECTED,
        "input_join_fingerprint": joined["fingerprint"],
        "private_join_sha256": binding["private_join_sha256"],
        "aggregate_fingerprint": aggregate["fingerprint"],
        "freeze_receipt_fingerprint": receipt["fingerprint"],
        "human_reference": truth_receipt["counts"],
        "readiness": aggregate["readiness"],
        "scientific_cases": 100,
        "joined_assessments": 300,
        "missing_joins": 0,
        "duplicate_joins": 0,
        "provider_calls": 0,
        "credentials_read": False,
        "construction_intent_decoded": False,
        "mutation_success_analysis": False,
        "structural_v2_run": False,
        "hybrid_run": False,
        "security_run": False,
        "static_graph_detector_comparison": False,
        "significance_test_run": False,
        "AI_or_human_frozen_data_modified": False,
    }
    verification = append_sealed(PUBLIC, verification)
    print(
        canonical(
            {
                "status": verification["status"],
                "aggregate_fingerprint": aggregate["fingerprint"],
                "freeze_receipt_fingerprint": receipt["fingerprint"],
                "public_fingerprint": verification["fingerprint"],
                "provider_calls": 0,
            }
        )
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        code = str(error)
        print(
            canonical(
                {
                    "status": code
                    if code.startswith("P017_BLOCKED_") and len(code) < 70
                    else "P017_BLOCKED_EVALUATION_INTEGRITY",
                    "error_type": type(error).__name__,
                    "provider_calls": 0,
                }
            )
        )
        sys.exit(1)
