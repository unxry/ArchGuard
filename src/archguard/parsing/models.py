from collections import Counter
from dataclasses import dataclass, field
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator
from tree_sitter import Node, Tree

from archguard.core.identifiers import SnapshotId
from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString, RepositoryPath
from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import (
    DiagnosticSeverity,
    ParserDiagnosticCode,
    ParserLanguage,
    ParseSkipReason,
    ParseStatus,
)
from archguard.repository.fingerprint import inventory_fingerprint, snapshot_id
from archguard.repository.models import NonnegativeInt, RepositoryFile, RepositorySnapshot, Sha256

Coordinate = Annotated[int, Field(strict=True, ge=1)]


class ParserRuntimeInfo(DomainModel):
    parser_id: NonEmptyString
    language: ParserLanguage
    implementation_version: NonEmptyString
    grammar_package: NonEmptyString
    grammar_version: NonEmptyString
    grammar_abi_version: NonnegativeInt
    runtime_package: Literal["tree-sitter"] = "tree-sitter"
    runtime_version: NonEmptyString


class ParserDiagnostic(DomainModel):
    relative_path: RepositoryPath
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    code: ParserDiagnosticCode
    message: NonEmptyString
    line: Coordinate | None = None
    column: Coordinate | None = None
    start_byte: NonnegativeInt | None = None
    end_byte: NonnegativeInt | None = None

    @model_validator(mode="after")
    def validate_position(self) -> Self:
        if (self.line is None) != (self.column is None):
            raise ValueError("line and byte column must be supplied together")
        if self.end_byte is not None and (
            self.start_byte is None or self.end_byte < self.start_byte
        ):
            raise ValueError("exclusive end byte must follow start byte")
        return self


class FileParseMetadata(DomainModel):
    snapshot_id: SnapshotId
    source_file: RepositoryFile
    language: ParserLanguage | None = None
    parser: ParserRuntimeInfo | None = None
    status: ParseStatus
    source_encoding: Literal["utf8"] = "utf8"
    syntax_error_nodes: NonnegativeInt = 0
    missing_nodes: NonnegativeInt = 0
    has_syntax_errors: bool = False
    diagnostics: tuple[ParserDiagnostic, ...] = ()
    skip_reason: ParseSkipReason | None = None

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.parser is not None and self.parser.language != self.language:
            raise ValueError("parser metadata must agree with file dialect")
        if self.status in {ParseStatus.PARSED, ParseStatus.INVALID} and (
            self.parser is None or self.language is None or not self.source_file.analysis_eligible
        ):
            raise ValueError("parsed files require an eligible source and parser metadata")
        if (self.status == ParseStatus.SKIPPED) != (self.skip_reason is not None):
            raise ValueError("skip reason is required exactly for skipped files")
        if self.has_syntax_errors != bool(self.syntax_error_nodes or self.missing_nodes):
            raise ValueError("syntax error flag must agree with node counts")
        if self.status == ParseStatus.INVALID and not self.has_syntax_errors:
            raise ValueError("syntax-invalid outcome requires syntax errors")
        if self.status in {ParseStatus.FAILED, ParseStatus.UNSUPPORTED} and not self.diagnostics:
            raise ValueError("failed and unsupported outcomes require a diagnostic")
        if any(item.relative_path != self.source_file.relative_path for item in self.diagnostics):
            raise ValueError("diagnostic paths must agree with source identity")
        return self


@dataclass(frozen=True, slots=True, weakref_slot=True)
class ParsedSourceFile:
    metadata: FileParseMetadata
    tree: Tree = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self.metadata.status not in {ParseStatus.PARSED, ParseStatus.INVALID}:
            raise ValueError("a syntax tree requires a parsed outcome")

    @property
    def root(self) -> Node:
        return self.tree.root_node


class ParseLanguageStatistics(DomainModel):
    candidates: NonnegativeInt
    parsed: NonnegativeInt
    invalid: NonnegativeInt
    failed: NonnegativeInt
    skipped: NonnegativeInt
    unsupported: NonnegativeInt


