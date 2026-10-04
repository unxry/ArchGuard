from typing import Protocol

from archguard.architecture.classification.models import NodeClassification
from archguard.architecture.specification.models import RuleSpecification, RuleType


class StaticArchitectureRule(Protocol):
    rule_type: RuleType

    def violates(
        self, rule: RuleSpecification, source: NodeClassification, target: NodeClassification
    ) -> bool: ...
