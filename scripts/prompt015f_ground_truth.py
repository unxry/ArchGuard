"""Approved category-only final truth; explicit metadata recovery remains separate."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import prompt015e3_corrected_acceptance as e3
from prompt015c_agreement import (
    EXPECTATIONS,
    PRIVATE,
    PRIVATE_OUTPUT,
    PUBLIC_OUTPUT,
    verify_baseline,
)

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_adjudication import AdjudicatorSubmission
from archguard.benchmark.semantic_agreement import CaseAlignment
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_adjudication_corrected_acceptance import (
    recover_round_os_metadata,
)
from archguard.infrastructure.semantic_agreement import (
    build_agreement_artifacts,
    verify_agreement_artifacts,
    verify_frozen_review,
)
from archguard.infrastructure.semantic_final_truth import (
    freeze_final_truth,
    merge_final_truth,
    verify_final_truth,
)

BASELINE = "ee481149d17c2ca97c02e72100d146434e99961e"
ACCEPTANCE_FP = "ba7397577483b344a5f94a0fc1adb4fbe51732d20d3234f61944fb2241b7e32e"
ADJUDICATOR_FP = "9ce7c7c38703ed0425a973de8fdee07812a4284ae85b64d916679fc198baa494"
DESTINATION = PRIVATE / "final-human-ground-truth-v1"
PUBLIC_RECEIPT = Path("experiments/semantic-holdout/final-human-ground-truth-verification-v1.json")


def material():
    subprocess.run(["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"], check=True)
    result = subprocess.run(
        [sys.executable, "scripts/prompt015e3_corrected_acceptance.py", "--verify-accepted"],
        check=True,
        capture_output=True,
        text=True,
    )
    verified = json.loads(result.stdout)
    if (
        verified["acceptance_receipt_fingerprint"] != ACCEPTANCE_FP
        or verified["submission_fingerprint"] != ADJUDICATOR_FP
    ):
        raise ValueError("MACRO_BLOCKED_STAGE_0_SCIENTIFIC_DRIFT")
    sample, source_lineage = verify_baseline()
    a, b = tuple(
        verify_frozen_review(
            PRIVATE / f"reviewer-{expected.reviewer_slot.lower()}-submissions-v1/frozen-v1",
            expected,
        )
        for expected in EXPECTATIONS
    )
    cases = tuple(
        CaseAlignment(
            case_id=c.case_id,
            a_blinded_id=c.blinded_id,
            b_blinded_id=c.blinded_id,
            rule_id=c.rule_id,
            language=c.language,
        )
        for c in sample.cases
    )
    agreement = build_agreement_artifacts(cases, a, b, source_lineage)
    verify_agreement_artifacts(PUBLIC_OUTPUT, PRIVATE_OUTPUT, agreement)
    mapping = json.loads(
        verify_opaque_seal(
            PRIVATE / "adjudicator-coordinator-v1/adjudicator-mapping-v1.json",
            e3.EXPECTED["mapping"],
        )
    )
    raw = (e3.FROZEN / "submission-v1.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != e3.CORRECTED_SHA:
        raise ValueError("approved accepted adjudicator SHA mismatch")
    adjudicator = AdjudicatorSubmission.model_validate_json(raw)
    if digest(adjudicator) != ADJUDICATOR_FP:
        raise ValueError("approved canonical adjudicator mismatch")
    lineage = {
        **{
            k: source_lineage[k]
            for k in ("sample_fingerprint", "sample_freeze_fingerprint", "corpus_fingerprint")
        },
        **{
            f"{expected.reviewer_slot}_{key}": getattr(expected, key)
            for expected in EXPECTATIONS
            for key in (
                "submission_sha256",
                "submission_fingerprint",
                "acceptance_receipt_fingerprint",
            )
        },
        "agreement_analysis_fingerprint": e3.EXPECTED["analysis"],
        "conflict_manifest_fingerprint": e3.EXPECTED["conflicts"],
        "safe_conflict_index_fingerprint": e3.EXPECTED["index"],
        "adjudicator_submission_sha256": e3.CORRECTED_SHA,
        "adjudicator_submission_fingerprint": ADJUDICATOR_FP,
        "adjudicator_acceptance_receipt_fingerprint": ACCEPTANCE_FP,
        "adjudicator_mapping_fingerprint": e3.EXPECTED["mapping"],
        "source_closure_commit": BASELINE,
    }
    return merge_final_truth(
        cases,
        a.decisions,
        b.decisions,
        {r.blinded_id: r.decision for r in adjudicator.responses},
        {r["adjudicator_blinded_id"]: r["case_id"] for r in mapping["rows"]},
        {c["case_id"] for c in agreement["conflicts"]["conflicts"]},
        lineage,
    )


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--verify", action="store_true")
    action.add_argument("--recover-metadata", action="store_true")
    args = parser.parse_args()
    if args.recover_metadata:
        audit = recover_round_os_metadata(e3.ROUND, e3.CORRECTION["package"])
        e3.prerequisites()
        audit.update(schema_version="adjudicator-macro-metadata-recovery-v1", live_ai_calls=0)
        # Each explicitly authorized recovery has a new immutable audit, never replaces history.
        path = Path("experiments/semantic-holdout") / (
            "metadata-recovery-" + digest(audit) + ".json"
        )
        write_new(path, audit | {"fingerprint": digest(audit)})
        print(json.dumps({"recovery": "PASS", "audit_fingerprint": digest(audit)}))
        return
    truth = material()
    for name in ("ground-truth-v1.json", "ground-truth-freeze-v1.json"):
        subprocess.run(["git", "check-ignore", "-q", str(DESTINATION / name)], check=True)
    if args.freeze:
        if PUBLIC_RECEIPT.exists() or PUBLIC_RECEIPT.is_symlink():
            raise ValueError("public final truth verification immutable")
        receipt = freeze_final_truth(DESTINATION, truth)
        public = {k: v for k, v in receipt.items() if k not in {"schema_version", "fingerprint"}}
        public.update(
            schema_version="semantic-final-human-ground-truth-verification-v1",
            freeze_receipt_fingerprint=receipt["fingerprint"],
            A_verification="PASS",
            B_verification="PASS",
            agreement_verification="PASS",
            adjudicator_verification="PASS",
        )
        write_new(PUBLIC_RECEIPT, public | {"fingerprint": digest(public)})
    receipt = verify_final_truth(DESTINATION, truth)
    public = json.loads(PUBLIC_RECEIPT.read_bytes())
    if (
        public["ground_truth_fingerprint"] != truth.fingerprint
        or public["freeze_receipt_fingerprint"] != receipt["fingerprint"]
    ):
        raise ValueError("public final truth binding changed")
    verify_opaque_seal(PUBLIC_RECEIPT, public["fingerprint"])
    expected = {k: v for k, v in receipt.items() if k not in {"schema_version", "fingerprint"}}
    expected.update(
        schema_version="semantic-final-human-ground-truth-verification-v1",
        freeze_receipt_fingerprint=receipt["fingerprint"],
        A_verification="PASS",
        B_verification="PASS",
        agreement_verification="PASS",
        adjudicator_verification="PASS",
    )
    if (
        PUBLIC_RECEIPT.read_bytes()
        != (canonical(expected | {"fingerprint": digest(expected)}) + "\n").encode()
    ):
        raise ValueError("public final truth bytes changed")
    print(json.dumps(public, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "MACRO_BLOCKED_STAGE_A: frozen input, mapping, counts or freeze verification failed"
        ) from None
