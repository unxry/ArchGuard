from contextlib import contextmanager
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from archguard.application.analyze_architecture_semantics import AnalyzeArchitectureSemantics
from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import (
    AIAnalysisBudget,
    AIAnalysisConfig,
    ArchitectureContextPack,
    ContextSelectionConfig,
    LLMUsage,
    SourceFragment,
    TargetSelectionConfig,
)
from archguard.architecture.intelligence.selection import ContextSelectionError, resolve_node
from archguard.infrastructure.graph_configuration import load_graph_configuration
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.helpers.scripted_llm import ScriptedLLMProvider
from tests.intelligence.conftest import building
from tests.intelligence.test_context import pack
from tests.intelligence.test_semantics import analyze

ROOT = Path(__file__).parents[1]


def test_manifest_and_transient_pack_cannot_disagree(chain):
    context = pack(chain)
    fragment = context.fragments[0]
    with pytest.raises(ValidationError):
        SourceFragment(reference=fragment.reference, text="different source")
    with pytest.raises(ValidationError):
        ArchitectureContextPack(manifest=context.manifest, fragments=())
    with pytest.raises(ValidationError):
        type(context.manifest).model_validate(context.manifest.model_copy(update={"files": 999}))
    with pytest.raises(ValidationError):
        LLMUsage(input_tokens=10, output_tokens=20, total_tokens=99)


def test_graph_and_discovery_identity_must_match(chain):
    inputs, workspace, _ = chain
    graph = inputs.graph.model_copy(
        update={
            "reproducibility": inputs.graph.reproducibility.model_copy(
                update={"iam_fingerprint": "f" * 64}
            )
        }
    )
    with pytest.raises(ContextSelectionError):
        GraphGuidedContextBuilder().build(
            resolve_node(inputs.iam, "B"), inputs.iam, graph, workspace
        )
    discovered = inputs.discovery.model_copy(update={"graph": graph})
    with pytest.raises(ContextSelectionError):
        GraphGuidedContextBuilder().build(
            resolve_node(inputs.iam, "B"), inputs.iam, inputs.graph, workspace, discovery=discovered
        )


@pytest.mark.parametrize("projection", ["file", "target_layer"])
def test_semantic_context_rejects_other_projections(projection):
    with pytest.raises(ValidationError):
        AIAnalysisConfig.model_validate({"graph": {"projection": {"projection": projection}}})


def test_invalid_and_incomplete_upstream_do_not_claim_success(chain):
    inputs, workspace, _ = chain
    invalid = inputs.graph.model_copy(update={"is_valid": False, "status": "INVALID"})
    result = SemanticArchitectureAnalyzer().analyze(
        inputs.iam, invalid, workspace, AIAnalysisConfig()
    )
    assert result.status == "INVALID" and result.calls == 0
    incomplete = inputs.graph.model_copy(update={"is_complete": False, "status": "INCOMPLETE"})
    config = AIAnalysisConfig(targets=TargetSelectionConfig(explicit_targets=("B",)))
    result = SemanticArchitectureAnalyzer().analyze(
        inputs.iam, incomplete, workspace, config, ScriptedLLMProvider()
    )
    assert result.status == "PARTIAL" and result.candidates


@pytest.mark.parametrize(
    "count,code", [(None, "UNMEASURABLE"), (-1, "INVALID"), (True, "INVALID"), (1000, "EXCEEDED")]
)
def test_preflight_token_limits_are_fail_closed(chain, count, code):
    provider = ScriptedLLMProvider(input_count=count)
    result = analyze(chain, provider, budget=AIAnalysisBudget(max_total_input_tokens=50))
    assert result.calls == 0 and not provider.requests
    assert any(code in d.code for d in result.diagnostics)


def test_token_counter_failure_and_late_response_are_isolated(chain):
    provider = ScriptedLLMProvider()
    with patch.object(provider, "count_input_tokens", side_effect=RuntimeError("PRIVATE")):
        result = analyze(chain, provider, budget=AIAnalysisBudget(max_total_input_tokens=1))
    assert result.calls == 0 and any(d.code == "AI_TOKEN_COUNT_FAILURE" for d in result.diagnostics)
    # No sleep: simulate elapsed wall time around the synchronous provider contract.
    with patch(
        "archguard.architecture.intelligence.analyzer.monotonic", side_effect=[0, 100, 101] * 3
    ):
        result = analyze(chain, provider)
    assert not result.candidates and all(
        i.diagnostic.code == "AI_PROVIDER_TIMEOUT" for i in result.invocations
    )


def test_byte_scan_and_missing_coordinates_drop_fragments(chain):
    inputs, workspace, _ = chain
    target = resolve_node(inputs.iam, "B")

    class Reader:
        @contextmanager
        def open_source_file(self, path):
            yield BytesIO(b"x\n" * 50)

    iam = inputs.iam.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(
                    update={
                        "source_location": n.source_location.model_copy(
                            update={"start_line": 20, "end_line": 20}
                        )
                    }
                )
                if n.id == target
                else n
                for n in inputs.iam.nodes
            )
        }
    )
    from archguard.architecture.intelligence.fragments import extract_fragments
    from archguard.architecture.intelligence.models import SelectedNode

    selected = (SelectedNode(node_id=target, distance=0, reason="TARGET"),)
    fragments, _, dropped, _ = extract_fragments(
        iam, selected, Reader(), ContextSelectionConfig(max_scan_bytes_per_file=2), None
    )
    assert not fragments and dropped == 1
    iam = iam.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"source_location": None}) if n.id == target else n
                for n in iam.nodes
            )
        }
    )
    assert extract_fragments(iam, selected, workspace, ContextSelectionConfig(), None)[2] == 1


@pytest.mark.parametrize("fixture", ["conflict", "java-layered", "features"])
def test_default_target_preselection_uses_structural_hypotheses(fixture):
    root = ROOT / "fixtures/discovery" / fixture
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as repo:
        result = AnalyzeArchitectureSemantics(building()).execute(
            repo.snapshot, repo.workspace, dry_run=True
        )
    if fixture == "conflict":
        assert {t.candidate_rule_id for t in result.targets} == {"ARCH202", "ARCH204"}
    elif fixture == "java-layered":
        assert len(result.targets) == 1 and result.targets[0].candidate_rule_id == "ARCH202"
    else:
        assert result.targets and all(t.candidate_rule_id == "ARCH202" for t in result.targets)


def test_graph_candidates_select_semantic_questions_without_creating_findings():
    root = ROOT / "fixtures/graph/hub"
    config = AIAnalysisConfig(
        graph=load_graph_configuration(ROOT.parent / "examples/graph/research-demo.json")
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as repo:
        result = AnalyzeArchitectureSemantics(building()).execute(
            repo.snapshot, repo.workspace, config, dry_run=True
        )
    assert result.targets and all(t.candidate_rule_id == "ARCH205" for t in result.targets)


def test_point_coordinates_above_cached_integer_range_keep_valid_locations(tmp_path):
    text = "\n" * 300 + " " * 300 + "class Long { void run() {} }\n"
    (tmp_path / "Long.java").write_text(text)
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        iam = building().execute(repo.snapshot, repo.workspace).iam
    declaration = next(n for n in iam.nodes if n.name == "Long")
    assert declaration.source_location.start_line == 301
    assert declaration.source_location.start_column == 301


def test_syntax_diagnostic_after_line_and_column_256_is_safe(tmp_path):
    (tmp_path / "Broken.java").write_text("\n" * 300 + " " * 300 + "class Broken { @@@ }")
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repo:
        result = building().execute(repo.snapshot, repo.workspace)
    assert not result.is_complete
