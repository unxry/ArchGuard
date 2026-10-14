"""V2 application entry point. Callers supply classified source bytes, never traversal internals."""

import hashlib
from collections.abc import Iterable
from uuid import uuid5

from pydantic import TypeAdapter

from archguard.core.identifiers import EvidenceId
from archguard.core.model.types import JsonObject
from archguard.parsing.config import ParserConfig
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.api_v1 import supported_rules
from archguard.security.domain import (
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
from archguard.security.engine_v1 import Candidate
from archguard.security.engine_v2 import InterproceduralEngine, V2Candidate
from archguard.security.flow_v1 import TraceStep
from archguard.security.index_v2 import DeclarationIndex, SourceUnit
from archguard.security.ports import DetectorRegistration, DetectorResult
from archguard.security.rules import ImplementationStatus, SecurityRuleRegistry, canonical_rules
from archguard.security.summaries_v2 import VERSION, SummaryCache, V2Limits, fingerprint


def make_finding(
    candidate: Candidate, context: SecurityAnalysisContext, path: tuple[TraceStep, ...] = ()
) -> SecurityFinding:
    extra = candidate.supporting_steps if isinstance(candidate, V2Candidate) else ()
    steps = (
        (*path, TraceStep(FlowRole.SINK, candidate.source, candidate.api_id))
        if path
        else extra or (TraceStep(FlowRole.SINK, candidate.source, candidate.api_id),)
    )
    kinds = {
        FlowRole.SOURCE: SecurityEvidenceKind.DATAFLOW_SOURCE,
        FlowRole.PROPAGATION: SecurityEvidenceKind.DATAFLOW_STEP,
        FlowRole.SANITIZER: SecurityEvidenceKind.SANITIZER,
        FlowRole.SINK: SecurityEvidenceKind.DATAFLOW_SINK,
        FlowRole.INTERPROCEDURAL_BOUNDARY: SecurityEvidenceKind.CALL_SITE,
    }
    evidence = tuple(
        SecurityEvidence(
            id=EvidenceId(
                uuid5(
                    context.snapshot_id,
                    f"{candidate.rule}:{s.role}:{s.source.model_dump_json()}:{s.api_id}",
                )
            ),
            kind=kinds[s.role]
            if path
            else SecurityEvidenceKind.RANDOMNESS_CALL
            if candidate.rule == SecurityRuleId.SEC009
            else SecurityEvidenceKind.CRYPTO_CALL
            if candidate.rule == SecurityRuleId.SEC008
            else SecurityEvidenceKind.AST_PATTERN,
            source=s.source,
            summary="Embedded credential [REDACTED]"
            if candidate.rule == SecurityRuleId.SEC001
            else s.api_id,
            analysis_version=VERSION,
            metadata={"step_kind": s.api_id},
        )
        for s in steps
    )
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
    rule = SecurityRuleRegistry().get(candidate.rule)
    return SecurityFinding(
        id=finding_identity(
            context.repository_id,
            context.snapshot_id,
            candidate.rule,
            candidate.source,
            candidate.source if path else None,
            flow,
        ),
        repository_id=context.repository_id,
        snapshot_id=context.snapshot_id,
        rule_id=candidate.rule,
        title=rule.name,
        description="Bounded Security V2 evidence; inspect declared scope and referenced locations",
        severity=SecuritySeverity.MEDIUM
        if candidate.status == SecurityFindingStatus.POTENTIAL
        or candidate.rule in {SecurityRuleId.SEC008, SecurityRuleId.SEC009}
        else SecuritySeverity.HIGH,
        evidence_strength=EvidenceStrength.MEDIUM
        if candidate.status == SecurityFindingStatus.POTENTIAL
        else EvidenceStrength.HIGH,
        status=candidate.status,
        language=context.language,
        primary_source=candidate.source,
        evidence=unique,
        evidence_refs=tuple(e.id for e in unique),
        source_ref=evidence[0].id if path else None,
        sink_ref=evidence[-1].id if path else None,
        flow=flow,
        remediation=rule.remediation,
        metadata={"detector_id": candidate.rule.value.lower() + "-v2", "raw_values": "OMITTED"},
        analyzer_version=VERSION,
    )


class V2Detector:
    def __init__(self, rule: SecurityRuleId, candidates: tuple[Candidate, ...]) -> None:
        self.rule, self.candidates = rule, candidates

    @property
    def registration(self) -> DetectorRegistration:
        return DetectorRegistration(
            id=self.rule.value.lower() + "-v2",
            version=VERSION,
            supported_rule_ids=(self.rule,),
            supported_languages=(SecurityLanguage.JAVA,)
            if self.rule == SecurityRuleId.SEC005
            else tuple(SecurityLanguage),
            required_capabilities=frozenset(),
        )

    def analyze(self, context: SecurityAnalysisContext, /) -> DetectorResult:
        results: list[SecurityFinding] = []
        for c in self.candidates:
            if c.rule == self.rule:
                results.extend(
                    make_finding(c, context, p) for p in c.value.paths
                ) if c.value else results.append(make_finding(c, context))
        return DetectorResult(
            evaluated_rules=(self.rule,), applicable_rules=(self.rule,), findings=tuple(results)
        )


class SecurityAnalyzerV2:
    version = VERSION

    def __init__(self, limits: V2Limits | None = None) -> None:
        self.limits = limits or V2Limits()
        self.cache = SummaryCache()

    def analyze(
        self, context: SecurityAnalysisContext, sources: Iterable[SecuritySourceInput], /
    ) -> SecurityAnalysisResult:
        context = SecurityAnalysisContext.model_validate(context)
        units: list[SourceUnit] = []
        diagnostics = set()
        failed = False
        byte_total = 0
        ids = set()
        paths = set()
        for input_index, source in enumerate(sources):
            byte_total += len(source.source)
            if (
                input_index >= self.limits.max_source_files
                or byte_total > self.limits.max_total_source_bytes
            ):
                failed = True
                diagnostics.add("SOURCE_INTAKE_LIMIT")
                break
            if source.file_id in ids or source.file.relative_path in paths:
                raise ValueError("duplicate V2 source identity/path")
            ids.add(source.file_id)
            paths.add(source.file.relative_path)
            if source.file.language.value != context.language.value:
                failed = True
                diagnostics.add("UNSUPPORTED_LANGUAGE")
                continue
            if context.iam is not None and not any(
                f.id == source.file_id and f.file_path == source.file.relative_path
                for f in context.iam.source_files
            ):
                raise ValueError("V2 source is not bound to supplied IAM")
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
                    failed = True
                    diagnostics.add("SOURCE_PARSE_ERROR")
                    continue
                units.append(
                    SourceUnit(
                        source.file_id,
                        source.file.relative_path,
                        context.language,
                        parsed.tree.root_node,
                        hashlib.sha256(source.source).hexdigest(),
                    )
                )
            except Exception:
                failed = True
                diagnostics.add("SOURCE_ANALYSIS_ERROR")
        supported = set(supported_rules(context.language))
        requested = set(context.requested_rules)
        if not units:
            failed = True
            diagnostics.add("SOURCE_UNAVAILABLE")
        candidates: tuple[Candidate, ...] = ()
        summaries = []
        proofs = []
        call_states = []
        if not failed:
            try:
                index = DeclarationIndex(tuple(sorted(units, key=lambda u: u.path)), self.limits)
                engine = InterproceduralEngine(index, self.limits, self.cache)
                engine.run_all()
                candidates = tuple(engine.output.candidates)
                diagnostics.update(engine.output.diagnostics | index.diagnostics)
                summaries = [s.model_dump(mode="json") for _, s in sorted(engine.summaries.items())]
                proofs = sorted(
                    {
                        p.model_dump_json(): p.model_dump(mode="json") for p in engine.proven
                    }.values(),
                    key=fingerprint,
                )
                call_states = [
                    dict(
                        location=ref.model_dump(mode="json"),
                        state=res.state.value,
                        targets=[str(s.id) for s in res.targets],
                    )
                    for ref, res in sorted(
                        engine.resolutions,
                        key=lambda x: (
                            x[0].location.file_path,
                            x[0].location.start_line,
                            x[0].location.start_column,
                        ),
                    )
                ]
            except Exception:
                failed = True
                diagnostics.add("ANALYSIS_ERROR")
        detectors = tuple(V2Detector(r, candidates) for r in sorted(supported))
        definitions = tuple(
            r.model_copy(
                update={
                    "implementation_status": ImplementationStatus.IMPLEMENTED,
                    "detector_ids": (r.rule_id.value.lower() + "-v2",),
                }
            )
            if r.rule_id in supported
            else r
            for r in canonical_rules()
        )
        SecurityRuleRegistry(definitions, detectors)
        findings: list[SecurityFinding] = []
        evaluated = set()
        failed_rules = set()
        for detector in detectors:
            if detector.rule not in requested:
                continue
            if failed:
                failed_rules.add(detector.rule)
                continue
            try:
                result = DetectorResult.model_validate(detector.analyze(context))
                if result.evaluated_rules != (detector.rule,):
                    raise ValueError("unbound V2 detector coverage")
                for f in result.findings:
                    if (
                        f.repository_id != context.repository_id
                        or f.snapshot_id != context.snapshot_id
                        or f.language != context.language
                        or f.analyzer_version != VERSION
                        or any(e.source.file_id not in ids for e in f.evidence)
                    ):
                        raise ValueError("unbound V2 finding")
                findings = list(deduplicate_findings((*findings, *result.findings)))
                evaluated.add(detector.rule)
            except Exception:
                failed_rules.add(detector.rule)
                diagnostics.add("DETECTOR_ERROR")
        if requested - supported:
            diagnostics.add("UNSUPPORTED_RULE")
        diagnostics.add("PARTIAL_ANALYSIS")
        metadata = TypeAdapter(JsonObject).validate_python(
            dict(
                coverage={
                    r.value: dict(
                        requested=True,
                        supported=r in supported,
                        evaluated=r in evaluated,
                        status="FAILED"
                        if r in failed_rules
                        else "SUPPORTED_PARTIAL_V2_SCOPE"
                        if r in evaluated
                        else "CONTRACT_ONLY",
                    )
                    for r in sorted(requested)
                },
                limits=self.limits.model_dump(mode="json"),
                summaries=summaries,
                proofs=proofs,
                call_resolution=call_states,
                source_pack_version=VERSION,
                interprocedural="BOUNDED_LOCAL_IMPORTED_CONTEXT_SPECIALIZATION",
                provider_calls=0,
                credential_reads=0,
                connectivity_calls=0,
                security_effectiveness="NOT_AVAILABLE",
                partial=True,
            )
        )
        analysis_result = SecurityAnalysisResult(
            requested_rules=tuple(sorted(requested)),
            analyzed_rules=tuple(sorted(evaluated)),
            applicable_rules=tuple(sorted({f.rule_id for f in findings})),
            unsupported_rules=tuple(sorted(requested - evaluated)),
            findings=tuple(
                sorted(
                    findings,
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
                    message="Bounded Security V2 limitation; inspect per-rule coverage",
                )
                for c in sorted(diagnostics)
            ),
            analyzer_version=VERSION,
            analysis_metadata=metadata,
        )
        return analysis_result.model_copy(
            update={
                "analysis_metadata": metadata
                | {"result_fingerprint": fingerprint(analysis_result.model_dump(mode="json"))}
            }
        )


def run_security_analysis(
    context: SecurityAnalysisContext,
    sources: Iterable[SecuritySourceInput],
    limits: V2Limits | None = None,
) -> SecurityAnalysisResult:
    return SecurityAnalyzerV2(limits).analyze(context, sources)
