import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from archguard.application.build_iam import BuildIAM
from archguard.application.discover_architecture import DiscoverArchitecture
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.discovery.analyzer import (
    ArchitectureDiscoveryAnalyzer,
    serialize_discovery,
)
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
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
from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam.model import ArchitectureModel
from archguard.iam_building.serialization import serialize_iam
from archguard.infrastructure.graph_configuration import load_graph_configuration
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/discovery"


def building() -> BuildIAM:
    return BuildIAM(
        ParseRepository(create_parser_registry()),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace="discovery-tests"),
    )


def build(path: Path) -> ArchitectureModel:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    ) as repository:
        return building().execute(repository.snapshot, repository.workspace).iam


def analyze(
    iam: ArchitectureModel, config: ArchitectureDiscoveryConfig | None = None
) -> ArchitectureDiscoveryResult:
    config = config if config is not None else ArchitectureDiscoveryConfig()
    return ArchitectureDiscoveryAnalyzer().analyze(
        iam, GraphAnalyzer().analyze(iam, config.graph), config
    )


@pytest.fixture(scope="module")
def mixed() -> ArchitectureModel:
    return build(FIXTURES / "mixed")


@pytest.mark.parametrize(
    "fixture,components,known",
    [("java-layered", 6, 6), ("typescript-layered", 6, 5), ("mixed", 12, 11)],
)
def test_real_language_neutral_pipeline(fixture: str, components: int, known: int) -> None:
    result = analyze(build(FIXTURES / fixture))
    assert result.is_valid and result.is_complete
    assert result.statistics.components_total == components
    assert result.statistics.role_coverage == known / components
    assert result.statistics.layer_coverage == known / components
    assert not result.graph.findings and result.graph.conformance is None
    assert result.statistics.module_assigned_components == known
    assert result.reproducibility.upstream_versions["builder_version"] == "1.0.0"
    for component in result.discovered.components:
        if component.name == "Widget":
            assert component.role.role == Role.UNKNOWN and component.layer.label == Layer.UNKNOWN
        assert component.role.subject_id == component.layer.subject_id == component.id


def test_exact_mixed_counts_matrices_and_no_cross_language_inference(
    mixed: ArchitectureModel,
) -> None:
    result = analyze(mixed)
    stats = result.statistics
    assert stats.role_strength_counts == {"STRONG": 11, "WEAK": 1}
    assert stats.layer_counts == {
        "PRESENTATION": 2,
        "APPLICATION": 2,
        "DOMAIN": 1,
        "PERSISTENCE": 2,
        "INFRASTRUCTURE": 4,
        "UNKNOWN": 1,
    }
    assert (
        stats.module_candidates == 5
        and stats.module_assigned_components == 11
        and stats.module_unassigned_components == 1
    )
    cells = {
        (cell.source, cell.target): cell.unique_projected_edges
        for cell in result.discovered.layer_dependency_matrix.cells
    }
    assert cells == {
        ("PRESENTATION", "APPLICATION"): 2,
        ("APPLICATION", "PERSISTENCE"): 2,
        ("INFRASTRUCTURE", "INFRASTRUCTURE"): 2,
    }
    components = {c.id: c for c in result.discovered.components}
    assert all(
        components[e.source_id].language == components[e.target_id].language
        for e in result.graph.graph.edges
    )
    raw = serialize_discovery(result)
    assert "PRIVATE_DECORATOR_ARGUMENT" not in raw and "PRIVATE_JSX_CONTENT" not in raw
    assert str(ROOT) not in raw and '"confidence": 0.' not in raw
    assert serialize_discovery(ArchitectureDiscoveryResult.model_validate_json(raw)) == raw


