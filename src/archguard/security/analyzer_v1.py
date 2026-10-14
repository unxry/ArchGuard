"""Executable V1 application service; foundation-only P027 contracts remain immutable."""

from collections.abc import Iterable
from dataclasses import dataclass, field
from uuid import uuid5

from archguard.core.identifiers import EvidenceId, SourceFileId
from archguard.core.model.types import JsonObject
from archguard.parsing.config import ParserConfig
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.repository.models import RepositoryFile
from archguard.security.api_v1 import supported_rules
from archguard.security.domain import (
    EvidenceCapability,
    EvidenceStrength,
    FlowPath,
    FlowRole,
    FlowStep,
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecurityDiagnostic,
    SecurityEvidence,
    SecurityEvidenceKind,
    SecurityFinding,
    SecurityFindingStatus,
    SecurityLanguage,
    SecurityRuleId,
    SecuritySeverity,
    deduplicate_findings,
    finding_identity,
)
from archguard.security.engine_v1 import BoundedFlowEngine, Candidate, EngineOutput
from archguard.security.flow_v1 import VERSION, FlowLimits, TraceStep
from archguard.security.ports import DetectorRegistration, DetectorResult, SecurityRuleDetector
from archguard.security.rules import ImplementationStatus, SecurityRuleRegistry, canonical_rules


@dataclass(frozen=True)
class SecuritySourceInput:
    file: RepositoryFile
    source: bytes = field(repr=False)
    file_id: SourceFileId


def finding(
    candidate: Candidate, context: SecurityAnalysisContext, path: tuple[TraceStep, ...] = ()
) -> SecurityFinding:
    steps = (
        (*path, TraceStep(FlowRole.SINK, candidate.source, candidate.api_id))
        if path
        else (TraceStep(FlowRole.SINK, candidate.source, candidate.api_id),)
    )
    evidence = tuple(
        SecurityEvidence(
            id=EvidenceId(
                uuid5(
                    context.snapshot_id,
                    f"{candidate.rule}:{step.role}:{step.source.model_dump_json()}:{step.api_id}",
                )
            ),
            kind=SecurityEvidenceKind.AST_PATTERN
            if not path
            else {
                FlowRole.SOURCE: SecurityEvidenceKind.DATAFLOW_SOURCE,
                FlowRole.PROPAGATION: SecurityEvidenceKind.DATAFLOW_STEP,
                FlowRole.SANITIZER: SecurityEvidenceKind.SANITIZER,
                FlowRole.SINK: SecurityEvidenceKind.DATAFLOW_SINK,
            }[step.role],
            source=step.source,
            summary="Embedded credential [REDACTED]"
            if candidate.rule == SecurityRuleId.SEC001
            else f"{step.role.value}: {step.api_id}",
            analysis_version=VERSION,
            metadata={"api_id": step.api_id},
        )
        for step in steps
    )
    # Repeated visits to identical locations share evidence; paths retain their ordered refs.
    unique = tuple({e.id: e for e in evidence}.values())
    uncertainty = candidate.value.uncertainty if candidate.value else ()
    flow = (
        FlowPath(
            protocol_version=VERSION,
            steps=tuple(
                FlowStep(role=s.role, evidence_ref=e.id)
                for s, e in zip(steps, evidence, strict=True)
            ),
            complete=not uncertainty,
            uncertainty=uncertainty,
        )
        if path
        else None
    )
    primary = candidate.source
    sink = candidate.source if path else None
    return SecurityFinding(
        id=finding_identity(
            context.repository_id, context.snapshot_id, candidate.rule, primary, sink, flow
        ),
        repository_id=context.repository_id,
        snapshot_id=context.snapshot_id,
        rule_id=candidate.rule,
        title=SecurityRuleRegistry().get(candidate.rule).name,
        description=(
            "Bounded Security pattern; review the referenced locations and documented API scope"
        ),
        severity=SecuritySeverity.HIGH
        if candidate.rule not in {SecurityRuleId.SEC008, SecurityRuleId.SEC009}
        else SecuritySeverity.MEDIUM,
        evidence_strength=EvidenceStrength.MEDIUM
        if candidate.status == SecurityFindingStatus.POTENTIAL
        else EvidenceStrength.HIGH,
        status=candidate.status,
        language=context.language,
        primary_source=primary,
        evidence=unique,
        evidence_refs=tuple(e.id for e in unique),
        source_ref=evidence[0].id if path else None,
        sink_ref=evidence[-1].id if path else None,
        flow=flow,
        analyzer_version=VERSION,
        remediation=SecurityRuleRegistry().get(candidate.rule).remediation,
        metadata={"detector_id": f"{candidate.rule.value.lower()}-v1", "raw_values": "OMITTED"},
    )


