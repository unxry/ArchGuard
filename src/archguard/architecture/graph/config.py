import hashlib
import json
from typing import Annotated, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from archguard.architecture.graph.enums import GraphProjection
from archguard.architecture.specification.models import DEFAULT_RELATIONS
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind

PositiveInt = Annotated[int, Field(strict=True, gt=0)]
NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]
UnitFloat = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


def fingerprint(value: DomainModel) -> str:
    return hashlib.sha256(
        json.dumps(
            value.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


class GraphProjectionSpec(DomainModel):
    projection: GraphProjection = GraphProjection.COMPONENT
    included_relations: tuple[EdgeKind, ...] = DEFAULT_RELATIONS
    include_external: StrictBool = False
    include_self_edges: StrictBool = False

    @field_validator("included_relations")
    @classmethod
    def supported_relations(cls, values: tuple[EdgeKind, ...]) -> tuple[EdgeKind, ...]:
        if not set(values) <= set(DEFAULT_RELATIONS):
            raise ValueError("only architecture dependency relations are supported")
        return tuple(sorted(set(values)))


class CandidateThresholds(DomainModel):
    excessive_coupling: PositiveInt | None = None
    hub_fan_in: PositiveInt | None = None
    god_min_members: PositiveInt | None = None
    god_min_methods: NonnegativeInt | None = None
    god_min_coupling: PositiveInt | None = None
    unstable_delta: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] | None = None
    bottleneck_betweenness: Annotated[float, Field(gt=0, le=1, allow_inf_nan=False)] | None = None
    bottleneck_min_neighbors: NonnegativeInt | None = None

    @model_validator(mode="after")
    def coherent_thresholds(self) -> Self:
        if (self.god_min_members is None) != (self.god_min_coupling is None):
            raise ValueError("God Component requires both size and coupling thresholds")
        if self.god_min_methods is not None and self.god_min_members is None:
            raise ValueError("method threshold requires God Component configuration")
        if self.bottleneck_min_neighbors is not None and self.bottleneck_betweenness is None:
            raise ValueError("support threshold requires bottleneck configuration")
        return self

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)


class GraphAnalysisConfig(DomainModel):
    projection: GraphProjectionSpec = Field(default_factory=GraphProjectionSpec)
    max_graph_nodes: PositiveInt = 10_000
    max_graph_edges: PositiveInt = 100_000
    calculate_pagerank: StrictBool = True
    calculate_betweenness: StrictBool = True
    betweenness_node_limit: PositiveInt = 1_000
    pagerank_alpha: Annotated[float, Field(gt=0, lt=1, allow_inf_nan=False)] = 0.85
    pagerank_tolerance: Annotated[float, Field(gt=0, allow_inf_nan=False)] = 1e-10
    pagerank_max_iterations: PositiveInt = 200
    max_cycle_trace_length: Annotated[int, Field(strict=True, ge=3)] = 256
    max_neighbourhood_nodes: PositiveInt = 1_000
    candidates: CandidateThresholds = Field(default_factory=CandidateThresholds)

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)
