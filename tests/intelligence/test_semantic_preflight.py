import importlib.util
import json
import subprocess
from collections import Counter
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.models import GraphDiagnostic
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import ContextStrategy, SemanticDecision
from archguard.architecture.intelligence.selection import ContextSelectionError, resolve_node
from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_preflight import (
    PricingAssumption,
    RequestPreflight,
    SemanticAssessmentJudgment,
    SemanticExperimentManifest,
    cost_report,
    experiment_manifest,
    measure_request,
    research_request,
)
from archguard.infrastructure.llm_provider import OpenAIResponsesProvider
from archguard.infrastructure.semantic_preflight import publish_preflight, wire_payload


def test_preflight_reproduction_accepts_freeze_descendant_but_rejects_unrelated_head(
    tmp_path, monkeypatch
):
    script = Path(__file__).parents[2] / "scripts/prompt014_cost_preflight.py"
    spec = importlib.util.spec_from_file_location("prompt014_preflight", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.chdir(tmp_path)

    def git(*args):
        return subprocess.check_output(["git", *args], text=True).strip()

    git("init", "-q")
    git("config", "user.name", "Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("commit", "-q", "--allow-empty", "-m", "P013 baseline")
    baseline = git("rev-parse", "HEAD")
    assert module.verify_baseline_head(baseline) == baseline
    git("commit", "-q", "--allow-empty", "-m", "P014 freeze")
    assert module.verify_baseline_head(baseline) == git("rev-parse", "HEAD")
    git("checkout", "-q", "--orphan", "unrelated")
    git("commit", "-q", "--allow-empty", "-m", "Unrelated baseline")
    with pytest.raises(ValueError, match="frozen P013 baseline"):
        module.verify_baseline_head(baseline)


@pytest.fixture
def manifest():
    return experiment_manifest("a" * 64, "b" * 64, "c" * 64, tuple(f"case-{i}" for i in range(40)))


def revised(manifest, **updates):
    return seal(
        SemanticExperimentManifest,
        **(manifest.model_dump(exclude={"fingerprint"}) | updates),
    )


def test_frozen_protocol_is_balanced_and_deterministic(manifest):
    assert manifest == experiment_manifest("a" * 64, "b" * 64, "c" * 64, manifest.cases)
    assert len(manifest.execution_order) == len(set(manifest.execution_order)) == 120
    assert Counter(s for _, s in manifest.execution_order) == dict.fromkeys(ContextStrategy, 40)
    assert manifest.execution_authorized is False
    assert manifest.max_network_attempts == 360
    assert manifest.max_primary_output_tokens == 240000
    configs = [c.model_dump(exclude={"strategy"}) for c in manifest.strategies]
    assert configs[0] == configs[1] == configs[2]
    assert not any(configs[0][k] for k in ("include_discovery", "include_metrics", "include_spec"))


@pytest.mark.parametrize(
    "updates",
    [
        {"max_primary_output_tokens": 1},
        {"max_output_tokens_per_request": 128001},
        {"expected_output_tokens_per_request": 2001},
        {"prompt_version": "changed"},
    ],
)
def test_rejects_incoherent_protocol_even_when_resealed(manifest, updates):
    with pytest.raises(ValidationError):
        revised(manifest, **updates)


def test_rejects_duplicate_order_and_strategy_budget_changes(manifest):
    with pytest.raises(ValidationError):
        revised(manifest, execution_order=(manifest.execution_order[0],) * 120)
    first = manifest.strategies[0].model_copy(update={"max_total_chars": 19000})
    with pytest.raises(ValidationError):
        revised(manifest, strategies=(first, *manifest.strategies[1:]))


def test_research_not_applicable_does_not_change_production_schema():
    result = SemanticAssessmentJudgment(
        candidate_rule_id="ARCH202",
        subject_node_ids=("subject",),
        judgment="NOT_APPLICABLE",
        short_reason="No presentation responsibility.",
        evidence_refs=(),
        limitations=(),
    )
    assert SemanticAssessmentJudgment.model_validate_json(result.model_dump_json()) == result
    assert "NOT_APPLICABLE" not in {item.value for item in SemanticDecision}


def test_requests_need_no_credentials_or_answers_and_match_wire_format(chain, manifest):
    inputs, workspace, _ = chain
    target = resolve_node(inputs.iam, "B")
    with patch(
        "archguard.infrastructure.llm_provider.AIProviderSettings", side_effect=AssertionError
    ):
        requests = []
        for config in manifest.strategies:
            pack = GraphGuidedContextBuilder().build(
                target, inputs.iam, inputs.graph, workspace, config
            )
            request = research_request(manifest.cases[0], "ARCH202", pack, manifest)
            measured = measure_request(manifest.cases[0], pack, request, manifest)
            assert measured.input_estimate <= measured.conservative_input_upper <= 32768
            assert measured.provider_reported_input_tokens is None
            assert set(request.task) == {
                "case_id",
                "candidate_rule_id",
                "candidate_question",
                "subject_node_id",
            }
            assert set(request.untrusted_context) == {
                "trust",
                "target_node_id",
                "selected_node_ids",
                "source_fragments",
                "evidence",
                "context_status",
            }
            assert (
                request.untrusted_context["context_status"]["truncated"] == pack.manifest.truncated
            )
            requests.append(request)
        assert requests[0].task == requests[1].task == requests[2].task
        assert (
            requests[0].response_schema
            == requests[1].response_schema
            == requests[2].response_schema
        )
        captured = []

        def local_transport(body, key, timeout):
            captured.append(json.loads(body))
            return json.dumps(
                {
                    "status": "completed",
                    "model": manifest.model,
                    "output": [
                        {"type": "message", "content": [{"type": "output_text", "text": "{}"}]}
                    ],
                }
            ).encode()

        OpenAIResponsesProvider(
            manifest.model, SecretStr("synthetic"), local_transport
        ).complete_structured(requests[0])
        assert captured == [wire_payload(requests[0], manifest.model)]


def test_measuring_unicode_counts_utf8_and_rejects_oversized_input(chain, manifest):
    inputs, workspace, _ = chain
    pack = GraphGuidedContextBuilder().build(
        resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace
    )
    request = research_request(manifest.cases[0], "ARCH201", pack, manifest)
    ascii_row = measure_request(manifest.cases[0], pack, request, manifest)
    unicode_row = measure_request(
        manifest.cases[0],
        pack,
        request.model_copy(update={"system_instructions": request.system_instructions + "ж" * 3}),
        manifest,
    )
    assert unicode_row.conservative_input_upper == ascii_row.conservative_input_upper + 6
    assert unicode_row.input_estimate == ascii_row.input_estimate + 2
    with pytest.raises(ValueError, match="input budget"):
        measure_request(
            manifest.cases[0],
            pack,
            request.model_copy(update={"system_instructions": "x" * 40000}),
            manifest,
        )


def test_per_request_pricing_boundary_and_model_limits():
    pricing = seal(PricingAssumption)
    assert pricing.charge(272000, 1000) == Decimal("0.0277")
    assert pricing.charge(272001, 1000) == Decimal("0.0551502")
    assert pricing.charge(922000, 128000) == Decimal("0.2804")
    for counts in ((922001, 128000), (1, 128001), (-1, 0), (0, -1)):
        with pytest.raises(ValueError):
            pricing.charge(*counts)


@pytest.fixture
def measured_rows(manifest):
    return tuple(
        RequestPreflight(
            case_id=case,
            strategy=strategy,
            context_fingerprint="d" * 64,
            request_fingerprint="e" * 64,
            nodes=1,
            files=1,
            fragments=1,
            context_chars=100,
            source_chars=50,
            truncated=False,
            input_estimate=1000,
            conservative_input_upper=2000,
        )
        for case, strategy in manifest.execution_order
    )


def test_cost_totals_and_bounded_retry_exposure(manifest, measured_rows):
    rows = measured_rows
    report = cost_report(manifest, rows, seal(PricingAssumption))
    assert Decimal(report["expected_usd"]) == Decimal("0.048")
    assert Decimal(report["conservative_usd"]) == Decimal("0.144")
    assert Decimal(report["maximum_primary_usd"]) == Decimal("0.5132160")
    assert Decimal(report["maximum_additional_retry_usd"]) == Decimal("1.0264320")
    assert Decimal(report["maximum_usd_including_retries"]) == Decimal("1.5396480")
    assert report["budget_sufficiency_including_all_retries"] == {"1": False, "2": True, "5": True}
    assert report["live_api_calls"] == 0 and report["api_key_required"] is False
    with pytest.raises(ValueError, match="order"):
        cost_report(manifest, tuple(reversed(rows)), seal(PricingAssumption))
    with pytest.raises(ValueError, match="input budget"):
        cost_report(
            manifest,
            (rows[0].model_copy(update={"conservative_input_upper": 32769}), *rows[1:]),
            seal(PricingAssumption),
        )


def test_mixed_pricing_is_per_request_and_flags_long_context(manifest, measured_rows):
    manifest = revised(
        manifest, max_input_tokens_per_request=300000, max_primary_input_tokens=36000000
    )
    first = measured_rows[0].model_copy(
        update={"input_estimate": 272001, "conservative_input_upper": 272001}
    )
    report = cost_report(manifest, (first, *measured_rows[1:]), seal(PricingAssumption))
    assert Decimal(report["expected_usd"]) == Decimal("0.0548502") + 119 * Decimal("0.0004")
    assert report["long_context_requests"] == [(first.case_id, first.strategy.value)]
    assert not report["approaching_context_limit"]


def test_publication_rejects_tampering_and_never_overwrites(tmp_path, manifest, measured_rows):
    payload = {"experiment_fingerprint": manifest.fingerprint, "requests": measured_rows}
    contexts = payload | {"fingerprint": digest(payload)}
    pricing = seal(PricingAssumption)
    public = tmp_path / "scientific"
    report = publish_preflight(manifest, measured_rows, contexts, pricing, public)
    assert report["context_manifest_fingerprint"] == contexts["fingerprint"]
    assert {p.name for p in public.iterdir()} == {
        "semantic-context-v1.json",
        "context-manifest-v1.json",
        "research-response-schema-v1.json",
        "research-system-prompt-v1.txt",
    }
    with pytest.raises(ValueError, match="immutable"):
        publish_preflight(manifest, measured_rows, contexts, pricing, public)
    with pytest.raises(ValueError, match="identity"):
        publish_preflight(
            manifest,
            measured_rows,
            contexts | {"fingerprint": "0" * 64},
            pricing,
            tmp_path / "tampered",
        )
    assert not (tmp_path / "tampered").exists()


def test_partial_iam_is_explicit_and_does_not_weaken_default_guard(chain):
    inputs, workspace, _ = chain
    iam = inputs.iam.model_copy(update={"metadata": inputs.iam.metadata | {"is_valid": False}})
    graph = GraphAnalyzer().analyze(iam)
    target = resolve_node(iam, "B")
    builder = GraphGuidedContextBuilder()
    with pytest.raises(ContextSelectionError):
        builder.build(target, iam, graph, workspace)
    pack = builder.build(target, iam, graph, workspace, allow_invalid_iam_context=True)
    assert [d.code for d in pack.manifest.diagnostics] == ["CONTEXT_INVALID_IAM_PARTIAL_DATA"]
    assert not graph.is_valid and iam.metadata["is_valid"] is False
    assert graph.reproducibility.iam_fingerprint == iam_fingerprint(iam)
    broken = graph.model_copy(
        update={
            "diagnostics": (
                *graph.diagnostics,
                GraphDiagnostic(code="BROKEN_TOPOLOGY", message="Synthetic invalid topology"),
            )
        }
    )
    with pytest.raises(ContextSelectionError):
        builder.build(target, iam, broken, workspace, allow_invalid_iam_context=True)
    wrong = graph.model_copy(
        update={
            "reproducibility": graph.reproducibility.model_copy(
                update={"iam_fingerprint": "f" * 64}
            )
        }
    )
    with pytest.raises(ContextSelectionError):
        builder.build(target, iam, wrong, workspace, allow_invalid_iam_context=True)
