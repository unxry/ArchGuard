from pathlib import Path
from uuid import uuid4

import pytest

from archguard.architecture.classification.classifier import path_matches
from archguard.architecture.classification.models import NodeClassification
from archguard.architecture.rules.builtin import LayerDependencyRule
from archguard.architecture.rules.registry import StaticRuleRegistry, create_static_rule_registry
from archguard.architecture.specification.errors import StaticRuleRegistrationError
from archguard.architecture.specification.models import ArchitectureSpecification, RuleType
from archguard.core.identifiers import NodeId, SourceFileId
from archguard.infrastructure.architecture_specification import load_architecture_file

SPEC = Path(__file__).parents[2] / "examples" / "architecture" / "layered-strict.yaml"


def classified(layer: str | None, module: str | None) -> NodeClassification:
    return NodeClassification(
        node_id=NodeId(uuid4()),
        file_id=SourceFileId(uuid4()),
        file_path="src/File.ts",
        layer=layer,
        module=module,
        layer_candidates=(layer,) if layer else (),
        module_candidates=(module,) if module else (),
    )


@pytest.mark.parametrize(
    "pattern,path,expected",
    [
        ("**/controller/**", "controller/A.java", True),
        ("**/controller/**", "src/shop/controller/A.java", True),
        ("controller/*.java", "controller/nested/A.java", False),
        ("controller/*.java", "Controller/A.java", False),
        ("**/*.ts", "A.ts", True),
        ("src/**/A.?s", "src/A.ts", True),
        ("src/**/A.?s", "src/one/two/A.js", True),
        ("src/[AB].ts", "src/B.ts", True),
        ("src/[AB].ts", "src/C.ts", False),
        ("src/**/api/**/A.*", "src/api/A.ts", True),
        ("src/**/api/**/A.*", "src/a/api/b/A.java", True),
        ("src/*/A.ts", "src/A.ts", False),
        ("src/**/A.ts", "other/A.ts", False),
    ],
)
def test_posix_glob_semantics(pattern: str, path: str, expected: bool) -> None:
    assert path_matches(path, pattern) is expected


@pytest.mark.parametrize(
    "rule_id,left,right,expected",
    [
        ("ARCH001", "domain", "infrastructure", True),
        ("ARCH001", "infrastructure", "domain", False),
        ("ARCH001", "domain", None, False),
        ("ARCH002", "presentation", "persistence", True),
        ("ARCH002", "presentation", "application", False),
        ("ARCH002", "application", "persistence", False),
        ("ARCH002", "presentation", "presentation", True),
        ("ARCH002", "presentation", None, False),
        ("ARCH004", "domain", "application", True),
        ("ARCH004", "application", "domain", False),
        ("ARCH004", "domain", "infrastructure", False),
        ("ARCH004", None, "application", False),
        ("ARCH005", "orders", "payments", True),
        ("ARCH005", "payments", "orders", False),
        ("ARCH005", "orders", "orders", False),
        ("ARCH005", "orders", None, False),
    ],
)
def test_four_explicit_rules(
    rule_id: str, left: str | None, right: str | None, expected: bool
) -> None:
    rule = next(item for item in load_architecture_file(SPEC).rules if item.id == rule_id)
    module = rule_id == "ARCH005"
    source = classified(None if module else left, left if module else None)
    target = classified(None if module else right, right if module else None)
    assert create_static_rule_registry().get(rule.type).violates(rule, source, target) is expected


@pytest.mark.parametrize(
    "rule_id,constraint,source,target,expected",
    [
        ("ARCH002", "deny", "presentation", "persistence", True),
        ("ARCH002", "deny", "presentation", "application", False),
        ("ARCH002", "allow", "presentation", "presentation", False),
        ("ARCH005", "allow", "orders", "payments", False),
        ("ARCH005", "allow", "orders", "shared", True),
        ("ARCH005", "deny", "orders", "orders", False),
    ],
)
def test_allow_deny_and_same_scope(
    rule_id: str, constraint: str, source: str, target: str, expected: bool
) -> None:
    data = load_architecture_file(SPEC).model_dump(mode="json", by_alias=True)
    rule = next(item for item in data["rules"] if item["id"] == rule_id)
    rule["allow"] = rule["deny"] = None
    rule[constraint] = ["persistence" if rule_id == "ARCH002" else "payments"]
    if rule_id == "ARCH002":
        rule["allow_same_layer"] = True
    else:
        data["architecture"]["modules"].append({"name": "shared", "include": ["shared/**"]})
    spec = ArchitectureSpecification.model_validate(data)
    parsed = next(item for item in spec.rules if item.id == rule_id)
    module = rule_id == "ARCH005"
    assert (
        create_static_rule_registry()
        .get(parsed.type)
        .violates(
            parsed,
            classified(None if module else source, source if module else None),
            classified(None if module else target, target if module else None),
        )
        is expected
    )


def test_registry_duplicate_missing_and_instance_isolation() -> None:
    registry = StaticRuleRegistry()
    registry.register(LayerDependencyRule())
    with pytest.raises(StaticRuleRegistrationError):
        registry.register(LayerDependencyRule())
    with pytest.raises(StaticRuleRegistrationError):
        StaticRuleRegistry().get(RuleType.LAYER)
    assert set(create_static_rule_registry().supported_types()) == set(RuleType)
