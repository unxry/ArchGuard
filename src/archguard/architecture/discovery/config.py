import re
from typing import Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from archguard.architecture.discovery.enums import DiscoveryEvidenceKind, DiscoveryStrength
from archguard.architecture.graph.config import GraphAnalysisConfig, PositiveInt, fingerprint
from archguard.architecture.graph.enums import GraphProjection
from archguard.core.model.base import DomainModel


class ArchitectureDiscoveryConfig(DomainModel):
    profile: Literal["structural-baseline-v1"] = "structural-baseline-v1"
    role_pattern_version: Literal["suffix-tokens-v1"] = "suffix-tokens-v1"
    enabled_signal_types: tuple[DiscoveryEvidenceKind, ...] = tuple(DiscoveryEvidenceKind)
    framework_signals: StrictBool = True
    graph_refinement: StrictBool = True
    minimum_role_strength: DiscoveryStrength = DiscoveryStrength.MODERATE
    minimum_layer_strength: DiscoveryStrength = DiscoveryStrength.MODERATE
    minimum_module_strength: DiscoveryStrength = DiscoveryStrength.MODERATE
    module_root_hints: tuple[str, ...] = ("src",)
    min_module_components: PositiveInt = 2
    max_module_depth: PositiveInt = 4
    java_min_package_depth: PositiveInt = 3
    java_common_prefix: str | None = None
    topology_rank_limit: PositiveInt = 5
    graph: GraphAnalysisConfig = Field(default_factory=GraphAnalysisConfig)

    @field_validator("enabled_signal_types")
    @classmethod
    def signal_order(
        cls, values: tuple[DiscoveryEvidenceKind, ...]
    ) -> tuple[DiscoveryEvidenceKind, ...]:
        return tuple(sorted(set(values)))

    @field_validator("module_root_hints")
    @classmethod
    def relative_roots(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            not value
            or "\\" in value
            or ":" in value
            or "\x00" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))
            for value in values
        ):
            raise ValueError("module roots must be relative POSIX directories")
        return tuple(sorted(set(values)))

    @field_validator("java_common_prefix")
    @classmethod
    def namespace(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(
            r"[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*", value
        ):
            raise ValueError("Java common prefix must be a package namespace")
        return value

    @model_validator(mode="after")
    def discovery_scope(self) -> Self:
        if DiscoveryStrength.AMBIGUOUS in {
            self.minimum_role_strength,
            self.minimum_layer_strength,
            self.minimum_module_strength,
        }:
            raise ValueError("ambiguity is not a minimum evidence strength")
        projection = self.graph.projection
        if (
            projection.projection != GraphProjection.COMPONENT
            or projection.include_external
            or projection.include_self_edges
        ):
            raise ValueError("discovery requires an internal component graph without self edges")
        return self

    @property
    def fingerprint(self) -> str:
        return fingerprint(self)
