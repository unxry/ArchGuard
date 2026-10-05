from uuid import UUID

from archguard.architecture.hybrid.models import (
    AlignmentMethod,
    EvidenceAgreement,
    HybridCase,
    SubjectPair,
)
from archguard.architecture.intelligence.models import SemanticDecision
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel

# These mappings describe related concerns, never equivalence or calibrated proof.
GRAPH_SEMANTIC_CONCERNS: dict[str, frozenset[str]] = {
    "ARCH101": frozenset({"ARCH205"}),
    "ARCH102": frozenset({"ARCH205"}),
    "ARCH103": frozenset({"ARCH201", "ARCH202", "ARCH205"}),
    "ARCH104": frozenset(),
    "ARCH105": frozenset({"ARCH203", "ARCH205"}),
}


class HybridEvidenceAligner:
    """Identity first. Only IAM parent links and directed dependencies broaden identity."""

    def __init__(self, iam: ArchitectureModel) -> None:
        self.nodes = {node.id: node for node in iam.nodes}
        self.parents: dict[NodeId, NodeId] = {}
        for node in iam.nodes:
            raw = node.attributes.get("parent_node_id")
            if isinstance(raw, str):
                try:
                    parent = NodeId(UUID(raw))
                except ValueError:
                    continue
                if parent in self.nodes:
                    self.parents[node.id] = parent
        self.dependencies = {(edge.source_id, edge.target_id) for edge in iam.edges}

    def ancestors(self, subject: NodeId) -> tuple[NodeId, ...]:
        result: list[NodeId] = []
        seen = {subject}
        while subject in self.parents:
            subject = self.parents[subject]
            if subject in seen:
                break
            seen.add(subject)
            if self.nodes[subject].kind in {NodeKind.PROJECT, NodeKind.PACKAGE, NodeKind.MODULE}:
                break
            result.append(subject)
            if self.nodes[subject].kind == NodeKind.FILE:
                break
        return tuple(result)

    def match(
        self,
        case: HybridCase,
        subjects: tuple[NodeId, ...],
        pairs: tuple[SubjectPair, ...] = (),
        explicit_anchor: bool = False,
    ) -> AlignmentMethod | None:
        if explicit_anchor:
            return AlignmentMethod.EXPLICIT_CANDIDATE_LINK
        # A shared endpoint never makes A->B evidence relevant to A->C.
        if case.subject_pairs and pairs:
            if set(case.subject_pairs) & set(pairs):
                return AlignmentMethod.EXACT_SUBJECT_PAIR
            return None
        primary = set(case.primary_subject_ids)
        if primary & set(subjects):
            return AlignmentMethod.EXACT_SUBJECT
        if any(owner in subjects for node in primary for owner in self.ancestors(node)):
            return AlignmentMethod.CONTAINMENT_OWNER
        if any(owner in primary for node in subjects for owner in self.ancestors(node)):
            return AlignmentMethod.CONTAINMENT_OWNER
        if not case.subject_pairs and any(
            (left, right) in self.dependencies or (right, left) in self.dependencies
            for left in primary
            for right in subjects
        ):
            return AlignmentMethod.DIRECT_GRAPH_RELATION
        return None


def concern_agreement(
    graph_rule: str,
    semantic_rule: str,
    decision: SemanticDecision,
    method: AlignmentMethod | None,
) -> EvidenceAgreement:
    if method not in {
        AlignmentMethod.EXACT_SUBJECT,
        AlignmentMethod.EXACT_SUBJECT_PAIR,
        AlignmentMethod.CONTAINMENT_OWNER,
    } or semantic_rule not in GRAPH_SEMANTIC_CONCERNS.get(graph_rule, frozenset()):
        return EvidenceAgreement.NEUTRAL
    if decision == SemanticDecision.INSUFFICIENT_CONTEXT:
        return EvidenceAgreement.MISSING
    return (
        EvidenceAgreement.SUPPORTING
        if decision == SemanticDecision.SUPPORTED
        else EvidenceAgreement.CONTRADICTING
    )
