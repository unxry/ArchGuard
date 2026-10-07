"""Approved frozen snapshots and immutable, privacy-separated agreement artifacts."""

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_agreement import CaseAlignment, align_decisions, analyze_agreement
from archguard.benchmark.semantic_review import Outcome, ReviewerASubmission, ReviewerBSubmission
from archguard.core.model.base import DomainModel
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory

SOURCE_LINEAGE_KEYS = {
    "p015_commit",
    "B_closure_commit",
    "corpus_fingerprint",
    "sample_fingerprint",
    "sample_freeze_fingerprint",
    "protocol_fingerprint",
}


class ReviewExpectation(DomainModel):
    reviewer_slot: Literal["A", "B"]
    submission_sha256: Digest
    acceptance_receipt_fingerprint: Digest
    submission_fingerprint: Digest
    bundle_fingerprint: Digest


class FrozenDecisions(ReviewExpectation):
    decisions: dict[str, Outcome]


def verify_frozen_review(root: Path, expected: ReviewExpectation) -> FrozenDecisions:
    if (
        root.name != "frozen-v1"
        or root.parent.name != (f"reviewer-{expected.reviewer_slot.lower()}-submissions-v1")
        or root.is_symlink()
    ):
        raise ValueError("accepted frozen reviewer path required")
    source = root / "submission-v1.json"
    receipt_path = root / "submission-freeze-v1.json"
    if source.is_symlink() or receipt_path.is_symlink():
        raise ValueError("symlinked reviewer inputs forbidden")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected.submission_sha256:
        raise ValueError("approved frozen snapshot SHA-256 mismatch")
    receipt = json.loads(receipt_path.read_bytes())
    if (
        receipt["fingerprint"] != expected.acceptance_receipt_fingerprint
        or digest({k: v for k, v in receipt.items() if k != "fingerprint"})
        != expected.acceptance_receipt_fingerprint
    ):
        raise ValueError("approved acceptance receipt mismatch")
    submission = (
        ReviewerASubmission.model_validate_json(raw)
        if expected.reviewer_slot == "A"
        else ReviewerBSubmission.model_validate_json(raw)
    )
    if digest(submission) != expected.submission_fingerprint:
        raise ValueError("approved canonical submission mismatch")
    if (
        submission.bundle_fingerprint != expected.bundle_fingerprint
        or receipt["bundle_fingerprint"] != expected.bundle_fingerprint
        or receipt["submission_sha256"] != expected.submission_sha256
        or receipt["submission_fingerprint"] != expected.submission_fingerprint
        or receipt["reviewer_slot"] != expected.reviewer_slot
        or receipt["responses"] != 100
        or receipt["decision_counts"] != dict(Counter(r.decision for r in submission.responses))
        or receipt["final_ground_truth"] is not False
    ):
        raise ValueError("frozen reviewer lineage/completeness mismatch")
    return FrozenDecisions(
        **expected.model_dump(), decisions={r.blinded_id: r.decision for r in submission.responses}
    )


def _sealed(value: dict[str, Any]) -> dict[str, Any]:
    return value | {"fingerprint": digest(value)}


