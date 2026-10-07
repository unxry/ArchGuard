"""Symmetric categorical agreement; no truth assignment or semantic evaluation."""

from fractions import Fraction
from itertools import combinations
from typing import Any

from pydantic import Field

from archguard.benchmark.semantic_holdout import Language
from archguard.benchmark.semantic_review import Outcome
from archguard.core.model.base import DomainModel

CATEGORIES: tuple[Outcome, ...] = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
BINARY: tuple[Outcome, ...] = ("POSITIVE", "NEGATIVE")


class CaseAlignment(DomainModel):
    case_id: str = Field(min_length=1)
    a_blinded_id: str = Field(min_length=1)
    b_blinded_id: str = Field(min_length=1)
    rule_id: str = Field(pattern=r"^ARCH20[1-5]$")
    language: Language


class PairedDecision(CaseAlignment):
    a_decision: Outcome
    b_decision: Outcome


def align_decisions(
    cases: tuple[CaseAlignment, ...],
    a: dict[str, Outcome],
    b: dict[str, Outcome],
    *,
    expected_cases: int = 100,
) -> tuple[PairedDecision, ...]:
    if len(cases) != expected_cases or any(
        len({getattr(case, field) for case in cases}) != expected_cases
        for field in ("case_id", "a_blinded_id", "b_blinded_id")
    ):
        raise ValueError("case alignment must be complete and one-to-one")
    if set(a) != {c.a_blinded_id for c in cases} or set(b) != {c.b_blinded_id for c in cases}:
        raise ValueError("missing or extra reviewer counterpart")
    return tuple(
        PairedDecision(
            **case.model_dump(), a_decision=a[case.a_blinded_id], b_decision=b[case.b_blinded_id]
        )
        for case in sorted(cases, key=lambda c: c.case_id)
    )


def agreement_statistics(
    paired: tuple[PairedDecision, ...],
    categories: tuple[Outcome, ...] = CATEGORIES,
) -> dict[str, Any]:
    if len(set(categories)) != len(categories) or not categories:
        raise ValueError("nonempty distinct categories required")
    matrix = {a: {b: 0 for b in categories} for a in categories}
    for case in paired:
        if case.a_decision not in matrix or case.b_decision not in matrix:
            raise ValueError("decision outside specified agreement categories")
        matrix[case.a_decision][case.b_decision] += 1
    n = len(paired)
    exact = sum(matrix[c][c] for c in categories)
    marginal_a = {c: sum(matrix[c].values()) for c in categories}
    marginal_b = {c: sum(matrix[a][c] for a in categories) for c in categories}
    observed = Fraction(exact, n) if n else None
    expected = (
        Fraction(sum(marginal_a[c] * marginal_b[c] for c in categories), n * n) if n else None
    )
    kappa = (
        (observed - expected) / (1 - expected)
        if (observed is not None and expected is not None and expected != 1)
        else None
    )
    return {
        "n": n,
        "categories": list(categories),
        "matrix_rows": "Reviewer A",
        "matrix_columns": "Reviewer B",
        "matrix": matrix,
        "exact_agreement": exact,
        "disagreement": n - exact,
        "agreement_percentage": float(observed * 100) if observed is not None else None,
        "observed_agreement": float(observed) if observed is not None else None,
        "expected_chance_agreement": float(expected) if expected is not None else None,
        "cohens_kappa": float(kappa) if kappa is not None else None,
        "kappa_undefined_reason": (
            "NO_PAIRED_CASES"
            if not n
            else "EXPECTED_CHANCE_AGREEMENT_IS_ONE; denominator 1 - p_e = 0"
            if expected == 1
            else None
        ),
        "marginals_A": marginal_a,
        "marginals_B": marginal_b,
    }


def analyze_agreement(paired: tuple[PairedDecision, ...]) -> dict[str, Any]:
    if not paired or len({c.case_id for c in paired}) != len(paired):
        raise ValueError("unique paired scientific cases required")
    binary = tuple(c for c in paired if c.a_decision in BINARY and c.b_decision in BINARY)
    rank = {c: i for i, c in enumerate(CATEGORIES)}
    taxonomy = {f"{a}<->{b}": 0 for a, b in combinations(CATEGORIES, 2)}
    for case in paired:
        if case.a_decision != case.b_decision:
            a, b = sorted((case.a_decision, case.b_decision), key=rank.__getitem__)
            taxonomy[f"{a}<->{b}"] += 1
    strata: dict[str, dict[str, Any]] = {}
    for field, values in (
        ("rule_id", tuple(f"ARCH20{i}" for i in range(1, 6))),
        ("language", ("JAVA", "TYPESCRIPT")),
    ):
        strata[field] = {}
        for value in values:
            subset = tuple(c for c in paired if getattr(c, field) == value)
            stats = agreement_statistics(subset)
            stats["interpretation"] = "DESCRIPTIVE_ONLY; small N, no population inference"
            if len(subset) < 2 or any(
                sum(count > 0 for count in stats[key].values()) < 2
                for key in ("marginals_A", "marginals_B")
            ):
                stats["cohens_kappa"] = None
                stats["kappa_undefined_reason"] = (
                    stats["kappa_undefined_reason"]
                    or "STRATUM_KAPPA_NOT_REPORTED: insufficient N or marginal category variation"
                )
            strata[field][value] = stats
    return {
        "primary": agreement_statistics(paired),
        "binary": agreement_statistics(binary, BINARY)
        | {"excluded_nonbinary": len(paired) - len(binary)},
        "disagreement_taxonomy": taxonomy,
        "strata": strata,
        "confidence_intervals": None,
        "no_reviewer_is_reference_truth": True,
        "final_ground_truth_materialized": False,
        "conflicts_resolved": 0,
        "live_ai_calls": 0,
    }