@pytest.mark.parametrize(
    "suffix,annotation,kind,expected",
    [
        ("java", "RestController", Kind.ANNOTATION, Role.CONTROLLER),
        ("java", "Service", Kind.ANNOTATION, Role.SERVICE),
        ("java", "Repository", Kind.ANNOTATION, Role.REPOSITORY),
        ("java", "Configuration", Kind.ANNOTATION, Role.CONFIGURATION),
        ("java", "Entity", Kind.ANNOTATION, Role.DOMAIN_MODEL),
        ("java", "Component", Kind.ANNOTATION, Role.UNKNOWN),
        ("ts", "Controller", Kind.DECORATOR, Role.CONTROLLER),
        ("ts", "Injectable", Kind.DECORATOR, Role.UNKNOWN),
    ],
)
def test_framework_names_without_arguments_and_generic_hints_are_conservative(
    tmp_path: Path, suffix: str, annotation: str, kind: Kind, expected: Role
) -> None:
    source = (
        f'@{annotation}("PRIVATE_ARGUMENT") '
        + ("public" if suffix == "java" else "export")
        + " class Thing {}"
    )
    (tmp_path / ("Thing." + suffix)).write_text(source)
    iam = build(tmp_path)
    result = analyze(iam)
    (component,) = result.discovered.components
    assert component.role.role == expected
    assert any(
        item.kind == kind and item.observed_value == annotation for item in component.role.evidence
    )
    assert component.role.strength == (
        Strength.STRONG if expected != Role.UNKNOWN else Strength.WEAK
    )
    assert "PRIVATE_ARGUMENT" not in serialize_discovery(result)
    disabled = analyze(iam, ArchitectureDiscoveryConfig(framework_signals=False))
    assert disabled.discovered.components[0].role.role == Role.UNKNOWN
    assert not any(item.kind == kind for item in disabled.discovered.components[0].role.evidence)


def test_layer_conflict_preserves_strong_role_and_excludes_ambiguous_coverage() -> None:
    result = analyze(build(FIXTURES / "conflict"))
    (component,) = result.discovered.components
    assert component.role.role == Role.CONTROLLER and component.role.strength == Strength.STRONG
    assert (
        component.layer.label == Layer.AMBIGUOUS and component.layer.strength == Strength.AMBIGUOUS
    )
    assert component.layer.candidate_layers == (Layer.DOMAIN, Layer.PRESENTATION)
    assert result.statistics.role_coverage == 1 and result.statistics.layer_coverage == 0
    assert result.statistics.layer_ambiguous == 1 and result.discovered.ambiguous_components == (
        component.id,
    )


def test_equal_role_precedence_is_ambiguous(tmp_path: Path) -> None:
    (tmp_path / "Thing.java").write_text("@RestController @Repository public class Thing {}")
    result = analyze(build(tmp_path))
    (component,) = result.discovered.components
    assert component.role.strength == Strength.AMBIGUOUS and component.role.role == Role.UNKNOWN
    assert component.role.candidate_roles == (Role.CONTROLLER, Role.REPOSITORY)
    assert component.layer.label == Layer.AMBIGUOUS
    assert result.statistics.role_ambiguous == 1 and result.statistics.role_unknown == 0
    assert result.statistics.role_coverage == result.statistics.layer_coverage == 0


def test_unknown_graph_cycle_is_observation_not_role_or_violation() -> None:
    result = analyze(build(FIXTURES / "unknown"))
    assert result.statistics.role_unknown == result.statistics.layer_unknown == 3
    assert result.statistics.role_coverage == result.statistics.layer_coverage == 0
    assert all(c.role.strength == Strength.WEAK for c in result.discovered.components)
    assert len(result.discovered.topology.cyclic_sccs) == 1 and not result.graph.findings
    assert not result.discovered.module_candidates


def test_exact_seven_of_ten_coverage_and_role_layer_distinction(tmp_path: Path) -> None:
    for name in (
        "UserController",
        "OrderService",
        "PaymentRepository",
        "DomainEntity",
        "StripeAdapter",
        "ExternalClient",
        "AppConfig",
        "Foo",
        "Bar",
        "Baz",
    ):
        (tmp_path / (name + ".ts")).write_text(f"export class {name} {{}}")
    result = analyze(build(tmp_path))
    assert result.statistics.role_coverage == result.statistics.layer_coverage == 0.7
    assert result.statistics.role_strength_counts == {"MODERATE": 7, "WEAK": 3}
    by_name = {c.name: c for c in result.discovered.components}
    assert (
        by_name["AppConfig"].role.role == Role.CONFIGURATION
        and by_name["AppConfig"].layer.label == Layer.INFRASTRUCTURE
    )


