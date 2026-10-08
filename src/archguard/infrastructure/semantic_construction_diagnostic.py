"""Read-only original construction inventory and append-only P018 diagnostic publication."""

import hashlib
import json
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_construction_diagnostic import (
    ConstructionCase,
    HumanCase,
    aggregate_diagnostic,
    diagnostic_plan,
    join_intent,
    pair_category,
    sealed,
    validate_design,
)
from archguard.benchmark.semantic_holdout import PrivatePair
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_final_truth import FinalHumanTruth
from archguard.infrastructure.semantic_holdout import verify_file_freeze
from archguard.infrastructure.semantic_positive_evaluation_freeze import append_sealed

FILES = (
    "intent-input-v1.json",
    "construction-truth-join-v1.json",
    "private-diagnostic-v1.json",
    "aggregate-diagnostic-v1.json",
    "diagnostic-freeze-v1.json",
)


def verify_p017(public: Path, private: Path, expected: dict[str, str]) -> dict[str, Any]:
    from archguard.infrastructure.semantic_positive_evaluation_freeze import verify_evaluation

    binding = json.loads(
        verify_opaque_seal(public / "p017-input-binding-v1.json", expected["binding"])
    )
    aggregate = json.loads(
        verify_opaque_seal(public / "p017-aggregate-evaluation-v1.json", expected["aggregate"])
    )
    receipt = json.loads(
        verify_opaque_seal(public / "p017-evaluation-freeze-v1.json", expected["receipt"])
    )
    verification = json.loads(
        verify_opaque_seal(public / "p017-verification-v1.json", expected["verification"])
    )
    local = verify_evaluation(private, expected["receipt"])
    if (
        local != receipt
        or receipt["aggregate_fingerprint"] != aggregate["fingerprint"]
        or receipt["input_join_fingerprint"] != expected["join"]
        or binding["input_join_fingerprint"] != expected["join"]
        or aggregate["input_join_fingerprint"] != expected["join"]
        or verification["input_join_fingerprint"] != expected["join"]
        or not verification["semantic_effectiveness_results_frozen"]
    ):
        raise ValueError("P018_BLOCKED_P017_FREEZE_DRIFT")
    verify_opaque_seal(private / "input-join-v1.json", expected["join"])
    if (private / "aggregate-evaluation-v1.json").read_bytes() != (
        public / "p017-aggregate-evaluation-v1.json"
    ).read_bytes():
        raise ValueError("P018_BLOCKED_P017_FREEZE_DRIFT")
    return {"P017_frozen": True, "P017_metrics_recomputed": False}


def require_plan(path: Path, fingerprint: str, inputs: dict[str, str]) -> dict[str, Any]:
    plan: dict[str, Any] = json.loads(verify_opaque_seal(path, fingerprint))
    definition = {
        k: v for k, v in plan.items() if k not in {"fingerprint", "implementation_sha256"}
    }
    expected = diagnostic_plan(inputs)
    if digest(definition) != expected["fingerprint"]:
        raise ValueError("P018_BLOCKED_DIAGNOSTIC_PLAN_DRIFT")
    return plan


def load_construction(
    public: Path,
    private: Path,
    expected: dict[str, str],
    plan_path: Path,
    plan_fingerprint: str,
    inputs: dict[str, str],
) -> dict[str, Any]:
    require_plan(plan_path, plan_fingerprint, inputs)
    raw = verify_opaque_seal(private / "provenance-v1.json", expected["provenance"])
    inventory = json.loads(
        verify_opaque_seal(private / "private-freeze-v1.json", expected["inventory"])
    )
    freeze = json.loads(verify_opaque_seal(public / "sample-freeze-v1.json", expected["freeze"]))
    for file, key in (
        ("corpus-v1.json", "corpus"),
        ("sample-v1.json", "sample"),
        ("analysis-plan-v1.json", "future_analysis"),
    ):
        verify_opaque_seal(public / file, expected[key])
    if (
        inventory["provenance_fingerprint"] != expected["provenance"]
        or freeze["private_provenance_fingerprint"] != expected["provenance"]
        or freeze["private_freeze_fingerprint"] != expected["inventory"]
        or freeze["corpus_fingerprint"] != expected["corpus"]
        or freeze["sample_fingerprint"] != expected["sample"]
        or freeze["analysis_plan_fingerprint"] != expected["future_analysis"]
        or freeze["human_labels"] != "NONE"
        or freeze["live_ai_calls"] != 0
    ):
        raise ValueError("P018_BLOCKED_CONSTRUCTION_FREEZE_DRIFT")
    for root, sealed_inventory in ((public, freeze), (private, inventory)):
        if root.is_symlink() or any((root / p).is_symlink() for p in sealed_inventory["files"]):
            raise ValueError("P018_BLOCKED_CONSTRUCTION_FREEZE_DRIFT")
        verify_file_freeze(root, sealed_inventory)
    provenance = json.loads(raw)
    pairs = [PrivatePair.model_validate(p) for p in provenance["pairs"]]
    if len(pairs) != 50 or len({p.pair_id for p in pairs}) != 50:
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    cases = []
    for pair in pairs:
        for intent, case_id in (
            ("MUTATION", pair.mutation_case_id),
            ("CONTROL", pair.control_case_id),
        ):
            cases.append(
                ConstructionCase.model_validate(
                    {
                        "scientific_case_id": case_id,
                        "pair_id": pair.pair_id,
                        "rule": pair.rule_id,
                        "language": pair.language,
                        "operator_id": pair.operator_id,
                        "intent": intent,
                    }
                )
            )
    validate_design(cases)
    sample = json.loads((public / "sample-v1.json").read_bytes())
    sample_cases = sample["cases"]
    indexed = {c["case_id"]: c for c in sample_cases}
    if (
        len(sample_cases) != 100
        or len(indexed) != 100
        or set(indexed) != {c.scientific_case_id for c in cases}
    ):
        raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    for c in cases:
        s = indexed[c.scientific_case_id]
        if (s["rule_id"], s["language"]) != (c.rule, c.language):
            raise ValueError("P018_BLOCKED_CONSTRUCTION_DESIGN_MISMATCH")
    return sealed(
        {
            "schema_version": "p018-private-intent-input-v1",
            "construction_provenance_fingerprint": expected["provenance"],
            "plan_fingerprint": plan_fingerprint,
            "cases": [
                c.model_dump(mode="json") for c in sorted(cases, key=lambda c: c.scientific_case_id)
            ],
        }
    )


