from archguard.parsing.registry import ParserRegistry
from archguard.parsing.tree_sitter_adapters import (
    JavaParser,
    JavaScriptParser,
    TSXParser,
    TypeScriptParser,
)


def create_parser_registry() -> ParserRegistry:
    return ParserRegistry((JavaParser(), TypeScriptParser(), JavaScriptParser(), TSXParser()))
