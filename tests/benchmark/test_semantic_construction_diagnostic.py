"""Synthetic original inventories only; no real intent, credentials or detector execution."""

import hashlib
import socket

import pytest

from archguard.benchmark.oss.models import canonical, seal
from archguard.benchmark.semantic_construction_diagnostic import (
    CATEGORIES,
    OPERATORS,
    ConstructionCase,
    HumanCase,
    aggregate_diagnostic,
    diagnostic_plan,
    join_intent,
    pair_category,
    sealed,
    summarize,
    validate_design,
)
from archguard.infrastructure.semantic_construction_diagnostic import (
    FILES,
    freeze_diagnostic,
    load_construction,
    make_join,
    require_plan,
    verify_diagnostic,
    verify_p017,
)
from archguard.infrastructure.semantic_final_truth import (
    LINEAGE_KEYS,
    FinalHumanTruth,
    TruthCase,
    freeze_final_truth,
)
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    append_sealed,
    evaluation_io,
    freeze_evaluation,
    verify_truth,
)


@pytest.fixture
def synthetic(tmp_path):
    public = tmp_path / "public"
    private = tmp_path / "private"
    cases, pairs, sample, humans = [], [], [], []
    for rule in OPERATORS:
        for language in ("JAVA", "TYPESCRIPT"):
            for n in range(5):
                pair_id = f"pair-{rule}-{language}-{n}"
                members = {}
                for intent in ("MUTATION", "CONTROL"):
                    case_id = pair_id + "-" + intent
                    members[intent] = case_id
                    case = ConstructionCase(
                        scientific_case_id=case_id,
                        pair_id=pair_id,
                        rule=rule,
                        language=language,
                        operator_id=OPERATORS[rule],
                        intent=intent,
                    )
                    cases.append(case)
                    sample.append({"case_id": case_id, "rule_id": rule, "language": language})
                    category = "POSITIVE" if intent == "MUTATION" else "NEGATIVE"
                    if intent == "CONTROL":
                        if rule == "ARCH203" and language == "JAVA" and n == 4:
                            category = "OUT_OF_SCOPE"
                        if rule == "ARCH205" and (n == 4 or (language == "JAVA" and n == 3)):
                            category = "UNCERTAIN"
                    if (
                        rule == "ARCH201"
                        and language == "JAVA"
                        and (
                            (intent == "MUTATION" and n in (0, 1))
                            or (intent == "CONTROL" and n in (0, 2))
                        )
                    ):
                        category = "NEGATIVE" if intent == "MUTATION" else "POSITIVE"
                    humans.append(
                        TruthCase.model_validate(
                            {
                                "scientific_case_id": case_id,
                                "target_rule": rule,
                                "language": language,
                                "final_category": category,
                                "resolution_provenance": "A_B_AGREEMENT"
                                if category in ("POSITIVE", "NEGATIVE")
                                else "THIRD_HUMAN_ADJUDICATION",
                            }
                        )
                    )
                pairs.append(
                    {
                        "pair_id": pair_id,
                        "rule_id": rule,
                        "language": language,
                        "origin_project": "synthetic",
                        "operator_id": OPERATORS[rule],
                        "mutation_case_id": members["MUTATION"],
                        "control_case_id": members["CONTROL"],
                        "before_hashes": {},
                        "after_hashes": {},
                        "mutation_validation_fingerprint": "a" * 64,
                        "control_validation_fingerprint": "b" * 64,
                    }
                )
    provenance = append_sealed(
        private / "provenance-v1.json",
        {"pairs": pairs, "private_blinding_seed": "private-only-synthetic-seed"},
    )
    inventory = append_sealed(
        private / "private-freeze-v1.json",
        {
            "files": {
                "provenance-v1.json": hashlib.sha256(
                    (private / "provenance-v1.json").read_bytes()
                ).hexdigest()
            },
            "provenance_fingerprint": provenance["fingerprint"],
        },
    )
    sample_data = append_sealed(public / "sample-v1.json", {"cases": sample})
    corpus = append_sealed(public / "corpus-v1.json", {"synthetic": True})
    future = append_sealed(public / "analysis-plan-v1.json", {"future": True})
    freeze = append_sealed(
        public / "sample-freeze-v1.json",
        {
            "files": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in public.iterdir()},
            "private_provenance_fingerprint": provenance["fingerprint"],
            "private_freeze_fingerprint": inventory["fingerprint"],
            "corpus_fingerprint": corpus["fingerprint"],
            "sample_fingerprint": sample_data["fingerprint"],
            "analysis_plan_fingerprint": future["fingerprint"],
            "human_labels": "NONE",
            "live_ai_calls": 0,
        },
    )
    expected = {
        "provenance": provenance["fingerprint"],
        "inventory": inventory["fingerprint"],
        "freeze": freeze["fingerprint"],
        "sample": sample_data["fingerprint"],
        "corpus": corpus["fingerprint"],
        "future_analysis": future["fingerprint"],
    }
    inputs = {"construction_" + k: v for k, v in expected.items()}
    plan_path = tmp_path / "p018-plan.json"
    plan = append_sealed(plan_path, diagnostic_plan(inputs))
    truth = seal(FinalHumanTruth, lineage={k: "a" * 64 for k in LINEAGE_KEYS}, cases=tuple(humans))
    human_rows = [
        HumanCase(
            scientific_case_id=h.scientific_case_id,
            rule=h.target_rule,
            language=h.language,
            final_human_category=h.final_category,
        )
        for h in humans
    ]
    return locals()