def make_join(
    intent_input: dict[str, Any], truth: FinalHumanTruth, plan: str, inputs: dict[str, str]
) -> dict[str, Any]:
    if intent_input["plan_fingerprint"] != plan or intent_input["fingerprint"] != digest(
        {k: v for k, v in intent_input.items() if k != "fingerprint"}
    ):
        raise ValueError("P018 construction input binding drift")
    joined = join_intent(
        [ConstructionCase.model_validate(c) for c in intent_input["cases"]],
        [
            HumanCase(
                scientific_case_id=h.scientific_case_id,
                rule=h.target_rule,
                language=h.language,
                final_human_category=h.final_category,
            )
            for h in truth.cases
        ],
        inputs,
        plan,
    )
    return sealed(
        {k: v for k, v in joined.items() if k != "fingerprint"}
        | {"construction_intent_input_fingerprint": intent_input["fingerprint"]}
    )


def private_diagnostic(joined: dict[str, Any], aggregate: dict[str, Any]) -> dict[str, Any]:
    pairs: dict[str, dict[str, Any]] = {}
    for r in joined["rows"]:
        pairs.setdefault(r["pair_id"], {})[r["intent"]] = r
    return sealed(
        {
            "schema_version": "p018-private-pair-diagnostic-v1",
            "join_fingerprint": joined["fingerprint"],
            "aggregate_fingerprint": aggregate["fingerprint"],
            "pairs": [
                {
                    "pair_id": pid,
                    "mutation_scientific_case_id": p["MUTATION"]["scientific_case_id"],
                    "control_scientific_case_id": p["CONTROL"]["scientific_case_id"],
                    "mutation_human_category": p["MUTATION"]["final_human_category"],
                    "control_human_category": p["CONTROL"]["final_human_category"],
                    "category": pair_category(
                        p["MUTATION"]["final_human_category"], p["CONTROL"]["final_human_category"]
                    ),
                    "involving_uncertain": any(
                        r["final_human_category"] == "UNCERTAIN" for r in p.values()
                    ),
                    "involving_out_of_scope": any(
                        r["final_human_category"] == "OUT_OF_SCOPE" for r in p.values()
                    ),
                }
                for pid, p in sorted(pairs.items())
            ],
        }
    )


def freeze_diagnostic(
    destination: Path, intent_input: dict[str, Any], joined: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    if destination.exists():
        raise ValueError("P018 diagnostic freeze append-only")
    aggregate = aggregate_diagnostic(joined)
    diagnostic = private_diagnostic(joined, aggregate)
    for name, value in zip(FILES[:-1], (intent_input, joined, diagnostic, aggregate), strict=True):
        append_sealed(destination / name, value)
    receipt = append_sealed(
        destination / FILES[-1],
        {
            "schema_version": "p018-diagnostic-freeze-v1",
            "status": "CONSTRUCTION_INTENT_DIAGNOSTIC_FROZEN",
            "plan_fingerprint": joined["plan_fingerprint"],
            "construction_intent_input_fingerprint": intent_input["fingerprint"],
            "join_fingerprint": joined["fingerprint"],
            "private_diagnostic_fingerprint": diagnostic["fingerprint"],
            "aggregate_fingerprint": aggregate["fingerprint"],
            "files": {
                name: hashlib.sha256((destination / name).read_bytes()).hexdigest()
                for name in FILES[:-1]
            },
            "frozen_inputs": joined["inputs"],
            "provider_calls": 0,
            "plan_frozen_before_intent_join": True,
            "human_truth_or_p017_modified": False,
        },
    )
    return aggregate, receipt


def verify_diagnostic(
    destination: Path, expected_receipt: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = json.loads(verify_opaque_seal(destination / FILES[-1], expected_receipt))
    if destination.is_symlink() or {p.name for p in destination.iterdir()} != set(FILES):
        raise ValueError("P018 frozen diagnostic inventory drift")
    for name, sha in receipt["files"].items():
        path = destination / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("P018 frozen diagnostic bytes drift")
    input_data = json.loads(
        verify_opaque_seal(destination / FILES[0], receipt["construction_intent_input_fingerprint"])
    )
    joined = json.loads(verify_opaque_seal(destination / FILES[1], receipt["join_fingerprint"]))
    diagnostic = json.loads(
        verify_opaque_seal(destination / FILES[2], receipt["private_diagnostic_fingerprint"])
    )
    aggregate = json.loads(
        verify_opaque_seal(destination / FILES[3], receipt["aggregate_fingerprint"])
    )
    if (
        aggregate != aggregate_diagnostic(joined)
        or diagnostic != private_diagnostic(joined, aggregate)
        or joined["construction_intent_input_fingerprint"] != input_data["fingerprint"]
        or receipt["plan_fingerprint"] != joined["plan_fingerprint"]
        or receipt["frozen_inputs"] != joined["inputs"]
    ):
        raise ValueError("P018 deterministic diagnostic drift")
    return aggregate, receipt
