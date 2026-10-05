from collections import Counter
from math import isfinite
from uuid import UUID, uuid5

import networkx as nx
import pytest
from pydantic import ValidationError

from archguard.architecture.graph.algorithms import (
    GraphQueryError,
    cycle_observations,
    neighbourhood,
    shortest_path,
    strongly_connected_components,
)
from archguard.architecture.graph.candidates import generate_candidates, meets_float_threshold
from archguard.architecture.graph.config import (
    CandidateThresholds,
    GraphAnalysisConfig,
    GraphProjectionSpec,
)
from archguard.architecture.graph.enums import NeighbourhoodDirection
from archguard.architecture.graph.metrics import (
    PageRankConvergenceError,
    calculate_metrics,
    pagerank,
)
from archguard.architecture.graph.models import (
    ArchitectureGraph,
    DependencyProof,
    GraphEdge,
    GraphEdgeId,
    GraphNode,
    GraphNodeId,
)
from archguard.core.identifiers import EdgeId, NodeId, ProjectId
from archguard.core.locations import SourceLocation
from archguard.core.model.enums import EdgeKind, NodeKind

PROJECT = ProjectId(UUID(int=1))


def node_id(name: str) -> GraphNodeId:
    return GraphNodeId(uuid5(PROJECT, name))


def graph(
    pairs: list[tuple[str, str]],
    isolated: tuple[str, ...] = (),
    sizes: dict[str, tuple[int, int]] | None = None,
    self_edges: bool = False,
) -> ArchitectureGraph:
    names = sorted({name for pair in pairs for name in pair} | set(isolated))
    nodes = tuple(
        GraphNode(
            id=node_id(name),
            label=name,
            kind=NodeKind.CLASS,
            iam_node_ids=(NodeId(node_id(name)),),
            member_count=(sizes or {}).get(name, (0, 0))[0],
            method_count=(sizes or {}).get(name, (0, 0))[1],
        )
        for name in names
    )
    edges = []
    for left, right in sorted(set(pairs)):
        identity = uuid5(PROJECT, left + "->" + right)
        location = SourceLocation(file_path=left + ".ts", start_line=1)
        proof = DependencyProof(
            iam_edge_id=EdgeId(identity),
            source_node_id=NodeId(node_id(left)),
            target_node_id=NodeId(node_id(right)),
            relation=EdgeKind.CALLS,
            occurrences=1,
            locations=(location,),
            provenance=(
                {
                    "source_location": location.model_dump(mode="json"),
                    "resolution_status": "RESOLVED",
                    "resolution_method": "EXACT_IMPORT",
                    "reference_kind": "CALL",
                },
            ),
        )
        edges.append(
            GraphEdge(
                id=GraphEdgeId(identity),
                source_id=node_id(left),
                target_id=node_id(right),
                relation_kinds=(EdgeKind.CALLS,),
                proofs=(proof,),
            )
        )
    return ArchitectureGraph(
        project_id=PROJECT,
        projection=GraphProjectionSpec(include_self_edges=self_edges),
        nodes=nodes,
        edges=tuple(edges),
    )


def metrics(value: ArchitectureGraph, config: GraphAnalysisConfig | None = None):
    return calculate_metrics(
        value, strongly_connected_components(value), config or GraphAnalysisConfig()
    )


