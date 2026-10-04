import tree_sitter_java
import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Parser

from archguard.core.identifiers import SnapshotId
from archguard.parsing.config import ParserConfig
from archguard.parsing.diagnostics import collect_syntax_diagnostics
from archguard.parsing.enums import ParserLanguage, ParseStatus
from archguard.parsing.errors import (
    IneligibleSourceError,
    ParserExecutionError,
    ParserResourceLimitError,
    SourceDecodingError,
)
from archguard.parsing.models import FileParseMetadata, ParsedSourceFile, ParserRuntimeInfo
from archguard.parsing.registry import parser_language
from archguard.parsing.runtime import runtime_info
from archguard.repository.enums import RepositoryFileKind
from archguard.repository.models import RepositoryFile


class TreeSitterParserAdapter:
    def __init__(
        self,
        language: ParserLanguage,
        extensions: tuple[str, ...],
        grammar: Language,
        grammar_package: str,
    ) -> None:
        self._language = language
        self._extensions = extensions
        self._grammar = grammar
        self._runtime = runtime_info(language, grammar_package, grammar.abi_version)

    @property
    def language(self) -> ParserLanguage:
        return self._language

    @property
    def supported_extensions(self) -> tuple[str, ...]:
        return self._extensions

    @property
    def runtime_info(self) -> ParserRuntimeInfo:
        return self._runtime

    def parse(
        self,
        snapshot_id: SnapshotId,
        source_file: RepositoryFile,
        source: bytes,
        config: ParserConfig,
    ) -> ParsedSourceFile:
        if (
            not source_file.analysis_eligible
            or source_file.kind not in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST}
            or source_file.is_binary
            or source_file.is_generated
            or source_file.is_large
            or parser_language(source_file) != self.language
            or source_file.extension not in self.supported_extensions
            or self.language not in config.enabled_languages
        ):
            raise IneligibleSourceError("source is not eligible for this parser")
        if max(source_file.size_bytes, len(source)) > config.max_source_file_bytes:
            raise ParserResourceLimitError("source exceeds the parser byte limit")
        if len(source) != source_file.size_bytes:
            raise IneligibleSourceError("source byte count differs from repository metadata")
        try:
            source.decode("utf-8", errors="strict")
        except UnicodeDecodeError as error:
            prefix = source[: error.start]
            raise SourceDecodingError(
                error.start,
                prefix.count(b"\n") + 1,
                error.start - prefix.rfind(b"\n"),
            ) from error
        if b"\x00" in source:
            raise IneligibleSourceError("source contains binary NUL bytes")
        try:
            tree = Parser(self._grammar).parse(source, encoding="utf8")
        except (ValueError, RuntimeError, TypeError) as error:
            raise ParserExecutionError("Tree-sitter could not build a syntax tree") from error
        syntax = collect_syntax_diagnostics(tree.root_node, source_file.relative_path, config)
        has_errors = bool(syntax.error_nodes or syntax.missing_nodes)
        return ParsedSourceFile(
            metadata=FileParseMetadata(
                snapshot_id=snapshot_id,
                source_file=source_file,
                language=self.language,
                parser=self.runtime_info,
                status=(
                    ParseStatus.INVALID
                    if config.strict_syntax_errors and has_errors
                    else ParseStatus.PARSED
                ),
                syntax_error_nodes=syntax.error_nodes,
                missing_nodes=syntax.missing_nodes,
                has_syntax_errors=has_errors,
                diagnostics=syntax.diagnostics,
            ),
            tree=tree,
        )


class JavaParser(TreeSitterParserAdapter):
    def __init__(self) -> None:
        super().__init__(
            ParserLanguage.JAVA,
            (".java",),
            Language(tree_sitter_java.language()),
            "tree-sitter-java",
        )


class TypeScriptParser(TreeSitterParserAdapter):
    def __init__(self) -> None:
        super().__init__(
            ParserLanguage.TYPESCRIPT,
            (".ts",),
            Language(tree_sitter_typescript.language_typescript()),
            "tree-sitter-typescript",
        )


class JavaScriptParser(TreeSitterParserAdapter):
    def __init__(self) -> None:
        super().__init__(
            ParserLanguage.JAVASCRIPT,
            (".js", ".jsx"),
            Language(tree_sitter_javascript.language()),
            "tree-sitter-javascript",
        )


class TSXParser(TreeSitterParserAdapter):
    def __init__(self) -> None:
        super().__init__(
            ParserLanguage.TSX,
            (".tsx",),
            Language(tree_sitter_typescript.language_tsx()),
            "tree-sitter-typescript",
        )