def test_module_feature_cohesion_shared_weak_and_matrices() -> None:
    result = analyze(build(FIXTURES / "features"))
    modules = {m.structural_name: m for m in result.discovered.module_candidates}
    orders, shared = modules["orders"], modules["shared"]
    assert (
        orders.internal_dependency_edges,
        orders.incoming_cross_module_edges,
        orders.outgoing_cross_module_edges,
    ) == (2, 0, 1)
    assert orders.cohesion_ratio == 2 / 3 and orders.strength == Strength.STRONG
    assert (
        shared.internal_dependency_edges,
        shared.incoming_cross_module_edges,
        shared.outgoing_cross_module_edges,
    ) == (1, 1, 0)
    assert shared.cohesion_ratio == 0.5 and shared.shared_support
    assert modules["ui"].strength == Strength.WEAK and modules["ui"].cohesion_ratio is None
    assert orders.outgoing_module_ids == (shared.id,) and shared.incoming_module_ids == (orders.id,)
    cells = {(c.source, c.target): c for c in result.discovered.module_dependency_matrix.cells}
    assert cells[str(orders.id), str(orders.id)].internal
    assert cells[str(orders.id), str(shared.id)].unique_projected_edges == 1
    assert not cells[str(orders.id), str(shared.id)].internal


def test_java_common_prefix_and_configurable_size_and_roots() -> None:
    iam = build(FIXTURES / "java-layered")
    result = analyze(iam)
    assert {m.namespace for m in result.discovered.module_candidates} == {
        "com.example.orders",
        "com.example.payments",
    }
    oversized = analyze(iam, ArchitectureDiscoveryConfig(min_module_components=4))
    assert oversized.statistics.module_assigned_components == 0
    assert all(m.strength == Strength.WEAK for m in oversized.discovered.module_candidates)
    explicit = analyze(iam, ArchitectureDiscoveryConfig(java_common_prefix="com.example"))
    assert {m.namespace for m in explicit.discovered.module_candidates} == {
        m.namespace for m in result.discovered.module_candidates
    }
    overlap = analyze(
        build(FIXTURES / "typescript-layered"),
        ArchitectureDiscoveryConfig(module_root_hints=("src", "src/orders")),
    )
    assert any(d.code == "AMBIGUOUS_MODULE_ROOT" for d in overlap.diagnostics)
    assert overlap.statistics.module_unassigned_components >= 4


def test_signals_can_be_disabled_and_graph_support_never_forces_roles(
    mixed: ArchitectureModel,
) -> None:
    result = analyze(
        mixed,
        ArchitectureDiscoveryConfig(
            enabled_signal_types=(), framework_signals=False, graph_refinement=False
        ),
    )
    assert result.statistics.role_unknown == result.statistics.layer_unknown == 12
    assert not result.statistics.evidence_count_by_type and not result.discovered.module_candidates
    supporting = analyze(mixed, ArchitectureDiscoveryConfig(graph_refinement=False))
    assert Kind.GRAPH_POSITION not in supporting.statistics.evidence_count_by_type
    assert Kind.DEPENDENCY_DIRECTION not in supporting.statistics.evidence_count_by_type
    assert supporting.statistics.role_coverage == 11 / 12


def test_uncertain_roots_stay_weak_and_minimum_strengths_are_explicit(tmp_path: Path) -> None:
    for feature in ("orders", "payments"):
        folder = tmp_path / feature
        folder.mkdir()
        for name in ("Foo", "Bar"):
            (folder / (name + ".ts")).write_text(f"export class {name} {{}}")
    iam = build(tmp_path)
    baseline = analyze(iam)
    assert baseline.statistics.module_candidates == 2
    assert all(m.strength == Strength.WEAK for m in baseline.discovered.module_candidates)
    assert baseline.statistics.module_assigned_components == 0
    accepted = analyze(iam, ArchitectureDiscoveryConfig(minimum_module_strength=Strength.WEAK))
    assert accepted.statistics.module_assigned_components == 4
    assert accepted.statistics.role_coverage == 0


def test_minimum_role_and_layer_strength_prevents_overassignment(tmp_path: Path) -> None:
    (tmp_path / "OrderService.ts").write_text("export class OrderService {}")
    iam = build(tmp_path)
    result = analyze(iam, ArchitectureDiscoveryConfig(minimum_role_strength=Strength.STRONG))
    assert result.statistics.role_unknown == result.statistics.layer_unknown == 1
    assert result.discovered.components[0].role.candidate_roles == (Role.SERVICE,)
    layer_only = analyze(iam, ArchitectureDiscoveryConfig(minimum_layer_strength=Strength.STRONG))
    assert layer_only.statistics.role_coverage == 1 and layer_only.statistics.layer_coverage == 0


