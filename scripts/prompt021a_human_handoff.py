"""P021.A coordination only. No command imports human answers or executes a model."""

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from archguard.infrastructure import unified_human_review as review

READY = review.BASE / "p021-a-handoff-readiness-v1.json"
PROTOCOL = {
    "version": "p021-a-independent-human-intake-v1",
    "authority": "P020_REVIEW_V2_ONLY; LEGACY_REVIEW_FORBIDDEN",
    "categories": ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
    "definitions": "UNCHANGED_P020_QUESTIONS_AND_P015_COMPATIBLE_RUBRIC",
    "responses_per_reviewer": 100,
    "human_only": True,
    "assistance": "NO_CHATGPT_CLAUDE_GEMINI_COPILOT_LLM_OR_AUTOMATIC_CLASSIFIER",
    "independence": "OWN_PACKAGE_ONLY; NO_ANSWER_EXCHANGE_BEFORE_BOTH_FREEZES",
    "evidence": "SUPPLIED_CASE_EVIDENCE_ID; INCLUSIVE_EXISTING_SOURCE_LINES; NO_EXTRA_FIELDS",
    "reviewer_privacy": "OPAQUE_human-32_LOWERCASE_HEX; PRIVATE_SELF_ATTESTATION",
    "identity_limit": (
        "COORDINATOR_MUST_VERIFY_TWO_DISTINCT_HUMANS; SOFTWARE_CANNOT_PROVE_AUTHORSHIP"
    ),
    "freeze": "SEPARATE_APPEND_ONLY_A_B; BYTE_EXACT_ORIGINAL_RESPONSE_PRESERVED",
    "correction": "EXPLICIT_HUMAN_VERSION_REASON_ATTESTATION_PREVIOUS_RECEIPT; NO_OVERWRITE",
    "metadata_recovery": "ROOT_DS_STORE_ONLY_IF_SOLE_EXTRA_AND_ALL_FROZEN_HASHES_MATCH",
    "agreement": {
        "gate": "BOTH_DISTINCT_REAL_HUMAN_SUBMISSIONS_ACCEPTED_AND_FROZEN",
        "case_alignment": "EXACT_SAME_100_OPAQUE_IDS; NOT_RESPONSE_ORDER",
        "exact_count": "COUNT_A_CATEGORY_EQUALS_B_CATEGORY_OVER_ALL_FOUR_CATEGORIES",
        "agreement_rate": "EXACT_COUNT / 100",
        "cohens_kappa": "(P_OBSERVED-P_EXPECTED)/(1-P_EXPECTED); NULL_IF_1-P_EXPECTED_ZERO",
        "p_expected": "SUM_OVER_FOUR_CATEGORIES(P_A_CATEGORY * P_B_CATEGORY)",
        "binary_eligible": "BOTH_SELECTED_POSITIVE_OR_NEGATIVE; NO_UNCERTAIN_OOS_COERCION",
        "binary_rate": "EXACT_BINARY_COUNT/BINARY_ELIGIBLE_COUNT; NULL_IF_DENOMINATOR_ZERO",
        "binary_coverage": "BINARY_ELIGIBLE_COUNT/100; RETAIN_ALL_FOUR_CATEGORY_COUNTS",
        "conflict": "A_CATEGORY != B_CATEGORY; RATIONALE_WORDING_IRRELEVANT",
        "conflict_manifest": (
            "IMMUTABLE_PRIVATE_ID_CATEGORY_ALIGNMENT; NO_CONSTRUCTION_OR_MODEL_INPUT"
        ),
        "executed": False,
    },
    "adjudication": {
        "gate": "A_B_FROZEN_AND_CATEGORICAL_CONFLICT_MANIFEST_FROZEN",
        "selection": "CATEGORICAL_CONFLICTS_ONLY; NEVER_EXACT_AGREEMENTS",
        "judge": "THIRD_DISTINCT_REAL_HUMAN; NO_AI",
        "packet": "ORIGINAL_SOURCE_TARGET_RULE_QUESTION_CONTRACT_ONLY",
        "a_b_categories_or_rationales_exposed": False,
        "design": "P015_COMPATIBLE_SOURCE_ONLY_INDEPENDENT_JUDGMENT",
        "categories": ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
        "rationale_and_line_evidence_required": True,
        "human_corrections": "SAME_EXPLICIT_APPEND_ONLY_VERSIONED_WORKFLOW",
        "executed": False,
    },
    "semantic_normalization": False,
    "construction_access": False,
    "provider_calls": 0,
    "connectivity_calls": 0,
    "paid_spend_usd": 0,
    "paid_execution_approved": False,
    "human_answers_created": False,
    "final_semantic_human_truth": "NOT_CREATED",
    "hybrid_training": False,
    "final_evaluation": False,
}


