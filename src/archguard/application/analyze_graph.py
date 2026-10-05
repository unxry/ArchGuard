from archguard.application.build_iam import BuildIAM
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


class AnalyzeGraph:
    def __init__(self, building: BuildIAM, analyzer: GraphAnalyzer | None = None) -> None:
        self.building = building
        self.analyzer = analyzer if analyzer is not None else GraphAnalyzer()

    def execute(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        config: GraphAnalysisConfig | None = None,
        spec: ArchitectureSpecification | None = None,
    ) -> GraphAnalysisResult:
        valid_spec = ArchitectureSpecification.model_validate(spec) if spec is not None else None
        valid_config = GraphAnalysisConfig.model_validate(
            config if config is not None else GraphAnalysisConfig()
        )
        built = self.building.execute(snapshot, workspace)
        return self.analyzer.analyze(built.iam, valid_config, valid_spec)
