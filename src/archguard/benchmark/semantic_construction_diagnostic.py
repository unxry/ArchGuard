"""Post-freeze construction diagnostics; independent human categories remain authoritative."""

from collections import Counter, defaultdict
from collections.abc import Sequence
from typing import Any, Literal

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_holdout import LANGUAGES, RULES, Language
from archguard.benchmark.semantic_positive_evaluation import ratio
from archguard.benchmark.semantic_review import Outcome
from archguard.core.model.base import DomainModel

INTENTS = ("MUTATION", "CONTROL")
CATEGORIES = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")
PAIR_CATEGORIES = (
    "FULLY_CONFIRMED",
    "MUTATION_NOT_CONFIRMED",
    "CONTROL_NOT_CONFIRMED",
    "BOTH_NOT_CONFIRMED",
)
OPERATORS = {
    "ARCH201": "arch201-replace-mapper-delegation-v1",
    "ARCH202": "arch202-inline-controller-policy-v1",
    "ARCH203": "arch203-direct-domain-persistence-v1",
    "ARCH204": "arch204-relocate-domain-policy-v1",
    "ARCH205": "arch205-mix-application-concerns-v1",
}


class ConstructionCase(DomainModel):
    scientific_case_id: str
    pair_id: str
    rule: str
    language: Language
    operator_id: str
    intent: Literal["MUTATION", "CONTROL"]


class HumanCase(DomainModel):
    scientific_case_id: str
    rule: str
    language: Language
    final_human_category: Outcome


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    return value | {"fingerprint": digest(value)}


def diagnostic_plan(inputs: dict[str, str]) -> dict[str, Any]:
    return sealed(
        {
            "schema_version": "p018-construction-diagnostic-plan-v1",
            "inputs": inputs,
            "design": {
                "cases": 100,
                "pairs": 50,
                "mutation_cases": 50,
                "control_cases": 50,
                "pairs_per_rule": 10,
                "pairs_per_language": 25,
                "pairs_per_rule_language": 5,
                "operators": OPERATORS,
            },
            "stable_identity_join": "scientific_case_id; never array position",
            "intent_directions": {
                "MUTATION": "INTENDED_MUTATION_POSITIVE",
                "CONTROL": "INTENDED_CONTROL_NEGATIVE",
            },
            "human_authority": "FINAL_HUMAN_CATEGORY; intention is not ground truth",
            "case_cross_tab": {"rows": INTENTS, "columns": CATEGORIES},
            "case_rates": {
                "mutation_positive_confirmation": "MUTATION human POSITIVE / all MUTATION",
                "mutation_negative_contradiction": "MUTATION human NEGATIVE / all MUTATION",
                "mutation_uncertain_rate": "MUTATION human UNCERTAIN / all MUTATION",
                "mutation_oos_rate": "MUTATION human OUT_OF_SCOPE / all MUTATION",
                "control_negative_confirmation": "CONTROL human NEGATIVE / all CONTROL",
                "control_positive_contradiction": "CONTROL human POSITIVE / all CONTROL",
                "control_uncertain_rate": "CONTROL human UNCERTAIN / all CONTROL",
                "control_oos_rate": "CONTROL human OUT_OF_SCOPE / all CONTROL",
                "nonbinary_rate": "(UNCERTAIN + OUT_OF_SCOPE) / all corresponding intent",
            },
            "binary_agreement": {
                "population": "human POSITIVE/NEGATIVE only; excluded categories reported",
                "agreement": "MUTATION/POSITIVE or CONTROL/NEGATIVE",
                "disagreement": "MUTATION/NEGATIVE or CONTROL/POSITIVE",
                "rate": "agreements / human binary-eligible cases; not detector accuracy",
            },
            "pair_categories": {
                "FULLY_CONFIRMED": "mutation == POSITIVE and control == NEGATIVE",
                "MUTATION_NOT_CONFIRMED": "mutation != POSITIVE and control == NEGATIVE",
                "CONTROL_NOT_CONFIRMED": "mutation == POSITIVE and control != NEGATIVE",
                "BOTH_NOT_CONFIRMED": "mutation != POSITIVE and control != NEGATIVE",
            },
            "pair_rates": "category count / all original pairs; nonbinary pairs retained",
            "pair_tags": ["either member UNCERTAIN", "either member OUT_OF_SCOPE"],
            "directionality": "full 4x4 mutation/control human categories; no ordinal ranking",
            "strata": ["rule/operator", "language", "rule x language"],
            "strata_interpretation": "DESCRIPTIVE; small N; no statistical superiority",
            "interpretation": {
                "mutation_negative": "intended violation not independently confirmed",
                "control_positive": "matched control judged to exhibit target violation",
                "uncertain": "preserve uncertainty",
                "out_of_scope": "preserve scope exclusion",
            },
            "zero_denominator": None,
            "objective_validity_threshold": None,
            "no_relabel_no_replacement": True,
            "no_pair_or_operator_changes": True,
            "no_filtering_rebalancing_or_regeneration": True,
            "no_p017_recalculation_or_clean_subset_f1": True,
            "no_ai_error_cross_reference": True,
            "no_inferential_tests": True,
            "no_provider_network_detector_or_paid_execution": True,
            "privacy": "case/pair identities private; public aggregates only",
        }
    )


