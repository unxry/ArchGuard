from collections.abc import Iterable

from archguard.extraction.errors import DuplicateExtractorError, UnsupportedExtractorError
from archguard.extraction.protocols import LanguageExtractor
from archguard.parsing.enums import ParserLanguage


class ExtractorRegistry:
    def __init__(self, extractors: Iterable[LanguageExtractor] = ()) -> None:
        self._extractors: dict[ParserLanguage, LanguageExtractor] = {}
        for extractor in extractors:
            self.register(extractor)

    def register(self, extractor: LanguageExtractor) -> None:
        if extractor.metadata.dialect != extractor.language:
            raise ValueError("extractor metadata must match its registered dialect")
        if extractor.language in self._extractors or any(
            item.metadata.extractor_id == extractor.metadata.extractor_id
            for item in self._extractors.values()
        ):
            raise DuplicateExtractorError("extractor language or identity is already registered")
        self._extractors[extractor.language] = extractor

    def get(self, language: ParserLanguage) -> LanguageExtractor:
        extractor = self._extractors.get(language)
        if extractor is None:
            raise UnsupportedExtractorError("no extractor is registered for this dialect")
        return extractor

    def supports(self, language: ParserLanguage) -> bool:
        return language in self._extractors

    def supported_languages(self) -> tuple[ParserLanguage, ...]:
        return tuple(sorted(self._extractors))
