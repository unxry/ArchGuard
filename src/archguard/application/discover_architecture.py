from archguard.application.build_iam import BuildIAM
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


class DiscoverArchitecture:
    def __init__(
        self,
        building: BuildIAM,
        graph: GraphAnalyzer | None = None,
        analyzer: ArchitectureDiscoveryAnalyzer | None = None,
    ) -> None:
        self.building = building
        self.graph = graph if graph is not None else GraphAnalyzer()
        self.analyzer = analyzer if analyzer is not None else ArchitectureDiscoveryAnalyzer()

    def execute(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        config: ArchitectureDiscoveryConfig | None = None,
    ) -> ArchitectureDiscoveryResult:
        config = ArchitectureDiscoveryConfig.model_validate(
            config if config is not None else ArchitectureDiscoveryConfig()
        )
        built = self.building.execute(snapshot, workspace)
        graph = self.graph.analyze(built.iam, config.graph)
        return self.analyzer.analyze(built.iam, graph, config)
