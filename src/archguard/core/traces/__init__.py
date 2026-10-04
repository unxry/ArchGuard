from typing import Annotated, Self

from pydantic import Field, model_validator

from archguard.core.identifiers import EdgeId, NodeId, TraceId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind
from archguard.core.model.types import JsonObject, NonEmptyString


class TraceStep(DomainModel):
    sequence: Annotated[int, Field(strict=True, ge=1)]
    node_id: NodeId | None = None
    edge_id: EdgeId | None = None
    location: SourceLocation | None = None
    relation: EdgeKind | None = None
    label: NonEmptyString
    metadata: JsonObject = Field(default_factory=dict)


class Trace(DomainModel):
    """Steps are supplied in contiguous one-based order; relation describes the incoming edge."""

    id: TraceId
    steps: Annotated[tuple[TraceStep, ...], Field(min_length=1)]
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if tuple(step.sequence for step in self.steps) != tuple(range(1, len(self.steps) + 1)):
            raise ValueError("trace steps must be ordered and contiguous, starting at 1")
        return self