class StaticFlowDetector:
    def __init__(self, rule: SecurityRuleId, output: EngineOutput) -> None:
        self.rule, self.output = rule, output

    @property
    def registration(self) -> DetectorRegistration:
        return DetectorRegistration(
            id=f"{self.rule.value.lower()}-v1",
            version=VERSION,
            supported_rule_ids=(self.rule,),
            supported_languages=(SecurityLanguage.JAVA,)
            if self.rule == SecurityRuleId.SEC005
            else tuple(SecurityLanguage),
            required_capabilities=frozenset({EvidenceCapability.AST_STATIC})
            if self.rule
            in {
                SecurityRuleId.SEC001,
                SecurityRuleId.SEC005,
                SecurityRuleId.SEC008,
                SecurityRuleId.SEC009,
            }
            else frozenset(
                {
                    EvidenceCapability.AST_STATIC,
                    EvidenceCapability.DATAFLOW,
                    EvidenceCapability.TAINT_FLOW,
                }
            ),
        )

    def analyze(self, context: SecurityAnalysisContext, /) -> DetectorResult:
        findings: list[SecurityFinding] = []
        for c in self.output.candidates:
            if c.rule == self.rule:
                if c.value is not None:
                    findings.extend(finding(c, context, p) for p in c.value.paths)
                else:
                    findings.append(finding(c, context))
        return DetectorResult(
            evaluated_rules=(self.rule,), applicable_rules=(self.rule,), findings=tuple(findings)
        )


