import hashlib
import json
import re
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import ConfigDict, Field, StrictBool, field_validator, model_validator

from archguard.architecture.graph.enums import GraphProjection
from archguard.core.findings.enums import Severity
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import EdgeKind
from archguard.core.model.types import NonEmptyString

Name = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z][A-Za-z0-9_.-]*$")]
DEFAULT_RELATIONS = (
    EdgeKind.IMPORTS,
    EdgeKind.INHERITS,
    EdgeKind.IMPLEMENTS,
    EdgeKind.CALLS,
    EdgeKind.CREATES,
    EdgeKind.USES,
)


class RuleType(StrEnum):
    FORBIDDEN = "forbidden_dependency"
    LAYER = "layer_dependency"
    REVERSE = "reverse_dependency"
    MODULE = "module_boundary"
    CIRCULAR = "circular_dependency"


class ArchitectureSpecModel(DomainModel):
    model_config = ConfigDict(populate_by_name=True)


class ArchitectureScope(ArchitectureSpecModel):
    name: Name
    include: Annotated[tuple[NonEmptyString, ...], Field(min_length=1)]
    exclude: tuple[NonEmptyString, ...] = ()
    description: NonEmptyString | None = None

    @field_validator("include", "exclude")
    @classmethod
    def normalize_globs(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if (
                len(value) > 512
                or value.startswith("/")
                or "\\" in value
                or "\x00" in value
                or re.match(r"^[A-Za-z]:", value)
                or any(part in {"", ".", ".."} for part in value.split("/"))
                or any("**" in part and part != "**" for part in value.split("/"))
            ):
                raise ValueError(
                    "selectors must be relative POSIX globs; ** must be a full segment"
                )
        return tuple(sorted(set(values)))


class LayerSpecification(ArchitectureScope):
    pass


class TargetArchitectureModule(ArchitectureScope):
    pass


class TargetArchitecture(ArchitectureSpecModel):
    layers: tuple[LayerSpecification, ...] = ()
    modules: tuple[TargetArchitectureModule, ...] = ()

    @model_validator(mode="after")
    def unique_scopes(self) -> Self:
        for scopes in (self.layers, self.modules):
            if len({scope.name for scope in scopes}) != len(scopes):
                raise ValueError("scope names must be unique within their dimension")
        object.__setattr__(self, "layers", tuple(sorted(self.layers, key=lambda item: item.name)))
        object.__setattr__(self, "modules", tuple(sorted(self.modules, key=lambda item: item.name)))
        return self


class TargetSelector(ArchitectureSpecModel):
    layer: Name | None = None
    module: Name | None = None

    @model_validator(mode="after")
    def exactly_one_dimension(self) -> Self:
        if (self.layer is None) == (self.module is None):
            raise ValueError("selector requires exactly one of layer/module")
        return self


class RuleBase(ArchitectureSpecModel):
    severity: Severity = Severity.MEDIUM
    description: NonEmptyString | None = None
    enabled: StrictBool = True
    relations: Annotated[tuple[EdgeKind, ...], Field(min_length=1)] = DEFAULT_RELATIONS

    @field_validator("severity", mode="before")
    @classmethod
    def severity_name(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value

    @field_validator("relations")
    @classmethod
    def dependency_relations(cls, values: tuple[EdgeKind, ...]) -> tuple[EdgeKind, ...]:
        if not set(values) <= set(DEFAULT_RELATIONS):
            raise ValueError("only supported architecture dependency relations are accepted")
        return tuple(sorted(set(values)))


class ForbiddenDependencySpecification(RuleBase):
    id: Literal["ARCH001"]
    type: Literal[RuleType.FORBIDDEN]
    source: TargetSelector = Field(alias="from")
    target: TargetSelector = Field(alias="to")


class DependencyConstraint(RuleBase):
    source: Name = Field(alias="from")
    allow: Annotated[tuple[Name, ...], Field(min_length=1)] | None = None
    deny: Annotated[tuple[Name, ...], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def exactly_one_constraint(self) -> Self:
        if (self.allow is None) == (self.deny is None):
            raise ValueError("exactly one of allow/deny is required")
        for field in ("allow", "deny"):
            values = getattr(self, field)
            if values is not None:
                object.__setattr__(self, field, tuple(sorted(set(values))))
        return self


class LayerDependencySpecification(DependencyConstraint):
    id: Literal["ARCH002"]
    type: Literal[RuleType.LAYER]
    allow_same_layer: StrictBool = True


class ExpectedDirection(ArchitectureSpecModel):
    source: Name = Field(alias="from")
    target: Name = Field(alias="to")

    @model_validator(mode="after")
    def distinct_layers(self) -> Self:
        if self.source == self.target:
            raise ValueError("reverse direction requires different layers")
        return self


class ReverseDependencySpecification(RuleBase):
    id: Literal["ARCH004"]
    type: Literal[RuleType.REVERSE]
    expected: ExpectedDirection


class ModuleBoundarySpecification(DependencyConstraint):
    id: Literal["ARCH005"]
    type: Literal[RuleType.MODULE]


class CircularDependencySpecification(RuleBase):
    id: Literal["ARCH003"]
    type: Literal[RuleType.CIRCULAR]
    projection: GraphProjection = GraphProjection.COMPONENT

    @field_validator("projection", mode="before")
    @classmethod
    def projection_alias(cls, value: object) -> object:
        return (
            {"target_layer": "layer", "target_module": "module"}.get(value, value)
            if isinstance(value, str)
            else value
        )


RuleSpecification = Annotated[
    ForbiddenDependencySpecification
    | LayerDependencySpecification
    | ReverseDependencySpecification
    | ModuleBoundarySpecification
    | CircularDependencySpecification,
    Field(discriminator="type"),
]


class ArchitectureSpecification(ArchitectureSpecModel):
    version: Literal["1.0"]
    architecture: TargetArchitecture
    rules: tuple[RuleSpecification, ...] = ()

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        layers = {scope.name for scope in self.architecture.layers}
        modules = {scope.name for scope in self.architecture.modules}
        if len({rule.id for rule in self.rules}) != len(self.rules):
            raise ValueError("builtin rule IDs must be unique")
        for rule in self.rules:
            if isinstance(rule, ForbiddenDependencySpecification):
                for selector in (rule.source, rule.target):
                    if (selector.layer is not None and selector.layer not in layers) or (
                        selector.module is not None and selector.module not in modules
                    ):
                        raise ValueError("rule selector refers to an unknown scope")
            elif isinstance(rule, LayerDependencySpecification):
                if not {rule.source, *(rule.allow or ()), *(rule.deny or ())} <= layers:
                    raise ValueError("layer constraint refers to an unknown layer")
            elif isinstance(rule, ReverseDependencySpecification):
                if not {rule.expected.source, rule.expected.target} <= layers:
                    raise ValueError("direction refers to an unknown layer")
            elif isinstance(rule, ModuleBoundarySpecification):
                if not {rule.source, *(rule.allow or ()), *(rule.deny or ())} <= modules:
                    raise ValueError("module constraint refers to an unknown module")
            elif (rule.projection == GraphProjection.TARGET_LAYER and not layers) or (
                rule.projection == GraphProjection.TARGET_MODULE and not modules
            ):
                raise ValueError("target cycle projection requires declared scopes")
        object.__setattr__(self, "rules", tuple(sorted(self.rules, key=lambda item: item.id)))
        return self

    def canonical_json(self) -> str:
        return json.dumps(
            self.model_dump(mode="json", by_alias=True),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
