import ast
import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_holdout import (
    LANGUAGES,
    RULES,
    SCENARIOS,
    BlindedPacket,
    HoldoutSample,
    PrivatePair,
    SourceEvidence,
    fixture_sources,
    opaque_id,
    validate_pairs,
)
from archguard.infrastructure.semantic_holdout import (
    construct_holdout,
    future_context_input,
    make_packet,
    sealed,
    verify_file_freeze,
)

SEED = b"fixed-test-only-blinding-seed"


@pytest.fixture(scope="module")
def generated(tmp_path_factory):
    folder = tmp_path_factory.mktemp("holdout")
    public, private = folder / "public", folder / "private"
    protocol = sealed({"allowed_outcomes": ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]})
    guidance = sealed({"source_evidence_only": True})
    plan = sealed({"metrics_not_computed": True})
    freeze = construct_holdout(
        public, private, SEED, "f" * 40, {"oss-frozen-case"}, protocol, guidance, plan
    )
    return public, private, freeze, protocol, guidance, plan


def read(path):
    return json.loads(path.read_text())


def test_deterministic_opaque_ids_with_private_seed():
    identity = ("ARCH201", "JAVA", "pricing", True)
    assert opaque_id(SEED, "case", identity) == opaque_id(SEED, "case", identity)
    assert opaque_id(SEED, "case", identity) != opaque_id(b"another-seed", "case", identity)
    assert opaque_id(SEED, "case", identity) != opaque_id(SEED, "review", identity)
    assert make_packet(SEED, "ARCH201", "JAVA", "pricing", True) == make_packet(
        SEED, "ARCH201", "JAVA", "pricing", True
    )


def test_exact_case_rule_language_balance_and_unique_ids(generated):
    public, _, freeze, *_ = generated
    sample = HoldoutSample.model_validate(read(public / "sample-v1.json"))
    assert len(sample.cases) == 100
    assert Counter(c.rule_id for c in sample.cases) == {r: 20 for r in RULES}
    assert Counter(c.language for c in sample.cases) == {lang: 50 for lang in LANGUAGES}
    assert Counter((c.rule_id, c.language) for c in sample.cases) == {
        (r, lang): 10 for r in RULES for lang in LANGUAGES
    }
    assert (
        len({c.case_id for c in sample.cases}) == len({c.blinded_id for c in sample.cases}) == 100
    )
    assert freeze["human_labels"] == "NONE" and freeze["status"] == "WAITING_FOR_HUMAN_REVIEW"


def test_pair_integrity_intent_counts_and_no_p013_reuse(generated):
    public, private, *_ = generated
    sample = HoldoutSample.model_validate(read(public / "sample-v1.json"))
    store = read(private / "provenance-v1.json")
    pairs = tuple(PrivatePair.model_validate(p) for p in store["pairs"])
    validate_pairs(sample, pairs, {"oss-frozen-case"})
    assert len(pairs) == 50 and len({p.mutation_case_id for p in pairs}) == 50
    assert len({p.control_case_id for p in pairs}) == 50
    assert Counter((p.rule_id, p.language) for p in pairs) == {
        (r, lang): 5 for r in RULES for lang in LANGUAGES
    }
    assert not any(store["construction_access"].values())
    with pytest.raises(ValueError, match="P013"):
        validate_pairs(sample, pairs, {sample.cases[0].case_id})
    with pytest.raises(ValueError, match="50"):
        validate_pairs(sample, pairs[:-1], set())


def keys_recursive(value):
    if isinstance(value, dict):
        yield from value
        for item in value.values():
            yield from keys_recursive(item)
    elif isinstance(value, list):
        for item in value:
            yield from keys_recursive(item)


def test_blinded_bundles_have_no_pair_intent_operator_or_human_answers(generated):
    _, private, freeze, *_ = generated
    forbidden = {
        "operator_id",
        "pair_id",
        "construction_intent",
        "private_blinding_seed",
        "mutation_case_id",
        "control_case_id",
        "origin_project",
        "judgment",
        "answer",
        "label",
        "final_human_label",
        "rationale",
        "reviewer_identity",
    }
    orders = []
    for slot in ("A", "B"):
        bundle = read(private / "review" / slot / "bundle-v1.json")
        assert not forbidden & set(keys_recursive(bundle))
        assert len(bundle["packets"]) == 100
        assert bundle["fingerprint"] == freeze["reviewer_bundle_fingerprints"][slot]
        orders.append([p["blinded_id"] for p in bundle["packets"]])
    assert set(orders[0]) == set(orders[1]) and orders[0] != orders[1]


def test_future_context_builder_cannot_accept_construction_intent(generated):
    _, private, *_ = generated
    packet = BlindedPacket.model_validate(read(next((private / "packets").glob("*.json"))))
    prepared = future_context_input(packet)
    assert "source_evidence" in prepared
    for key in ("pair_id", "operator_id", "construction_intent", "label", "answer"):
        contaminated = packet.model_dump(mode="json") | {key: "MUTATION_CANDIDATE"}
        contaminated["fingerprint"] = digest(
            {k: v for k, v in contaminated.items() if k != "fingerprint"}
        )
        with pytest.raises(ValidationError):
            BlindedPacket.model_validate(contaminated)
    with pytest.raises(ValidationError):
        future_context_input(read(private / "provenance-v1.json"))


