from archguard.application.build_iam import BuildIAM
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


class CheckArchitecture:
    def __init__(
        self, building: BuildIAM, analyzer: StaticConformanceAnalyzer | None = None
    ) -> None:
        self.building = building
        self.analyzer = analyzer if analyzer is not None else StaticConformanceAnalyzer()

    def execute(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        spec: ArchitectureSpecification,
    ) -> StaticConformanceResult:
        validated = ArchitectureSpecification.model_validate(spec)
        result = self.building.execute(snapshot, workspace)
        return self.analyzer.analyze(result.iam, validated)