def validate_design(cases: Sequence[ConstructionCase]) -> None:
    if len(cases) != 100 or len({c.scientific_case_id for c in cases}) != 100:
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    if Counter(c.intent for c in cases) != {"MUTATION": 50, "CONTROL": 50}:
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    pairs: dict[str, list[ConstructionCase]] = defaultdict(list)
    for c in cases:
        if c.rule not in OPERATORS or c.operator_id != OPERATORS[c.rule] or not c.pair_id:
            raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
        pairs[c.pair_id].append(c)
    if len(pairs) != 50:
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    for members in pairs.values():
        if (
            len(members) != 2
            or {c.intent for c in members} != set(INTENTS)
            or len({(c.rule, c.language, c.operator_id) for c in members}) != 1
        ):
            raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    if Counter((v[0].rule, v[0].language) for v in pairs.values()) != {
        (rule, language): 5 for rule in RULES for language in LANGUAGES
    }:
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")


def join_intent(
    cases: Sequence[ConstructionCase],
    humans: Sequence[HumanCase],
    inputs: dict[str, str],
    plan: str,
) -> dict[str, Any]:
    validate_design(cases)
    reference = {h.scientific_case_id: h for h in humans}
    if (
        len(humans) != 100
        or len(reference) != 100
        or set(reference) != {c.scientific_case_id for c in cases}
    ):
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    rows = []
    for case in sorted(cases, key=lambda c: c.scientific_case_id):
        h = reference[case.scientific_case_id]
        if (h.rule, h.language) != (case.rule, case.language):
            raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
        rows.append(case.model_dump(mode="json") | {"final_human_category": h.final_human_category})
    return sealed(
        {
            "schema_version": "p018-private-construction-truth-join-v1",
            "plan_fingerprint": plan,
            "inputs": inputs,
            "rows": rows,
        }
    )


def pair_category(mutation: str, control: str) -> str:
    if mutation not in CATEGORIES or control not in CATEGORIES:
        raise ValueError("unknown final human category")
    if mutation == "POSITIVE":
        return "FULLY_CONFIRMED" if control == "NEGATIVE" else "CONTROL_NOT_CONFIRMED"
    return "MUTATION_NOT_CONFIRMED" if control == "NEGATIVE" else "BOTH_NOT_CONFIRMED"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cross = {intent: {category: 0 for category in CATEGORIES} for intent in INTENTS}
    pairs: dict[str, dict[str, str]] = defaultdict(dict)
    for row in rows:
        cross[row["intent"]][row["final_human_category"]] += 1
        if row["intent"] in pairs[row["pair_id"]]:
            raise ValueError("duplicate pair member")
        pairs[row["pair_id"]][row["intent"]] = row["final_human_category"]
    if any(set(p) != set(INTENTS) for p in pairs.values()):
        raise ValueError("incomplete diagnostic pair")
    counts = {category: 0 for category in PAIR_CATEGORIES}
    directions = {m: {c: 0 for c in CATEGORIES} for m in CATEGORIES}
    uncertain = oos = 0
    for p in pairs.values():
        m, c = p["MUTATION"], p["CONTROL"]
        counts[pair_category(m, c)] += 1
        directions[m][c] += 1
        uncertain += "UNCERTAIN" in (m, c)
        oos += "OUT_OF_SCOPE" in (m, c)
    mutation, control = cross["MUTATION"], cross["CONTROL"]
    n_m, n_c = sum(mutation.values()), sum(control.values())
    binary = sum(v["POSITIVE"] + v["NEGATIVE"] for v in cross.values())
    agree = mutation["POSITIVE"] + control["NEGATIVE"]
    disagree = mutation["NEGATIVE"] + control["POSITIVE"]
    rates = {
        "mutation_positive_confirmation": ratio(mutation["POSITIVE"], n_m),
        "mutation_negative_contradiction": ratio(mutation["NEGATIVE"], n_m),
        "mutation_uncertain_rate": ratio(mutation["UNCERTAIN"], n_m),
        "mutation_oos_rate": ratio(mutation["OUT_OF_SCOPE"], n_m),
        "mutation_nonbinary_rate": ratio(mutation["UNCERTAIN"] + mutation["OUT_OF_SCOPE"], n_m),
        "control_negative_confirmation": ratio(control["NEGATIVE"], n_c),
        "control_positive_contradiction": ratio(control["POSITIVE"], n_c),
        "control_uncertain_rate": ratio(control["UNCERTAIN"], n_c),
        "control_oos_rate": ratio(control["OUT_OF_SCOPE"], n_c),
        "control_nonbinary_rate": ratio(control["UNCERTAIN"] + control["OUT_OF_SCOPE"], n_c),
    }
    return {
        "descriptive_only": True,
        "case_counts": {"total": len(rows), "MUTATION": n_m, "CONTROL": n_c},
        "intent_human_cross_tab": cross,
        "rates": rates,
        "rate_denominators": {"mutation": n_m, "control": n_c},
        "binary_agreement": {
            "eligible": binary,
            "excluded": len(rows) - binary,
            "agreements": agree,
            "disagreements": disagree,
            "rate": ratio(agree, binary),
            "cross_tab": {i: {c: cross[i][c] for c in ("POSITIVE", "NEGATIVE")} for i in INTENTS},
        },
        "pairs": {
            "total": len(pairs),
            "categories": counts,
            "rates": {c: ratio(n, len(pairs)) for c, n in counts.items()},
            "involving_uncertain": uncertain,
            "involving_out_of_scope": oos,
            "direction_cross_tab": directions,
        },
    }