def load(f):
    return load_construction(
        f["public"],
        f["private"],
        f["expected"],
        f["plan_path"],
        f["plan"]["fingerprint"],
        f["inputs"],
    )


@pytest.mark.parametrize(
    "key", ["provenance", "inventory", "freeze", "sample", "corpus", "future_analysis"]
)
def test_exact_construction_seals(synthetic, key):
    f = synthetic
    f["expected"][key] = "0" * 64
    with pytest.raises(ValueError):
        load(f)


@pytest.mark.parametrize("change", ["added", "removed", "modified"])
def test_original_inventory_no_repairs(synthetic, change):
    f = synthetic
    before = f["private"].joinpath("provenance-v1.json").read_bytes()
    if change == "added":
        f["private"].joinpath("extra.txt").write_text("extra")
    elif change == "removed":
        f["public"].joinpath("corpus-v1.json").unlink()
    else:
        f["public"].joinpath("sample-v1.json").write_text("{}")
    with pytest.raises((ValueError, OSError)):
        load(f)
    assert f["private"].joinpath("provenance-v1.json").read_bytes() == before


def test_plan_must_be_frozen_before_intent_access(synthetic, monkeypatch):
    f = synthetic
    f["plan_path"].unlink()
    from pathlib import Path

    real_read = Path.read_bytes
    accessed = []

    def read(path):
        accessed.append(path)
        return real_read(path)

    monkeypatch.setattr(Path, "read_bytes", read)
    with pytest.raises(OSError):
        load(f)
    assert f["private"] / "provenance-v1.json" not in accessed
    append_sealed(f["plan_path"], f["plan"])
    assert len(load(f)["cases"]) == 100
    changed = sealed(
        {k: v for k, v in f["plan"].items() if k != "fingerprint"}
        | {"objective_validity_threshold": 0.95}
    )
    f["plan_path"].write_text(canonical(changed) + "\n")
    with pytest.raises(ValueError):
        require_plan(f["plan_path"], changed["fingerprint"], f["inputs"])


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "same_intent",
        "wrong_operator",
        "unbalanced_language",
        "unbalanced_rule",
        "duplicate_pair",
    ],
)
def test_frozen_design_guards(synthetic, change):
    cases = list(synthetic["cases"])
    if change == "missing":
        cases.pop()
    elif change == "duplicate":
        cases[0] = cases[1]
    elif change == "same_intent":
        cases[1] = cases[1].model_copy(update={"intent": "MUTATION"})
    elif change == "wrong_operator":
        cases[0] = cases[0].model_copy(update={"operator_id": "new-operator"})
    elif change == "unbalanced_language":
        for i in (0, 1):
            cases[i] = cases[i].model_copy(update={"language": "TYPESCRIPT"})
    elif change == "unbalanced_rule":
        for i in (0, 1):
            cases[i] = cases[i].model_copy(
                update={"rule": "ARCH202", "operator_id": OPERATORS["ARCH202"]}
            )
    else:
        for i in (0, 1):
            cases[i] = cases[i].model_copy(update={"pair_id": cases[2].pair_id})
    with pytest.raises(ValueError, match="CONSTRUCTION_DESIGN_MISMATCH"):
        validate_design(cases)


def test_stable_id_join_and_complete_partition(synthetic):
    f = synthetic
    first = join_intent(f["cases"], f["human_rows"], f["inputs"], f["plan"]["fingerprint"])
    reversed_join = join_intent(
        list(reversed(f["cases"])),
        list(reversed(f["human_rows"])),
        f["inputs"],
        f["plan"]["fingerprint"],
    )
    assert first == reversed_join
    assert len(first["rows"]) == 100 and len({r["pair_id"] for r in first["rows"]}) == 50
    h = list(f["human_rows"])
    h[0] = h[0].model_copy(update={"scientific_case_id": "extra"})
    with pytest.raises(ValueError):
        join_intent(f["cases"], h, f["inputs"], f["plan"]["fingerprint"])
    h = list(f["human_rows"])
    h[0] = h[0].model_copy(update={"rule": "ARCH202"})
    with pytest.raises(ValueError):
        join_intent(f["cases"], h, f["inputs"], f["plan"]["fingerprint"])


