"""Category-only deterministic human merge; no source, construction or detector inputs."""

import hashlib
from collections import Counter
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from archguard.benchmark.oss.models import Sealed, canonical, digest
from archguard.benchmark.semantic_agreement import (
    BINARY,
    CATEGORIES,
    CaseAlignment,
    align_decisions,
)
from archguard.benchmark.semantic_holdout import Language
from archguard.benchmark.semantic_review import Outcome
from archguard.core.model.base import DomainModel
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory

MERGE_RULE: Literal["EXACT_A_B_AGREEMENT_ELSE_ACCEPTED_THIRD_HUMAN_V1"] = (
    "EXACT_A_B_AGREEMENT_ELSE_ACCEPTED_THIRD_HUMAN_V1"
)
METHODOLOGY = (
    "P015 is a CONTROLLED PROSPECTIVE SEMANTIC HOLDOUT created using mutation-based "
    "matched-pair construction. Its final human category distribution is NOT natural "
    "real-world prevalence. P013/P014 remains a separate OSS/natural cohort; prevalence "
    "statistics must not be merged."
)
EXPECTED_COUNTS = {"POSITIVE": 50, "NEGATIVE": 46, "UNCERTAIN": 3, "OUT_OF_SCOPE": 1}
LINEAGE_KEYS = {
    "sample_fingerprint",
    "sample_freeze_fingerprint",
    "corpus_fingerprint",
    "A_submission_sha256",
    "A_submission_fingerprint",
    "A_acceptance_receipt_fingerprint",
    "B_submission_sha256",
    "B_submission_fingerprint",
    "B_acceptance_receipt_fingerprint",
    "agreement_analysis_fingerprint",
    "conflict_manifest_fingerprint",
    "safe_conflict_index_fingerprint",
    "adjudicator_submission_sha256",
    "adjudicator_submission_fingerprint",
    "adjudicator_acceptance_receipt_fingerprint",
    "adjudicator_mapping_fingerprint",
    "source_closure_commit",
}


class TruthCase(DomainModel):
    scientific_case_id: str
    target_rule: str = Field(pattern=r"^ARCH20[1-5]$")
    language: Language
    final_category: Outcome
    resolution_provenance: Literal["A_B_AGREEMENT", "THIRD_HUMAN_ADJUDICATION"]


class FinalHumanTruth(Sealed):
    schema_version: Literal["semantic-final-human-ground-truth-v1"] = (
        "semantic-final-human-ground-truth-v1"
    )
    merge_rule: Literal["EXACT_A_B_AGREEMENT_ELSE_ACCEPTED_THIRD_HUMAN_V1"] = MERGE_RULE
    methodology: str = METHODOLOGY
    lineage: dict[str, str]
    cases: tuple[TruthCase, ...]

    @model_validator(mode="after")
    def partition(self) -> Self:
        if len(self.cases) != 100 or len({c.scientific_case_id for c in self.cases}) != 100:
            raise ValueError("exactly 100 unique final scientific cases required")
        if Counter(c.final_category for c in self.cases) != EXPECTED_COUNTS:
            raise ValueError("MACRO_BLOCKED_STAGE_A_COUNT_MISMATCH")
        if Counter(c.resolution_provenance for c in self.cases) != {
            "A_B_AGREEMENT": 96,
            "THIRD_HUMAN_ADJUDICATION": 4,
        }:
            raise ValueError("96 agreement plus 4 adjudication partition required")
        if Counter((c.target_rule, c.language) for c in self.cases) != {
            (f"ARCH20{i}", language): 10 for i in range(1, 6) for language in ("JAVA", "TYPESCRIPT")
        }:
            raise ValueError("frozen rule/language cohort mismatch")
        if (
            self.methodology != METHODOLOGY
            or set(self.lineage) != LINEAGE_KEYS
            or any(
                len(value) not in (40, 64) or any(c not in "0123456789abcdef" for c in value)
                for value in self.lineage.values()
            )
        ):
            raise ValueError("source-free immutable lineage required")
        return self


