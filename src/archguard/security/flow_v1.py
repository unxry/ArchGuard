"""Bounded, rule-specific flow lattice. Values never leave the analysis process."""

from dataclasses import dataclass, field, replace
from enum import StrEnum

from pydantic import Field

from archguard.core.model.base import DomainModel
from archguard.security.domain import FlowRole, SecurityRuleId, SecuritySourceReference

VERSION = "security-static-dataflow-v1"


class FlowState(StrEnum):
    UNTAINTED = "UNTAINTED"
    TAINTED = "TAINTED"
    SANITIZED = "SANITIZED"
    UNKNOWN = "UNKNOWN"


class FlowLimits(DomainModel):
    max_flow_steps: int = Field(default=32, ge=3, le=256)
    max_tracked_values: int = Field(default=512, ge=1, le=4096)
    max_nodes_per_function: int = Field(default=10000, ge=1, le=100000)
    max_branch_states: int = Field(default=32, ge=1, le=256)
    max_file_nodes: int = Field(default=60000, ge=1, le=500000)
    max_expression_depth: int = Field(default=64, ge=1, le=256)
    max_source_bytes: int = Field(default=2 * 1024 * 1024, ge=1, le=8 * 1024 * 1024)


@dataclass(frozen=True)
class TraceStep:
    role: FlowRole
    source: SecuritySourceReference
    api_id: str = "local-propagation"


@dataclass(frozen=True)
class FlowValue:
    state: FlowState = FlowState.UNKNOWN
    paths: tuple[tuple[TraceStep, ...], ...] = ()
    sanitized_for: frozenset[SecurityRuleId] = frozenset()
    uncertainty: tuple[str, ...] = ()
    # Internal facts only: no model_dump, logging, preview or value-derived digest.
    literal: str | None = field(default=None, repr=False)
    api_type: str | None = None
    fields: tuple[tuple[str, "FlowValue"], ...] = field(default=(), repr=False)

    @classmethod
    def unknown(cls, reason: str) -> "FlowValue":
        return cls(uncertainty=(reason,))

    @classmethod
    def source(cls, source: SecuritySourceReference, api_id: str) -> "FlowValue":
        return cls(FlowState.TAINTED, ((TraceStep(FlowRole.SOURCE, source, api_id),),))

    def step(self, source: SecuritySourceReference, limit: int) -> "FlowValue":
        if any(len(p) >= limit - 1 for p in self.paths):
            return replace(
                self,
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=tuple(sorted({*self.uncertainty, "FLOW_LIMIT_EXCEEDED"})),
            )
        return replace(
            self, paths=tuple((*p, TraceStep(FlowRole.PROPAGATION, source)) for p in self.paths)
        )

    def sanitize(
        self, rule: SecurityRuleId, source: SecuritySourceReference, api_id: str, limit: int
    ) -> "FlowValue":
        value = self.step(source, limit)
        if value.state == FlowState.UNKNOWN or not value.paths:
            return value
        return replace(
            value,
            state=FlowState.SANITIZED,
            sanitized_for=value.sanitized_for | {rule},
            paths=tuple(
                (*p[:-1], TraceStep(FlowRole.SANITIZER, source, api_id)) for p in value.paths
            ),
        )


def merge(values: tuple[FlowValue, ...], max_paths: int = 32) -> FlowValue:
    """UNKNOWN dominates; otherwise taint dominates, with rule-wise sanitizer intersection."""
    if not values:
        return FlowValue(FlowState.UNTAINTED)
    paths = tuple(dict.fromkeys(p for v in values for p in v.paths))
    uncertainty = tuple(sorted({r for v in values for r in v.uncertainty}))
    unknown = any(v.state == FlowState.UNKNOWN for v in values)
    if unknown and not uncertainty:
        uncertainty = ("UNRESOLVED_VALUE",)
    if len(paths) > max_paths:
        paths = paths[:max_paths]
        uncertainty = tuple(sorted({*uncertainty, "PATH_LIMIT_EXCEEDED"}))
        unknown = True
    tainted = [v for v in values if v.paths]
    safe_rules = (
        frozenset.intersection(*(v.sanitized_for for v in tainted)) if tainted else frozenset()
    )
    state = (
        FlowState.UNKNOWN
        if unknown
        else FlowState.SANITIZED
        if tainted and safe_rules
        else FlowState.TAINTED
        if tainted
        else FlowState.UNTAINTED
    )
    types = {v.api_type for v in values}
    literals = {v.literal for v in values}
    return FlowValue(
        state,
        paths,
        safe_rules if not unknown else frozenset(),
        uncertainty,
        next(iter(literals)) if len(literals) == 1 else None,
        next(iter(types)) if len(types) == 1 else None,
    )