def test_chain_exact_metrics_and_pagerank() -> None:
    value = graph([("A", "B"), ("B", "C")])
    results, diagnostics, computed, skipped = metrics(value)
    assert not diagnostics and not skipped and "pagerank" in computed
    values = {item.node_id: item for item in results}
    a, b, c = (values[node_id(name)] for name in "ABC")
    assert (a.afferent_coupling, a.efferent_coupling, a.instability) == (0, 1, 1)
    assert (b.afferent_coupling, b.efferent_coupling, b.instability) == (1, 1, 0.5)
    assert (c.afferent_coupling, c.efferent_coupling, c.instability) == (1, 0, 0)
    assert (a.out_degree_edges, c.in_degree_edges) == (1, 1)
    assert a.out_degree_centrality == b.in_degree_centrality == 0.5
    assert (a.betweenness_centrality, b.betweenness_centrality, c.betweenness_centrality) == (
        0,
        0.5,
        0,
    )
    alpha = 0.85
    base = 1 / (3 + 2 * alpha + alpha**2)
    assert [a.pagerank, b.pagerank, c.pagerank] == pytest.approx(
        [base, (1 + alpha) * base, (1 + alpha + alpha**2) * base], abs=1e-8
    )
    assert sum(item.pagerank for item in results) == pytest.approx(1)
    assert all(item.scc_size == 1 and not item.is_cyclic for item in results)


def test_isolated_metrics_are_undefined_instability_and_standard_singleton_centrality() -> None:
    value = graph([], ("I",))
    (result,) = metrics(value)[0]
    assert result.instability is None and result.afferent_coupling == result.efferent_coupling == 0
    assert result.pagerank == 1 and result.betweenness_centrality == 0
    assert result.in_degree_centrality == result.out_degree_centrality == 1


def test_cycle_metrics_and_canonical_closed_proof() -> None:
    value = graph([("A", "B"), ("B", "C"), ("C", "A")])
    sccs = strongly_connected_components(value)
    assert len(sccs) == 1 and sccs[0].size == 3 and sccs[0].internal_edge_count == 3
    (cycle,) = cycle_observations(value, sccs, 4)
    assert cycle.node_ids == tuple(node_id(name) for name in "ABCA")
    assert len(cycle.edge_ids) == 3 and not cycle.truncated
    result = metrics(value)[0]
    assert all(item.instability == 0.5 and item.scc_size == 3 and item.is_cyclic for item in result)
    assert [item.pagerank for item in result] == pytest.approx([1 / 3] * 3)
    shuffled = value.model_copy(
        update={"nodes": tuple(reversed(value.nodes)), "edges": tuple(reversed(value.edges))}
    )
    assert strongly_connected_components(shuffled) == sccs
    assert cycle_observations(shuffled, sccs, 4) == (cycle,)


def test_multiple_cycles_and_independent_sccs_have_bounded_proofs() -> None:
    value = graph([("A", "B"), ("B", "A"), ("B", "C"), ("C", "B"), ("D", "E"), ("E", "D")])
    cycles = cycle_observations(value, strongly_connected_components(value), 10)
    assert len(cycles) == 2
    first = next(item for item in cycles if node_id("A") in item.members)
    assert first.node_ids == tuple(node_id(name) for name in "ABA")
    assert len(first.members) == 3


def test_trace_limit_and_kept_self_loop_are_explicit() -> None:
    value = graph([("A", "B"), ("B", "C"), ("C", "A")])
    (cycle,) = cycle_observations(value, strongly_connected_components(value), 3)
    assert cycle.truncated and not cycle.node_ids and not cycle.edge_ids
    loop = graph([("A", "A")], self_edges=True)
    assert not cycle_observations(loop, strongly_connected_components(loop), 10)
    (item,) = metrics(loop)[0]
    assert item.in_degree_edges == item.out_degree_edges == 1
    assert item.instability is None and not item.is_cyclic


def test_dense_scc_never_enumerates_all_simple_cycles(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args, **kwargs):
        raise AssertionError("simple cycle enumeration is forbidden")

    monkeypatch.setattr(nx, "simple_cycles", forbidden)
    names = [f"N{i:02}" for i in range(35)]
    value = graph([(left, right) for left in names for right in names if left != right])
    sccs = strongly_connected_components(value)
    assert len(sccs) == 1 and sccs[0].size == 35
    (cycle,) = cycle_observations(value, sccs, 256)
    assert len(cycle.node_ids) == 3


