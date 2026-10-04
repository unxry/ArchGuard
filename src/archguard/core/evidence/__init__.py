from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from archguard.core.findings.enums import FindingNamespace
from archguard.core.identifiers import EvidenceId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject, NonEmptyString


class EvidenceType(StrEnum):
    STATIC_RULE = "STATIC_RULE"
    GRAPH_PATH = "GRAPH_PATH"
    GRAPH_METRIC = "GRAPH_METRIC"
    SOURCE_CODE = "SOURCE_CODE"
    ARCHITECTURE_RULE = "ARCHITECTURE_RULE"
    LLM_RESULT = "LLM_RESULT"
    SECRET_PATTERN = "SECRET_PATTERN"
    DEPENDENCY_DATABASE = "DEPENDENCY_DATABASE"
    CONFIGURATION = "CONFIGURATION"
    DATA_FLOW = "DATA_FLOW"
    TAINT_PATH = "TAINT_PATH"


SECURITY_EVIDENCE_TYPES = frozenset(
    {
        EvidenceType.SECRET_PATTERN,
        EvidenceType.DEPENDENCY_DATABASE,
        EvidenceType.CONFIGURATION,
        EvidenceType.DATA_FLOW,
        EvidenceType.TAINT_PATH,
    }
)


class Evidence(DomainModel):
    id: EvidenceId
    namespace: FindingNamespace
    type: EvidenceType
    message: NonEmptyString
    location: SourceLocation | None = None
    properties: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_namespace(self) -> Self:
        if self.namespace == FindingNamespace.ARCH and self.type in SECURITY_EVIDENCE_TYPES:
            raise ValueError("security-specific evidence cannot belong to ARCH")
        return self
