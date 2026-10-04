from typing import Literal, Self

from pydantic import model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString, RepositoryPath
from archguard.extraction.enums import ResolutionMethod, ResolutionStatus
from archguard.extraction.models import SymbolReference


class ExternalDependency(DomainModel):
    ecosystem: Literal["java_namespace", "npm", "node"]
    namespace: NonEmptyString

    @property
    def identity(self) -> str:
        return f"external:{self.ecosystem}:{self.namespace}"


class ResolutionResult(DomainModel):
    source_file: RepositoryPath
    reference: SymbolReference
    status: ResolutionStatus
    method: ResolutionMethod = ResolutionMethod.NONE
    target_key: NonEmptyString | None = None
    target_file: RepositoryPath | None = None
    external: ExternalDependency | None = None
    candidates: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.status == ResolutionStatus.RESOLVED:
            if self.target_file is None or self.external is not None:
                raise ValueError("resolved reference requires an internal target file")
        elif self.target_key is not None or self.target_file is not None:
            raise ValueError("non-resolved reference cannot carry an internal target")
        if (self.status == ResolutionStatus.EXTERNAL) != (self.external is not None):
            raise ValueError("external target is required exactly for EXTERNAL status")
        if self.status == ResolutionStatus.AMBIGUOUS and len(self.candidates) < 2:
            raise ValueError("ambiguous resolution requires multiple candidates")
        return self
