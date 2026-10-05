from collections import defaultdict
from uuid import uuid5

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import (
    STRENGTH_ORDER,
)
from archguard.architecture.discovery.enums import (
    ComponentRole as Role,
)
from archguard.architecture.discovery.enums import (
    DiscoveredLayer as Layer,
)
from archguard.architecture.discovery.enums import (
    DiscoveryEvidenceKind as Kind,
)
from archguard.architecture.discovery.enums import (
    DiscoveryStrength as Strength,
)
from archguard.architecture.discovery.models import (
    DiscoveryEvidence,
    LayerHypothesis,
    RoleHypothesis,
)
from archguard.architecture.discovery.signals import (
    FRAMEWORK_SIGNALS,
    IMPORT_SIGNALS,
    PATH_SIGNALS,
    ROLE_LAYERS,
    evidence,
    name_role,
)
from archguard.architecture.graph.models import GraphNode, GraphNodeId, GraphNodeMetrics
from archguard.architecture.graph.provenance import dependency_proof
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.core.model.enums import EdgeKind, Language
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode


class StructuralRoleClassifier:
    def __init__(self, iam: ArchitectureModel) -> None:
        self.symbol_attributes = {symbol.id: symbol.attributes for symbol in iam.symbols}

    def classify(
        self,
        node: ArchitectureNode,
        projected: GraphNode,
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        config: ArchitectureDiscoveryConfig,
        metric: GraphNodeMetrics | None,
        structural_evidence: tuple[DiscoveryEvidence, ...] = (),
    ) -> RoleHypothesis:
        observed = list(structural_evidence)
        path = (
            node.source_location.file_path
            if node.source_location
            else next(file.file_path for file in iam.source_files if file.id == node.file_id)
        )

        def add(
            kind: Kind,
            value: str,
            signal: str,
            strength: Strength,
            role: Role | None = None,
            layer: Layer | None = None,
        ) -> None:
            if kind in config.enabled_signal_types:
                observed.append(
                    evidence(
                        config,
                        iam.project.id,
                        projected.id,
                        kind,
                        value,
                        signal,
                        strength,
                        role,
                        layer,
                        node.source_location,
                    )
                )

        if role := name_role(node.name):
            add(Kind.NAME_PATTERN, node.name, "bounded-name-suffix", Strength.MODERATE, role)
        for part in sorted(set(path.split("/")[:-1])):
            if hint := PATH_SIGNALS.get(part.casefold()):
                add(Kind.PATH_PATTERN, part, "directory-segment", Strength.MODERATE, *hint)
        if config.framework_signals:
            signals = FRAMEWORK_SIGNALS.get(node.language, {})
            names = (
                self.symbol_attributes.get(node.symbol_id, {}).get("annotations")
                if node.symbol_id is not None
                else None
            )
            if isinstance(names, list):
                for name in sorted({value for value in names if isinstance(value, str)}):
                    simple = name.rsplit(".", 1)[-1]
                    if simple in signals:
                        role = signals[simple]
                        add(
                            Kind.ANNOTATION if node.language == Language.JAVA else Kind.DECORATOR,
                            simple,
                            "framework-name-hint",
                            Strength.STRONG if role else Strength.MODERATE,
                            role,
                            ROLE_LAYERS.get(role) if role else None,
                        )
        if config.graph_refinement:
            if metric:
                add(
                    Kind.GRAPH_POSITION,
                    f"Ca={metric.afferent_coupling};Ce={metric.efferent_coupling}",
                    "directed-coupling-support",
                    Strength.WEAK,
                )
            add(
                Kind.STRUCTURAL_SHAPE,
                f"members={projected.member_count};methods={projected.method_count}",
                "declaration-member-shape",
                Strength.WEAK,
            )
        by_role: dict[Role, list[DiscoveryEvidence]] = defaultdict(list)
        for item in observed:
            if item.role_hint is not None and item.role_hint != Role.UNKNOWN:
                by_role[item.role_hint].append(item)
        strengths = {}
        for role, items in by_role.items():
            strength = max((item.strength for item in items), key=STRENGTH_ORDER.__getitem__)
            if {Kind.NAME_PATTERN, Kind.PATH_PATTERN} <= {item.kind for item in items}:
                strength = Strength.STRONG
            strengths[role] = strength
        candidates = tuple(sorted(by_role))
        selected, strength = Role.UNKNOWN, Strength.WEAK
        conflicts: tuple[Role, ...] = ()
        explanation = "Insufficient specific structural evidence; UNKNOWN is a valid hypothesis"
        if strengths:
            highest = max(STRENGTH_ORDER[value] for value in strengths.values())
            winners = tuple(
                sorted(
                    role for role, value in strengths.items() if STRENGTH_ORDER[value] == highest
                )
            )
            if len(winners) > 1:
                strength, conflicts = Strength.AMBIGUOUS, candidates
                explanation = (
                    "Conflicting roles at equal evidence precedence; no first-match assignment"
                )
            elif highest >= STRENGTH_ORDER[config.minimum_role_strength]:
                selected = winners[0]
                strength = strengths[selected]
                conflicts = tuple(role for role in candidates if role != selected)
                explanation = (
                    "Specific framework hint or independent name/path agreement takes precedence"
                    if strength == Strength.STRONG
                    else "Structural role hypothesis from explicit matched signals"
                )
        return RoleHypothesis(
            id=uuid5(iam.project.id, f"discovery-role-v1:{config.fingerprint}:{projected.id}"),
            subject_id=projected.id,
            role=selected,
            strength=strength,
            candidate_roles=candidates,
            conflicting_roles=conflicts,
            evidence=tuple(
                sorted({item.id: item for item in observed}.values(), key=lambda item: str(item.id))
            ),
            explanation=explanation,
        )


