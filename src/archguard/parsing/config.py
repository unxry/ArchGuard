from typing import Self

from pydantic import model_validator

from archguard.core.model.base import DomainModel
from archguard.parsing.enums import ParserLanguage
from archguard.repository.policy import PositiveInt


class ParserConfig(DomainModel):
    enabled_languages: tuple[ParserLanguage, ...] = tuple(sorted(ParserLanguage))
    max_source_file_bytes: PositiveInt = 2 * 1024 * 1024
    collect_error_nodes: bool = True
    strict_syntax_errors: bool = False
    max_diagnostics_per_file: PositiveInt = 100

    @model_validator(mode="after")
    def validate_languages(self) -> Self:
        if self.enabled_languages != tuple(sorted(set(self.enabled_languages))):
            raise ValueError("enabled languages must be unique and sorted")
        return self
