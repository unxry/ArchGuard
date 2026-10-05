from time import monotonic
from uuid import uuid4

from archguard.architecture.discovery.models import ArchitectureDiscoveryResult
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import (
    AIAnalysisConfig,
    AIAnalysisResult,
    AIInvocation,
    ContextDiagnostic,
    LLMUsage,
    SemanticArchitectureCandidate,
)
from archguard.architecture.intelligence.ports import LLMProvider, LLMProviderError, SourceReader
from archguard.architecture.intelligence.prompt import (
    build_request,
    request_metadata,
    validate_response,
)
from archguard.architecture.intelligence.selection import SemanticAnalysisTargetSelector
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.iam.model import ArchitectureModel


class SemanticArchitectureAnalyzer:
    def __init__(self, builder: GraphGuidedContextBuilder | None = None) -> None:
        self.builder = builder or GraphGuidedContextBuilder()

    def analyze(
        self,
        iam: ArchitectureModel,
        graph: GraphAnalysisResult,
        workspace: SourceReader,
        config: AIAnalysisConfig,
        provider: LLMProvider | None = None,
        discovery: ArchitectureDiscoveryResult | None = None,
        spec: ArchitectureSpecification | None = None,
        dry_run: bool = False,
    ) -> AIAnalysisResult:
        if not graph.is_valid or iam.metadata.get("is_valid") is False:
            return AIAnalysisResult(
                status="INVALID",
                targets=(),
                manifests=(),
                request_metadata=(),
                diagnostics=(
                    ContextDiagnostic(
                        code="AI_INVALID_UPSTREAM", message="upstream IAM or graph is invalid"
                    ),
                ),
            )
        targets, skipped = SemanticAnalysisTargetSelector().select(
            iam, graph, discovery, config.targets
        )
        packs = tuple(
            self.builder.build(
                target.node_id, iam, graph, workspace, config.context, spec, discovery
            )
            for target in targets
        )
        requests = tuple(
            build_request(target, pack, config.budget)
            for target, pack in zip(targets, packs, strict=True)
        )
        metadata = tuple(request_metadata(request) for request in requests)
        manifests = tuple(pack.manifest for pack in packs)
        diagnostics = [diagnostic for pack in packs for diagnostic in pack.manifest.diagnostics]
        if skipped:
            diagnostics.append(
                ContextDiagnostic(
                    code="AI_TARGET_BUDGET_EXCEEDED",
                    message="remaining targets omitted by target budget",
                )
            )
        if not graph.is_complete or iam.metadata.get("is_complete") is False:
            diagnostics.append(
                ContextDiagnostic(
                    code="AI_UPSTREAM_INCOMPLETE",
                    message="semantic analysis uses incomplete static structure",
                )
            )
        if dry_run:
            return AIAnalysisResult(
                status="DRY_RUN",
                targets=targets,
                manifests=manifests,
                request_metadata=metadata,
                diagnostics=tuple(diagnostics),
                skipped_targets=skipped,
            )
        unavailable = (
            "AI_PROVIDER_UNAVAILABLE"
            if provider is None
            else "AI_REMOTE_PERMISSION_REQUIRED"
            if provider.capabilities.remote and not config.allow_remote_source
            else "AI_STRUCTURED_OUTPUT_UNAVAILABLE"
            if not provider.capabilities.structured_output
            else None
        )
        if unavailable is not None:
            diagnostics.append(
                ContextDiagnostic(
                    code=unavailable,
                    message="provider configuration or explicit permission is required",
                )
            )
            return AIAnalysisResult(
                status="UNAVAILABLE",
                targets=targets,
                manifests=manifests,
                request_metadata=metadata,
                diagnostics=tuple(diagnostics),
                skipped_targets=skipped + len(targets),
            )
        assert provider is not None
        candidates: list[SemanticArchitectureCandidate] = []
        invocations: list[AIInvocation] = []
        input_tokens = 0
        for target, pack, request in zip(targets, packs, requests, strict=True):
            code = None
            if (
                len(invocations) >= config.budget.max_calls
                or len(candidates) >= config.budget.max_candidates
            ):
                code = "AI_CALL_OR_CANDIDATE_BUDGET_EXCEEDED"
            token_cap = config.budget.max_total_input_tokens
            context_cap = config.context.token_budget
            count = None
            if code is None and (token_cap is not None or context_cap is not None):
                try:
                    count = provider.count_input_tokens(request)
                except Exception:
                    code = "AI_TOKEN_COUNT_FAILURE"
                if code is not None:
                    pass
                elif count is None:
                    code = "AI_TOKEN_BUDGET_UNMEASURABLE"
                elif type(count) is not int or count < 0:
                    code = "AI_TOKEN_COUNT_INVALID"
                elif (token_cap is not None and input_tokens + count > token_cap) or (
                    context_cap is not None and count > context_cap
                ):
                    code = "AI_TOKEN_BUDGET_EXCEEDED"
            if code is not None:
                skipped += 1
                diagnostics.append(
                    ContextDiagnostic(
                        code=code,
                        message="target skipped by analysis budget",
                        subject_node_id=target.node_id,
                    )
                )
                continue
            start = monotonic()
            input_tokens += count or 0
            request_id = None
            usage = LLMUsage()
            diagnostic = None
            actual_provider = provider.provider_id
            actual_model = provider.model_id
            try:
                response = provider.complete_structured(request)
                usage = response.usage
                request_id = response.request_id
                actual_provider, actual_model = response.provider_id, response.model_id
                if token_cap is not None:
                    input_tokens += max(0, (usage.input_tokens or 0) - (count or 0))
                if monotonic() - start > request.timeout_seconds:
                    raise LLMProviderError("AI_PROVIDER_TIMEOUT")
                try:
                    candidates.append(validate_response(iam.project.id, target, pack, response))
                except (ValueError, RecursionError):
                    diagnostic = ContextDiagnostic(
                        code="AI_ANALYSIS_INVALID_RESPONSE",
                        message="provider response failed schema or evidence validation",
                        subject_node_id=target.node_id,
                    )
            except Exception as error:
                # Isolate transport failures without exposing their payload.
                diagnostic = ContextDiagnostic(
                    code=error.code
                    if isinstance(error, LLMProviderError)
                    else "AI_PROVIDER_TIMEOUT"
                    if isinstance(error, TimeoutError)
                    else "AI_PROVIDER_FAILURE",
                    message="provider invocation failed",
                    subject_node_id=target.node_id,
                )
            if diagnostic is not None:
                diagnostics.append(diagnostic)
            invocations.append(
                AIInvocation(
                    invocation_id=uuid4(),
                    target=target,
                    provider_id=actual_provider,
                    model_id=actual_model,
                    provider_request_id=request_id,
                    usage=usage,
                    latency_seconds=monotonic() - start,
                    generation_parameters={
                        "max_output_tokens": request.max_output_tokens,
                        "timeout_seconds": request.timeout_seconds,
                    },
                    diagnostic=diagnostic,
                )
            )
        incomplete = bool(
            skipped
            or any(item.diagnostic for item in invocations)
            or any(item.truncated or item.diagnostics for item in manifests)
            or not graph.is_complete
            or iam.metadata.get("is_complete") is False
        )
        return AIAnalysisResult(
            status="PARTIAL"
            if candidates and incomplete
            else "INCOMPLETE"
            if incomplete
            else "COMPLETE",
            targets=targets,
            manifests=manifests,
            request_metadata=metadata,
            candidates=tuple(candidates),
            invocations=tuple(invocations),
            diagnostics=tuple(diagnostics),
            calls=len(invocations),
            skipped_targets=skipped,
        )
