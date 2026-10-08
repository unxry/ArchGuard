"""Opt-in ownership routing; historical P009 assemblers and graph artifacts are unchanged."""

from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.models import GraphNode
from archguard.architecture.hybrid.alignment import HybridEvidenceAligner
from archguard.architecture.hybrid.assembler import HybridEvidenceAssembler, HybridInputError
from archguard.benchmark.materialization import MaterializeEvaluationCase
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind

VERSION = "evidence-alignment-v2"
ARCHITECTURAL_KINDS = frozenset(
    {NodeKind.CLASS, NodeKind.INTERFACE, NodeKind.ENUM, NodeKind.TYPE_ALIAS, NodeKind.FUNCTION}
)


def architectural_owner(
    node: GraphNode,
    aligner: HybridEvidenceAligner,
    discovery: ArchitectureDiscoveryResult | None = None,
) -> NodeId:
    """Prefer projection identity, then validated Discovery, then unique containment root."""
    members = {s for s in node.iam_node_ids if s in aligner.nodes}
    candidates = {s for s in members if aligner.nodes[s].kind in ARCHITECTURAL_KINDS}
    identity = NodeId(node.id)
    if identity in candidates:
        return identity
    if (
        not candidates
        and identity in members
        and node.kind == NodeKind.FILE
        and aligner.nodes[identity].kind == NodeKind.FILE
    ):
        return identity
    if discovery:
        representatives = {
            c.iam_node_id for c in discovery.discovered.components if c.id == node.id
        }
        if representatives:
            if len(representatives) != 1 or not representatives <= candidates:
                raise HybridInputError("invalid architectural Discovery representative")
            return next(iter(representatives))
    roots = {c for c in candidates if not (set(aligner.ancestors(c)) & candidates)}
    if len(roots) != 1:
        raise HybridInputError("architectural ownership is missing or ambiguous")
    return next(iter(roots))


class ProspectiveMaterializeEvaluationCase(MaterializeEvaluationCase):
    def use_prospective_alignment(self) -> None:
        graph = self.graph
        if graph is None:
            return
        aligner = HybridEvidenceAligner(self.iam)
        # An ownership-only routing view feeds the unchanged legacy fusion algorithm.
        # Metrics, edges, proofs, SCCs and original graph evidence are never rewritten.
        nodes = tuple(
            n.model_copy(
                update={"iam_node_ids": (architectural_owner(n, aligner, self.discovery),)}
            )
            for n in graph.graph.nodes
        )
        routing = graph.model_copy(
            update={"graph": graph.graph.model_copy(update={"nodes": nodes})}
        )
        self.assembler = HybridEvidenceAssembler(
            self.iam,
            self.static,
            routing,
            self.discovery,
            self.ai,
            self.assembler.graph_conformance,
        )
        self.assembler.graph = graph