def merge_final_truth(
    cases: tuple[CaseAlignment, ...],
    a: dict[str, Outcome],
    b: dict[str, Outcome],
    adjudicator: dict[str, Outcome],
    adjudicator_mapping: dict[str, str],
    frozen_conflict_cases: set[str],
    lineage: dict[str, str],
) -> FinalHumanTruth:
    paired = align_decisions(cases, a, b)
    conflicts = {c.case_id for c in paired if c.a_decision != c.b_decision}
    if (
        len(conflicts) != 4
        or conflicts != frozen_conflict_cases
        or len(adjudicator_mapping) != 4
        or len(set(adjudicator_mapping.values())) != 4
        or set(adjudicator_mapping.values()) != conflicts
        or set(adjudicator) != set(adjudicator_mapping)
    ):
        raise ValueError("exact frozen conflict/adjudicator identity mapping required")
    resolved = {adjudicator_mapping[key]: value for key, value in adjudicator.items()}
    rows = [
        TruthCase(
            scientific_case_id=case.case_id,
            target_rule=case.rule_id,
            language=case.language,
            final_category=(
                case.a_decision if case.a_decision == case.b_decision else resolved[case.case_id]
            ),
            resolution_provenance=(
                "A_B_AGREEMENT"
                if case.a_decision == case.b_decision
                else "THIRD_HUMAN_ADJUDICATION"
            ),
        )
        for case in paired
    ]
    value = {
        "schema_version": "semantic-final-human-ground-truth-v1",
        "merge_rule": MERGE_RULE,
        "methodology": METHODOLOGY,
        "lineage": lineage,
        "cases": rows,
    }
    return FinalHumanTruth.model_validate(value | {"fingerprint": digest(value)})


def reference_counts(rows: tuple[TruthCase, ...]) -> dict[str, int]:
    counts = Counter(c.final_category for c in rows)
    return {
        "N": len(rows),
        **{category: counts[category] for category in CATEGORIES},
        "binary_eligible": sum(counts[c] for c in BINARY),
        "binary_excluded": counts["UNCERTAIN"] + counts["OUT_OF_SCOPE"],
    }


def truth_receipt(truth: FinalHumanTruth) -> dict[str, Any]:
    raw = (canonical(truth) + "\n").encode()
    value = {
        "schema_version": "semantic-final-human-ground-truth-freeze-v1",
        "status": "FINAL_HUMAN_GROUND_TRUTH_FROZEN",
        "ground_truth_sha256": hashlib.sha256(raw).hexdigest(),
        "ground_truth_fingerprint": truth.fingerprint,
        "lineage": truth.lineage,
        "lineage_fingerprint": digest(truth.lineage),
        "merge_rule": truth.merge_rule,
        "methodology": METHODOLOGY,
        "counts": reference_counts(truth.cases),
        "by_rule": {
            rule: reference_counts(tuple(c for c in truth.cases if c.target_rule == rule))
            for rule in sorted({c.target_rule for c in truth.cases})
        },
        "by_language": {
            language: reference_counts(tuple(c for c in truth.cases if c.language == language))
            for language in ("JAVA", "TYPESCRIPT")
        },
        "agreement_cases": 96,
        "adjudicated_cases": 4,
        "unique_scientific_cases": 100,
        "binary_eligible_categories": list(BINARY),
        "binary_excluded_categories": ["UNCERTAIN", "OUT_OF_SCOPE"],
        "POSITIVE_CLASS_PRESENT": True,
        "PRIMARY_SEMANTIC_EFFECTIVENESS_REFERENCE_READY": True,
        "human_content_modified": False,
        "construction_intent_used": False,
        "detector_effectiveness_calculated": False,
        "live_ai_calls": 0,
    }
    return value | {"fingerprint": digest(value)}


def freeze_final_truth(destination: Path, truth: FinalHumanTruth) -> dict[str, Any]:
    if destination.name != "final-human-ground-truth-v1" or destination.parent.name != "private":
        raise ValueError("private final truth destination required")
    receipt = truth_receipt(truth)

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        for name, value in (
            ("ground-truth-v1.json", truth),
            ("ground-truth-freeze-v1.json", receipt),
        ):
            write_new(stage / name, value)
            (stage / name).chmod(0o600)

    atomic_directory(destination, build)
    verify_final_truth(destination, truth)
    return receipt


def verify_final_truth(destination: Path, truth: FinalHumanTruth) -> dict[str, Any]:
    expected = {"ground-truth-v1.json": truth, "ground-truth-freeze-v1.json": truth_receipt(truth)}
    if destination.is_symlink() or {p.name for p in destination.iterdir()} != set(expected):
        raise ValueError("final truth frozen inventory changed")
    for name, value in expected.items():
        path = destination / name
        if path.is_symlink() or path.read_bytes() != (canonical(value) + "\n").encode():
            raise ValueError("final truth frozen bytes changed")
    return truth_receipt(truth)
