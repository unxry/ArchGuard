from collections import Counter

from archguard.application.build_iam import BuildIAM
from archguard.architecture.check_result import ArchitectureCheckResult
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.conformance.models import (
    ConformanceStatus,
    StaticConformanceResult,
    StaticConformanceStatistics,
)
from archguard.architecture.graph.conformance import GraphConformanceAnalyzer
from archguard.architecture.specification.models import (
    ArchitectureSpecification,
    CircularDependencySpecification,
)
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
    ) -> StaticConformanceResult | ArchitectureCheckResult:
        validated = ArchitectureSpecification.model_validate(spec)
        result = self.building.execute(snapshot, workspace)
        static = self.analyzer.analyze(result.iam, validated)
        if not any(
            isinstance(rule, CircularDependencySpecification) and rule.enabled
            for rule in validated.rules
        ):
            return static
        graph = GraphConformanceAnalyzer().analyze(result.iam, validated)
        valid, complete = (
            static.is_valid and graph.is_valid,
            static.is_complete and graph.is_complete,
        )
        findings = (
            tuple(
                sorted(
                    (*static.findings, *graph.findings),
                    key=lambda item: (item.rule_id, str(item.id)),
                )
            )
            if valid
            else ()
        )
        counts = static.statistics.model_dump()
        counts.update(
            rules_enabled=counts["rules_enabled"] + 1,
            rules_evaluated=counts["rules_evaluated"] + int(graph.is_valid),
            findings_total=len(findings),
            findings_by_rule=dict(sorted(Counter(f.rule_id for f in findings).items())),
            findings_by_severity=dict(sorted(Counter(f.severity.value for f in findings).items())),
        )
        return ArchitectureCheckResult(
            status=ConformanceStatus.INVALID
            if not valid
            else ConformanceStatus.NON_CONFORMANT
            if findings
            else ConformanceStatus.CONFORMANT
            if complete
            else ConformanceStatus.INCOMPLETE,
            is_valid=valid,
            is_complete=complete,
            static_result=static,
            graph_result=graph,
            findings=findings,
            statistics=StaticConformanceStatistics.model_validate(counts),
            reproducibility=static.reproducibility,
        )
