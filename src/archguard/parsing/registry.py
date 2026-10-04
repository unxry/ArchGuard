from collections.abc import Iterable

from archguard.parsing.enums import ParserLanguage
from archguard.parsing.errors import DuplicateParserError, UnsupportedLanguageError
from archguard.parsing.ports import ParserAdapter
from archguard.repository.enums import SourceLanguage
from archguard.repository.models import RepositoryFile


def parser_language(file: RepositoryFile) -> ParserLanguage | None:
    if file.language == SourceLanguage.JAVA:
        return ParserLanguage.JAVA
    if file.language == SourceLanguage.JAVASCRIPT:
        return ParserLanguage.JAVASCRIPT
    if file.language == SourceLanguage.TYPESCRIPT:
        return ParserLanguage.TSX if file.extension == ".tsx" else ParserLanguage.TYPESCRIPT
    return None


class ParserRegistry:
    def __init__(self, adapters: Iterable[ParserAdapter] = ()) -> None:
        self._adapters: dict[ParserLanguage, ParserAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: ParserAdapter) -> None:
        if adapter.language in self._adapters or any(
            item.runtime_info.parser_id == adapter.runtime_info.parser_id
            for item in self._adapters.values()
        ):
            raise DuplicateParserError("parser language or identity is already registered")
        self._adapters[adapter.language] = adapter

    def get(self, language: ParserLanguage | SourceLanguage) -> ParserAdapter:
        try:
            dialect = ParserLanguage(language.value)
        except ValueError as error:
            raise UnsupportedLanguageError("no parser is registered for this language") from error
        adapter = self._adapters.get(dialect)
        if adapter is None:
            raise UnsupportedLanguageError("no parser is registered for this language")
        return adapter

    def supports(self, language: ParserLanguage | SourceLanguage) -> bool:
        return language in self._adapters

    def supported_languages(self) -> tuple[ParserLanguage, ...]:
        return tuple(sorted(self._adapters))
