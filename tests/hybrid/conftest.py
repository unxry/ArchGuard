from pathlib import Path
from unittest.mock import patch

import pytest

from archguard.application.analyze_architecture_hybrid import AnalyzeArchitectureHybrid
from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.graph.config import CandidateThresholds, GraphAnalysisConfig
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig
from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.models import AIAnalysisConfig, TargetSelectionConfig
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.helpers.scripted_llm import ScriptedLLMProvider, assessment

ROOT = Path(__file__).parents[2]


@pytest.fixture(scope="module")
def isolated(tmp_path_factory):
    root = tmp_path_factory.mktemp("hybrid-isolated")
    for name in ("A", "B"):
        (root / f"{name}.java").write_text(f"package p; public class {name} {{ void run() {{}} }}")
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as repo:
        yield (
            AnalyzeArchitectureHybrid(building()).prepare(
                repo.snapshot, repo.workspace, configured()
            ),
            repo.workspace,
        )


def building():
    return BuildIAM(
        ParseRepository(create_parser_registry()),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace="hybrid-tests"),
    )


def configured(graph=None):
    return HybridAnalysisConfig(ai=AIAnalysisConfig(graph=graph or GraphAnalysisConfig()))


def semantic(inputs, workspace, target, rule="ARCH205", decision="SUPPORTED", context=None):
    config = AIAnalysisConfig(
        graph=inputs.graph.reproducibility.configuration,
        targets=TargetSelectionConfig(explicit_targets=(str(target),), rules=(rule,)),
        **({"context": context} if context else {}),
    )
    return SemanticArchitectureAnalyzer().analyze(
        inputs.iam,
        inputs.graph,
        workspace,
        config,
        ScriptedLLMProvider([lambda request: assessment(request, decision)]),
        inputs.discovery,
        inputs.spec,
    )


@pytest.fixture(autouse=True)
def no_remote():
    with patch(
        "archguard.infrastructure.llm_provider._post",
        side_effect=AssertionError("Hybrid tests are offline"),
    ):
        yield


@pytest.fixture(scope="module")
def violating():
    spec = load_architecture_file(ROOT / "examples/architecture/layered-strict.yaml")
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(ROOT / "tests/fixtures/conformance/violating/java"),
        )
    ) as repo:
        yield (
            AnalyzeArchitectureHybrid(building()).prepare(
                repo.snapshot, repo.workspace, configured(), spec
            ),
            repo.workspace,
        )


@pytest.fixture(scope="module")
def hub():
    config = configured(
        GraphAnalysisConfig(candidates=CandidateThresholds(excessive_coupling=4, hub_fan_in=3))
    )
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL, location=str(ROOT / "tests/fixtures/graph/hub")
        )
    ) as repo:
        yield (
            AnalyzeArchitectureHybrid(building()).prepare(repo.snapshot, repo.workspace, config),
            repo.workspace,
        )


@pytest.fixture(scope="module")
def cyclic():
    spec = load_architecture_file(ROOT / "examples/architecture/circular-component.yaml")
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(ROOT / "tests/fixtures/graph/cyclic/java"),
        )
    ) as repo:
        yield (
            AnalyzeArchitectureHybrid(building()).prepare(
                repo.snapshot, repo.workspace, configured(), spec
            ),
            repo.workspace,
        )