def run(repository: Path, *, prepare: bool) -> dict[str, Any]:
    lineage = review.verify_lineage(repository, allowed=review.PUBLIC_FILES)
    with review.handoff_capability(repository):
        authority = review.load_authority(repository)
        ready_path = repository / READY
        protocol_path = repository / review.PROTOCOL_PATH
        if not ready_path.exists() and not prepare:
            raise review.ReviewBlocked("P021_A_HANDOFF_NOT_PREPARED")
        if not protocol_path.exists():
            if not prepare or ready_path.exists():
                raise review.ReviewBlocked("P021_A_PROTOCOL_DRIFT")
            review.append_seal(protocol_path, PROTOCOL)
        protocol = review.read_seal(protocol_path)
        if protocol != PROTOCOL | {"fingerprint": review.digest(PROTOCOL)}:
            raise review.ReviewBlocked("P021_A_PROTOCOL_DRIFT")
        handoffs = {}
        for role in ("A", "B"):
            destination = repository / review.HANDOFF / f"reviewer-{role.lower()}"
            if not destination.exists() and prepare:
                review.prepare_handoff(authority, role, destination)
            handoffs[role] = review.verify_handoff(authority, role, destination)
        payload = dict(
            version="p021-a-authoritative-human-handoff-readiness-v1",
            status="P021_A_HUMAN_HANDOFF_READY",
            lineage=lineage,
            authoritative_review_v2="VERIFIED",
            registry_fingerprint=review.PINS[review.BASE / "p020-registry-v2.json"],
            packet_inventory_fingerprint=review.PINS[review.REVIEW / "packet-inventory.json"],
            assignment_fingerprint=authority.assignment_fingerprint,
            p020_handoff_fingerprint=review.PINS[
                review.BASE / "p020-blinded-review-handoff-v2.json"
            ],
            historical_generation_packet_fingerprint="86e037ed607c4b0d273e51215d0c174f61dcc926b8c16457bf349ef75f7a5130",
            historical_packet_authorized_for_handoff=False,
            protocol_fingerprint=protocol["fingerprint"],
            handoffs={
                role: dict(
                    role=role,
                    packets=100,
                    state="READY",
                    receipt_fingerprint=handoffs[role]["fingerprint"],
                    instructions_sha256=hashlib.sha256(review.instructions(role)).hexdigest(),
                    expected_file_count=6,
                    receipt_file_count=1,
                    archive_fingerprint=None,
                )
                for role in ("A", "B")
            },
            source_bindings={name: review.sha(repository / name) for name in review.SOURCE_FILES},
            legacy_exists=(repository / review.FINAL / "review").is_dir(),
            legacy_authorized=False,
            legacy_copied=False,
            same_case_set=True,
            independently_blinded_order=True,
            order_verification="FROZEN_OPAQUE_ID_SHA256_RANK_ONLY; NO_CONSTRUCTION_COMPARISON",
            pair_adjacency_guarantee=False,
            construction_leakage_findings=0,
            component_model_leakage_findings=0,
            source_packet_bytes_changed=False,
            answers_created=False,
            final_truth_created=False,
            agreement_executed=False,
            adjudication_executed=False,
            construction_intent_decoded=False,
            provider_calls=0,
            connectivity_calls=0,
            paid_spend_usd=0,
            paid_execution_approved=False,
            hybrid_trained=False,
            final_evaluation=False,
            workspace_exception=review.WORKTREE_EXCEPTION,
            exception_staged_or_committed=False,
            final_status=[
                "P021_A_HUMAN_HANDOFF_READY",
                "AUTHORITATIVE_REVIEW_V2_VERIFIED",
                "REVIEWER_A_PACKAGE_READY",
                "REVIEWER_B_PACKAGE_READY",
                "HUMAN_SUBMISSION_VALIDATOR_READY",
                "WAITING_FOR_REVIEWER_A_B",
            ],
        )
        if ready_path.exists():
            if review.read_seal(ready_path) != payload | {"fingerprint": review.digest(payload)}:
                raise review.ReviewBlocked("P021_A_READINESS_DRIFT")
        else:
            review.append_seal(ready_path, payload)
        # Reverify frozen authority after copying; no old package is ever opened.
        review.load_authority(repository)
    return dict(
        status=payload["status"],
        packets_per_reviewer=100,
        provider_calls=0,
        fingerprint=review.digest(payload),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify"))
    args = parser.parse_args()
    os.umask(0o077)
    sys.addaudithook(review.offline_guard)
    try:
        result = run(Path.cwd(), prepare=args.action == "prepare")
    except (ValueError, OSError, KeyError):
        # Suppress validation inputs and chained exceptions, including human/source bytes.
        print(json.dumps({"status": "P021_A_BLOCKED_FORM_OR_FREEZE_DRIFT"}))
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
