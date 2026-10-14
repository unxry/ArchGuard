"""Source-safe summary contracts, semantic resolution states and bounded private caching."""

import hashlib
import json
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Self
from uuid import UUID

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.security.domain import SecurityRuleId, SecuritySourceReference
from archguard.security.flow_v1 import FlowLimits, FlowState

VERSION = "security-interprocedural-v2"


class ResolutionState(StrEnum):
    EXACT = "EXACT"
    UNAMBIGUOUS_LOCAL = "UNAMBIGUOUS_LOCAL"
    PARTIAL = "PARTIAL"
    AMBIGUOUS = "AMBIGUOUS"
    UNRESOLVED = "UNRESOLVED"


class SummaryState(StrEnum):
    SUPPORTED = "SUPPORTED"
    PARTIAL = "PARTIAL"
    UNKNOWN = "UNKNOWN"


class ProofKind(StrEnum):
    SQL_PARAMETERIZATION = "SQL_PARAMETERIZATION"
    PATH_CONFINEMENT = "PATH_CONFINEMENT"
    SSRF_ALLOWLIST = "SSRF_ALLOWLIST"
    XSS_SANITIZATION = "XSS_SANITIZATION"
    COMMAND_ARGUMENT_BOUNDARY = "COMMAND_ARGUMENT_BOUNDARY"


class V2Limits(FlowLimits):
    max_flow_steps: int = Field(default=64, ge=3, le=256)
    max_call_depth: int = Field(default=4, ge=1, le=16)
    max_summary_expansions: int = Field(default=256, ge=1, le=4096)
    max_recursive_visits: int = Field(default=1, ge=1, le=1)
    max_call_targets: int = Field(default=4, ge=1, le=16)
    max_summary_nodes: int = Field(default=4096, ge=1, le=20000)
    max_summary_cache_entries: int = Field(default=256, ge=1, le=4096)
    max_total_flow_steps: int = Field(default=64, ge=3, le=256)
    max_aliases_per_object: int = Field(default=32, ge=1, le=256)
    max_heap_objects: int = Field(default=256, ge=1, le=4096)
    max_fields_per_object: int = Field(default=64, ge=1, le=1024)
    max_total_heap_fields: int = Field(default=2048, ge=1, le=20000)
    max_source_files: int = Field(default=64, ge=1, le=256)
    max_total_source_bytes: int = Field(default=8 * 1024 * 1024, ge=1, le=32 * 1024 * 1024)
    max_total_nodes: int = Field(default=50000, ge=1, le=500000)
    max_total_summary_nodes: int = Field(default=50000, ge=1, le=500000)
    max_candidates: int = Field(default=512, ge=1, le=4096)

    @property
    def flow_bound(self) -> int:
        return min(self.max_flow_steps, self.max_total_flow_steps)


class ParameterFlow(DomainModel):
    parameter_index: int = Field(ge=0)
    destination: str
    evidence: tuple[SecuritySourceReference, ...]
    rule_ids: tuple[SecurityRuleId, ...] = ()


class ReturnFlow(DomainModel):
    state: FlowState
    parameter_indices: tuple[int, ...] = ()
    sources: tuple[SecuritySourceReference, ...] = ()
    sanitized_for: tuple[SecurityRuleId, ...] = ()


class SinkEffect(DomainModel):
    rule_id: SecurityRuleId
    sink: SecuritySourceReference
    parameter_indices: tuple[int, ...]
    source_locations: tuple[SecuritySourceReference, ...]


class SanitizerEffect(DomainModel):
    rule_ids: tuple[SecurityRuleId, ...]
    evidence: tuple[SecuritySourceReference, ...]


class FieldEffect(DomainModel):
    action: str
    location: SecuritySourceReference
    projection_depth: int = Field(ge=1)
    parameter_indices: tuple[int, ...] = ()


class UnknownEffect(DomainModel):
    code: str


class SafetyProof(DomainModel):
    kind: ProofKind
    rule_ids: tuple[SecurityRuleId, ...]
    evidence: tuple[SecuritySourceReference, ...] = Field(min_length=1)
    scope: str


class FunctionSummary(DomainModel):
    version: str = VERSION
    symbol_id: UUID
    declaration: SecuritySourceReference
    arity: int = Field(ge=0)
    state: SummaryState
    parameter_flows: tuple[ParameterFlow, ...] = ()
    return_flow: ReturnFlow
    sinks: tuple[SinkEffect, ...] = ()
    sanitizers: tuple[SanitizerEffect, ...] = ()
    call_targets: tuple[UUID, ...] = ()
    analysis_nodes: int = Field(default=0, ge=0)
    field_effects: tuple[FieldEffect, ...] = ()
    unknown_effects: tuple[UnknownEffect, ...] = ()
    fingerprint: str

    @model_validator(mode="after")
    def verify_fingerprint(self) -> Self:
        value = self.model_dump(mode="json", exclude={"fingerprint"})
        if self.fingerprint != fingerprint(value):
            raise ValueError("summary fingerprint does not bind its semantic effects")
        if any(i >= self.arity for i in self.return_flow.parameter_indices):
            raise ValueError("summary parameter outside signature")
        return self


def fingerprint(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass
class SummaryCache:
    # Keys contain source-version digests, never exported or used as secret-value digests.
    entries: OrderedDict[tuple[str, str, str], FunctionSummary] = field(
        default_factory=OrderedDict, repr=False
    )
    hits: int = 0
    misses: int = 0

    def get(self, key: tuple[str, str, str]) -> FunctionSummary | None:
        value = self.entries.get(key)
        if value is None:
            self.misses += 1
        else:
            self.hits += 1
            self.entries.move_to_end(key)
        return value

    def put(self, key: tuple[str, str, str], value: FunctionSummary, limit: int) -> None:
        self.entries[key] = value
        self.entries.move_to_end(key)
        while len(self.entries) > limit:
            self.entries.popitem(last=False)
