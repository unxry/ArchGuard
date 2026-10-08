"""P020 prospective contracts, synthetic candidates, blindness and engineering replay."""

import copy
import json
from pathlib import Path

import pytest

from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.benchmark import component_holdout as structural
from archguard.benchmark import unified_hybrid as domain
from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.calibration.unified import fit_candidate
from archguard.infrastructure import unified_hybrid as infra
from archguard.infrastructure.component_holdout import build, normalized, offline
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.semantic_positive_evaluation_freeze import evaluation_io
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput


def test_protocol_routes_schema_limits_and_lineage():
    p = domain.protocol()
    assert p["model"] == "gpt-6-luna" and p["provider"] == "openai"
    assert p["expected_new_requests"] == {"DEVELOPMENT": 180, "FINAL": 300}
    assert (
        p["hops"],
        p["max_context_chars"],
        p["max_input_tokens"],
        p["max_output_tokens"],
        p["max_technical_retries"],
    ) == (1, 20000, 32768, 2000, 2)
    assert p["paid_execution_approved"] is False
    assert set(domain.STRUCTURAL_QUESTIONS) == set(domain.RULES[:10])
    assert len(domain.RULES) == 15 and set(domain.QUESTIONS) == set(domain.RULES[10:])
    props = domain.UnifiedAssessment.model_json_schema()["properties"]
    assert set(props["decision"]["enum"]) == {
        "SUPPORTED",
        "NOT_SUPPORTED",
        "INSUFFICIENT_CONTEXT",
        "NOT_APPLICABLE",
    }
    assert "confidence" not in props


@pytest.mark.parametrize("rule", domain.RULES)
def test_family_catalog(rule):
    assert domain.family(rule) in {"NORMATIVE_STATIC", "GRAPH_STRUCTURAL", "SEMANTIC"}
    with pytest.raises(ValueError):
        domain.family("SEC001")


@pytest.mark.parametrize("rule", domain.RULES[:10])
@pytest.mark.parametrize("positive", [False, True])
def test_new_structural_operator_and_oracle(rule, positive):
    for index in range(5, 10):
        facts = structural.topology(rule, index, positive)
        assert structural.oracle(rule, facts, structural.specification(rule)) == positive
        assert len(facts["nodes"]) >= 17


@pytest.mark.parametrize("language", ["JAVA", "TYPESCRIPT"])
@pytest.mark.parametrize("rule", domain.RULES[10:])
def test_fresh_semantic_namespace_and_technical_replay(tmp_path, language, rule):
    a, target, contract = infra.renamed_semantic(rule, language, 2, True, "a" * 32)
    b, _, _ = infra.renamed_semantic(rule, language, 2, False, "b" * 32)
    assert not set(a.values()) & set(b.values())
    assert target in contract
    for relative, text in a.items():
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    iam, receipt = build(tmp_path, "p020-synthetic-" + language + rule)
    assert receipt["status"] == "VALID" and receipt["replay"]
    assert infra.locator(iam, target)["kind"] == "CLASS"


@pytest.mark.parametrize("language", ["JAVA", "TYPESCRIPT"])
def test_fresh_structural_engineering(tmp_path, language):
    facts = structural.topology("ARCH104", 7, True)
    for relative, text in structural.sources("c" * 32, language, facts).items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    iam, receipt = build(tmp_path, "p020-structural-synthetic")
    observed = normalized(iam)
    assert observed["edges"] == facts["edges"] and receipt["replay"]


