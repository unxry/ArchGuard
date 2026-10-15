"""Auditable, deliberately narrow rule-scoped completeness certificates."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.extraction.common import child, text
from archguard.security.domain import SecurityLanguage, SecurityRuleId
from archguard.security.index_v2 import SourceUnit
from archguard.security_benchmark.protocol import Outcome, map_outcome, map_p029_outcome


class CompletenessCertificate(DomainModel):
    version: Literal["security-completeness-v3"] = "security-completeness-v3"
    rule_id: SecurityRuleId
    language: SecurityLanguage
    declared_scope: str
    applicable: bool = Field(default=False, strict=True)
    scope_complete: bool = Field(default=False, strict=True)
    source_coverage_complete: bool = Field(default=False, strict=True)
    sink_coverage_complete: bool = Field(default=False, strict=True)
    call_resolution_complete: bool = Field(default=False, strict=True)
    summary_resolution_complete: bool = Field(default=False, strict=True)
    dataflow_scope_complete: bool = Field(default=False, strict=True)
    framework_model_complete: bool = Field(default=False, strict=True)
    unsupported_constructs_present: bool = Field(default=True, strict=True)
    analysis_failures_present: bool = Field(default=False, strict=True)
    proofs_sufficient: bool = Field(default=False, strict=True)
    reason_codes: tuple[str, ...]
    certificate_status: Literal["COMPLETE", "NOT_PROVEN"] = "NOT_PROVEN"

    @model_validator(mode="after")
    def valid_complete(self) -> Self:
        if self.certificate_status == "COMPLETE" and (
            not all(
                getattr(self, key)
                for key in (
                    "applicable",
                    "scope_complete",
                    "source_coverage_complete",
                    "sink_coverage_complete",
                    "call_resolution_complete",
                    "summary_resolution_complete",
                    "dataflow_scope_complete",
                    "framework_model_complete",
                    "proofs_sufficient",
                )
            )
            or self.unsupported_constructs_present
            or self.analysis_failures_present
        ):
            raise ValueError("incomplete or invalidated negative certificate")
        return self


def certify(
    rule: SecurityRuleId,
    language: SecurityLanguage,
    units: tuple[SourceUnit, ...],
    diagnostics: set[str],
    failed: bool,
) -> CompletenessCertificate:
    blocked = sorted(diagnostics - {"PARTIAL_ANALYSIS"})
    complete = False
    if (
        rule == SecurityRuleId.SEC008
        and language == SecurityLanguage.TYPESCRIPT
        and len(units) == 1
    ):
        statements = units[0].root.named_children
        if len(statements) == 2 and statements[0].type == "import_statement":
            imp, stmt = statements
            clause = next((n for n in imp.named_children if n.type == "import_clause"), None)
            imported = text(child(imp, "source")).strip("\"'")
            alias = clause.named_children[0] if clause and len(clause.named_children) == 1 else None
            call = stmt.named_children[0] if stmt.type == "expression_statement" else None
            func = child(call, "function") if call is not None else None
            args = child(call, "arguments") if call is not None else None
            method = text(child(func, "property")) if func is not None else ""
            literals = args.named_children if args is not None else ()
            algorithm = text(literals[0]).strip("\"'").lower() if literals else ""
            complete = bool(
                imported in {"crypto", "node:crypto"}
                and alias is not None
                and alias.type == "identifier"
                and call is not None
                and call.type == "call_expression"
                and func is not None
                and func.type == "member_expression"
                and text(child(func, "object")) == text(alias)
                and literals
                and all(n.type == "string" for n in literals)
                and (
                    method == "createHash"
                    and len(literals) == 1
                    and algorithm in {"sha256", "sha384", "sha512", "sha3-256", "sha3-512"}
                    or method == "createCipheriv"
                    and len(literals) == 3
                    and algorithm in {"aes-128-gcm", "aes-192-gcm", "aes-256-gcm"}
                )
                and not blocked
                and not failed
            )
    return CompletenessCertificate(
        rule_id=rule,
        language=language,
        declared_scope="Entire supplied source restricted to one default crypto import and one "
        "direct literal-only secure algorithm selection; no callbacks, branches or other calls",
        applicable=complete,
        scope_complete=complete,
        source_coverage_complete=complete,
        sink_coverage_complete=complete,
        call_resolution_complete=complete,
        summary_resolution_complete=complete,
        dataflow_scope_complete=complete,
        framework_model_complete=complete,
        unsupported_constructs_present=not complete,
        analysis_failures_present=failed,
        proofs_sufficient=complete,
        reason_codes=("CLOSED_LITERAL_CRYPTO_SCOPE",)
        if complete
        else tuple(blocked) or ("COMPLETENESS_NOT_PROVEN",),
        certificate_status="COMPLETE" if complete else "NOT_PROVEN",
    )


def map_v3_outcome(result: dict[str, Any], rule: str, language: str) -> Outcome:
    """Versioned certificate intake, using the unchanged frozen P030 outcome adapter."""
    original = map_p029_outcome(result, rule)
    if original != Outcome.PARTIAL:
        return original
    value = result["analysis_metadata"].get("completeness_certificates", {}).get(rule)
    if value is None:
        return original
    certificate = CompletenessCertificate.model_validate(value)
    if certificate.rule_id.value != rule or certificate.language.value != language:
        raise ValueError("certificate rule/language mismatch")
    if certificate.certificate_status != "COMPLETE":
        return original
    if any(d["code"] != "PARTIAL_ANALYSIS" for d in result.get("diagnostics", ())):
        raise ValueError("diagnostic invalidates completeness")
    return map_outcome((), "COMPLETE", certificate.applicable)
