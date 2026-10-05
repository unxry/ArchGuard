from collections import Counter, defaultdict
from uuid import UUID, uuid5

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.discovery.enums import STRENGTH_ORDER
from archguard.architecture.discovery.enums import DiscoveryEvidenceKind as Kind
from archguard.architecture.discovery.enums import DiscoveryStrength as Strength
from archguard.architecture.discovery.models import DiscoveredComponent, ModuleCandidate
from archguard.architecture.discovery.signals import evidence
from archguard.architecture.graph.models import GraphDiagnostic, GraphNodeId
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.core.model.enums import Language
from archguard.iam.model import ArchitectureModel

TECHNICAL_SEGMENTS = {
    "src",
    "main",
    "java",
    "com",
    "org",
    "example",
    "controller",
    "controllers",
    "service",
    "services",
    "repository",
    "repositories",
    "domain",
    "application",
    "infrastructure",
    "infra",
    "adapter",
    "adapters",
    "presentation",
    "persistence",
}
SHARED_SEGMENTS = {"shared", "common", "utils", "util"}


def common_prefix(paths: list[tuple[str, ...]]) -> tuple[str, ...]:
    if not paths:
        return ()
    result = []
    for parts in zip(*paths, strict=False):
        if len(set(parts)) != 1:
            break
        result.append(parts[0])
    return tuple(result)


