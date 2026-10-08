"""Experiment-only opt-in adapter; architectural ownership has no benchmark dependency."""

from archguard.architecture.hybrid.alignment import HybridEvidenceAligner
from archguard.architecture.hybrid.assembler import HybridEvidenceAssembler
from archguard.architecture.hybrid.prospective_alignment import architectural_owner
from archguard.benchmark.materialization import MaterializeEvaluationCase


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