def test_inheritance_and_import_patterns_are_grounded(tmp_path: Path) -> None:
    (tmp_path / "BaseController.java").write_text("public class BaseController {}")
    (tmp_path / "Thing.java").write_text(
        "import org.springframework.web.bind.annotation.RestController; "
        "public class Thing extends BaseController {}"
    )
    iam = build(tmp_path)
    result = analyze(iam)
    thing = next(c for c in result.discovered.components if c.name == "Thing")
    assert thing.role.role == Role.CONTROLLER and thing.role.strength == Strength.MODERATE
    assert {Kind.INHERITANCE, Kind.IMPORT_PATTERN} <= {e.kind for e in thing.role.evidence}
    edge_ids = {str(edge.id) for edge in iam.edges}
    assert all(
        e.metadata["iam_edge_id"] in edge_ids
        for e in thing.role.evidence
        if e.kind in {Kind.INHERITANCE, Kind.IMPORT_PATTERN}
    )


def test_single_iam_and_graph_execution() -> None:
    engine, graph = building(), GraphAnalyzer()
    with (
        create_discovery().open(
            RepositoryInput(
                source_type=RepositorySourceType.LOCAL, location=str(FIXTURES / "mixed")
            )
        ) as repository,
        patch.object(engine, "execute", wraps=engine.execute) as build_call,
        patch.object(graph, "analyze", wraps=graph.analyze) as graph_call,
    ):
        result = DiscoverArchitecture(engine, graph).execute(
            repository.snapshot, repository.workspace
        )
        assert build_call.call_count == graph_call.call_count == 1
    assert result.statistics.components_total == 12


def test_deterministic_order_root_and_no_input_mutation(
    mixed: ArchitectureModel, tmp_path: Path
) -> None:
    before = serialize_iam(mixed)
    expected = serialize_discovery(analyze(mixed))
    assert serialize_iam(mixed) == before
    reordered = mixed.model_copy(
        update={
            "nodes": tuple(reversed(mixed.nodes)),
            "edges": tuple(reversed(mixed.edges)),
            "symbols": tuple(reversed(mixed.symbols)),
            "source_files": tuple(reversed(mixed.source_files)),
        }
    )
    assert serialize_discovery(analyze(reordered)) == expected
    copy = tmp_path / "copy"
    shutil.copytree(FIXTURES / "mixed", copy)
    assert serialize_discovery(analyze(build(copy))) == expected
    path = copy / "typescript/src/orders/controllers/UserController.ts"
    path.write_text("\n" + path.read_text())
    changed = analyze(build(copy))
    assert {c.role.id for c in changed.discovered.components} == {
        c.role.id for c in analyze(mixed).discovered.components
    }
    assert changed.reproducibility.snapshot_fingerprint != mixed.metadata["snapshot_fingerprint"]


def test_graph_candidate_refs_not_promoted_and_target_input_rejected() -> None:
    iam = build(ROOT / "tests/fixtures/graph/hub")
    config = ArchitectureDiscoveryConfig(
        graph=load_graph_configuration(ROOT / "examples/graph/research-demo.json")
    )
    result = analyze(iam, config)
    assert len(result.discovered.topology.graph_candidate_ids) == 7 and not result.graph.findings
    assert all(c.role.role == Role.UNKNOWN for c in result.discovered.components)
    spec = ArchitectureSpecification.model_validate({"version": "1.0", "architecture": {}})
    with pytest.raises(ValueError, match="target conformance"):
        ArchitectureDiscoveryAnalyzer().analyze(iam, GraphAnalyzer().analyze(iam, spec=spec))
    with pytest.raises(ValueError, match="same IAM"):
        ArchitectureDiscoveryAnalyzer().analyze(
            iam, GraphAnalyzer().analyze(iam, GraphAnalysisConfig(calculate_pagerank=False))
        )


def test_invalid_incomplete_empty_and_public_contracts(
    mixed: ArchitectureModel, tmp_path: Path
) -> None:
    empty = analyze(build(tmp_path))
    assert empty.statistics.components_total == 0 and empty.statistics.role_coverage is None
    partial = mixed.model_copy(deep=True)
    partial.metadata["is_complete"] = False
    result = analyze(partial)
    assert result.is_valid and not result.is_complete and result.status == "INCOMPLETE"
    partial.metadata["is_valid"] = False
    invalid = analyze(partial)
    assert invalid.status == "INVALID" and not invalid.discovered.components
    raw = result.model_dump(mode="json")
    raw["statistics"]["components_total"] = 999
    with pytest.raises(ValidationError):
        ArchitectureDiscoveryResult.model_validate(raw)
