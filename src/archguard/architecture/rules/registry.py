from collections.abc import Iterable

from archguard.architecture.rules.builtin import (
    ForbiddenDependencyRule,
    LayerDependencyRule,
    ModuleBoundaryRule,
    ReverseDependencyRule,
)
from archguard.architecture.rules.protocol import StaticArchitectureRule
from archguard.architecture.specification.errors import StaticRuleRegistrationError
from archguard.architecture.specification.models import RuleType


class StaticRuleRegistry:
    version = "1.0.0"

    def __init__(self, rules: Iterable[StaticArchitectureRule] = ()) -> None:
        self._rules: dict[RuleType, StaticArchitectureRule] = {}
        for rule in rules:
            self.register(rule)

    def register(self, rule: StaticArchitectureRule) -> None:
        if rule.rule_type in self._rules:
            raise StaticRuleRegistrationError("rule evaluator type is already registered")
        self._rules[rule.rule_type] = rule

    def get(self, rule_type: RuleType) -> StaticArchitectureRule:
        if rule_type not in self._rules:
            raise StaticRuleRegistrationError("no evaluator registered for rule type")
        return self._rules[rule_type]

    def supported_types(self) -> tuple[RuleType, ...]:
        return tuple(sorted(self._rules))


def create_static_rule_registry() -> StaticRuleRegistry:
    return StaticRuleRegistry(
        (
            ForbiddenDependencyRule(),
            LayerDependencyRule(),
            ReverseDependencyRule(),
            ModuleBoundaryRule(),
        )
    )
