import logging
from collections import Counter
from contextlib import closing

from archguard.application.parse_repository import ParseRepository
from archguard.core.locations import SourceLocation
from archguard.core.model.enums import NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ExtractionDiagnosticCode, ResolutionStatus
from archguard.extraction.errors import UnsupportedExtractorError
from archguard.extraction.models import ExtractedFileFacts, ExtractionDiagnostic
from archguard.extraction.registry import ExtractorRegistry
from archguard.extraction.resolution.index import SymbolIndex
from archguard.extraction.resolution.resolver import SymbolResolver
from archguard.iam_building.builder import IAMBuilder
from archguard.iam_building.models import IAMBuildResult, IAMBuildStatistics
from archguard.parsing.enums import DiagnosticSeverity, ParseStatus
from archguard.parsing.models import FileParseMetadata, ParsedSourceFile, ParseRepositoryResult
from archguard.repository.models import RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace


class BuildIAM:
    def __init__(
        self,
        parsing: ParseRepository,
        extractors: ExtractorRegistry,
        config: ExtractionConfig | None = None,
        resolver: SymbolResolver | None = None,
        builder: IAMBuilder | None = None,
    ) -> None:
        self._parsing = parsing
        self._extractors = extractors
        self._config = config if config is not None else ExtractionConfig()
        self._resolver = resolver if resolver is not None else SymbolResolver()
        self._builder = builder if builder is not None else IAMBuilder()

    def execute(
        self, snapshot: RepositorySnapshot, workspace: RepositoryWorkspace
    ) -> IAMBuildResult:
        logger = logging.getLogger("archguard.extraction")
        metadata: list[FileParseMetadata] = []
        facts: list[ExtractedFileFacts] = []
        diagnostics: list[ExtractionDiagnostic] = []
        complete = True
        logger.info("IAM build started snapshot=%s", snapshot.snapshot_id)
        with closing(self._parsing.iter_parse(snapshot, workspace)) as outcomes:
            for outcome in outcomes:
                item = outcome.metadata if isinstance(outcome, ParsedSourceFile) else outcome
                metadata.append(item)
                if not isinstance(outcome, ParsedSourceFile):
                    if (
                        item.status in {ParseStatus.FAILED, ParseStatus.UNSUPPORTED}
                        or item.source_file.analysis_eligible
                    ):
                        complete = False
                    del outcome
                    continue
                if item.status == ParseStatus.INVALID and self._config.skip_invalid_files:
                    diagnostics.append(
                        ExtractionDiagnostic(
                            code=ExtractionDiagnosticCode.INVALID_FILE_SKIPPED,
                            message="strict-invalid source was skipped by extraction policy",
                            source_location=SourceLocation(
                                file_path=item.source_file.relative_path, start_line=1
                            ),
                        )
                    )
                    complete = False
                    del outcome
                    continue
                try:
                    assert item.language is not None
                    extractor = self._extractors.get(item.language)
                    file = extractor.extract(outcome, self._config)
                    if (
                        file.snapshot_id != snapshot.snapshot_id
                        or file.source_file != item.source_file
                        or file.parser != item.parser
                        or file.extractor != extractor.metadata
                    ):
                        raise ValueError("extractor returned mismatched source identity")
                    facts.append(file)
                    diagnostics.extend(file.diagnostics)
                    complete = (
                        complete and not file.source_had_syntax_errors and not file.diagnostics
                    )
                except Exception as error:
                    code = (
                        ExtractionDiagnosticCode.MISSING_EXTRACTOR
                        if isinstance(error, UnsupportedExtractorError)
                        else ExtractionDiagnosticCode.EXTRACTION_FAILED
                    )
                    diagnostics.append(
                        ExtractionDiagnostic(
                            code=code,
                            message="source could not be extracted",
                            severity=DiagnosticSeverity.ERROR,
                            source_location=SourceLocation(
                                file_path=item.source_file.relative_path, start_line=1
                            ),
                        )
                    )
                    logger.error(
                        "extraction failed snapshot=%s dialect=%s code=%s exception_type=%s",
                        snapshot.snapshot_id,
                        item.language,
                        code.value,
                        type(error).__name__,
                    )
                    complete = False
                finally:
                    del outcome
        parsing = ParseRepositoryResult.from_files(snapshot, self._parsing.config, tuple(metadata))
        compact = tuple(facts)
        index = SymbolIndex(compact)
        resolutions = self._resolver.resolve(compact, index)
        codes = {
            ResolutionStatus.UNRESOLVED: ExtractionDiagnosticCode.RESOLUTION_UNRESOLVED,
            ResolutionStatus.AMBIGUOUS: ExtractionDiagnosticCode.RESOLUTION_AMBIGUOUS,
            ResolutionStatus.EXTERNAL: ExtractionDiagnosticCode.RESOLUTION_EXTERNAL,
        }
        for result in resolutions:
            if result.status in codes:
                diagnostics.append(
                    ExtractionDiagnostic(
                        code=codes[result.status],
                        message="reference resolution: " + result.status.value,
                        source_location=result.reference.source_location,
                    )
                )
        iam, build_diagnostics = self._builder.build(
            snapshot, compact, resolutions, self._config, parsing, self._resolver.version
        )
        diagnostics.extend(build_diagnostics)
        statuses = Counter(result.status for result in resolutions)
        languages: Counter[str] = Counter()
        for file in compact:
            languages[file.language.value] += len(file.declarations)
        statistics = IAMBuildStatistics(
            files_seen=len(metadata),
            files_extracted=len(compact),
            files_with_parse_errors=parsing.statistics.syntax_error_files,
            declarations_total=sum(len(file.declarations) for file in compact),
            imports_total=sum(len(file.imports) for file in compact),
            references_total=len(resolutions),
            references_resolved=statuses[ResolutionStatus.RESOLVED],
            references_ambiguous=statuses[ResolutionStatus.AMBIGUOUS],
            references_unresolved=statuses[ResolutionStatus.UNRESOLVED],
            references_external=statuses[ResolutionStatus.EXTERNAL],
            nodes_created=len(iam.nodes),
            edges_created=len(iam.edges),
            external_nodes=sum(node.kind == NodeKind.EXTERNAL_DEPENDENCY for node in iam.nodes),
            declarations_by_language=dict(sorted(languages.items())),
        )
        valid = parsing.is_valid and not any(
            item.severity == DiagnosticSeverity.ERROR for item in diagnostics
        )
        iam = iam.model_copy(
            update={
                "metadata": {
                    **iam.metadata,
                    "is_valid": valid,
                    "is_complete": complete,
                    "statistics": statistics.model_dump(mode="json"),
                }
            }
        )
        logger.info(
            "IAM build finished snapshot=%s files=%d declarations=%d nodes=%d edges=%d",
            snapshot.snapshot_id,
            statistics.files_extracted,
            statistics.declarations_total,
            statistics.nodes_created,
            statistics.edges_created,
        )
        return IAMBuildResult(
            iam=iam,
            config=self._config,
            parsing=parsing,
            facts=compact,
            resolutions=resolutions,
            statistics=statistics,
            diagnostics=tuple(diagnostics),
            is_valid=valid,
            is_complete=complete,
            builder_version=self._builder.version,
            resolver_version=self._resolver.version,
        )