def test_provenance_and_mutation_receipts_are_sealed(generated):
    _, private, *_ = generated
    for path in [
        private / "provenance-v1.json",
        *sorted((private / "mutation-receipts").glob("*.json")),
    ]:
        payload = read(path)
        assert payload["fingerprint"] == digest(
            {k: v for k, v in payload.items() if k != "fingerprint"}
        )
    receipts = [read(p) for p in (private / "mutation-receipts").glob("*.json")]
    assert len(receipts) == 50
    assert all(r["source_before_sha256"] != r["source_after_sha256"] for r in receipts)
    assert not any(r["semantic_truth_established"] for r in receipts)


def test_validity_source_spans_and_dependency_replay(generated):
    public, _, freeze, *_ = generated
    receipts = read(public / "validation-receipts-v1.json")["cases"]
    assert len(receipts) == 100 and freeze["technical_counts"] == {"VALID": 100}
    assert all(
        r["intake_succeeded"]
        and r["parser_valid"]
        and r["iam_valid"]
        and r["iam_complete"]
        and r["graph_valid"]
        and r["graph_complete"]
        and all(r["source_spans_resolved"].values())
        and r["dependency_extraction_replay_equal"]
        for r in receipts
    )
    assert all(r["native_validation"]["status"] == "NOT_RUN" for r in receipts)


def test_frozen_file_tampering_and_reconstruction_are_rejected(generated, tmp_path):
    public, private, freeze, protocol, guidance, plan = generated
    verify_file_freeze(public, freeze)
    private_freeze = read(private / "private-freeze-v1.json")
    verify_file_freeze(private, private_freeze)
    path = tmp_path / "receipt.json"
    path.write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        verify_file_freeze(tmp_path, sealed({"files": {"receipt.json": "0" * 64}}))
    with pytest.raises(ValueError, match="overwritten"):
        construct_holdout(public, private, SEED, "f" * 40, set(), protocol, guidance, plan)


def test_deterministic_generation_and_context_diagnostics(generated, tmp_path):
    public, _, freeze, protocol, guidance, plan = generated
    repeated = construct_holdout(
        tmp_path / "public",
        tmp_path / "private",
        SEED,
        "f" * 40,
        {"oss-frozen-case"},
        protocol,
        guidance,
        plan,
    )
    assert repeated == freeze
    assert read(public / "context-diagnostics-v1.json") == read(
        tmp_path / "public/context-diagnostics-v1.json"
    )
    contexts = read(public / "context-diagnostics-v1.json")["cases"]
    assert len(contexts) == 100
    assert all(
        set(c["strategies"]) == {"LOCAL_ONLY", "GRAPH_GUIDED", "EXPANDED_BASELINE"}
        for c in contexts
    )
    assert all(
        not d["expected_truncation"] and not d["missing_evidence_reasons"]
        for c in contexts
        for d in c["strategies"].values()
    )


@pytest.mark.parametrize("rule", RULES)
@pytest.mark.parametrize("language", LANGUAGES)
def test_each_operator_materially_changes_code_preserving_surroundings(rule, language):
    for scenario in SCENARIOS:
        before = fixture_sources(rule, language, scenario, False)
        after = fixture_sources(rule, language, scenario, True)
        assert before != after
        assert sum(before.get(p) == text for p, text in after.items()) >= 4
        assert 0.65 < sum(map(len, after.values())) / sum(map(len, before.values())) < 1.5


def test_no_ai_evaluation_or_secret_configuration_execution_path():
    root = Path(__file__).parents[2]
    for relative in (
        "src/archguard/benchmark/semantic_holdout.py",
        "src/archguard/infrastructure/semantic_holdout.py",
        "scripts/prompt015_holdout.py",
    ):
        tree = ast.parse((root / relative).read_text())
        imports = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
        assert not any(
            part in name
            for name in imports
            for part in (
                "llm_provider",
                "semantic_evaluation",
                "calibration",
                "hybrid",
                "security",
                "review",
            )
        )
        assert not any(
            isinstance(n, ast.Constant)
            and isinstance(n.value, str)
            and (".env.ai.local" in n.value or "/v1/responses" in n.value)
            for n in ast.walk(tree)
        )


def test_source_evidence_hash_and_path_integrity():
    with pytest.raises(ValidationError):
        SourceEvidence(evidence_id="e", path="x.java", text="class A {}", sha256="0" * 64)
    with pytest.raises(ValidationError):
        SourceEvidence(
            evidence_id="e", path="../x.java", text="", sha256=hashlib.sha256(b"").hexdigest()
        )


def test_minimum_valid_gate_cannot_be_bypassed_by_resealing(generated):
    public, *_ = generated
    sample = read(public / "sample-v1.json")
    for row in sample["cases"][:11]:
        row["technical_status"] = "PARTIAL"
    sample["fingerprint"] = digest({k: v for k, v in sample.items() if k != "fingerprint"})
    with pytest.raises(ValidationError, match="90"):
        HoldoutSample.model_validate(sample)


def test_analysis_plan_is_frozen_before_outcomes_and_has_no_computed_metrics():
    script = Path(__file__).parents[2] / "scripts/prompt015_holdout.py"
    spec = importlib.util.spec_from_file_location("prospective_holdout", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    protocol, guidance, analysis = module.definitions()
    assert protocol["auto_review"] is False
    assert set(guidance["rules"]) == set(RULES)
    assert analysis["computed_metrics"] == "NONE; no human truth exists"
    assert analysis["do_not_pool_with_p013_p014"] is True
    assert "effective_positive_correctness" in analysis["mandatory_companions"]
