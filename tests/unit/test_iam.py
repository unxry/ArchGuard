from uuid import UUID

import pytest
from pydantic import ValidationError

from archguard.core.identifiers import ProjectId, stable_edge_id, stable_node_id
from archguard.core.model.enums import EdgeKind
from archguard.iam.edges import ArchitectureEdge
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode


def test_iam_roundtrip_and_entity_links(synthetic_iam: ArchitectureModel) -> None:
    assert ArchitectureModel.model_validate_json(synthetic_iam.model_dump_json()) == synthetic_iam
    assert len(synthetic_iam.nodes) == 3
    assert synthetic_iam.edges[0].target_id == synthetic_iam.nodes[1].id
    assert synthetic_iam.symbols[0].file_id == synthetic_iam.source_files[0].id
    assert synthetic_iam.model_json_schema()["properties"]["iam_schema_version"]["const"] == "1.0"


def test_node_roundtrip_and_frozen_fields(synthetic_iam: ArchitectureModel) -> None:
    node = synthetic_iam.nodes[0]
    assert ArchitectureNode.model_validate_json(node.model_dump_json()) == node
    with pytest.raises(ValidationError, match="frozen"):
        node.name = "Changed"


@pytest.mark.parametrize("kind", list(EdgeKind))
def test_edge_relation_contract(kind: EdgeKind, synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.edges[0].model_dump(mode="json") | {"kind": kind}
    edge = ArchitectureEdge.model_validate(data)
    assert ArchitectureEdge.model_validate_json(edge.model_dump_json()).kind == kind


@pytest.mark.parametrize("field", ["id", "source_id", "target_id"])
@pytest.mark.parametrize("value", ["", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_invalid_edge_identifiers(field: str, value: str, synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.edges[0].model_dump(mode="json") | {field: value}
    with pytest.raises(ValidationError):
        ArchitectureEdge.model_validate(data)


@pytest.mark.parametrize("weight", [-1, float("nan"), float("inf"), True])
def test_invalid_edge_weights(weight: float, synthetic_iam: ArchitectureModel) -> None:
    with pytest.raises(ValidationError):
        ArchitectureEdge.model_validate(synthetic_iam.edges[0].model_dump() | {"weight": weight})


@pytest.mark.parametrize("name", ["", "  "])
def test_blank_node_names(name: str, synthetic_iam: ArchitectureModel) -> None:
    with pytest.raises(ValidationError):
        ArchitectureNode.model_validate(synthetic_iam.nodes[0].model_dump() | {"name": name})


@pytest.mark.parametrize(
    "collection", ["modules", "packages", "source_files", "symbols", "nodes", "edges"]
)
def test_duplicate_ids(collection: str, synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.model_dump(mode="json")
    data[collection].append(data[collection][0])
    with pytest.raises(ValidationError, match="unique"):
        ArchitectureModel.model_validate(data)


@pytest.mark.parametrize(
    ("collection", "field"),
    [
        ("modules", "project_id"),
        ("packages", "module_id"),
        ("source_files", "module_id"),
        ("source_files", "package_id"),
        ("symbols", "file_id"),
        ("nodes", "module"),
        ("nodes", "package"),
        ("nodes", "file_id"),
        ("nodes", "symbol_id"),
        ("edges", "source_id"),
        ("edges", "target_id"),
    ],
)
def test_unknown_entity_references(
    collection: str, field: str, synthetic_iam: ArchitectureModel
) -> None:
    data = synthetic_iam.model_dump(mode="json")
    data[collection][0][field] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    with pytest.raises(ValidationError):
        ArchitectureModel.model_validate(data)


@pytest.mark.parametrize("collection", ["symbols", "nodes"])
def test_inconsistent_source_location(collection: str, synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.model_dump(mode="json")
    data[collection][0]["source_location"]["file_path"] = "wrong.java"
    with pytest.raises(ValidationError, match="(location|linked source file)"):
        ArchitectureModel.model_validate(data)


def test_inconsistent_node_symbol_file(synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.model_dump(mode="json")
    data["nodes"][0]["file_id"] = data["source_files"][1]["id"]
    with pytest.raises(ValidationError, match="symbol/file"):
        ArchitectureModel.model_validate(data)


def test_inconsistent_node_language(synthetic_iam: ArchitectureModel) -> None:
    data = synthetic_iam.model_dump(mode="json")
    data["nodes"][0]["language"] = "TYPESCRIPT"
    with pytest.raises(ValidationError, match="linked source file"):
        ArchitectureModel.model_validate(data)


def test_version_and_unknown_fields_rejected(synthetic_iam: ArchitectureModel) -> None:
    for changes in [{"iam_schema_version": "2.0"}, {"uncontracted": True}]:
        with pytest.raises(ValidationError):
            ArchitectureModel.model_validate(synthetic_iam.model_dump() | changes)


def test_stable_ids_are_project_and_category_scoped(synthetic_iam: ArchitectureModel) -> None:
    project = synthetic_iam.project.id
    identity = "JAVA:src/Orders.java:sample.Orders#submit(String)"
    node = stable_node_id(project, identity)
    assert node == stable_node_id(project, identity)
    assert node != stable_node_id(project, identity + ":overload")
    assert node != stable_node_id(ProjectId(UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")), identity)
    assert node != stable_edge_id(project, identity)
    assert node.version == 5


@pytest.mark.parametrize("identity", ["", " ", "null\x00identity"])
def test_invalid_stable_identity(identity: str, synthetic_iam: ArchitectureModel) -> None:
    with pytest.raises(ValueError):
        stable_node_id(synthetic_iam.project.id, identity)


def test_stable_identity_rejects_nil_project() -> None:
    with pytest.raises(ValueError):
        stable_node_id(ProjectId(UUID(int=0)), "valid")