def test_nonbinary_denominators_pair_classification_and_reconciliation(synthetic):
    f = synthetic
    input_data = load(f)
    joined = make_join(input_data, f["truth"], f["plan"]["fingerprint"], f["inputs"])
    aggregate = aggregate_diagnostic(joined)
    a = aggregate["overall"]
    assert a["intent_human_cross_tab"] == {
        "MUTATION": dict(zip(CATEGORIES, [48, 2, 0, 0], strict=True)),
        "CONTROL": dict(zip(CATEGORIES, [2, 44, 3, 1], strict=True)),
    }
    assert a["rates"]["mutation_positive_confirmation"] == 48 / 50
    assert a["rates"]["control_negative_confirmation"] == 44 / 50
    assert a["rates"]["control_nonbinary_rate"] == 4 / 50
    assert a["binary_agreement"]["eligible"] == 96
    assert a["binary_agreement"]["agreements"] == 92 and a["binary_agreement"]["disagreements"] == 4
    assert a["binary_agreement"]["rate"] == 92 / 96
    assert a["pairs"]["categories"] == {
        "FULLY_CONFIRMED": 43,
        "MUTATION_NOT_CONFIRMED": 1,
        "CONTROL_NOT_CONFIRMED": 5,
        "BOTH_NOT_CONFIRMED": 1,
    }
    assert a["pairs"]["involving_uncertain"] == 3 and a["pairs"]["involving_out_of_scope"] == 1
    assert a["pairs"]["rates"]["FULLY_CONFIRMED"] == 43 / 50
    for row in aggregate["by_rule"].values():
        assert (
            row["case_counts"] == {"total": 20, "MUTATION": 10, "CONTROL": 10}
            and row["pairs"]["total"] == 10
        )
    for row in aggregate["by_language"].values():
        assert (
            row["case_counts"] == {"total": 50, "MUTATION": 25, "CONTROL": 25}
            and row["pairs"]["total"] == 25
        )
    for rule in aggregate["by_rule_language"].values():
        for row in rule.values():
            assert row["case_counts"]["total"] == 10 and row["pairs"]["total"] == 5
    for kind in ("by_rule", "by_language"):
        assert sum(v["binary_agreement"]["eligible"] for v in aggregate[kind].values()) == 96
        assert (
            sum(v["pairs"]["categories"]["FULLY_CONFIRMED"] for v in aggregate[kind].values()) == 43
        )
    assert sum(sum(v.values()) for v in a["pairs"]["direction_cross_tab"].values()) == 50
    assert summarize([])["binary_agreement"]["rate"] is None
    assert "CONSTRUCTION_VALID" not in aggregate["readiness"]
    assert aggregate["objective_validity_threshold"] is None
    for mutation in CATEGORIES:
        for control in CATEGORIES:
            expected = (
                ("FULLY_CONFIRMED" if control == "NEGATIVE" else "CONTROL_NOT_CONFIRMED")
                if mutation == "POSITIVE"
                else ("MUTATION_NOT_CONFIRMED" if control == "NEGATIVE" else "BOTH_NOT_CONFIRMED")
            )
            assert pair_category(mutation, control) == expected
    with pytest.raises(ValueError):
        pair_category("unknown", "NEGATIVE")


def test_determinism_append_only_and_public_privacy(synthetic, tmp_path):
    f = synthetic
    intent = load(f)
    joined = make_join(intent, f["truth"], f["plan"]["fingerprint"], f["inputs"])
    frozen = {p: p.read_bytes() for root in (f["public"], f["private"]) for p in root.iterdir()}
    a, r = freeze_diagnostic(tmp_path / "diagnostic", intent, joined)
    assert verify_diagnostic(tmp_path / "diagnostic", r["fingerprint"]) == (a, r)
    assert aggregate_diagnostic(joined) == a
    public_text = canonical(a) + canonical(r)
    for c in f["cases"]:
        assert c.scientific_case_id not in public_text and c.pair_id not in public_text
    assert "private-only-synthetic-seed" not in public_text and "rationale" not in public_text
    assert (
        not a["provider_calls"] and not a["significance_tests"] and not a["p017_results_modified"]
    )
    assert {p.name for p in (tmp_path / "diagnostic").iterdir()} == set(FILES)
    assert all(p.stat().st_mode & 0o777 == 0o600 for p in (tmp_path / "diagnostic").iterdir())
    with pytest.raises(ValueError, match="append-only"):
        freeze_diagnostic(tmp_path / "diagnostic", intent, joined)
    assert all(p.read_bytes() == raw for p, raw in frozen.items())
    (tmp_path / "diagnostic" / FILES[1]).write_text("{}")
    with pytest.raises(ValueError):
        verify_diagnostic(tmp_path / "diagnostic", r["fingerprint"])