def test_grouped_stratified_split_and_project_leakage():
    rows = [
        dict(
            scientific_case_id=str(i),
            project_id="p" + str(i // 2),
            target_rule_id="ARCH001",
            category="POSITIVE" if i % 2 else "NEGATIVE",
        )
        for i in range(40)
    ]
    a = domain.grouped_split(rows)
    assert a == domain.grouped_split(rows)
    train = {r["project_id"] for r in a["rows"] if r["split"] == "TRAIN"}
    val = {r["project_id"] for r in a["rows"] if r["split"] == "VALIDATION"}
    assert not train & val and len(train) == 15 and len(val) == 5
    assert a["seed_fingerprint"] == digest(domain.GROUP_SEED)


@pytest.mark.parametrize(
    "field", sorted(infra.FORBIDDEN | {"pair_id", "human_rationale", "reviewer_identity"})
)
def test_request_metadata_leakage_rejected(field):
    with pytest.raises(ValueError):
        infra.audit_request({"context": [{field: "private"}]})


@pytest.mark.parametrize(
    "file",
    [
        "truth.json",
        "intent.json",
        "review/A.json",
        "p017-correctness.json",
        "p019-correctness.json",
        ".env.ai.local",
    ],
)
def test_execution_worker_capabilities(tmp_path, file):
    root = tmp_path / "experiments"
    root.mkdir()
    inputs = root / "inputs"
    inputs.mkdir()
    forbidden = root / file
    forbidden.parent.mkdir(parents=True, exist_ok=True)
    forbidden.write_text("synthetic prohibited input")
    with evaluation_io(root, (inputs,), root / "output"), pytest.raises(PermissionError):
        forbidden.read_bytes()
    with pytest.raises(PermissionError):
        offline("socket.connect", ())


def test_secret_env_never_fingerprinted_and_provider_absent():
    with pytest.raises(PermissionError):
        infra.sha(Path(".env.ai.local"))
    source = Path(infra.__file__).read_text()
    assert "create_provider" not in source and "OpenAI(" not in source
    assert 'os.environ.get("ARCHGUARD_AI_API_KEY"' not in source


@pytest.mark.parametrize(
    "states,expected",
    [
        (("SUPPORTED", "NOT_SUPPORTED", "NOT_SUPPORTED"), "SUPPORTED"),
        (("NOT_SUPPORTED", "SUPPORTED", "NOT_SUPPORTED"), "SUPPORTED"),
        (("NOT_APPLICABLE", "NOT_APPLICABLE", "SUPPORTED"), "SUPPORTED"),
        (("NOT_APPLICABLE", "NOT_APPLICABLE", "NOT_SUPPORTED"), "NOT_SUPPORTED"),
        (("NOT_APPLICABLE", "NOT_APPLICABLE", "INSUFFICIENT_EVIDENCE"), "INSUFFICIENT_EVIDENCE"),
        (("NOT_APPLICABLE",) * 3, "NOT_APPLICABLE"),
    ],
)
def test_h0_categorical_scope_and_disagreements(states, expected):
    assert domain.h0(dict(zip(domain.COMPONENTS, states, strict=True))) == expected
    with pytest.raises(ValueError):
        domain.h0({"LLM": "UNKNOWN"})


def training_rows():
    rows = []
    for i in range(12):
        label = i % 2
        values = {n: float(label) for names in domain.FEATURES.values() for n in names}
        values["graph.I"] = None
        rows.append(
            dict(
                cohort="SYNTHETIC",
                split="TRAIN",
                llm_bound=True,
                label=label,
                values=values,
                evidence={
                    "STATIC": "NOT_APPLICABLE",
                    "GRAPH": "SUPPORTED" if label else "NOT_SUPPORTED",
                    "LLM": "INSUFFICIENT_EVIDENCE",
                },
            )
        )
    return rows


@pytest.mark.parametrize("method", ["H1", "H2"])
@pytest.mark.parametrize("components", domain.ABLATIONS[3:])
def test_learned_synthetic_ablations_refit_and_precedence(method, components):
    rows = training_rows()
    artifact = fit_candidate(rows, method, components)
    assert artifact == fit_candidate(rows, method, components)
    assert len(artifact["coefficients"]) == 2 * sum(len(domain.FEATURES[c]) for c in components)
    assert all(
        c["name"] in {n for c in components for n in domain.FEATURES[c]}
        for c in artifact["columns"]
    )
    for proof, component in (("static_proof", "STATIC"), ("cycle_proof", "GRAPH")):
        if component in components:
            row = copy.deepcopy(rows[0])
            row["evidence"][proof] = True
            assert domain.predict(row, artifact) == "SUPPORTED"
    row = copy.deepcopy(rows[0])
    row["evidence"] = dict.fromkeys(domain.COMPONENTS, "INSUFFICIENT_EVIDENCE")
    assert domain.predict(row, artifact) == "INSUFFICIENT_EVIDENCE"
    assert all(c["scale"] > 0 for c in artifact["columns"])
    altered = copy.deepcopy(rows[0])
    altered["values"]["case_id"] = 999
    assert domain.transform(altered["values"], artifact) == domain.transform(
        rows[0]["values"], artifact
    )


@pytest.mark.parametrize("partition", ["VALIDATION", "TEST"])
def test_no_validation_or_test_fit(partition):
    rows = training_rows()
    rows[0]["split"] = partition
    with pytest.raises(ValueError, match="TRAIN"):
        fit_candidate(rows, "H2", domain.COMPONENTS)


def test_no_missing_llm_placeholder_fit():
    rows = training_rows()
    rows[0]["llm_bound"] = False
    with pytest.raises(ValueError, match="missing"):
        fit_candidate(rows, "H1", domain.COMPONENTS)
    rows = training_rows()
    rows[0]["cohort"] = "FINAL"
    with pytest.raises(ValueError):
        fit_candidate(rows, "H1", domain.COMPONENTS)


def test_selection_nulls_ties_and_metric_denominators():
    assert domain.metric_scores([], []) == dict(F1=None, Precision=None, effective_correctness=None)
    scores = dict.fromkeys(
        ("H0", "H1", "H2"), dict(F1=0.6, Precision=0.8, effective_correctness=0.7)
    )
    assert domain.select_candidate(scores, "VALIDATION") == "H0"
    with pytest.raises(ValueError):
        domain.select_candidate(scores, "TEST")
    scores["H2"] = dict(F1=0.61, Precision=0.7, effective_correctness=0.6)
    assert domain.select_candidate(scores, "VALIDATION") == "H2"


def test_cost_preflight_retry_exposure_and_limits():
    pricing = PricingAssumption.model_validate_json(infra.PRICING.read_bytes())
    rows = [
        dict(
            input_estimate=1000,
            input_upper=4000,
            context_chars=3000,
            source_chars=1000,
            truncated=False,
        )
    ] * 480
    cost = domain.costs(rows, pricing)
    assert cost["input_tokens"] == 480000 and cost["expected_output"] == 288000
    assert cost["max_output"] == 960000 and cost["invoice"] is None
    assert float(cost["absolute_with_retries_usd"]) == pytest.approx(
        float(cost["primary_max_usd"]) * 3
    )
    rows[0] = dict(rows[0], input_upper=32769)
    with pytest.raises(ValueError, match="ceiling"):
        domain.costs(rows, pricing)
    assert pricing.charge(272001, 2000) > pricing.charge(272000, 2000)


def test_public_private_experiment_contract():
    text = Path(".gitignore").read_text()
    assert "experiments/unified-hybrid/private/" in text and ".env.*" in text
    p = domain.hybrid_protocol()
    assert len(domain.ABLATIONS) == 7 and p["ablation_refit"] and not p["real_model_trained"]
    assert "TRAIN_ONLY" in p["preprocessing"] and "NO_PREDICTIVE" in p["rule_identity"]
    assert "INSUFFICIENT_CONTEXT" in json.dumps(domain.protocol())


@pytest.mark.parametrize("rule", domain.RULES)
@pytest.mark.parametrize("language", ["JAVA", "TYPESCRIPT"])
def test_all_routes_build_deterministic_truth_blind_payloads(tmp_path, rule, language):
    case = "d" * 32
    if rule.startswith("ARCH2"):
        files, target, contract = infra.renamed_semantic(rule, language, 1, True, case)
        spec = {"version": "1.0", "architecture": {}, "rules": []}
        targets = [target]
    else:
        facts = structural.topology(rule, 5, True)
        files = structural.sources(case, language, facts)
        spec = structural.specification(rule)["spec"]
        contract = json.dumps(spec)
        targets = ["Unit" + case[:12] + "N" + str(i) for i in facts["target"]]
    for relative, text in files.items():
        p = tmp_path / relative
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    iam, _ = build(tmp_path, "request-synthetic")
    graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
    row = dict(
        execution_id=case,
        target_rule_id=rule,
        language=language,
        architecture_contract=contract,
        spec=spec,
        subjects=dict(
            locators=[infra.locator(iam, t) for t in targets], directed=len(targets) == 2
        ),
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        first = infra.request_material(row, iam, graph, repo.workspace)
        assert first == infra.request_material(row, iam, graph, repo.workspace)
    infra.audit_request(first[0])
    assert first[1]["context_chars"] <= 20000 and first[1]["input_upper"] <= 32768
    with pytest.raises(ValueError):
        infra.audit_request({"input": json.dumps({"human_rationale": "forbidden"})})


def test_total_budget_reserves_supplemental_structural_context(tmp_path):
    case = "e" * 32
    facts = structural.topology("ARCH101", 9, True)
    files = structural.sources(case, "JAVA", facts)
    for relative, text in files.items():
        text = text.replace(" {\n", " {\n// " + "x" * 2400 + "\n")
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    iam, _ = build(tmp_path, "large-context-synthetic")
    graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
    spec = structural.specification("ARCH101")["spec"]
    row = dict(
        execution_id=case,
        target_rule_id="ARCH101",
        language="JAVA",
        architecture_contract=json.dumps(spec),
        spec=spec,
        subjects=dict(locators=[infra.locator(iam, "Unit" + case[:12] + "N0")], directed=False),
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        material, metadata = infra.request_material(row, iam, graph, repo.workspace)
    assert metadata["context_chars"] <= 20000 and metadata["input_upper"] <= 32768
    assert material["context_manifest"]["configuration"]["max_total_chars"] < 20000


@pytest.mark.parametrize(
    "decision", ["SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"]
)
def test_future_vector_binding_uses_only_legitimate_component_values(decision):
    record = dict(
        STATIC="NOT_APPLICABLE",
        GRAPH="NOT_SUPPORTED",
        v2_score=0.2,
        existing_contract={"static": []},
        existing_features={"graph.cyclic": False, "quality.unresolved": 2},
        case_id="not-predictive",
        truth="not-predictive",
        severity=999,
    )
    assessment = domain.UnifiedAssessment(
        request_id="a" * 64,
        target_rule_id="ARCH201",
        decision=decision,
        subject_node_ids=("subject",),
        short_reason="Synthetic response",
        evidence_refs=(),
        limitations=(),
    )
    values = infra.candidate_values(record, assessment, truncated=True)
    assert values["llm.supported"] == float(decision == "SUPPORTED")
    assert values["llm.abstention"] == float(decision == "INSUFFICIENT_CONTEXT")
    assert values["llm.not_applicable"] == float(decision == "NOT_APPLICABLE")
    assert values["static.applicable"] == 0 and values["graph.is_cyclic"] == 0
    assert not {"case_id", "truth", "severity"} & set(values)
    missing = infra.candidate_values(record, None, truncated=False)
    assert all(missing[n] is None for n in domain.FEATURES["LLM"])
