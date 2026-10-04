import copy
import json
from pathlib import Path

import pytest
import yaml

from archguard.architecture.specification.errors import (
    ArchitectureSpecificationError,
    ArchitectureSpecResourceLimitError,
    UnsupportedArchitectureRuleError,
    UnsupportedArchitectureSpecVersionError,
)
from archguard.architecture.specification.loader import (
    ArchitectureSpecLoader,
    ArchitectureSpecLoaderConfig,
)
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.infrastructure.architecture_specification import load_architecture_file

EXAMPLES = Path(__file__).parents[2] / "examples" / "architecture"


@pytest.mark.parametrize("name", ["layered-clean", "layered-strict", "modular"])
def test_examples_roundtrip_and_normalize(name: str) -> None:
    spec = load_architecture_file(EXAMPLES / f"{name}.yaml")
    assert ArchitectureSpecification.model_validate(spec) == spec
    assert ArchitectureSpecification.model_validate_json(spec.canonical_json()) == spec
    assert len(spec.fingerprint) == 64
    assert ArchitectureSpecLoader().load(spec.canonical_json()) == spec


def test_hash_ignores_mapping_scope_and_rule_order() -> None:
    original = load_architecture_file(EXAMPLES / "layered-strict.yaml")
    data = json.loads(original.canonical_json())
    data["rules"].reverse()
    data["architecture"]["layers"].reverse()
    data["architecture"]["modules"].reverse()
    data["architecture"]["layers"][0]["include"] *= 2
    equivalent = ArchitectureSpecLoader().load(
        "# comment\n" + yaml.safe_dump(data, sort_keys=False)
    )
    assert equivalent.fingerprint == original.fingerprint


@pytest.mark.parametrize(
    "case",
    [
        "missing_version",
        "unknown_field",
        "duplicate_layer",
        "duplicate_module",
        "duplicate_rule",
        "unknown_layer",
        "unknown_module",
        "sec_id",
        "bad_id",
        "severity",
        "empty_include",
        "both_constraints",
        "no_constraint",
        "empty_allow",
        "empty_relations",
        "future_relation",
        "wrong_enabled",
        "selector_dimensions",
        "same_reverse_layers",
        "bad_name",
        "disabled_unknown_reference",
        "noncanonical_alias",
    ],
)
def test_schema_rejects_invalid_configuration(case: str) -> None:
    data = json.loads(load_architecture_file(EXAMPLES / "layered-strict.yaml").canonical_json())
    architecture, rules = data["architecture"], data["rules"]
    if case == "missing_version":
        del data["version"]
    elif case == "unknown_field":
        data["priority"] = 1
    elif case.startswith("duplicate_"):
        items = (
            rules
            if case == "duplicate_rule"
            else architecture[case.removeprefix("duplicate_") + "s"]
        )
        items.append(copy.deepcopy(items[0]))
    elif case in {"unknown_layer", "disabled_unknown_reference"}:
        rules[0]["from"] = {"layer": "unknown"}
        rules[0]["enabled"] = case != "disabled_unknown_reference"
    elif case == "unknown_module":
        rules[3]["from"] = "unknown"
    elif case in {"sec_id", "bad_id"}:
        rules[0]["id"] = "SEC001" if case == "sec_id" else "ARCH002"
    elif case == "severity":
        rules[0]["severity"] = "urgent"
    elif case == "empty_include":
        architecture["layers"][0]["include"] = []
    elif case == "both_constraints":
        rules[1]["deny"] = ["persistence"]
    elif case == "no_constraint":
        rules[1]["allow"] = None
    elif case == "empty_allow":
        rules[1]["allow"] = []
    elif case == "empty_relations":
        rules[0]["relations"] = []
    elif case == "future_relation":
        rules[0]["relations"] = ["READS"]
    elif case == "wrong_enabled":
        rules[0]["enabled"] = "false"
    elif case == "selector_dimensions":
        rules[0]["from"]["module"] = "orders"
    elif case == "same_reverse_layers":
        rules[2]["expected"] = {"from": "domain", "to": "domain"}
    elif case == "bad_name":
        architecture["layers"][0]["name"] = "bad name"
    elif case == "noncanonical_alias":
        rules[1]["source"] = rules[1].pop("from")
    with pytest.raises(ArchitectureSpecificationError):
        ArchitectureSpecLoader().load(json.dumps(data))


