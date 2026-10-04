import pytest
from pydantic import ValidationError

from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.errors import DuplicateParserError, UnsupportedLanguageError
from archguard.parsing.factory import create_parser_registry
from archguard.parsing.registry import ParserRegistry
from archguard.parsing.tree_sitter_adapters import (
    JavaParser,
    JavaScriptParser,
    TSXParser,
    TypeScriptParser,
)
from archguard.repository.enums import SourceLanguage


@pytest.mark.parametrize(
    ("language", "adapter_type"),
    [
        (ParserLanguage.JAVA, JavaParser),
        (ParserLanguage.TYPESCRIPT, TypeScriptParser),
        (ParserLanguage.JAVASCRIPT, JavaScriptParser),
        (ParserLanguage.TSX, TSXParser),
    ],
)
def test_registry_routes_each_dialect(language, adapter_type) -> None:
    registry = create_parser_registry()
    assert registry.supports(language)
    assert isinstance(registry.get(language), adapter_type)


def test_registry_unsupported_and_unconfigured_are_typed() -> None:
    registry = create_parser_registry()
    assert not registry.supports(SourceLanguage.UNKNOWN)
    with pytest.raises(UnsupportedLanguageError):
        registry.get(SourceLanguage.UNKNOWN)
    with pytest.raises(UnsupportedLanguageError):
        ParserRegistry().get(ParserLanguage.JAVA)
    assert isinstance(registry.get(SourceLanguage.JAVA), JavaParser)


def test_duplicate_registration_does_not_replace_adapter() -> None:
    parser = JavaParser()
    registry = ParserRegistry((parser,))
    with pytest.raises(DuplicateParserError):
        registry.register(JavaParser())
    assert registry.get(ParserLanguage.JAVA) is parser


def test_duplicate_identity_across_languages_is_typed() -> None:
    java = JavaParser()

    class ConflictingParser(TypeScriptParser):
        @property
        def runtime_info(self):
            return super().runtime_info.model_copy(
                update={"parser_id": java.runtime_info.parser_id}
            )

    with pytest.raises(DuplicateParserError):
        ParserRegistry((java, ConflictingParser()))


def test_registration_order_is_deterministic_and_instances_are_isolated() -> None:
    first = ParserRegistry((TSXParser(), JavaParser(), JavaScriptParser(), TypeScriptParser()))
    second = create_parser_registry()
    assert (
        first.supported_languages() == second.supported_languages() == tuple(sorted(ParserLanguage))
    )
    assert ParserRegistry().supported_languages() == ()


@pytest.mark.parametrize(
    "values",
    [
        {"max_source_file_bytes": 0},
        {"max_diagnostics_per_file": -1},
        {"enabled_languages": (ParserLanguage.JAVA, ParserLanguage.JAVA)},
        {"enabled_languages": tuple(reversed(sorted(ParserLanguage)))},
    ],
)
def test_parser_config_rejects_invalid_limits_and_nondeterministic_languages(values) -> None:
    with pytest.raises(ValidationError):
        ParserConfig(**values)
