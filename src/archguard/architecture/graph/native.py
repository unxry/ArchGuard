from __future__ import annotations

import networkx as nx

from archguard.architecture.graph.models import ArchitectureGraph, GraphNodeId


def native_graph(graph: ArchitectureGraph) -> nx.DiGraph[GraphNodeId]:
    result: nx.DiGraph[GraphNodeId] = nx.DiGraph()
    result.add_nodes_from(sorted((node.id for node in graph.nodes), key=str))
    result.add_edges_from(
        sorted(
            ((edge.source_id, edge.target_id) for edge in graph.edges),
            key=lambda pair: (str(pair[0]), str(pair[1])),
        )
    )
    return result
