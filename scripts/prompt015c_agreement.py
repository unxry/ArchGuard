"""Offline agreement of approved snapshots; never adjudicate or materialize truth."""

import argparse
import json
import subprocess
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_agreement import CaseAlignment
from archguard.benchmark.semantic_holdout import HoldoutSample
from archguard.infrastructure.semantic_agreement import (
    ReviewExpectation,
    build_agreement_artifacts,
    freeze_agreement_artifacts,
    verify_agreement_artifacts,
    verify_frozen_review,
)
from archguard.infrastructure.semantic_holdout import verify_file_freeze

B_CLOSURE = "439a536b38828bd78926ad6c324c21a4cc38d197"
P015 = "e91e6c13e6cc7dff7b640f9a968e52dd07745f11"
P014 = "f69a544a9b80911a471040b478173bb8bf7f9486"
SAMPLE_FREEZE = "b291e47d6b5ed7ffcbbac967b221b5dee7366fa2d559031b19bc5b3d751b3dfb"
EXPECTATIONS = (
    ReviewExpectation(
        reviewer_slot="A",
        submission_sha256="b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e",
        acceptance_receipt_fingerprint="58488f51c3050266ecdc930e8c24814d7d4040ba1101765ed2180d8a1c0ffb08",
        submission_fingerprint="5c9e97870a96b195eee3d2331f3003918cdf30ad30236922b56b93b16cf114d2",
        bundle_fingerprint="54069d685872195aafa91692d4184d4790655915da8ac4ef18d61620794c6151",
    ),
    ReviewExpectation(
        reviewer_slot="B",
        submission_sha256="dd3d7d4f97bd088eeca6e9cedbfec6a6d9732d6e05a906863f91df44e757be9f",
        acceptance_receipt_fingerprint="c6463eeb506130de7d4b02a2e511abec5e99cb299edb64791e8a8ecdc06d451d",
        submission_fingerprint="edb3a7abb78adedb7a3fc45689d713569e762ad4ede1d2c93d6982f39a6cc8db",
        bundle_fingerprint="e8dd9955c0b3151fbe98d24024d74c09ec0e6d259ae7b49e80d75805629f682a",
    ),
)
COHORT = Path("experiments/semantic-holdout/semantic-positive-holdout-v1")
PRIVATE = Path("experiments/semantic-holdout/private")
PUBLIC_OUTPUT = Path("experiments/semantic-holdout/inter-reviewer-agreement-v1")
PRIVATE_OUTPUT = PRIVATE / "inter-reviewer-agreement-v1"


def verify_baseline():
    for commit in (P014, P015, B_CLOSURE):
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
    protected = (
        "experiments/oss",
        "experiments/ai",
        "experiments/preflight",
        "experiments/pricing",
        "experiments/calibration",
        "experiments/results",
        str(COHORT),
    )
    if subprocess.check_output(["git", "diff", P015, "--name-only", "--", *protected]):
        raise ValueError("old scientific artifacts changed")
    freeze = json.loads((COHORT / "sample-freeze-v1.json").read_bytes())
    if freeze["fingerprint"] != SAMPLE_FREEZE:
        raise ValueError("unapproved P015 source freeze")
    verify_file_freeze(COHORT, freeze)
    original_private = PRIVATE / "semantic-positive-holdout-v1"
    private_freeze = json.loads((original_private / "private-freeze-v1.json").read_bytes())
    if private_freeze["fingerprint"] != freeze["private_freeze_fingerprint"]:
        raise ValueError("original private inventory changed")
    # Integrity hashes only: provenance/intent content is never decoded or joined.
    verify_file_freeze(original_private, private_freeze)
    if freeze["reviewer_bundle_fingerprints"] != {
        e.reviewer_slot: e.bundle_fingerprint for e in EXPECTATIONS
    }:
        raise ValueError("reviewer bundles differ from approved source freeze")
    sample = HoldoutSample.model_validate_json((COHORT / "sample-v1.json").read_bytes())
    if sample.fingerprint != freeze["sample_fingerprint"] or any(
        case.technical_status != "VALID" for case in sample.cases
    ):
        raise ValueError("frozen scientific case mapping changed")
    protocol = json.loads((COHORT / "review-protocol-v1.json").read_bytes())
    if protocol["fingerprint"] != digest({k: v for k, v in protocol.items() if k != "fingerprint"}):
        raise ValueError("P015 protocol seal mismatch")
    for name in ("conflict-manifest-v1.json", "adjudicator-safe-index-v1.json"):
        subprocess.run(["git", "check-ignore", "-q", str(PRIVATE_OUTPUT / name)], check=True)
    return sample, {
        "p015_commit": P015,
        "B_closure_commit": B_CLOSURE,
        "corpus_fingerprint": freeze["corpus_fingerprint"],
        "sample_fingerprint": sample.fingerprint,
        "sample_freeze_fingerprint": SAMPLE_FREEZE,
        "protocol_fingerprint": protocol["fingerprint"],
    }


def main():
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--freeze", action="store_true")
    action.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if (
        args.freeze
        and subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() != B_CLOSURE
    ):
        raise ValueError("initial agreement freeze must descend directly from approved B closure")
    sample, lineage = verify_baseline()
    a, b = tuple(
        verify_frozen_review(
            PRIVATE / f"reviewer-{e.reviewer_slot.lower()}-submissions-v1/frozen-v1", e
        )
        for e in EXPECTATIONS
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
    artifacts = build_agreement_artifacts(cases, a, b, lineage)
    if args.freeze:
        freeze_agreement_artifacts(PUBLIC_OUTPUT, PRIVATE_OUTPUT, artifacts)
    verify_agreement_artifacts(PUBLIC_OUTPUT, PRIVATE_OUTPUT, artifacts)
    verify_baseline()
    for expected in EXPECTATIONS:
        verify_frozen_review(
            PRIVATE / f"reviewer-{expected.reviewer_slot.lower()}-submissions-v1/frozen-v1",
            expected,
        )
    print(
        json.dumps(
            {"verification": artifacts["receipt"], "agreement": artifacts["analysis"]},
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError):
        raise SystemExit(
            "PROMPT_015_C_BLOCKED: approved frozen-input/artifact verification failed"
        ) from None
