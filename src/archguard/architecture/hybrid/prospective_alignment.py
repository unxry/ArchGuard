"""Opt-in ownership routing; historical P009 assemblers and graph artifacts are unchanged."""

from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.models import GraphNode
from archguard.architecture.hybrid.alignment import HybridEvidenceAligner
from archguard.architecture.hybrid.assembler import HybridInputError
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