def build_agreement_artifacts(
    cases: tuple[CaseAlignment, ...],
    a: FrozenDecisions,
    b: FrozenDecisions,
    source_lineage: dict[str, str],
) -> dict[str, dict[str, Any]]:
    if a.reviewer_slot != "A" or b.reviewer_slot != "B":
        raise ValueError("independent A and B streams required")
    if set(source_lineage) != SOURCE_LINEAGE_KEYS:
        raise ValueError("only approved source-free lineage fields allowed")
    paired = align_decisions(cases, a.decisions, b.decisions)
    a_lineage = a.model_dump(exclude={"decisions"})
    b_lineage = b.model_dump(exclude={"decisions"})
    lineage = {"source": source_lineage, "A": a_lineage, "B": b_lineage}
    analysis = _sealed(
        {
            "schema_version": "semantic-inter-reviewer-agreement-v1",
            "status": "INTER_REVIEWER_AGREEMENT_FROZEN",
            "lineage": lineage,
            **analyze_agreement(paired),
        }
    )
    conflicts = []
    safe_cases = []
    for case in paired:
        if case.a_decision == case.b_decision:
            continue
        conflict_id = "conflict-" + digest(
            {
                "sample_fingerprint": source_lineage["sample_fingerprint"],
                "case_id": case.case_id,
            }
        )
        conflicts.append(
            case.model_dump()
            | {
                "conflict_id": conflict_id,
                "source_freeze_lineage": source_lineage,
                "A_freeze_lineage": a_lineage,
                "B_freeze_lineage": b_lineage,
            }
        )
        safe_cases.append(
            {
                "conflict_id": conflict_id,
                "case_id": case.case_id,
                "rule_id": case.rule_id,
                "language": case.language,
            }
        )
    count = len(conflicts)
    manifest = _sealed(
        {
            "schema_version": "semantic-review-conflicts-v1",
            "status": "FROZEN_UNRESOLVED",
            "lineage": lineage,
            "conflict_count": count,
            "conflicts": conflicts,
            "automatic_resolution": False,
            "final_ground_truth_materialized": False,
        }
    )
    index = _sealed(
        {
            "schema_version": "adjudicator-safe-conflict-index-v1",
            "source_lineage": source_lineage,
            "conflict_count": count,
            "cases": safe_cases,
            "full_handoff_created": False,
        }
    )
    if count != analysis["primary"]["disagreement"]:
        raise ValueError("conflict set incomplete")
    receipt = _sealed(
        {
            "schema_version": "semantic-agreement-verification-v1",
            "status": "INTER_REVIEWER_AGREEMENT_FROZEN",
            "next_state": "READY_FOR_ADJUDICATOR_HANDOFF",
            "ground_truth_status": "FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN",
            "lineage": lineage,
            "paired_cases": len(paired),
            "unique_scientific_cases": len(paired),
            "missing_counterparts": 0,
            "duplicate_counterparts": 0,
            "conflict_count": count,
            "agreement_analysis_fingerprint": analysis["fingerprint"],
            "conflict_manifest_fingerprint": manifest["fingerprint"],
            "adjudicator_safe_index_fingerprint": index["fingerprint"],
            "A_input_verification": "PASS",
            "B_input_verification": "PASS",
            "old_freezes_unchanged": True,
            "human_content_modified": False,
            "construction_intent_used_for_comparison": False,
            "conflicts_resolved": 0,
            "final_ground_truth_materialized": False,
            "full_adjudicator_handoff_created": False,
            "live_ai_calls": 0,
            "structural_v2_run": False,
            "hybrid_run": False,
            "semantic_effectiveness_metrics_run": False,
            "prompt016_started": False,
        }
    )
    return {"analysis": analysis, "conflicts": manifest, "index": index, "receipt": receipt}


PUBLIC_FILES = {
    "analysis": "agreement-analysis-v1.json",
    "receipt": "agreement-verification-v1.json",
}
PRIVATE_FILES = {
    "conflicts": "conflict-manifest-v1.json",
    "index": "adjudicator-safe-index-v1.json",
}


def freeze_agreement_artifacts(
    public: Path, private: Path, artifacts: dict[str, dict[str, Any]]
) -> None:
    if any(p.exists() or p.is_symlink() for p in (public, private)):
        raise ValueError("agreement freeze is immutable; cannot overwrite")

    def build_private(stage: Path) -> None:
        stage.chmod(0o700)
        for key, name in PRIVATE_FILES.items():
            write_new(stage / name, artifacts[key])

    def build_public(stage: Path) -> None:
        for key, name in PUBLIC_FILES.items():
            write_new(stage / name, artifacts[key])

    atomic_directory(private, build_private)
    atomic_directory(public, build_public)


def verify_agreement_artifacts(
    public: Path, private: Path, artifacts: dict[str, dict[str, Any]]
) -> None:
    for root, files in ((public, PUBLIC_FILES), (private, PRIVATE_FILES)):
        if root.is_symlink() or {p.name for p in root.iterdir()} != set(files.values()):
            raise ValueError("frozen agreement inventory mismatch")
        for key, name in files.items():
            path = root / name
            if (
                path.is_symlink()
                or path.read_bytes() != (canonical(artifacts[key]) + "\n").encode()
            ):
                raise ValueError("frozen agreement artifact changed")
