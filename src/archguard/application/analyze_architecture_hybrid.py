from dataclasses import dataclass

from archguard.application.build_iam import BuildIAM
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer
from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.conformance import (
    GraphConformanceAnalyzer,
    GraphConformanceResult,
)
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig, HybridAnalyzer
from archguard.architecture.hybrid.assembler import HybridInputError
from archguard.architecture.hybrid.models import HybridAnalysisResult
from archguard.architecture.intelligence.analyzer import SemanticArchitectureAnalyzer
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import AIAnalysisResult
from archguard.architecture.intelligence.ports import LLMProvider
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.iam.model import ArchitectureModel
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


@dataclass(frozen=True)
class HybridAnalysisInputs:
    iam: ArchitectureModel
    static: StaticConformanceResult | None
    graph: GraphAnalysisResult
    discovery: ArchitectureDiscoveryResult | None
    graph_conformance: GraphConformanceResult | None
    spec: ArchitectureSpecification | None


class AnalyzeArchitectureHybrid:
    def __init__(
        self,
        building: BuildIAM,
        graph: GraphAnalyzer | None = None,
        discovery: ArchitectureDiscoveryAnalyzer | None = None,
        static: StaticConformanceAnalyzer | None = None,
        semantic: SemanticArchitectureAnalyzer | None = None,
        hybrid: HybridAnalyzer | None = None,
        conformance: GraphConformanceAnalyzer | None = None,
    ) -> None:
        self.building = building
        self.graph = graph or GraphAnalyzer()
        self.discovery = discovery or ArchitectureDiscoveryAnalyzer()
        self.static = static or StaticConformanceAnalyzer()
        self.semantic = semantic or SemanticArchitectureAnalyzer()
        self.hybrid = hybrid or HybridAnalyzer()
        self.conformance = conformance or GraphConformanceAnalyzer()

    def prepare(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        config: HybridAnalysisConfig,
        spec: ArchitectureSpecification | None = None,
    ) -> HybridAnalysisInputs:
        iam = self.building.execute(snapshot, workspace).iam
        static = self.static.analyze(iam, spec) if spec else None
        graph = self.graph.analyze(iam, config.ai.graph)
        discovery = (
            self.discovery.analyze(iam, graph, ArchitectureDiscoveryConfig(graph=config.ai.graph))
            if config.ai.include_discovery
            else None
        )
        conformance = self.conformance.analyze(iam, spec, config.ai.graph) if spec else None
        return HybridAnalysisInputs(iam, static, graph, discovery, conformance, spec)

    def execute_prepared(
        self,
        inputs: HybridAnalysisInputs,
        ai: AIAnalysisResult | None = None,
        config: HybridAnalysisConfig | None = None,
    ) -> HybridAnalysisResult:
        return self.hybrid.analyze(
            inputs.iam,
            inputs.static,
            inputs.graph,
            inputs.discovery,
            ai,
            inputs.spec,
            inputs.graph_conformance,
            config,
        )

    def execute(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        config: HybridAnalysisConfig | None = None,
        spec: ArchitectureSpecification | None = None,
        provider: LLMProvider | None = None,
        saved_ai: AIAnalysisResult | None = None,
    ) -> HybridAnalysisResult:
        config = HybridAnalysisConfig.model_validate(config or HybridAnalysisConfig())
        if provider is not None and (provider.capabilities.remote or saved_ai is not None):
            raise HybridInputError("Hybrid foundation accepts only one offline AI input")
        inputs = self.prepare(snapshot, workspace, config, spec)
        ai = saved_ai
        if ai is not None:
            ai = AIAnalysisResult.model_validate(ai)
            # Reconstruct only source contexts, never call a provider. This also checks
            # target specification, discovery, metrics, source hashes and selection budgets.
            builder = GraphGuidedContextBuilder()
            for manifest in ai.manifests:
                current = builder.build(
                    manifest.target_node_id,
                    inputs.iam,
                    inputs.graph,
                    workspace,
                    manifest.configuration,
                    spec,
                    inputs.discovery,
                )
                if current.manifest.context_fingerprint != manifest.context_fingerprint:
                    raise HybridInputError(
                        "saved AI context does not match current selected evidence"
                    )
        elif provider is not None:
            ai = self.semantic.analyze(
                inputs.iam, inputs.graph, workspace, config.ai, provider, inputs.discovery, spec
            )
        return self.execute_prepared(inputs, ai, config)
