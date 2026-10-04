import logging
from collections import Counter
from collections.abc import Generator
from time import perf_counter

from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import (
    DiagnosticSeverity,
    ParserDiagnosticCode,
    ParseSkipReason,
    ParseStatus,
)
from archguard.parsing.errors import ParsingError, SourceDecodingError, UnsupportedLanguageError
from archguard.parsing.models import (
    FileParseMetadata,
    ParsedSourceFile,
    ParserDiagnostic,
    ParseRepositoryResult,
    ParserRuntimeInfo,
)
from archguard.parsing.registry import ParserRegistry, parser_language
from archguard.repository.enums import RepositoryFileKind, SourceLanguage
from archguard.repository.errors import RepositoryIntakeError
from archguard.repository.models import RepositoryFile, RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


class ParseRepository:
    def __init__(self, registry: ParserRegistry, config: ParserConfig | None = None) -> None:
        self._registry = registry
        self._config = config if config is not None else ParserConfig()

    @property
    def config(self) -> ParserConfig:
        return self._config

    def execute(
        self, snapshot: RepositorySnapshot, workspace: RepositoryWorkspace
    ) -> ParseRepositoryResult:
        files = []
        for outcome in self.iter_parse(snapshot, workspace):
            files.append(outcome.metadata if isinstance(outcome, ParsedSourceFile) else outcome)
            del outcome
        return ParseRepositoryResult.from_files(snapshot, self._config, tuple(files))

    def iter_parse(
        self, snapshot: RepositorySnapshot, workspace: RepositoryWorkspace
    ) -> Generator[ParsedSourceFile | FileParseMetadata]:
        """Yield one tree or non-parsed outcome; caller owns the repository context and iterator."""
        logger = logging.getLogger("archguard.parsing")
        started = perf_counter()
        counts: Counter[ParseStatus] = Counter()
        syntax_files = 0
        logger.info("parsing started snapshot=%s", snapshot.snapshot_id)
        try:
            for file in snapshot.files:
                outcome = self._parse_one(snapshot, workspace, file)
                metadata = outcome.metadata if isinstance(outcome, ParsedSourceFile) else outcome
                counts[metadata.status] += 1
                syntax_files += metadata.has_syntax_errors
                logger.info(
                    "parsing file snapshot=%s language=%s status=%s",
                    snapshot.snapshot_id,
                    metadata.language,
                    metadata.status.value,
                )
                yield outcome
                del outcome
        finally:
            parsed = counts[ParseStatus.PARSED] + counts[ParseStatus.INVALID]
            logger.info(
                "parsing finished snapshot=%s attempted=%d parsed=%d skipped=%d "
                "unsupported=%d failed=%d syntax_error_files=%d duration=%.3fs",
                snapshot.snapshot_id,
                parsed + counts[ParseStatus.FAILED],
                parsed,
                counts[ParseStatus.SKIPPED],
                counts[ParseStatus.UNSUPPORTED],
                counts[ParseStatus.FAILED],
                syntax_files,
                perf_counter() - started,
            )

    def _parse_one(
        self,
        snapshot: RepositorySnapshot,
        workspace: RepositoryWorkspace,
        file: RepositoryFile,
    ) -> ParsedSourceFile | FileParseMetadata:
        language = parser_language(file)
        runtime: ParserRuntimeInfo | None = None

        def outcome(
            status: ParseStatus,
            diagnostic: ParserDiagnostic | None = None,
            reason: ParseSkipReason | None = None,
        ) -> FileParseMetadata:
            return FileParseMetadata(
                snapshot_id=snapshot.snapshot_id,
                source_file=file,
                language=language,
                parser=runtime,
                status=status,
                diagnostics=(diagnostic,) if diagnostic is not None else (),
                skip_reason=reason,
            )

        def diagnostic(code: ParserDiagnosticCode, message: str) -> ParserDiagnostic:
            return ParserDiagnostic(relative_path=file.relative_path, code=code, message=message)

        if not file.analysis_eligible:
            unsupported = (
                not (file.is_binary or file.is_generated or file.is_large)
                and (
                    file.language == SourceLanguage.UNKNOWN
                    or (file.kind in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST})
                )
                and language is None
            )
            if unsupported:
                return outcome(
                    ParseStatus.UNSUPPORTED,
                    diagnostic(
                        ParserDiagnosticCode.UNSUPPORTED_LANGUAGE,
                        "source language is not supported by the parser registry",
                    ),
                )
            return outcome(ParseStatus.SKIPPED, reason=ParseSkipReason.INELIGIBLE)
        if language not in self._config.enabled_languages:
            return outcome(ParseStatus.SKIPPED, reason=ParseSkipReason.DISABLED_LANGUAGE)
        if file.size_bytes > self._config.max_source_file_bytes:
            return outcome(
                ParseStatus.SKIPPED,
                ParserDiagnostic(
                    relative_path=file.relative_path,
                    severity=DiagnosticSeverity.WARNING,
                    code=ParserDiagnosticCode.RESOURCE_LIMIT,
                    message="source exceeds the parser byte limit",
                ),
                ParseSkipReason.SIZE_LIMIT,
            )
        try:
            if language is None:
                raise UnsupportedLanguageError("source has no parser dialect")
            adapter = self._registry.get(language)
            runtime = adapter.runtime_info
        except UnsupportedLanguageError:
            return outcome(
                ParseStatus.UNSUPPORTED,
                diagnostic(
                    ParserDiagnosticCode.UNSUPPORTED_LANGUAGE,
                    "no parser is registered for this source dialect",
                ),
            )
        try:
            with workspace.open_source_file(file.relative_path) as stream:
                source = stream.read(self._config.max_source_file_bytes + 1)
        except (RepositoryIntakeError, OSError):
            return outcome(
                ParseStatus.FAILED,
                diagnostic(
                    ParserDiagnosticCode.SOURCE_READ_ERROR, "source could not be read safely"
                ),
            )
        try:
            parsed = adapter.parse(snapshot.snapshot_id, file, source, self._config)
            if (
                parsed.metadata.snapshot_id != snapshot.snapshot_id
                or parsed.metadata.source_file != file
                or parsed.metadata.parser != adapter.runtime_info
            ):
                raise ValueError("parser returned mismatched source identity or runtime metadata")
            return parsed
        except SourceDecodingError as error:
            return outcome(
                ParseStatus.FAILED,
                ParserDiagnostic(
                    relative_path=file.relative_path,
                    code=error.code,
                    message="source is not valid UTF-8",
                    line=error.line,
                    column=error.column,
                    start_byte=error.byte_offset,
                ),
            )
        except Exception as error:
            # Isolate an adapter failure into a visible outcome; never log its source-bearing args.
            logger = logging.getLogger("archguard.parsing")
            code = (
                error.code
                if isinstance(error, ParsingError)
                else ParserDiagnosticCode.EXECUTION_ERROR
            )
            logger.error(
                "parser failed snapshot=%s language=%s code=%s exception_type=%s",
                snapshot.snapshot_id,
                language,
                code.value,
                type(error).__name__,
            )
            return outcome(
                ParseStatus.FAILED,
                diagnostic(code, "parser could not process this source file"),
            )