@pytest.mark.parametrize(
    "key",
    ["truth_sha256", "truth_fingerprint", "truth_receipt_fingerprint", "truth_lineage_fingerprint"],
)
def test_exact_truth_guard(synthetic, tmp_path, key):
    root = tmp_path / "truth/private/final-human-ground-truth-v1"
    truth = synthetic["truth"]
    receipt = freeze_final_truth(root, truth)
    pub = append_sealed(
        tmp_path / "truth-public.json", {"ground_truth_fingerprint": truth.fingerprint}
    )
    expected = {
        "truth_sha256": receipt["ground_truth_sha256"],
        "truth_fingerprint": truth.fingerprint,
        "truth_receipt_fingerprint": receipt["fingerprint"],
        "truth_lineage_fingerprint": receipt["lineage_fingerprint"],
        "truth_public_fingerprint": pub["fingerprint"],
    }
    expected[key] = "0" * 64
    with pytest.raises(ValueError):
        verify_truth(root, tmp_path / "truth-public.json", expected)


@pytest.mark.parametrize("key", ["join", "binding", "aggregate", "receipt", "verification"])
def test_exact_p017_freeze_guard(tmp_path, key):
    public = tmp_path / "p017"
    private = tmp_path / "private"
    joined = append_sealed(private / "input-join-v1.json", {"rows": []})
    binding = append_sealed(
        public / "p017-input-binding-v1.json", {"input_join_fingerprint": joined["fingerprint"]}
    )
    aggregate = sealed({"input_join_fingerprint": joined["fingerprint"]})
    receipt = freeze_evaluation(private, joined, binding, aggregate)
    append_sealed(public / "p017-aggregate-evaluation-v1.json", aggregate)
    append_sealed(public / "p017-evaluation-freeze-v1.json", receipt)
    verification = append_sealed(
        public / "p017-verification-v1.json",
        {
            "input_join_fingerprint": joined["fingerprint"],
            "semantic_effectiveness_results_frozen": True,
        },
    )
    expected = {
        "join": joined["fingerprint"],
        "binding": binding["fingerprint"],
        "aggregate": aggregate["fingerprint"],
        "receipt": receipt["fingerprint"],
        "verification": verification["fingerprint"],
    }
    assert verify_p017(public, private, expected)["P017_frozen"]
    expected[key] = "0" * 64
    with pytest.raises(ValueError):
        verify_p017(public, private, expected)


def test_offline_and_frozen_input_capabilities(tmp_path):
    root = tmp_path / "experiments"
    source = root / "private/construction"
    source.mkdir(parents=True)
    original = source / "sealed.json"
    original.write_text("unchanged")
    secret = tmp_path / ".env.ai.local"
    secret.write_text("synthetic")
    forbidden = root / "private/detector/results.json"
    forbidden.parent.mkdir()
    forbidden.write_text("unavailable")
    with evaluation_io(root, (source,), root / "private/p018"):
        with socket.socket() as s, pytest.raises(PermissionError):
            s.connect(("127.0.0.1", 9))
        with pytest.raises(PermissionError):
            secret.read_text()
        with pytest.raises(PermissionError):
            original.write_text("change")
        with pytest.raises(PermissionError):
            forbidden.read_text()
        append_sealed(root / "private/p018/result.json", {"provider_calls": 0})
    assert original.read_text() == "unchanged"


def test_cli_refuses_uncommitted_plan_before_loading_intent(synthetic, monkeypatch):
    import sys
    from pathlib import Path

    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "scripts"))
    import prompt018_diagnostic as cli

    f = synthetic
    plan = sealed(
        {k: v for k, v in f["plan"].items() if k != "fingerprint"}
        | {"implementation_sha256": {"synthetic": "a" * 64}}
    )
    f["plan_path"].write_text(canonical(plan) + "\n")
    monkeypatch.setattr(cli, "PLAN", f["plan_path"])
    monkeypatch.setattr(cli, "INPUTS", f["inputs"])
    monkeypatch.setattr(cli, "source_hashes", lambda: {"synthetic": "a" * 64})
    monkeypatch.setattr(cli, "repository_gate", lambda clean=False: None)
    monkeypatch.setattr(cli.subprocess, "check_output", lambda *a, **kw: b"uncommitted")

    def forbidden(*args):
        pytest.fail("uncommitted plan must not read real construction intent")

    monkeypatch.setattr(cli, "load_construction", forbidden)
    monkeypatch.setattr(sys, "argv", ["prompt018_diagnostic.py", "--run"])
    with pytest.raises(ValueError, match="P018_BLOCKED_DIAGNOSTIC_PLAN_DRIFT"):
        cli.main()
