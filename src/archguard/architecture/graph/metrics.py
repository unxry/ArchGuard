from math import fsum

import networkx as nx

from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    GraphDiagnostic,
    GraphNodeId,
    GraphNodeMetrics,
    StronglyConnectedComponent,
)
from archguard.architecture.graph.native import native_graph


class PageRankConvergenceError(Exception):
    pass


def pagerank(
    graph: ArchitectureGraph, alpha: float, tolerance: float, max_iterations: int
) -> dict[GraphNodeId, float]:
    native = native_graph(graph)
    nodes = sorted(native.nodes, key=str)
    if not nodes:
        return {}
    if not 0 < alpha < 1 or tolerance <= 0 or max_iterations < 1:
        raise ValueError("invalid PageRank parameters")
    count = len(nodes)
    outgoing = {node: native.out_degree(node) for node in nodes}
    incoming = {node: sorted(native.predecessors(node), key=str) for node in nodes}
    ranks = dict.fromkeys(nodes, 1.0 / count)
    for _ in range(max_iterations):
        dangling = fsum(ranks[node] for node in nodes if outgoing[node] == 0) / count
        updated = {
            node: (1 - alpha) / count
            + alpha
            * (
                dangling
                + fsum(ranks[predecessor] / outgoing[predecessor] for predecessor in incoming[node])
            )
            for node in nodes
        }
        if fsum(abs(updated[node] - ranks[node]) for node in nodes) < count * tolerance:
            return updated
        ranks = updated
    raise PageRankConvergenceError("PageRank did not converge within configured iterations")


def calculate_metrics(
    graph: ArchitectureGraph,
    sccs: tuple[StronglyConnectedComponent, ...],
    config: GraphAnalysisConfig,
) -> tuple[
    tuple[GraphNodeMetrics, ...], tuple[GraphDiagnostic, ...], tuple[str, ...], tuple[str, ...]
]:
    native = native_graph(graph)
    diagnostics = []
    computed = ["degree", "coupling", "instability", "degree_centrality"]
    skipped = []
    betweenness: dict[GraphNodeId, float] | None = None
    ranks: dict[GraphNodeId, float] | None = None
    if config.calculate_betweenness:
        if len(graph.nodes) > config.betweenness_node_limit:
            diagnostics.append(
                GraphDiagnostic(
                    code="BETWEENNESS_NODE_LIMIT",
                    message="exact betweenness skipped above configured node budget",
                )
            )
            skipped.append("betweenness")
        else:
            betweenness = nx.betweenness_centrality(native, normalized=True, weight=None)
            computed.append("betweenness")
    else:
        skipped.append("betweenness")
    if config.calculate_pagerank:
        try:
            ranks = pagerank(
                graph,
                config.pagerank_alpha,
                config.pagerank_tolerance,
                config.pagerank_max_iterations,
            )
            computed.append("pagerank")
        except PageRankConvergenceError:
            diagnostics.append(
                GraphDiagnostic(
                    code="PAGERANK_CONVERGENCE",
                    message="PageRank did not converge within configured iterations",
                )
            )
            skipped.append("pagerank")
    else:
        skipped.append("pagerank")
    incoming = nx.in_degree_centrality(native)
    outgoing = nx.out_degree_centrality(native)
    sizes = {node: scc.size for scc in sccs for node in scc.members}
    results = []
    for node in sorted(native.nodes, key=str):
        left, right = set(native.predecessors(node)) - {node}, set(native.successors(node)) - {node}
        ca, ce = len(left), len(right)
        results.append(
            GraphNodeMetrics(
                node_id=node,
                in_degree_edges=native.in_degree(node),
                out_degree_edges=native.out_degree(node),
                unique_in_neighbors=ca,
                unique_out_neighbors=ce,
                afferent_coupling=ca,
                efferent_coupling=ce,
                total_unique_neighbors=len(left | right),
                instability=ce / (ca + ce) if ca + ce else None,
                in_degree_centrality=incoming[node],
                out_degree_centrality=outgoing[node],
                betweenness_centrality=betweenness[node] if betweenness is not None else None,
                pagerank=ranks[node] if ranks is not None else None,
                scc_size=sizes[node],
                is_cyclic=sizes[node] > 1,
            )
        )
    return tuple(results), tuple(diagnostics), tuple(computed), tuple(skipped)
