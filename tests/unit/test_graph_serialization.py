from uuid import UUID

from archguard.architecture.graph.analyzer import serialize_graph_result
from archguard.architecture.graph.config import GraphAnalysisConfig, fingerprint
from archguard.architecture.graph.models import ArchitectureGraph, ProjectionStatistics
from archguard.architecture.graph.result import (
    GraphAnalysisResult,
    GraphReproducibility,
    GraphStatistics,
)
from archguard.core.identifiers import ProjectId


def test_canonical_precision_preserves_algorithm_configuration() -> None:
    config = GraphAnalysisConfig(pagerank_tolerance=1e-14)
    project_id = ProjectId(UUID(int=1))
    result = GraphAnalysisResult(
        status="COMPLETE",
        is_valid=True,
        is_complete=True,
        graph=ArchitectureGraph(project_id=project_id, projection=config.projection),
        projection_statistics=ProjectionStatistics(iam_nodes_input=0, iam_edges_input=0),
        statistics=GraphStatistics(
            scc_count=0,
            cyclic_scc_count=0,
            cycle_findings=0,
            metric_node_count=0,
            metrics_computed=(),
            metrics_skipped=(),
        ),
        metrics=(),
        sccs=(),
        cycles=(),
        reproducibility=GraphReproducibility(
            project_id=project_id,
            snapshot_fingerprint=None,
            iam_schema_version="1.0",
            iam_fingerprint="0" * 64,
            networkx_version="3.7",
            configuration=config,
            configuration_fingerprint=config.fingerprint,
            projection_fingerprint=fingerprint(config.projection),
            architecture_spec_fingerprint=None,
        ),
    )
    restored = GraphAnalysisResult.model_validate_json(serialize_graph_result(result))
    assert restored.reproducibility.configuration == config
    assert (
        restored.reproducibility.configuration.fingerprint
        == result.reproducibility.configuration_fingerprint
    )
