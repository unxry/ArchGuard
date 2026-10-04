from typing import Protocol

from archguard.extraction.config import ExtractionConfig
from archguard.extraction.models import ExtractedFileFacts, ExtractorMetadata
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParsedSourceFile


class LanguageExtractor(Protocol):
    @property
    def language(self) -> ParserLanguage: ...

    @property
    def metadata(self) -> ExtractorMetadata: ...

    def extract(
        self, parsed_file: ParsedSourceFile, config: ExtractionConfig
    ) -> ExtractedFileFacts: ...
