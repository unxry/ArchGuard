"""Local orchestration with explicit unsupported coverage; default detector set is empty."""

from archguard.security.dataflow import API_REGISTRY_VERSION, DATAFLOW_VERSION
from archguard.security.domain import (
    SECURITY_VERSION,
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecurityDiagnostic,
    SecurityFinding,
    SecurityRuleId,
    deduplicate_findings,
)
from archguard.security.ports import DetectorResult
from archguard.security.rules import SecurityRuleRegistry


class SecurityAnalyzer:
    version = SECURITY_VERSION

    def __init__(self, registry: SecurityRuleRegistry | None = None) -> None:
        self.registry = registry if registry is not None else SecurityRuleRegistry()

    def analyze(self, context: SecurityAnalysisContext, /) -> SecurityAnalysisResult:
        context = SecurityAnalysisContext.model_validate(context)
        requested = set(context.requested_rules)
        for rule in requested:
            self.registry.get(rule)
        evaluated: set[SecurityRuleId] = set()
        applicable: set[SecurityRuleId] = set()
        findings: list[SecurityFinding] = []
        diagnostics = []
        for detector in self.registry.detectors:
            registration = detector.registration
            scope = requested & set(registration.supported_rule_ids)
            if not scope:
                continue
            if context.language not in registration.supported_languages:
                continue
            if not registration.required_capabilities <= context.available_capabilities:
                diagnostics.append(
                    SecurityDiagnostic(
                        code="CAPABILITY_UNAVAILABLE",
                        rule_ids=tuple(sorted(scope)),
                        message="Required evidence capability unavailable",
                    )
                )
                continue
            narrowed = SecurityAnalysisContext.model_validate(
                context.model_dump() | {"requested_rules": tuple(sorted(scope))}
            )
            result = DetectorResult.model_validate(detector.analyze(narrowed))
            if not set(result.evaluated_rules) <= scope or not set(result.applicable_rules) <= set(
                result.evaluated_rules
            ):
                raise ValueError("detector output exceeds declared/requested scope")
            for finding in result.findings:
                finding = SecurityFinding.model_validate(finding)
                if (
                    finding.rule_id not in result.applicable_rules
                    or finding.language != context.language
                    or finding.repository_id != context.repository_id
                    or finding.snapshot_id != context.snapshot_id
                    or finding.analyzer_version != self.version
                    or any(e.source not in context.source_references for e in finding.evidence)
                ):
                    raise ValueError("detector finding has unbound rule/source/context/version")
                findings.append(finding)
            evaluated.update(result.evaluated_rules)
            applicable.update(result.applicable_rules)
        unsupported = requested - evaluated
        if unsupported:
            diagnostics.append(
                SecurityDiagnostic(
                    code="RULE_NOT_EVALUATED",
                    rule_ids=tuple(sorted(unsupported)),
                    message=(
                        "No available executable detector evaluated these rules; "
                        "no security guarantee"
                    ),
                )
            )
        return SecurityAnalysisResult(
            findings=deduplicate_findings(tuple(findings)),
            requested_rules=tuple(sorted(requested)),
            analyzed_rules=tuple(sorted(evaluated)),
            applicable_rules=tuple(sorted(applicable)),
            unsupported_rules=tuple(sorted(unsupported)),
            diagnostics=tuple(diagnostics),
            analyzer_version=self.version,
            analysis_metadata={
                "registry_version": self.registry.version,
                "source_sink_registry_version": API_REGISTRY_VERSION,
                "dataflow_protocol_version": DATAFLOW_VERSION,
                "dataflow_implemented": False,
                "taint_solver_implemented": False,
                "detector_set": {
                    d.registration.id: d.registration.version for d in self.registry.detectors
                },
                "provider_calls": 0,
                "security_effectiveness": "NOT_AVAILABLE",
            },
        )
