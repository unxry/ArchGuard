from archguard.architecture.classification.models import NodeClassification
from archguard.architecture.specification.models import (
    ForbiddenDependencySpecification,
    LayerDependencySpecification,
    ModuleBoundarySpecification,
    ReverseDependencySpecification,
    RuleSpecification,
    RuleType,
    TargetSelector,
)


def _matches(selector: TargetSelector, node: NodeClassification) -> bool:
    return (
        node.layer == selector.layer
        if selector.layer is not None
        else node.module == selector.module
    )


class ForbiddenDependencyRule:
    rule_type = RuleType.FORBIDDEN

    def violates(
        self, rule: RuleSpecification, source: NodeClassification, target: NodeClassification
    ) -> bool:
        return (
            isinstance(rule, ForbiddenDependencySpecification)
            and _matches(rule.source, source)
            and _matches(rule.target, target)
        )


class LayerDependencyRule:
    rule_type = RuleType.LAYER

    def violates(
        self, rule: RuleSpecification, source: NodeClassification, target: NodeClassification
    ) -> bool:
        if (
            not isinstance(rule, LayerDependencySpecification)
            or source.layer != rule.source
            or target.layer is None
        ):
            return False
        if source.layer == target.layer:
            return not rule.allow_same_layer
        return (
            target.layer not in rule.allow
            if rule.allow is not None
            else target.layer in (rule.deny or ())
        )


class ReverseDependencyRule:
    rule_type = RuleType.REVERSE

    def violates(
        self, rule: RuleSpecification, source: NodeClassification, target: NodeClassification
    ) -> bool:
        return (
            isinstance(rule, ReverseDependencySpecification)
            and source.layer == rule.expected.target
            and target.layer == rule.expected.source
        )


class ModuleBoundaryRule:
    rule_type = RuleType.MODULE

    def violates(
        self, rule: RuleSpecification, source: NodeClassification, target: NodeClassification
    ) -> bool:
        if (
            not isinstance(rule, ModuleBoundarySpecification)
            or source.module != rule.source
            or target.module is None
            or source.module == target.module
        ):
            return False
        return (
            target.module not in rule.allow
            if rule.allow is not None
            else target.module in (rule.deny or ())
        )