class SecurityAnalyzerV1:
    version = VERSION

    def __init__(self, limits: FlowLimits | None = None) -> None:
        self.limits = limits or FlowLimits()

    def analyze(
        self,
        context: SecurityAnalysisContext,
        sources: Iterable[SecuritySourceInput],
        /,
        *,
        detectors: Iterable[SecurityRuleDetector] | None = None,
    ) -> SecurityAnalysisResult:
        context = SecurityAnalysisContext.model_validate(context)
        output = EngineOutput()
        failed_input = False
        seen: set[SourceFileId] = set()
        source_list = tuple(sources)
        if not source_list:
            failed_input = True
            output.diagnostics.add("SOURCE_UNAVAILABLE")
        for source in sorted(source_list, key=lambda s: s.file.relative_path):
            # No filesystem/credential intake. Callers provide already-classified source bytes.
            if source.file_id in seen:
                raise ValueError("duplicate Security source identity")
            seen.add(source.file_id)
            if source.file.language.value != context.language.value:
                failed_input = True
                output.diagnostics.add("UNSUPPORTED_LANGUAGE")
                continue
            if context.iam is not None and not any(
                f.id == source.file_id and f.file_path == source.file.relative_path
                for f in context.iam.source_files
            ):
                raise ValueError("source input is not bound to IAM")
            try:
                parser = (
                    JavaParser()
                    if context.language == SecurityLanguage.JAVA
                    else TypeScriptParser()
                )
                parsed = parser.parse(
                    context.snapshot_id,
                    source.file,
                    source.source,
                    ParserConfig(
                        max_source_file_bytes=self.limits.max_source_bytes,
                        strict_syntax_errors=True,
                    ),
                )
                if parsed.metadata.has_syntax_errors:
                    failed_input = True
                    output.diagnostics.add("SOURCE_PARSE_ERROR")
                    continue
                engine_result = BoundedFlowEngine(
                    context.language, source.file_id, source.file.relative_path, self.limits
                ).run(parsed.tree.root_node)
                output.candidates.extend(engine_result.candidates)
                output.diagnostics.update(engine_result.diagnostics)
                output.partial |= engine_result.partial
            except Exception:
                # Exception text may contain source/credentials; publish neither message nor trace.
                failed_input = True
                output.diagnostics.add("SOURCE_ANALYSIS_ERROR")
        supported = set(supported_rules(context.language))
        selected = (
            tuple(detectors)
            if detectors is not None
            else tuple(StaticFlowDetector(r, output) for r in sorted(supported))
        )
        definitions = tuple(
            r.model_copy(
                update={
                    "implementation_status": ImplementationStatus.IMPLEMENTED,
                    "detector_ids": tuple(
                        d.registration.id
                        for d in selected
                        if r.rule_id in d.registration.supported_rule_ids
                    ),
                }
            )
            if any(r.rule_id in d.registration.supported_rule_ids for d in selected)
            else r
            for r in canonical_rules()
        )
        registry = SecurityRuleRegistry(definitions, selected)
        evaluated: set[SecurityRuleId] = set()
        failed: set[SecurityRuleId] = set()
        results: list[SecurityFinding] = []
        bound_sources = {c.source for c in output.candidates}
        for c in output.candidates:
            if c.value:
                bound_sources.update(step.source for p in c.value.paths for step in p)
        narrowed = context.model_copy(
            update={
                "source_references": tuple(
                    sorted(
                        bound_sources,
                        key=lambda s: (
                            s.location.file_path,
                            s.location.start_line,
                            s.location.start_column,
                        ),
                    )
                ),
                "available_capabilities": frozenset(
                    {
                        EvidenceCapability.AST_STATIC,
                        EvidenceCapability.DATAFLOW,
                        EvidenceCapability.TAINT_FLOW,
                    }
                ),
            }
        )
        requested = set(context.requested_rules)
        for d in registry.detectors:
            scope = requested & set(d.registration.supported_rule_ids)
            if not scope or context.language not in d.registration.supported_languages:
                continue
            if failed_input:
                failed.update(scope)
                continue
            if not d.registration.required_capabilities <= narrowed.available_capabilities:
                output.diagnostics.add("CAPABILITY_UNAVAILABLE")
                continue
            try:
                result = DetectorResult.model_validate(
                    d.analyze(
                        SecurityAnalysisContext.model_validate(
                            narrowed.model_dump() | {"requested_rules": tuple(sorted(scope))}
                        )
                    )
                )
                if (
                    set(result.evaluated_rules) != scope
                    or not set(result.applicable_rules) <= scope
                ):
                    raise ValueError("unbound detector coverage")
                for f in result.findings:
                    SecurityFinding.model_validate(f)
                    if (
                        f.rule_id not in result.applicable_rules
                        or f.repository_id != context.repository_id
                        or f.snapshot_id != context.snapshot_id
                        or f.language != context.language
                        or f.analyzer_version != VERSION
                        or any(e.source not in bound_sources for e in f.evidence)
                    ):
                        raise ValueError("unbound detector output")
                results = list(deduplicate_findings((*results, *result.findings)))
                evaluated.update(result.evaluated_rules)
            except Exception:
                failed.update(scope)
                output.diagnostics.add("DETECTOR_ERROR")
        # A failed detector never becomes successfully evaluated through another detector.
        evaluated -= failed
        results = [f for f in results if f.rule_id in evaluated]
        unsupported = requested - evaluated
        if unsupported - failed:
            output.diagnostics.add("UNSUPPORTED_RULE")
        if output.partial or evaluated:
            output.diagnostics.add("PARTIAL_ANALYSIS")
        coverage: JsonObject = {
            r.value: {
                "requested": True,
                "supported": r in supported,
                "evaluated": r in evaluated,
                "status": "FAILED"
                if r in failed
                else "PARTIAL"
                if r in evaluated
                else "UNSUPPORTED",
            }
            for r in sorted(requested)
        }
        return SecurityAnalysisResult(
            requested_rules=tuple(sorted(requested)),
            analyzed_rules=tuple(sorted(evaluated)),
            applicable_rules=tuple(sorted({f.rule_id for f in results})),
            unsupported_rules=tuple(sorted(unsupported)),
            findings=tuple(
                sorted(
                    deduplicate_findings(tuple(results)),
                    key=lambda f: (
                        f.rule_id,
                        f.primary_source.location.file_path,
                        f.primary_source.location.start_line,
                        f.primary_source.location.start_column,
                        str(f.id),
                    ),
                )
            ),
            diagnostics=tuple(
                SecurityDiagnostic(
                    code=c,
                    rule_ids=tuple(sorted(requested)),
                    message="Security analysis limitation; inspect coverage metadata",
                )
                for c in sorted(output.diagnostics)
            ),
            analyzer_version=VERSION,
            analysis_metadata={
                "coverage": coverage,
                "limits": self.limits.model_dump(mode="json"),
                "source_pack_version": VERSION,
                "interprocedural": False,
                "provider_calls": 0,
                "credential_reads": 0,
                "security_effectiveness": "NOT_AVAILABLE",
                "partial": True,
            },
        )


def run_security_analysis(
    context: SecurityAnalysisContext,
    sources: Iterable[SecuritySourceInput],
    limits: FlowLimits | None = None,
) -> SecurityAnalysisResult:
    return SecurityAnalyzerV1(limits).analyze(context, sources)
