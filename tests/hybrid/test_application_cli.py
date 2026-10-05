import json
from dataclasses import replace
from unittest.mock import Mock, patch

import pytest

from archguard.application.analyze_architecture_hybrid import AnalyzeArchitectureHybrid
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import CandidateThresholds, GraphAnalysisConfig
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig, HybridAnalyzer
from archguard.architecture.hybrid.assembler import HybridInputError
from archguard.architecture.hybrid.serialization import serialize_hybrid
from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.models import (
    AIAnalysisConfig,
    TargetSelectionConfig,
    serialize_ai,
)
from archguard.architecture.specification.models import (
    ForbiddenDependencySpecification,
    RuleType,
    TargetSelector,
)
from archguard.cli import main
from archguard.infrastructure.hybrid_configuration import (
    HybridConfigurationError,
    load_hybrid_ai_result,
    load_hybrid_configuration,
)
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.helpers.scripted_llm import ScriptedLLMProvider, assessment
from tests.hybrid.conftest import ROOT, building, configured, semantic
from tests.hybrid.test_decisions import analyze, target


def test_full_pipeline_each_stage_once(violating):
    inputs, _ = violating
    stages = [
        Mock(wraps=s)
        for s in (
            building(),
            GraphAnalyzer(),
            ArchitectureDiscoveryAnalyzer(),
            StaticConformanceAnalyzer(),
            SemanticArchitectureAnalyzer(),
            HybridAnalyzer(),
        )
    ]
    application = AnalyzeArchitectureHybrid(
        *stages[:3], static=stages[3], semantic=stages[4], hybrid=stages[5]
    )
    config = HybridAnalysisConfig(
        ai=AIAnalysisConfig(
            targets=TargetSelectionConfig(explicit_targets=("Controller",), rules=("ARCH202",))
        )
    )
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(ROOT / "tests/fixtures/conformance/violating/java"),
        )
    ) as repo:
        result = application.execute(
            repo.snapshot, repo.workspace, config, inputs.spec, ScriptedLLMProvider()
        )
    assert result.confirmed_finding_ids and result.review_case_ids
    assert stages[0].execute.call_count == 1
    assert all(s.analyze.call_count == 1 for s in stages[1:])


def test_partial_ai_keeps_success_and_missing_target(violating):
    inputs, workspace = violating
    ai = SemanticArchitectureAnalyzer().analyze(
        inputs.iam,
        inputs.graph,
        workspace,
        AIAnalysisConfig(
            targets=TargetSelectionConfig(
                explicit_targets=("Controller", "Service"), rules=("ARCH202",)
            )
        ),
        ScriptedLLMProvider(["invalid-json", assessment]),
        inputs.discovery,
        inputs.spec,
    )
    assert ai.status == "PARTIAL" and len(ai.candidates) == 1
    result = analyze(inputs, ai)
    assert result.confirmed_finding_ids and "AI_PARTIAL" in result.diagnostics
    assert any(
        c.origin == "CALLER" and d.state.value == "INSUFFICIENT_EVIDENCE"
        for c, d in zip(result.cases, result.decisions, strict=True)
    )
    assert any(
        s.candidate_id == ai.candidates[0].candidate_id
        for b in result.evidence_bundles
        for s in b.ai
    )
    assert all(
        b.completeness.ai_requested >= b.completeness.ai_completed for b in result.evidence_bundles
    )


def test_arch001_keeps_proof_with_explicit_context_contradiction(violating):
    inputs, workspace = violating
    spec = inputs.spec.model_copy(
        update={
            "rules": (
                ForbiddenDependencySpecification(
                    id="ARCH001",
                    type=RuleType.FORBIDDEN,
                    source=TargetSelector(layer="presentation"),
                    target=TargetSelector(layer="persistence"),
                    severity="HIGH",
                ),
            )
        }
    )

    def explicit(request):
        data = json.loads(assessment(request, "NOT_SUPPORTED"))
        data["evidence_refs"] = [
            e["evidence_id"]
            for e in request.untrusted_context["evidence"]
            if e["kind"] in {"DEPENDENCY", "TARGET_CONSTRAINT"}
        ]
        return json.dumps(data)

    ai = SemanticArchitectureAnalyzer().analyze(
        inputs.iam,
        inputs.graph,
        workspace,
        AIAnalysisConfig(
            targets=TargetSelectionConfig(explicit_targets=("Controller",), rules=("ARCH205",))
        ),
        ScriptedLLMProvider([explicit]),
        inputs.discovery,
        spec,
    )
    result = analyze(
        replace(inputs, spec=spec, static=StaticConformanceAnalyzer().analyze(inputs.iam, spec)), ai
    )
    index = next(i for i, c in enumerate(result.cases) if c.origin == "STATIC")
    assert result.cases[index].rule_id == "ARCH001"
    assert result.decisions[index].state.value == "CONFIRMED_DETERMINISTIC"
    assert result.decisions[index].severity.value == "HIGH"
    assert any(
        a.agreement.value == "CONTRADICTING" for a in result.evidence_bundles[index].alignments
    )


