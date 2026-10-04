import re
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from archguard.core.evidence import Evidence
from archguard.core.findings.confidence import Confidence
from archguard.core.findings.detector import Detector
from archguard.core.findings.enums import ARCHITECTURE_DETECTORS, FindingNamespace, Severity
from archguard.core.identifiers import FindingId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject, NonEmptyString
from archguard.core.traces import Trace

FINDING_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class Finding(DomainModel):
    finding_schema_version: Literal["1.0"] = FINDING_SCHEMA_VERSION
    id: FindingId
    namespace: FindingNamespace
    rule_id: NonEmptyString
    category: NonEmptyString
    title: NonEmptyString
    description: NonEmptyString
    severity: Severity
    confidence: Confidence | None = None
    primary_location: SourceLocation | None = None
    related_locations: tuple[SourceLocation, ...] = ()
    evidence: Annotated[tuple[Evidence, ...], Field(min_length=1)]
    trace: Trace | None = None
    detector: Detector
    recommendation: NonEmptyString | None = None
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_namespace(self) -> Self:
        if re.fullmatch(rf"{self.namespace.value}[0-9]{{3}}", self.rule_id) is None:
            raise ValueError("rule_id must match the namespace followed by three ASCII digits")
        is_arch_detector = self.detector.source in ARCHITECTURE_DETECTORS
        if (self.namespace == FindingNamespace.ARCH) != is_arch_detector:
            raise ValueError("detector source must match the finding namespace")
        if any(evidence.namespace != self.namespace for evidence in self.evidence):
            raise ValueError("all evidence must match the finding namespace")
        if len({evidence.id for evidence in self.evidence}) != len(self.evidence):
            raise ValueError("evidence identifiers must be unique within a finding")
        return self
