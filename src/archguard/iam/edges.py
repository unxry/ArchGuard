from typing import Annotated

from pydantic import Field

from archguard.core.identifiers import EdgeId, NodeId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind
from archguard.core.model.types import JsonObject


class ArchitectureEdge(DomainModel):
    id: EdgeId
    source_id: NodeId
    target_id: NodeId
    kind: EdgeKind
    source_location: SourceLocation | None = None
    weight: Annotated[float, Field(strict=True, ge=0)] = 1.0
    attributes: JsonObject = Field(default_factory=dict)
