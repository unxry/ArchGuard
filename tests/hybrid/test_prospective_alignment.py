"""Synthetic ownership contracts only; no scientific labels or historical predictions."""

from uuid import uuid4

import pytest

from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.models import GraphNodeId
from archguard.architecture.hybrid.alignment import HybridEvidenceAligner
from archguard.architecture.hybrid.assembler import HybridInputError
from archguard.architecture.hybrid.prospective_alignment import architectural_owner
from archguard.benchmark.prospective_materialization import ProspectiveMaterializeEvaluationCase
from archguard.core.model.enums import NodeKind
from archguard.infrastructure.component_holdout import build

JAVA = (
    "class A { int field; int run() { return 0; } }",
    "class A { class B { int field; void run() {} } }",
    "interface A { void run(); } class B implements A { public void run() {} }",
    "class A {} class B {}",
)
TS = (
    "export class A { property: number = 0; run(): number { return 0; } }",
    "export class A { constructor(public value: number) {} }",
    "export interface A { value: number; run(): void; } export type B = { x: number };",
    "export class A { nested = { property: 0 }; run() { return this.nested.property; } }",
    "export class A {} export class B {}",
)


@pytest.mark.parametrize("source,ext", [(s, "java") for s in JAVA] + [(s, "ts") for s in TS])
@pytest.mark.parametrize("with_discovery", [False, True])
def test_ownership_from_real_synthetic_iam(tmp_path, source, ext, with_discovery):
    (tmp_path / ("Example." + ext)).write_text(source)
    iam, _ = build(tmp_path, "synthetic-alignment")
    graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
    discovery = ArchitectureDiscoveryAnalyzer().analyze(iam, graph) if with_discovery else None
    aligner = HybridEvidenceAligner(iam)
    before = graph.model_dump(mode="json")
    for node in graph.graph.nodes:
        owner = architectural_owner(node, aligner, discovery)
        assert aligner.nodes[owner].kind not in {NodeKind.PROPERTY, NodeKind.FIELD, NodeKind.METHOD}
        assert owner == architectural_owner(
            node.model_copy(update={"iam_node_ids": tuple(reversed(node.iam_node_ids))}),
            aligner,
            discovery,
        )
        if node.id in aligner.nodes:
            assert owner == node.id
    materializer = ProspectiveMaterializeEvaluationCase(iam, None, graph, discovery)
    materializer.use_prospective_alignment()
    assert graph.model_dump(mode="json") == before
    for metric in graph.metrics:
        owner = materializer.assembler.owner[metric.node_id]
        assert materializer.assembler.measurements[owner].metrics == metric


def test_ambiguous_roots_rejected_and_identity_precedes_members(tmp_path):
    (tmp_path / "Example.ts").write_text("export class A { p = 0; } export class B {}")
    iam, _ = build(tmp_path, "ambiguity")
    graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
    aligner = HybridEvidenceAligner(iam)
    classes = tuple(n.id for n in iam.nodes if n.kind == NodeKind.CLASS)
    node = next(n for n in graph.graph.nodes if n.kind == NodeKind.CLASS).model_copy(
        update={"iam_node_ids": classes}
    )
    assert architectural_owner(node, aligner) == node.id
    node = node.model_copy(update={"id": GraphNodeId(uuid4())})
    with pytest.raises(HybridInputError, match="ambiguous"):
        architectural_owner(node, aligner)
    only = node.model_copy(update={"iam_node_ids": (classes[0],)})
    assert architectural_owner(only, aligner) == classes[0]
    parent, child = classes
    nested = iam.model_copy(
        update={
            "nodes": tuple(
                n.model_copy(update={"attributes": n.attributes | {"parent_node_id": str(parent)}})
                if n.id == child
                else n
                for n in iam.nodes
            )
        }
    )
    assert architectural_owner(node, HybridEvidenceAligner(nested)) == parent