def test_large_chain_respects_expensive_metric_budget() -> None:
    value = graph([(f"N{i}", f"N{i + 1}") for i in range(349)])
    results, diagnostics, computed, skipped = metrics(
        value, GraphAnalysisConfig(betweenness_node_limit=100)
    )
    assert len(results) == 350 and all(item.scc_size == 1 for item in results)
    assert all(item.betweenness_centrality is None for item in results)
    assert "betweenness" in skipped and "pagerank" in computed
    assert diagnostics[0].code == "BETWEENNESS_NODE_LIMIT"
    assert sum(item.out_degree_edges for item in results) == 349
    assert all(item.pagerank is not None and isfinite(item.pagerank) for item in results)


def test_pagerank_convergence_is_typed_and_not_fake_zero() -> None:
    value = graph([("A", "B"), ("B", "C")])
    with pytest.raises(PageRankConvergenceError):
        pagerank(value, 0.85, 1e-20, 1)
    results, diagnostics, _, skipped = metrics(
        value, GraphAnalysisConfig(pagerank_max_iterations=1)
    )
    assert "pagerank" in skipped and all(item.pagerank is None for item in results)
    assert diagnostics[0].code == "PAGERANK_CONVERGENCE"
    assert pagerank(graph([]), 0.85, 1e-10, 100) == {}


def test_directed_shortest_path_ties_and_provenance() -> None:
    value = graph([("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")], ("I",))
    path = shortest_path(value, node_id("A"), node_id("D"))
    assert path and path.node_ids == (
        node_id("A"),
        min((node_id("B"), node_id("C")), key=str),
        node_id("D"),
    )
    assert len(path.edge_ids) == len(path.iam_edge_ids) == 2
    assert shortest_path(value, node_id("D"), node_id("A")) is None
    assert shortest_path(value, node_id("A"), node_id("A")).node_ids == (node_id("A"),)
    with pytest.raises(GraphQueryError):
        shortest_path(value, node_id("absent"), node_id("D"))


@pytest.mark.parametrize("direction,expected", [("IN", "AB"), ("OUT", "BC"), ("BOTH", "ABC")])
def test_neighbourhood_directions_and_refs(direction: str, expected: str) -> None:
    value = graph([("A", "B"), ("B", "C")])
    result = neighbourhood(value, node_id("B"), 1, NeighbourhoodDirection(direction))
    assert set(result.node_ids) == {node_id(name) for name in expected} and not result.truncated
    assert len(result.iam_edge_ids) == len(result.edge_ids)


def test_neighbourhood_limits_are_deterministic() -> None:
    value = graph([("A", "B"), ("A", "C"), ("C", "D")])
    limited = neighbourhood(value, node_id("A"), 4, max_nodes=2)
    assert limited.truncated and len(limited.node_ids) == 2
    assert limited == neighbourhood(value, node_id("A"), 4, max_nodes=2)
    assert neighbourhood(value, node_id("A"), 0).node_ids == (node_id("A"),)
    assert not neighbourhood(value, node_id("A"), 4, max_nodes=4).truncated
    with pytest.raises(GraphQueryError):
        neighbourhood(value, node_id("A"), -1)
    with pytest.raises(GraphQueryError):
        neighbourhood(value, node_id("missing"), 1)


def hub() -> ArchitectureGraph:
    return graph(
        [(f"S{i}", "A") for i in range(4)] + [("A", "B")] + [("B", f"L{i}") for i in range(3)],
        sizes={"A": (4, 4), "B": (2, 2)},
    )


