from collections import Counter, deque
from uuid import uuid5

import networkx as nx

from archguard.architecture.graph.enums import NeighbourhoodDirection
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    CycleObservation,
    GraphNeighbourhood,
    GraphNodeId,
    GraphPath,
    StronglyConnectedComponent,
)
from archguard.architecture.graph.native import native_graph


class GraphQueryError(Exception):
    pass


def strongly_connected_components(
    graph: ArchitectureGraph,
) -> tuple[StronglyConnectedComponent, ...]:
    groups = [
        tuple(sorted(group, key=str))
        for group in nx.strongly_connected_components(native_graph(graph))
    ]
    membership = {node: index for index, group in enumerate(groups) for node in group}
    counts = Counter(
        membership[edge.source_id]
        for edge in graph.edges
        if membership[edge.source_id] == membership[edge.target_id]
    )
    results = [
        StronglyConnectedComponent(
            id=uuid5(
                graph.project_id,
                "graph-scc-v1:" + graph.projection.projection + ":" + ",".join(map(str, group)),
            ),
            members=group,
            size=len(group),
            internal_edge_count=counts[index],
        )
        for index, group in enumerate(groups)
    ]
    return tuple(sorted(results, key=lambda item: str(item.id)))


def cycle_observations(
    graph: ArchitectureGraph, sccs: tuple[StronglyConnectedComponent, ...], max_trace_length: int
) -> tuple[CycleObservation, ...]:
    native = native_graph(graph)
    keys = {node.id: (node.label, str(node.id)) for node in graph.nodes}
    edges = {(edge.source_id, edge.target_id): edge.id for edge in graph.edges}
    result = []
    for scc in sccs:
        if scc.size <= 1:
            continue
        members = set(scc.members)
        start = min(members, key=keys.__getitem__)
        distance = {start: 0}
        queue = deque([start])
        while queue:
            current = queue.popleft()
            for predecessor in sorted(native.predecessors(current), key=keys.__getitem__):
                if predecessor in members and predecessor not in distance:
                    distance[predecessor] = distance[current] + 1
                    queue.append(predecessor)
        first = min(
            (node for node in native.successors(start) if node in members and node != start),
            key=lambda node: (distance[node], keys[node]),
        )
        if distance[first] + 2 > max_trace_length:
            result.append(CycleObservation(scc_id=scc.id, members=scc.members, truncated=True))
            continue
        path = [start, first]
        while path[-1] != start:
            current = path[-1]
            following = min(
                (
                    node
                    for node in native.successors(current)
                    if node in members and distance[node] == distance[current] - 1
                ),
                key=keys.__getitem__,
            )
            path.append(following)
        result.append(
            CycleObservation(
                scc_id=scc.id,
                members=scc.members,
                node_ids=tuple(path),
                edge_ids=tuple(
                    edges[left, right] for left, right in zip(path, path[1:], strict=False)
                ),
            )
        )
    return tuple(result)


def shortest_path(
    graph: ArchitectureGraph, source: GraphNodeId, target: GraphNodeId
) -> GraphPath | None:
    native = native_graph(graph)
    if source not in native or target not in native:
        raise GraphQueryError("query node does not exist")
    parents: dict[GraphNodeId, GraphNodeId | None] = {source: None}
    queue = deque([source])
    while queue and target not in parents:
        current = queue.popleft()
        for neighbor in sorted(native.successors(current), key=str):
            if neighbor not in parents:
                parents[neighbor] = current
                queue.append(neighbor)
    if target not in parents:
        return None
    path = [target]
    while path[-1] != source:
        parent = parents[path[-1]]
        assert parent is not None
        path.append(parent)
    path.reverse()
    lookup = {(edge.source_id, edge.target_id): edge for edge in graph.edges}
    edges = [lookup[left, right] for left, right in zip(path, path[1:], strict=False)]
    return GraphPath(
        node_ids=tuple(path),
        edge_ids=tuple(edge.id for edge in edges),
        iam_edge_ids=tuple(
            sorted({proof.iam_edge_id for edge in edges for proof in edge.proofs}, key=str)
        ),
    )


def neighbourhood(
    graph: ArchitectureGraph,
    node: GraphNodeId,
    hops: int,
    direction: NeighbourhoodDirection = NeighbourhoodDirection.BOTH,
    max_nodes: int = 1_000,
) -> GraphNeighbourhood:
    native = native_graph(graph)
    if node not in native:
        raise GraphQueryError("query node does not exist")
    if hops < 0 or max_nodes < 1:
        raise GraphQueryError("invalid neighbourhood budget")
    seen = {node}
    queue = deque([(node, 0)])
    truncated = False
    while queue:
        current, depth = queue.popleft()
        if depth == hops:
            continue
        neighbors = (
            set(native.successors(current)) if direction != NeighbourhoodDirection.IN else set()
        )
        if direction != NeighbourhoodDirection.OUT:
            neighbors.update(native.predecessors(current))
        for neighbor in sorted(neighbors, key=str):
            if neighbor in seen:
                continue
            if len(seen) >= max_nodes:
                truncated = True
                continue
            seen.add(neighbor)
            queue.append((neighbor, depth + 1))
    edges = [edge for edge in graph.edges if edge.source_id in seen and edge.target_id in seen]
    return GraphNeighbourhood(
        node_ids=tuple(sorted(seen, key=str)),
        edge_ids=tuple(sorted((edge.id for edge in edges), key=str)),
        iam_edge_ids=tuple(
            sorted({proof.iam_edge_id for edge in edges for proof in edge.proofs}, key=str)
        ),
        truncated=truncated,
    )
