"""Source/sink/sanitizer contracts only: no text scanner or taint solver."""

from collections.abc import Iterable
from enum import StrEnum

from pydantic import Field

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString
from archguard.security.domain import SecurityLanguage, SecurityRuleId

API_REGISTRY_VERSION = "security-api-registry-v1"
DATAFLOW_VERSION = "security-dataflow-contract-v1"


class SecurityAPIRole(StrEnum):
    SOURCE = "SOURCE"
    SINK = "SINK"
    SANITIZER = "SANITIZER"
    SECURITY_SENSITIVE_API = "SECURITY_SENSITIVE_API"


class SecurityAPIContract(DomainModel):
    id: NonEmptyString
    language: SecurityLanguage
    qualified_api: NonEmptyString
    role: SecurityAPIRole
    rule_ids: tuple[SecurityRuleId, ...] = Field(min_length=1)
    conditions: tuple[NonEmptyString, ...] = Field(min_length=1)
    limitations: tuple[NonEmptyString, ...] = Field(min_length=1)
    engineering_test_binding: NonEmptyString


class SecurityAPIRegistry:
    version = API_REGISTRY_VERSION

    def __init__(self, entries: Iterable[SecurityAPIContract] = ()) -> None:
        self._entries: dict[str, SecurityAPIContract] = {}
        for entry in entries:
            entry = SecurityAPIContract.model_validate(entry)
            if entry.id in self._entries:
                raise ValueError("duplicate Security API identity")
            self._entries[entry.id] = entry

    def all(self) -> tuple[SecurityAPIContract, ...]:
        return tuple(self._entries[k] for k in sorted(self._entries))

    def select(
        self, language: SecurityLanguage, role: SecurityAPIRole
    ) -> tuple[SecurityAPIContract, ...]:
        return tuple(e for e in self.all() if e.language == language and e.role == role)

    def get(self, identity: str) -> SecurityAPIContract:
        return self._entries[identity]