def test_all_candidates_have_explicit_thresholds_and_null_confidence() -> None:
    value = hub()
    config = GraphAnalysisConfig(
        candidates=CandidateThresholds(
            excessive_coupling=4,
            hub_fan_in=3,
            god_min_members=3,
            god_min_methods=3,
            god_min_coupling=4,
            unstable_delta=0.4,
            bottleneck_betweenness=0.25,
            bottleneck_min_neighbors=4,
        )
    )
    candidates = generate_candidates(value, metrics(value)[0], config)
    assert Counter(item.rule_id for item in candidates) == {
        "ARCH101": 2,
        "ARCH102": 1,
        "ARCH103": 1,
        "ARCH104": 1,
        "ARCH105": 2,
    }
    assert all(
        item.not_calibrated
        and item.confidence is None
        and item.evidence
        and "Candidate" in item.title
        for item in candidates
    )
    unstable = next(item for item in candidates if item.rule_id == "ARCH104")
    assert unstable.metrics["source_instability"] == 0.2
    assert unstable.metrics["target_instability"] == 0.75
    assert unstable.metrics["delta"] == pytest.approx(0.55)
    assert generate_candidates(value, metrics(value)[0], config) == candidates
    assert generate_candidates(value, metrics(value)[0], GraphAnalysisConfig()) == ()


@pytest.mark.parametrize("members,coupling,expected", [(100, 10, 0), (1, 4, 0), (4, 4, 1)])
def test_god_candidate_requires_size_and_coupling(
    members: int, coupling: int, expected: int
) -> None:
    value = hub().model_copy(
        update={
            "nodes": tuple(
                node.model_copy(update={"member_count": members}) if node.label == "A" else node
                for node in hub().nodes
            )
        }
    )
    config = GraphAnalysisConfig(
        candidates=CandidateThresholds(god_min_members=3, god_min_coupling=coupling)
    )
    assert len(generate_candidates(value, metrics(value)[0], config)) == expected


@pytest.mark.parametrize("threshold,expected", [(4, 1), (5, 1), (6, 0)])
def test_coupling_threshold_uses_distinct_union(threshold: int, expected: int) -> None:
    value = hub()
    config = GraphAnalysisConfig(candidates=CandidateThresholds(excessive_coupling=threshold))
    assert (
        len(
            [
                item
                for item in generate_candidates(value, metrics(value)[0], config)
                if item.subject_node_id == node_id("A")
            ]
        )
        == expected
    )


def test_no_bottleneck_without_betweenness_and_undefined_instability_skipped() -> None:
    value = hub()
    calculated = metrics(value, GraphAnalysisConfig(calculate_betweenness=False))[0]
    calculated = tuple(
        item.model_copy(update={"instability": None}) if item.node_id == node_id("A") else item
        for item in calculated
    )
    config = GraphAnalysisConfig(
        candidates=CandidateThresholds(unstable_delta=0.4, bottleneck_betweenness=0.1)
    )
    assert not generate_candidates(value, calculated, config)


def test_configuration_identity_and_float_boundary_policy() -> None:
    a = GraphAnalysisConfig(
        projection=GraphProjectionSpec(included_relations=(EdgeKind.CALLS, EdgeKind.IMPORTS))
    )
    b = GraphAnalysisConfig(
        projection=GraphProjectionSpec(
            included_relations=(EdgeKind.IMPORTS, EdgeKind.CALLS, EdgeKind.CALLS)
        )
    )
    assert a.fingerprint == b.fingerprint
    assert meets_float_threshold(0.5 - 1e-14, 0.5)
    assert not meets_float_threshold(0.5 - 1e-8, 0.5)
    assert not meets_float_threshold(0, 1e-15)
    with pytest.raises(ValidationError):
        CandidateThresholds(god_min_members=3)
    with pytest.raises(ValidationError):
        GraphProjectionSpec(included_relations=(EdgeKind.READS,))


def test_graph_contracts_reject_invalid_endpoints_and_artificial_self_edges() -> None:
    value = graph([("A", "B")])
    with pytest.raises(ValidationError):
        ArchitectureGraph.model_validate(value.model_copy(update={"nodes": value.nodes[:1]}))
    with pytest.raises(ValidationError):
        ArchitectureGraph.model_validate(value.model_copy(update={"nodes": value.nodes * 2}))
    loop = graph([("A", "A")], self_edges=True)
    with pytest.raises(ValidationError):
        ArchitectureGraph.model_validate(
            loop.model_copy(update={"projection": GraphProjectionSpec()})
        )
