from typing import Annotated, Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.types import RepositoryPath

Coordinate = Annotated[int, Field(strict=True, ge=1)]


class SourceLocation(DomainModel):
    """One-based inclusive coordinates; no end means a point, not an open interval."""

    file_path: RepositoryPath
    start_line: Coordinate
    start_column: Coordinate = 1
    end_line: Coordinate | None = None
    end_column: Coordinate | None = None

    @model_validator(mode="after")
    def validate_range(self) -> Self:
        if (self.end_line is None) != (self.end_column is None):
            raise ValueError("end_line and end_column must be supplied together")
        if (
            self.end_line is not None
            and self.end_column is not None
            and (self.end_line, self.end_column) < (self.start_line, self.start_column)
        ):
            raise ValueError("end position must not precede start position")
        return self