def dependency_signals(
    iam: ArchitectureModel,
    graph: GraphAnalysisResult,
    config: ArchitectureDiscoveryConfig,
) -> dict[GraphNodeId, tuple[DiscoveryEvidence, ...]]:
    nodes = {node.id: node for node in iam.nodes}
    files = {file.id: file for file in iam.source_files}
    members = {member: node.id for node in graph.graph.nodes for member in node.iam_node_ids}
    found: dict[GraphNodeId, list[DiscoveryEvidence]] = defaultdict(list)
    for edge in graph.graph.edges:
        for proof in edge.proofs:
            if (
                proof.relation in {EdgeKind.INHERITS, EdgeKind.IMPLEMENTS}
                and Kind.INHERITANCE in config.enabled_signal_types
            ):
                target = nodes[proof.target_node_id]
                if role := name_role(target.name):
                    found[edge.source_id].append(
                        evidence(
                            config,
                            iam.project.id,
                            edge.source_id,
                            Kind.INHERITANCE,
                            target.qualified_name,
                            "resolved-base-name-hint",
                            Strength.MODERATE,
                            role,
                            location=proof.locations[0],
                            metadata={"iam_edge_id": str(proof.iam_edge_id)},
                        )
                    )
    if config.framework_signals and Kind.IMPORT_PATTERN in config.enabled_signal_types:
        for iam_edge in sorted(iam.edges, key=lambda item: str(item.id)):
            source, target = nodes[iam_edge.source_id], nodes[iam_edge.target_id]
            subject = members.get(source.id)
            if iam_edge.kind != EdgeKind.IMPORTS or subject is None or source.file_id not in files:
                continue
            namespace = target.attributes.get("namespace")
            imported_name = namespace if isinstance(namespace, str) else target.qualified_name
            for prefix, role in IMPORT_SIGNALS.items():
                if imported_name == prefix or imported_name.startswith(prefix + "."):
                    try:
                        proof = dependency_proof(
                            iam_edge, files[source.file_id].file_path, target.file_id is None
                        )
                    except ValueError:
                        continue
                    found[subject].append(
                        evidence(
                            config,
                            iam.project.id,
                            subject,
                            Kind.IMPORT_PATTERN,
                            prefix,
                            "framework-import-hint",
                            Strength.WEAK,
                            role,
                            ROLE_LAYERS.get(role) if role else None,
                            proof.locations[0],
                            {"iam_edge_id": str(iam_edge.id)},
                        )
                    )
    return {node: tuple(items) for node, items in found.items()}