class ModuleDiscovery:
    def discover(
        self,
        components: tuple[DiscoveredComponent, ...],
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        config: ArchitectureDiscoveryConfig,
    ) -> tuple[tuple[ModuleCandidate, ...], dict[GraphNodeId, UUID], tuple[GraphDiagnostic, ...]]:
        if Kind.MODULE_PATH not in config.enabled_signal_types:
            return (), {}, ()
        packages = {package.id: package.qualified_name for package in iam.packages}
        file_packages = {
            file.file_path: packages[file.package_id] if file.package_id is not None else ""
            for file in iam.source_files
        }
        java_parts = [
            tuple(file_packages[c.file_path].split("."))
            for c in components
            if c.language == Language.JAVA and file_packages[c.file_path]
        ]
        java_root = (
            tuple(config.java_common_prefix.split("."))
            if config.java_common_prefix
            else common_prefix(java_parts)[: max(0, config.java_min_package_depth - 1)]
        )
        es_paths = [
            tuple(c.file_path.split("/")[:-1])
            for c in components
            if c.language in {Language.TYPESCRIPT, Language.JAVASCRIPT}
        ]
        automatic_root = common_prefix(es_paths)
        groups: dict[tuple[str, str], list[DiscoveredComponent]] = defaultdict(list)
        clear_roots: dict[tuple[str, str], bool] = {}
        diagnostics = []
        for component in components:
            clear = True
            if component.language == Language.JAVA:
                parts = tuple(file_packages[component.file_path].split("."))
                index = max(len(java_root), config.java_min_package_depth - 1)
                if not java_root or parts[: len(java_root)] != java_root or len(parts) <= index:
                    continue
                branch = parts[index]
                namespace = ".".join(parts[: index + 1])
                kind = "java_package"
            elif component.language in {Language.TYPESCRIPT, Language.JAVASCRIPT}:
                parts = tuple(component.file_path.split("/")[:-1])
                roots = [
                    tuple(hint.split("/"))
                    for hint in config.module_root_hints
                    if parts[: len(hint.split("/"))] == tuple(hint.split("/"))
                ]
                if not roots:
                    roots = [
                        parts[: index + 1]
                        for index, part in enumerate(parts[: config.max_module_depth])
                        if part == "src"
                    ]
                if len(roots) > 1:
                    diagnostics.append(
                        GraphDiagnostic(
                            code="AMBIGUOUS_MODULE_ROOT",
                            message=(
                                "multiple structural roots match; component remains unassigned"
                            ),
                            subject_id=component.id,
                        )
                    )
                    continue
                root = roots[0] if roots else automatic_root
                clear = bool(roots)
                if len(root) > config.max_module_depth or len(parts) <= len(root):
                    continue
                branch = parts[len(root)]
                namespace = "/".join((*root, branch))
                kind = "source_directory"
            else:
                continue
            if branch.casefold() in TECHNICAL_SEGMENTS:
                continue
            key = kind, namespace
            groups[key].append(component)
            clear_roots[key] = clear_roots.get(key, True) and clear
        subjects = {item.id: key for key, group in groups.items() for item in group}
        internal: Counter[tuple[str, str]] = Counter()
        incoming: Counter[tuple[str, str]] = Counter()
        outgoing: Counter[tuple[str, str]] = Counter()
        ids = {
            key: uuid5(
                iam.project.id,
                f"discovery-module-v1:{config.fingerprint}:{key}:"
                + ",".join(sorted(str(c.id) for c in group)),
            )
            for key, group in groups.items()
        }
        incoming_modules: dict[tuple[str, str], set[UUID]] = defaultdict(set)
        outgoing_modules: dict[tuple[str, str], set[UUID]] = defaultdict(set)
        for edge in graph.graph.edges:
            left, right = subjects.get(edge.source_id), subjects.get(edge.target_id)
            if left is not None and left == right:
                internal[left] += 1
            else:
                if left is not None:
                    outgoing[left] += 1
                    if right is not None:
                        outgoing_modules[left].add(ids[right])
                if right is not None:
                    incoming[right] += 1
                    if left is not None:
                        incoming_modules[right].add(ids[left])
        candidates = []
        assigned = {}
        for key in sorted(groups):
            kind, namespace = key
            group = sorted(groups[key], key=lambda c: str(c.id))
            enough = len(group) >= config.min_module_components
            strength = (
                Strength.STRONG
                if enough and clear_roots[key] and internal[key] > incoming[key] + outgoing[key]
                else Strength.MODERATE
                if enough and clear_roots[key]
                else Strength.WEAK
            )
            total = internal[key] + incoming[key] + outgoing[key]
            candidate = ModuleCandidate(
                id=ids[key],
                structural_name=namespace.rsplit("." if kind == "java_package" else "/", 1)[-1],
                seed_kind="java_package" if kind == "java_package" else "source_directory",
                namespace=namespace,
                members=tuple(c.id for c in group),
                strength=strength,
                shared_support=namespace.rsplit("." if kind == "java_package" else "/", 1)[
                    -1
                ].casefold()
                in SHARED_SEGMENTS,
                evidence=tuple(
                    sorted(
                        (
                            evidence(
                                config,
                                iam.project.id,
                                c.id,
                                Kind.MODULE_PATH,
                                namespace,
                                kind,
                                Strength.MODERATE if clear_roots[key] else Strength.WEAK,
                                location=c.location,
                                metadata={
                                    "candidate_member_count": len(group),
                                    "minimum_components": config.min_module_components,
                                },
                            )
                            for c in group
                        ),
                        key=lambda item: str(item.id),
                    )
                ),
                internal_component_count=len(group),
                internal_dependency_edges=internal[key],
                incoming_cross_module_edges=incoming[key],
                outgoing_cross_module_edges=outgoing[key],
                cohesion_ratio=internal[key] / total if total else None,
                incoming_module_ids=tuple(sorted(incoming_modules[key], key=str)),
                outgoing_module_ids=tuple(sorted(outgoing_modules[key], key=str)),
            )
            candidates.append(candidate)
            if (
                enough
                and STRENGTH_ORDER[strength] >= STRENGTH_ORDER[config.minimum_module_strength]
            ):
                assigned.update({c.id: candidate.id for c in group})
        return (
            tuple(sorted(candidates, key=lambda item: str(item.id))),
            assigned,
            tuple(sorted(diagnostics, key=lambda item: str(item.subject_id))),
        )
