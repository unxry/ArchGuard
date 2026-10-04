from typing import Annotated, Literal

from pydantic import Field

from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language
from archguard.core.model.types import JsonObject, NonEmptyString


class ModelConfiguration(DomainModel):
    provider: NonEmptyString
    model: NonEmptyString
    parameters: JsonObject = Field(default_factory=dict)


class ParserVersion(DomainModel):
    language: Language
    version: NonEmptyString


class ReproducibilityManifest(DomainModel):
    """A run configuration contract, not an experiment result or an experiment runner."""

    schema_version: Literal["1.0"] = "1.0"
    software_version: NonEmptyString
    dataset_version: NonEmptyString
    random_seed: Annotated[int, Field(strict=True, ge=0)] | None = None
    model: ModelConfiguration | None = None
    parsers: tuple[ParserVersion, ...] = ()
    analysis_config: JsonObject = Field(default_factory=dict)
    git_commit: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")] | None = None