def test_method_ai_aligns_to_graph_owner(hub):
    inputs, workspace = hub
    owner = target(inputs, "Stable")
    method = next(
        n.id
        for n in inputs.iam.nodes
        if n.attributes.get("parent_node_id") == str(owner) and n.name == "ping"
    )
    result = analyze(inputs, semantic(inputs, workspace, method))
    assert any(
        a.method and a.method.value == "CONTAINMENT_OWNER" and a.agreement.value == "SUPPORTING"
        for c, b in zip(result.cases, result.evidence_bundles, strict=True)
        if c.rule_id == "ARCH102"
        for a in b.alignments
    )


def test_remote_provider_is_not_run():
    provider = ScriptedLLMProvider(remote=True)
    with pytest.raises(HybridInputError, match="offline"):
        AnalyzeArchitectureHybrid(building()).execute(None, None, provider=provider)
    assert not provider.requests


@pytest.mark.parametrize("flag", [[], ["--without-ai"]])
def test_cli_does_not_load_provider(flag, monkeypatch, capsys):
    monkeypatch.setenv("OPENAI_API_KEY", "PRIVATE_KEY_MARKER")
    with patch(
        "archguard.infrastructure.llm_provider.AIProviderSettings",
        side_effect=AssertionError("no credentials"),
    ):
        assert (
            main(
                [
                    "hybrid",
                    "analyze",
                    str(ROOT / "tests/fixtures/conformance/violating/java"),
                    "--spec",
                    str(ROOT / "examples/architecture/layered-strict.yaml"),
                    "--json",
                    *flag,
                ]
            )
            == 0
        )
    result = json.loads(capsys.readouterr().out)
    assert result["confirmed_finding_ids"] and result["statistics"]["channel_cases"]["ai"] == 0
    assert "PRIVATE_KEY_MARKER" not in json.dumps(result)


def test_saved_ai_cli_checks_context(violating, tmp_path, capsys):
    inputs, workspace = violating
    ai = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    path, output = tmp_path / "saved-ai.json", tmp_path / "hybrid.json"
    path.write_text(serialize_ai(ai))
    args = [
        "hybrid",
        "analyze",
        str(ROOT / "tests/fixtures/conformance/violating/java"),
        "--namespace",
        "hybrid-tests",
        "--spec",
        str(ROOT / "examples/architecture/layered-strict.yaml"),
        "--ai-result",
        str(path),
        "--output",
        str(output),
        "--json",
    ]
    assert main(args) == 0
    assert output.read_text() == capsys.readouterr().out
    assert json.loads(output.read_text())["statistics"]["channel_cases"]["ai"] >= 1
    changed = ai.model_copy(
        update={
            "manifests": (ai.manifests[0].model_copy(update={"context_fingerprint": "a" * 64}),)
        }
    )
    path.write_text(serialize_ai(changed))
    assert main(args) == 2
    out = capsys.readouterr()
    assert not out.out and "INVALID_HYBRID_INPUT" in out.err


@pytest.mark.parametrize(
    "payload",
    ["invalid-json", "[]", '{"source_fragments":["PRIVATE_SOURCE_MARKER"]}', " " * 131073],
)
def test_config_rejection_is_bounded_and_sanitized(tmp_path, payload):
    path = tmp_path / "config.json"
    path.write_text(payload)
    with pytest.raises(HybridConfigurationError) as caught:
        load_hybrid_configuration(path)
    assert "PRIVATE_SOURCE_MARKER" not in str(caught.value)


def test_saved_ai_loader_rejects_raw_prompt_and_oversize(tmp_path):
    path = tmp_path / "ai.json"
    for payload in ('{"raw_prompt":"PRIVATE_SOURCE_MARKER"}', " " * 8388609):
        path.write_text(payload)
        with pytest.raises(HybridConfigurationError):
            load_hybrid_ai_result(path)


def test_offline_pipeline_bytes_across_fresh_ai_runs(violating):
    inputs, workspace = violating
    a = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    b = semantic(inputs, workspace, target(inputs, "Controller"), "ARCH202")
    assert a.invocations[0].invocation_id != b.invocations[0].invocation_id
    assert serialize_hybrid(analyze(inputs, a)) == serialize_hybrid(analyze(inputs, b))


def test_hundreds_of_cases_and_explicit_budget(tmp_path):
    for i in range(301):
        body = "static void run() {}" if not i else "static void run() { N0.run(); }"
        (tmp_path / f"N{i}.java").write_text(f"package p; public class N{i} {{ {body} }}")
    config = configured(
        GraphAnalysisConfig(
            calculate_betweenness=False,
            calculate_pagerank=False,
            candidates=CandidateThresholds(excessive_coupling=1, hub_fan_in=1),
        )
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        inputs = AnalyzeArchitectureHybrid(building()).prepare(
            repo.snapshot, repo.workspace, config
        )
        a, b = analyze(inputs), analyze(inputs)
    assert len(a.cases) >= 302 and serialize_hybrid(a) == serialize_hybrid(b)
    truncated = analyze(inputs, config=HybridAnalysisConfig(max_candidate_cases=10))
    assert len(truncated.cases) == 10 and truncated.statistics.omitted_candidate_cases >= 292
    assert "CANDIDATE_CASE_BUDGET_TRUNCATED" in truncated.diagnostics