class ParseStatistics(DomainModel):
    total_files: NonnegativeInt
    total_candidates: NonnegativeInt
    attempted_files: NonnegativeInt
    parsed_files: NonnegativeInt
    invalid_files: NonnegativeInt
    skipped_files: NonnegativeInt
    unsupported_files: NonnegativeInt
    failed_files: NonnegativeInt
    syntax_error_files: NonnegativeInt
    syntax_error_nodes: NonnegativeInt
    missing_nodes: NonnegativeInt
    diagnostic_count: NonnegativeInt

    @classmethod
    def from_files(cls, files: tuple[FileParseMetadata, ...]) -> Self:
        counts = Counter(item.status for item in files)
        parsed = counts[ParseStatus.PARSED] + counts[ParseStatus.INVALID]
        return cls(
            total_files=len(files),
            total_candidates=sum(item.source_file.analysis_eligible for item in files),
            attempted_files=parsed + counts[ParseStatus.FAILED],
            parsed_files=parsed,
            invalid_files=counts[ParseStatus.INVALID],
            skipped_files=counts[ParseStatus.SKIPPED],
            unsupported_files=counts[ParseStatus.UNSUPPORTED],
            failed_files=counts[ParseStatus.FAILED],
            syntax_error_files=sum(item.has_syntax_errors for item in files),
            syntax_error_nodes=sum(item.syntax_error_nodes for item in files),
            missing_nodes=sum(item.missing_nodes for item in files),
            diagnostic_count=sum(len(item.diagnostics) for item in files),
        )


def _language_stats(
    files: tuple[FileParseMetadata, ...],
) -> dict[ParserLanguage, ParseLanguageStatistics]:
    counts: dict[ParserLanguage, Counter[ParseStatus]] = {}
    candidates: Counter[ParserLanguage] = Counter()
    for item in files:
        if item.language is not None:
            counts.setdefault(item.language, Counter())[item.status] += 1
            candidates[item.language] += item.source_file.analysis_eligible
    return {
        language: ParseLanguageStatistics(
            candidates=candidates[language],
            parsed=counts[language][ParseStatus.PARSED] + counts[language][ParseStatus.INVALID],
            invalid=counts[language][ParseStatus.INVALID],
            failed=counts[language][ParseStatus.FAILED],
            skipped=counts[language][ParseStatus.SKIPPED],
            unsupported=counts[language][ParseStatus.UNSUPPORTED],
        )
        for language in sorted(counts)
    }


def _parser_versions(files: tuple[FileParseMetadata, ...]) -> tuple[ParserRuntimeInfo, ...]:
    parsers: dict[str, ParserRuntimeInfo] = {}
    for item in files:
        if item.parser is not None:
            key = item.parser.parser_id
            if key in parsers and parsers[key] != item.parser:
                raise ValueError("one parser identity must have consistent runtime metadata")
            parsers[key] = item.parser
    return tuple(parsers[key] for key in sorted(parsers))


class ParseRepositoryResult(DomainModel):
    parsing_schema_version: Literal["1.0"] = "1.0"
    snapshot_id: SnapshotId
    snapshot_fingerprint: Sha256
    config: ParserConfig
    files: tuple[FileParseMetadata, ...]
    statistics: ParseStatistics
    language_stats: dict[ParserLanguage, ParseLanguageStatistics]
    parser_versions: tuple[ParserRuntimeInfo, ...]
    is_valid: bool

    @classmethod
    def from_files(
        cls,
        snapshot: RepositorySnapshot,
        config: ParserConfig,
        files: tuple[FileParseMetadata, ...],
    ) -> Self:
        if tuple(item.source_file for item in files) != snapshot.files:
            raise ValueError("parse outcomes must cover the complete source inventory")
        statistics = ParseStatistics.from_files(files)
        return cls(
            snapshot_id=snapshot.snapshot_id,
            snapshot_fingerprint=snapshot.fingerprint,
            config=config,
            files=files,
            statistics=statistics,
            language_stats=_language_stats(files),
            parser_versions=_parser_versions(files),
            is_valid=not (statistics.invalid_files or statistics.failed_files),
        )

    @model_validator(mode="after")
    def validate_files(self) -> Self:
        paths = tuple(item.source_file.relative_path for item in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("parse outcomes must be unique and ordered")
        if any(item.snapshot_id != self.snapshot_id for item in self.files):
            raise ValueError("parse outcomes must belong to the repository snapshot")
        if self.snapshot_fingerprint != inventory_fingerprint(
            tuple(item.source_file for item in self.files)
        ) or self.snapshot_id != snapshot_id(self.snapshot_fingerprint):
            raise ValueError("parse identity must agree with the repository inventory")
        if self.statistics != ParseStatistics.from_files(self.files):
            raise ValueError("parse statistics must agree with file outcomes")
        if self.language_stats != _language_stats(self.files):
            raise ValueError("language statistics must agree with file outcomes")
        if self.parser_versions != _parser_versions(self.files):
            raise ValueError("parser versions must agree with file outcomes")
        if self.is_valid != (not (self.statistics.invalid_files or self.statistics.failed_files)):
            raise ValueError("validity must agree with file outcomes")
        return self

    @property
    def diagnostics(self) -> tuple[ParserDiagnostic, ...]:
        return tuple(diagnostic for item in self.files for diagnostic in item.diagnostics)
