from dataclasses import dataclass

from archguard.application.build_iam import BuildIAM
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.models import AIAnalysisConfig, AIAnalysisResult
from archguard.architecture.intelligence.ports import LLMProvider
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.iam.model import ArchitectureModel
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


@dataclass(frozen=True)
class SemanticAnalysisInputs:
    iam: ArchitectureModel
    graph: GraphAnalysisResult
    discovery: ArchitectureDiscoveryResult | None


class AnalyzeArchitectureSemantics:
    def __init__(
        self,
        building: BuildIAM,
        graph: GraphAnalyzer | None = None,
        discovery: ArchitectureDiscoveryAnalyzer | None = None,
    ) -> None:
        self.building = building
        self.graph = graph or GraphAnalyzer()
        self.discovery = discovery or ArchitectureDiscoveryAnalyzer()

    def prepare(
        self, snapshot: RepositorySnapshot, workspace: RepositoryWorkspace, config: AIAnalysisConfig
    ) -> SemanticAnalysisInputs:
        built = self.building.execute(snapshot, workspace)
        graph = self.graph.analyze(built.iam, config.graph)
        discovered = (
            self.discovery.analyze(
                built.iam, graph, ArchitectureDiscoveryConfig(graph=config.graph)
            )
            if config.include_discovery
            else None
        )
        return SemanticAnalysisInputs(built.iam, graph, discovered)

    def execute(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        config: AIAnalysisConfig | None = None,
        provider: LLMProvider | None = None,
        spec: ArchitectureSpecification | None = None,
        dry_run: bool = False,
    ) -> AIAnalysisResult:
        config = AIAnalysisConfig.model_validate(config or AIAnalysisConfig())
        inputs = self.prepare(snapshot, workspace, config)
        return SemanticArchitectureAnalyzer().analyze(
            inputs.iam, inputs.graph, workspace, config, provider, inputs.discovery, spec, dry_run
        )
