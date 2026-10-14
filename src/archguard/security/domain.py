"""SEC-only, source-bound contracts; no vulnerability detector or probability model."""

from enum import StrEnum
from typing import Annotated, Literal, Self
from uuid import uuid5

from pydantic import Field, model_validator

from archguard.core.identifiers import (
    EvidenceId,
    FindingId,
    ModuleId,
    RepositoryId,
    SnapshotId,
    SourceFileId,
    SymbolId,
)
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject, NonEmptyString
from archguard.iam.model import ArchitectureModel

SECURITY_VERSION = "security-foundation-v1"
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]


class SecurityRuleId(StrEnum):
    SEC001 = "SEC001"
    SEC002 = "SEC002"
    SEC003 = "SEC003"
    SEC004 = "SEC004"
    SEC005 = "SEC005"
    SEC006 = "SEC006"
    SEC007 = "SEC007"
    SEC008 = "SEC008"
    SEC009 = "SEC009"
    SEC010 = "SEC010"


class SecurityLanguage(StrEnum):
    JAVA = "JAVA"
    TYPESCRIPT = "TYPESCRIPT"


class SecuritySeverity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class EvidenceStrength(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class SecurityFindingStatus(StrEnum):
    CONFIRMED_PATTERN = "CONFIRMED_PATTERN"
    SUPPORTED = "SUPPORTED"
    POTENTIAL = "POTENTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class EvidenceCapability(StrEnum):
    LEXICAL_STATIC = "LEXICAL_STATIC"
    AST_STATIC = "AST_STATIC"
    CALL_GRAPH = "CALL_GRAPH"
    DATAFLOW = "DATAFLOW"
    TAINT_FLOW = "TAINT_FLOW"
    SEMANTIC_CONTEXT = "SEMANTIC_CONTEXT"
    CONFIGURATION = "CONFIGURATION"


class SecurityEvidenceKind(StrEnum):
    SOURCE_LOCATION = "SOURCE_LOCATION"
    AST_PATTERN = "AST_PATTERN"
    CALL_SITE = "CALL_SITE"
    CONFIG_VALUE = "CONFIG_VALUE"
    DEPENDENCY_EDGE = "DEPENDENCY_EDGE"
    DATAFLOW_SOURCE = "DATAFLOW_SOURCE"
    DATAFLOW_STEP = "DATAFLOW_STEP"
    DATAFLOW_SINK = "DATAFLOW_SINK"
    SANITIZER = "SANITIZER"
    NETWORK_SINK = "NETWORK_SINK"
    FILESYSTEM_SINK = "FILESYSTEM_SINK"
    SQL_SINK = "SQL_SINK"
    COMMAND_SINK = "COMMAND_SINK"
    HTML_SINK = "HTML_SINK"
    CRYPTO_CALL = "CRYPTO_CALL"
    RANDOMNESS_CALL = "RANDOMNESS_CALL"
    DYNAMIC_EXECUTION_SINK = "DYNAMIC_EXECUTION_SINK"


class InputCategory(StrEnum):
    SOURCE = "SOURCE"
    CONFIGURATION = "CONFIGURATION"
    TEST_FIXTURE = "TEST_FIXTURE"
    EXAMPLE = "EXAMPLE"
    GENERATED = "GENERATED"
    VENDOR = "VENDOR"


class ConfigurationCategory(StrEnum):
    JSON = "JSON"
    YAML = "YAML"
    PROPERTIES = "PROPERTIES"
    ENV_ASSIGNMENT = "ENV_ASSIGNMENT"


class SecuritySourceReference(DomainModel):
    file_id: SourceFileId
    location: SourceLocation
    language: SecurityLanguage
    symbol_id: SymbolId | None = None
    module_id: ModuleId | None = None
    input_category: InputCategory = InputCategory.SOURCE
    configuration_category: ConfigurationCategory | None = None

    @model_validator(mode="after")
    def configuration_binding(self) -> Self:
        if (self.input_category == InputCategory.CONFIGURATION) != (
            self.configuration_category is not None
        ):
            raise ValueError("configuration references require an explicit configuration category")
        return self


class SecurityEvidence(DomainModel):
    namespace: Literal["SEC"] = "SEC"
    id: EvidenceId
    kind: SecurityEvidenceKind
    source: SecuritySourceReference
    summary: NonEmptyString
    analysis_version: NonEmptyString
    related_evidence: tuple[EvidenceId, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)


class FlowRole(StrEnum):
    SOURCE = "SOURCE"
    PROPAGATION = "PROPAGATION"
    SANITIZER = "SANITIZER"
    SINK = "SINK"
    INTERPROCEDURAL_BOUNDARY = "INTERPROCEDURAL_BOUNDARY"
    UNKNOWN_FLOW = "UNKNOWN_FLOW"


class FlowStep(DomainModel):
    role: FlowRole
    evidence_ref: EvidenceId


class FlowPath(DomainModel):
    protocol_version: NonEmptyString = "security-dataflow-contract-v1"
    steps: Annotated[tuple[FlowStep, ...], Field(min_length=1)]
    complete: bool
    uncertainty: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def conservative_flow(self) -> Self:
        unknown = any(s.role == FlowRole.UNKNOWN_FLOW for s in self.steps)
        if self.complete and (
            unknown
            or self.uncertainty
            or self.steps[0].role != FlowRole.SOURCE
            or self.steps[-1].role != FlowRole.SINK
        ):
            raise ValueError("complete flow requires source to sink and no unknown propagation")
        if not self.complete and not self.uncertainty:
            raise ValueError("incomplete flow must describe its uncertainty")
        return self


def finding_identity(
    repository_id: RepositoryId,
    snapshot_id: SnapshotId,
    rule_id: SecurityRuleId,
    primary: SecuritySourceReference,
    sink: SecuritySourceReference | None,
    flow: FlowPath | None,
) -> FindingId:
    """Identity within a source snapshot, independent of prose/severity/detector version."""
    import json

    payload = dict(
        snapshot=str(snapshot_id),
        rule=rule_id.value,
        primary=primary.model_dump(mode="json"),
        sink=sink.model_dump(mode="json") if sink else None,
        flow=flow.model_dump(mode="json") if flow else None,
    )
    return FindingId(
        uuid5(repository_id, json.dumps(payload, sort_keys=True, separators=(",", ":")))
    )


class SecurityFinding(DomainModel):
    schema_version: Literal["security-finding-v1"] = "security-finding-v1"
    namespace: Literal["SEC"] = "SEC"
    id: FindingId
    repository_id: RepositoryId
    snapshot_id: SnapshotId
    rule_id: SecurityRuleId
    title: NonEmptyString
    description: NonEmptyString
    severity: SecuritySeverity
    evidence_strength: EvidenceStrength
    status: SecurityFindingStatus
    language: SecurityLanguage
    primary_source: SecuritySourceReference
    evidence: Annotated[tuple[SecurityEvidence, ...], Field(min_length=1)]
    evidence_refs: Annotated[tuple[EvidenceId, ...], Field(min_length=1)]
    source_ref: EvidenceId | None = None
    sink_ref: EvidenceId | None = None
    flow: FlowPath | None = None
    remediation: NonEmptyString | None = None
    metadata: JsonObject = Field(default_factory=dict)
    analyzer_version: NonEmptyString

    @model_validator(mode="after")
    def evidence_integrity(self) -> Self:
        by_id = {e.id: e for e in self.evidence}
        if len(by_id) != len(self.evidence) or len(set(self.evidence_refs)) != len(
            self.evidence_refs
        ):
            raise ValueError("duplicate evidence references")
        if set(self.evidence_refs) != set(by_id):
            raise ValueError("finding evidence references must resolve exactly")
        flow_refs = tuple(s.evidence_ref for s in self.flow.steps) if self.flow else ()
        refs = (
            *self.evidence_refs,
            *(r for r in (self.source_ref, self.sink_ref) if r is not None),
            *flow_refs,
        )
        if any(r not in by_id for r in refs):
            raise ValueError("dangling source/sink/flow reference")
        if any(r not in by_id for e in self.evidence for r in e.related_evidence):
            raise ValueError("dangling related evidence")
        if any(
            e.analysis_version != self.analyzer_version or e.source.language != self.language
            for e in self.evidence
        ):
            raise ValueError("evidence must bind the same language and analysis version")
        if self.primary_source.language != self.language or self.primary_source not in (
            e.source for e in self.evidence
        ):
            raise ValueError("primary source must be concrete bound evidence")
        if (
            self.flow is not None
            and not self.flow.complete
            and self.status == SecurityFindingStatus.SUPPORTED
        ):
            raise ValueError("an incomplete flow cannot support a source-to-sink conclusion")
        sink = by_id[self.sink_ref].source if self.sink_ref else None
        if self.id != finding_identity(
            self.repository_id, self.snapshot_id, self.rule_id, self.primary_source, sink, self.flow
        ):
            raise ValueError("finding identity must match its stable source/flow inputs")
        return self


class SecurityAnalysisContext(DomainModel):
    repository_id: RepositoryId
    snapshot_id: SnapshotId
    language: SecurityLanguage
    requested_rules: tuple[SecurityRuleId, ...] = tuple(SecurityRuleId)
    source_references: tuple[SecuritySourceReference, ...] = ()
    available_capabilities: frozenset[EvidenceCapability] = frozenset()
    iam: ArchitectureModel | None = None

    @model_validator(mode="after")
    def context_binding(self) -> Self:
        if len(set(self.requested_rules)) != len(self.requested_rules):
            raise ValueError("duplicate requested rule")
        if any(s.language != self.language for s in self.source_references):
            raise ValueError("source language differs from context")
        if self.iam is not None:
            files = {f.id: f for f in self.iam.source_files}
            for source in self.source_references:
                file = files.get(source.file_id)
                if file is None or file.file_path != source.location.file_path:
                    raise ValueError("source reference is not in the supplied IAM")
                if file.language.value != self.language.value:
                    raise ValueError("IAM/source language mismatch")
                if source.module_id is not None and source.module_id != file.module_id:
                    raise ValueError("IAM/source module mismatch")
                if source.symbol_id is not None and not any(
                    s.id == source.symbol_id and s.file_id == source.file_id
                    for s in self.iam.symbols
                ):
                    raise ValueError("IAM/source symbol mismatch")
        return self


class SecurityDiagnostic(DomainModel):
    code: NonEmptyString
    rule_ids: tuple[SecurityRuleId, ...]
    message: NonEmptyString


class SecurityAnalysisResult(DomainModel):
    namespace: Literal["SEC"] = "SEC"
    findings: tuple[SecurityFinding, ...] = ()
    requested_rules: tuple[SecurityRuleId, ...]
    analyzed_rules: tuple[SecurityRuleId, ...] = ()
    applicable_rules: tuple[SecurityRuleId, ...] = ()
    unsupported_rules: tuple[SecurityRuleId, ...]
    diagnostics: tuple[SecurityDiagnostic, ...] = ()
    analyzer_version: NonEmptyString
    analysis_metadata: JsonObject = Field(default_factory=dict)
    zero_findings_is_security_guarantee: Literal[False] = False

    @model_validator(mode="after")
    def coverage_binding(self) -> Self:
        for values in (
            self.requested_rules,
            self.analyzed_rules,
            self.applicable_rules,
            self.unsupported_rules,
        ):
            if len(set(values)) != len(values):
                raise ValueError("duplicate coverage rule")
        requested, analyzed, unsupported = map(
            set, (self.requested_rules, self.analyzed_rules, self.unsupported_rules)
        )
        if analyzed & unsupported or analyzed | unsupported != requested:
            raise ValueError("evaluated/unsupported rules must partition requested rules")
        if not set(self.applicable_rules) <= analyzed:
            raise ValueError("applicable rules must have been evaluated")
        if len({f.id for f in self.findings}) != len(self.findings):
            raise ValueError("duplicate finding identity")
        if any(
            f.rule_id not in self.applicable_rules or f.analyzer_version != self.analyzer_version
            for f in self.findings
        ):
            raise ValueError("findings must bind evaluated applicable rules and analysis version")
        return self


class SecurityReportSection(DomainModel):
    domain: Literal["SECURITY"] = "SECURITY"
    result: SecurityAnalysisResult
    effectiveness_metrics_available: Literal[False] = False


def deduplicate_findings(findings: tuple[SecurityFinding, ...]) -> tuple[SecurityFinding, ...]:
    result: dict[FindingId, SecurityFinding] = {}
    for finding in findings:
        if finding.id in result and result[finding.id] != finding:
            raise ValueError("conflicting same-identity findings require an explicit merge policy")
        result[finding.id] = finding
    return tuple(result[k] for k in sorted(result, key=str))
