"""Explicit local detector scope; no LLM transport or Architecture decision port."""

from typing import Protocol, Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString
from archguard.security.domain import (
    EvidenceCapability,
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecurityFinding,
    SecurityLanguage,
    SecurityRuleId,
)


class DetectorRegistration(DomainModel):
    id: NonEmptyString
    version: NonEmptyString
    supported_rule_ids: tuple[SecurityRuleId, ...] = Field(min_length=1)
    supported_languages: tuple[SecurityLanguage, ...] = Field(min_length=1)
    required_capabilities: frozenset[EvidenceCapability]

    @model_validator(mode="after")
    def unique_scope(self) -> Self:
        for values in (self.supported_rule_ids, self.supported_languages):
            if len(set(values)) != len(values):
                raise ValueError("duplicate detector scope")
        return self


class DetectorResult(DomainModel):
    evaluated_rules: tuple[SecurityRuleId, ...]
    applicable_rules: tuple[SecurityRuleId, ...]
    findings: tuple[SecurityFinding, ...] = ()

    @model_validator(mode="after")
    def result_scope(self) -> Self:
        if (
            len(set(self.evaluated_rules)) != len(self.evaluated_rules)
            or len(set(self.applicable_rules)) != len(self.applicable_rules)
            or not set(self.applicable_rules) <= set(self.evaluated_rules)
        ):
            raise ValueError("invalid detector result coverage")
        return self


class SecurityRuleDetector(Protocol):
    @property
    def registration(self) -> DetectorRegistration: ...

    def analyze(self, context: SecurityAnalysisContext, /) -> DetectorResult: ...


class SecurityAnalyzerPort(Protocol):
    def analyze(self, context: SecurityAnalysisContext, /) -> SecurityAnalysisResult: ...
