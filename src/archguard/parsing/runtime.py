from functools import lru_cache
from importlib.metadata import version

from archguard.parsing.enums import ParserLanguage
from archguard.parsing.models import ParserRuntimeInfo

PARSER_IMPLEMENTATION_VERSION = "1.0.0"


@lru_cache(maxsize=4)
def package_version(package: str) -> str:
    return version(package)


def runtime_info(
    language: ParserLanguage, grammar_package: str, grammar_abi_version: int
) -> ParserRuntimeInfo:
    return ParserRuntimeInfo(
        parser_id=f"{language.value.lower()}-tree-sitter",
        language=language,
        implementation_version=PARSER_IMPLEMENTATION_VERSION,
        grammar_package=grammar_package,
        grammar_version=package_version(grammar_package),
        grammar_abi_version=grammar_abi_version,
        runtime_version=package_version("tree-sitter"),
    )