@pytest.mark.parametrize(
    "pattern",
    [
        "/src/**",
        "../**",
        "src/../**",
        "C:/src/**",
        "src\\**",
        "src//**",
        "src/a**",
        "./**",
        "a\x00b",
        "x" * 513,
    ],
)
def test_selector_rejects_noncanonical_paths(pattern: str) -> None:
    with pytest.raises(ArchitectureSpecificationError):
        ArchitectureSpecLoader().load(
            json.dumps(
                {
                    "version": "1.0",
                    "architecture": {"layers": [{"name": "app", "include": [pattern]}]},
                }
            )
        )


@pytest.mark.parametrize(
    "source",
    [
        "",
        "[",
        "- root",
        "version: '1.0'\nversion: '1.0'",
        "1: value",
        "version: '1.0'\narchitecture: &a {}",
        "architecture: *missing",
        "architecture: {<<: {layers: []}}",
        "architecture: 2026-10-04",
        "architecture: !!str {}",
        "architecture: !!str []",
        "version: .nan",
        b"\xff",
        "\ud800",
    ],
)
def test_loader_rejects_malformed_or_unsafe_yaml(source: str | bytes) -> None:
    with pytest.raises(ArchitectureSpecificationError):
        ArchitectureSpecLoader().load(source)


def test_yaml_constructor_never_executes(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    attack = f"!!python/object/apply:os.system ['touch {marker}']"
    with pytest.raises(ArchitectureSpecificationError) as caught:
        ArchitectureSpecLoader().load(attack)
    assert not marker.exists()
    assert str(marker) not in str(caught.value)
    assert "os.system" not in str(caught.value)


@pytest.mark.parametrize(
    "config,source",
    [
        (ArchitectureSpecLoaderConfig(max_bytes=8), "123456789"),
        (ArchitectureSpecLoaderConfig(max_depth=2), "a: [[[1]]]"),
        (ArchitectureSpecLoaderConfig(max_nodes=4), "a: [1, 2, 3, 4]"),
    ],
)
def test_loader_resource_limits(config: ArchitectureSpecLoaderConfig, source: str) -> None:
    with pytest.raises(ArchitectureSpecResourceLimitError):
        ArchitectureSpecLoader(config).load(source)


def test_version_and_graph_rule_have_typed_errors() -> None:
    with pytest.raises(UnsupportedArchitectureSpecVersionError):
        ArchitectureSpecLoader().load('version: "2.0"\narchitecture: {}')
    with pytest.raises(UnsupportedArchitectureRuleError):
        ArchitectureSpecLoader().load(
            'version: "1.0"\narchitecture: {}\nrules: [{id: ARCH003, type: circular_dependency}]'
        )


def test_file_read_is_bounded_and_errors_hide_paths(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_bytes(b" " * 100)
    with pytest.raises(ArchitectureSpecResourceLimitError):
        load_architecture_file(
            path, ArchitectureSpecLoader(ArchitectureSpecLoaderConfig(max_bytes=8))
        )
    with pytest.raises(ArchitectureSpecificationError) as caught:
        load_architecture_file(tmp_path / "absent")
    assert str(tmp_path) not in str(caught.value)


def test_syntax_error_has_safe_coordinates() -> None:
    with pytest.raises(ArchitectureSpecificationError) as caught:
        ArchitectureSpecLoader().load("version: [PRIVATE_MARKER")
    assert caught.value.line and caught.value.column
    assert "PRIVATE_MARKER" not in str(caught.value)
