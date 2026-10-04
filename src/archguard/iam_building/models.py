from collections import Counter
from typing import Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.enums import NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ResolutionStatus
from archguard.extraction.models import ExtractedFileFacts, ExtractionDiagnostic
from archguard.extraction.resolution.models import ResolutionResult
from archguard.iam.model import ArchitectureModel
from archguard.parsing.enums import DiagnosticSeverity
from archguard.parsing.models import ParseRepositoryResult
from archguard.repository.models import NonnegativeInt


class IAMBuildStatistics(DomainModel):
    files_seen: NonnegativeInt
    files_extracted: NonnegativeInt
    files_with_parse_errors: NonnegativeInt
    declarations_total: NonnegativeInt
    imports_total: NonnegativeInt
    references_total: NonnegativeInt
    references_resolved: NonnegativeInt
    references_ambiguous: NonnegativeInt
    references_unresolved: NonnegativeInt
    references_external: NonnegativeInt
    nodes_created: NonnegativeInt
    edges_created: NonnegativeInt
    external_nodes: NonnegativeInt
    declarations_by_language: dict[str, NonnegativeInt] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.references_total != sum(
            (
                self.references_resolved,
                self.references_ambiguous,
                self.references_unresolved,
                self.references_external,
            )
        ):
            raise ValueError("reference status counts must cover every reference")
        if sum(self.declarations_by_language.values()) != self.declarations_total:
            raise ValueError("language counts must cover every declaration")
        if self.files_extracted > self.files_seen or self.external_nodes > self.nodes_created:
            raise ValueError("build statistics are inconsistent")
        return self

    @property
    def resolution_rate(self) -> float:
        """Internally resolved / all references, including imports and external references."""
        return self.references_resolved / self.references_total if self.references_total else 0.0


class IAMBuildResult(DomainModel):
    iam: ArchitectureModel
    config: ExtractionConfig
    parsing: ParseRepositoryResult
    facts: tuple[ExtractedFileFacts, ...]
    resolutions: tuple[ResolutionResult, ...]
    statistics: IAMBuildStatistics
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()
    is_valid: bool
    is_complete: bool
    builder_version: str = "1.0.0"
    resolver_version: str = "1.0.0"

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        stats = self.statistics
        counts = Counter(item.status for item in self.resolutions)
        if (
            stats.files_seen != len(self.parsing.files)
            or stats.files_extracted != len(self.facts)
            or stats.files_with_parse_errors != self.parsing.statistics.syntax_error_files
            or stats.declarations_total != sum(len(file.declarations) for file in self.facts)
            or stats.declarations_total != len(self.iam.symbols)
            or stats.imports_total != sum(len(file.imports) for file in self.facts)
            or stats.references_total != sum(len(file.references) for file in self.facts)
            or stats.references_total != len(self.resolutions)
            or stats.nodes_created != len(self.iam.nodes)
            or stats.edges_created != len(self.iam.edges)
            or stats.external_nodes
            != sum(node.kind == NodeKind.EXTERNAL_DEPENDENCY for node in self.iam.nodes)
            or stats.references_resolved != counts[ResolutionStatus.RESOLVED]
            or stats.references_ambiguous != counts[ResolutionStatus.AMBIGUOUS]
            or stats.references_unresolved != counts[ResolutionStatus.UNRESOLVED]
            or stats.references_external != counts[ResolutionStatus.EXTERNAL]
        ):
            raise ValueError("build statistics must agree with actual facts and IAM")
        if self.is_valid != (
            self.parsing.is_valid
            and not any(item.severity == DiagnosticSeverity.ERROR for item in self.diagnostics)
        ):
            raise ValueError("build validity must agree with parsing and extraction diagnostics")
        if self.iam.metadata.get("snapshot_fingerprint") != self.parsing.snapshot_fingerprint:
            raise ValueError("IAM metadata must identify the parsed snapshot")
        return self