class LayerInferenceEngine:
    def infer(
        self, role: RoleHypothesis, iam: ArchitectureModel, config: ArchitectureDiscoveryConfig
    ) -> LayerHypothesis:
        candidates: dict[Layer, list[Strength]] = defaultdict(list)
        if role.role in ROLE_LAYERS:
            candidates[ROLE_LAYERS[role.role]].append(role.strength)
        for item in role.evidence:
            if item.layer_hint is not None:
                candidates[item.layer_hint].append(item.strength)
        if role.strength == Strength.AMBIGUOUS:
            for candidate_role in role.candidate_roles:
                if candidate_role in ROLE_LAYERS:
                    candidates[ROLE_LAYERS[candidate_role]].append(Strength.MODERATE)
        label, strength = Layer.UNKNOWN, Strength.WEAK
        explanation = "Insufficient layer evidence; UNKNOWN is a valid hypothesis"
        if len(candidates) > 1:
            label, strength = Layer.AMBIGUOUS, Strength.AMBIGUOUS
            explanation = "Role/framework and path evidence suggest conflicting discovered layers"
        elif candidates:
            candidate = next(iter(candidates))
            value = max(candidates[candidate], key=STRENGTH_ORDER.__getitem__)
            if STRENGTH_ORDER[value] >= STRENGTH_ORDER[config.minimum_layer_strength]:
                label, strength = candidate, value
                explanation = (
                    "Discovered layer hypothesis from role and structural path/framework evidence"
                )
        return LayerHypothesis(
            id=uuid5(iam.project.id, f"discovery-layer-v1:{config.fingerprint}:{role.subject_id}"),
            subject_id=role.subject_id,
            label=label,
            strength=strength,
            candidate_layers=tuple(sorted(candidates)),
            role_hypothesis_id=role.id,
            evidence=role.evidence,
            explanation=explanation,
        )

    def refine(
        self,
        layers: dict[GraphNodeId, LayerHypothesis],
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        config: ArchitectureDiscoveryConfig,
    ) -> dict[GraphNodeId, LayerHypothesis]:
        if (
            not config.graph_refinement
            or Kind.DEPENDENCY_DIRECTION not in config.enabled_signal_types
        ):
            return layers
        support: dict[GraphNodeId, list[DiscoveryEvidence]] = defaultdict(list)
        for edge in graph.graph.edges:
            left, right = layers.get(edge.source_id), layers.get(edge.target_id)
            if (
                left is None
                or right is None
                or left.label in {Layer.UNKNOWN, Layer.AMBIGUOUS}
                or right.label in {Layer.UNKNOWN, Layer.AMBIGUOUS}
            ):
                continue
            for subject, hypothesis in ((edge.source_id, left), (edge.target_id, right)):
                support[subject].append(
                    evidence(
                        config,
                        iam.project.id,
                        subject,
                        Kind.DEPENDENCY_DIRECTION,
                        f"{left.label}->{right.label}",
                        f"observed-directed-edge:{edge.id}",
                        Strength.WEAK,
                        layer=hypothesis.label,
                        location=edge.proofs[0].locations[0],
                        metadata={"graph_edge_id": str(edge.id)},
                    )
                )
        return {
            subject: item.model_copy(
                update={
                    "evidence": tuple(
                        sorted((*item.evidence, *support[subject]), key=lambda entry: str(entry.id))
                    )
                }
            )
            for subject, item in layers.items()
        }