def aggregate_diagnostic(joined: dict[str, Any]) -> dict[str, Any]:
    if joined["fingerprint"] != digest({k: v for k, v in joined.items() if k != "fingerprint"}):
        raise ValueError("P018 private join drift")
    rows = joined["rows"]
    validate_design(
        [
            ConstructionCase.model_validate({k: r[k] for k in ConstructionCase.model_fields})
            for r in rows
        ]
    )
    for row in rows:
        if row["final_human_category"] not in CATEGORIES:
            raise ValueError("unknown final human category")
    rules = {
        rule: summarize([r for r in rows if r["rule"] == rule]) | {"operator_id": OPERATORS[rule]}
        for rule in RULES
    }
    return sealed(
        {
            "schema_version": "p018-aggregate-construction-diagnostic-v1",
            "plan_fingerprint": joined["plan_fingerprint"],
            "construction_intent_input_fingerprint": joined[
                "construction_intent_input_fingerprint"
            ],
            "join_fingerprint": joined["fingerprint"],
            "frozen_inputs": joined["inputs"],
            "overall": summarize(rows),
            "by_rule": rules,
            "by_language": {
                lang: summarize([r for r in rows if r["language"] == lang]) for lang in LANGUAGES
            },
            "by_rule_language": {
                rule: {
                    lang: summarize(
                        [r for r in rows if r["rule"] == rule and r["language"] == lang]
                    )
                    for lang in LANGUAGES
                }
                for rule in RULES
            },
            "readiness": {
                "CONSTRUCTION_BINARY_AGREEMENT_AVAILABLE": True,
                "PAIR_VALIDITY_ANALYZED": True,
                "MUTATION_CONFIRMATION_BY_RULE_AVAILABLE": True,
                "CONTROL_CONFIRMATION_BY_RULE_AVAILABLE": True,
                "MUTATION_VALIDITY_EVIDENCE_AVAILABLE": True,
            },
            "objective_validity_threshold": None,
            "provider_calls": 0,
            "significance_tests": False,
            "p017_results_modified": False,
            "human_truth_modified": False,
            "cases_or_pairs_or_operators_modified": False,
            "limitations": [
                "INTENT_IS_NOT_GROUND_TRUTH; INDEPENDENT_FINAL_HUMAN_CATEGORY_AUTHORITATIVE",
                "CONTROLLED_HOLDOUT; NO_NATURAL_SOFTWARE_PREVALENCE_CLAIM",
                "DESCRIPTIVE_SMALL_STRATA: RULE10_PAIRS_LANGUAGE25_RULE_LANGUAGE5",
                "NONBINARY_MEMBERS_RETAINED_IN_ALL_INTENT_AND_PAIR_DENOMINATORS",
                "NO_POST_HOC_VALIDITY_THRESHOLD; NO_CONSTRUCTION_VALID_ASSERTION",
                "NO_RELABEL_REPLACEMENT_FILTERING_REBALANCING_OR_REGENERATION",
                "P017_AI_VS_HUMAN_METRICS_UNCHANGED; NO_CLEAN_SUBSET_F1",
                "NO_AI_CROSS_REFERENCE_PROVIDER_DETECTOR_HYBRID_V2_SECURITY_OR_ABLATION",
            ],
        }
    )
