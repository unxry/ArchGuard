"""Canonical SEC meanings and planned evidence, separate from executable detectors."""

from collections.abc import Iterable
from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString
from archguard.security.domain import (
    EvidenceCapability,
    SecurityLanguage,
    SecurityRuleId,
    SecuritySeverity,
)
from archguard.security.ports import SecurityRuleDetector

REGISTRY_VERSION = "sec-rule-registry-v1"
NAMES = (
    "Hardcoded Secret",
    "SQL Injection Risk",
    "Command Injection Risk",
    "Path Traversal Risk",
    "Unsafe Deserialization",
    "Server-Side Request Forgery Risk",
    "Cross-Site Scripting Risk",
    "Weak Cryptography",
    "Insecure Randomness",
    "Unsafe Dynamic Code Execution",
)


class ImplementationStatus(StrEnum):
    CONTRACT_FROZEN = "CONTRACT_FROZEN"
    FOUNDATION_READY = "FOUNDATION_READY"
    IMPLEMENTED = "IMPLEMENTED"


class SecurityRuleDefinition(DomainModel):
    rule_id: SecurityRuleId
    name: NonEmptyString
    description: NonEmptyString
    severity_default: SecuritySeverity | None = None
    evidence_requirements: tuple[EvidenceCapability, ...] = Field(min_length=1)
    supported_languages: tuple[SecurityLanguage, ...] = Field(min_length=1)
    implementation_status: ImplementationStatus = ImplementationStatus.CONTRACT_FROZEN
    detector_ids: tuple[NonEmptyString, ...] = ()
    limitations: tuple[NonEmptyString, ...] = Field(min_length=1)
    false_positive_risks: tuple[NonEmptyString, ...] = Field(min_length=1)
    false_negative_risks: tuple[NonEmptyString, ...] = Field(min_length=1)
    remediation: NonEmptyString
    references: tuple[NonEmptyString, ...] = ()

    @model_validator(mode="after")
    def frozen_metadata(self) -> Self:
        if self.name != NAMES[list(SecurityRuleId).index(self.rule_id)]:
            raise ValueError("SEC rule canonical name cannot be repurposed")
        if self.description != DEFINITIONS[list(SecurityRuleId).index(self.rule_id)][0]:
            raise ValueError("SEC rule canonical meaning cannot be repurposed")
        for values in (self.evidence_requirements, self.supported_languages, self.detector_ids):
            if len(set(values)) != len(values):
                raise ValueError("duplicate rule metadata")
        if (self.implementation_status == ImplementationStatus.IMPLEMENTED) != bool(
            self.detector_ids
        ):
            raise ValueError("implemented rule requires explicit detector identities")
        return self


# Definitions describe intended evidence routes, not capabilities executed by this stage.
DEFINITIONS = (
    (
        "Credible embedded credentials, tokens, API keys or private-key "
        "material in source/configuration.",
        ("LEXICAL_STATIC", "AST_STATIC", "CONFIGURATION"),
        "Arbitrary literals are not secret evidence; no secret entropy or validity detector yet.",
        "Examples, placeholders and test fixtures may resemble credentials.",
        "Indirect, encrypted or externally assembled secrets may be missed.",
        "Remove embedded secret material and use an appropriate secret-management boundary.",
    ),
    (
        "Untrusted data reaches SQL construction/execution without "
        "recognized safe parameterization.",
        ("AST_STATIC", "CALL_GRAPH", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "SQL text alone is insufficient; source/sink and parameterization semantics are required.",
        "Query text with safe bound parameters can resemble unsafe construction.",
        "Framework wrappers and interprocedural flows require additional modeling.",
        "Use parameterized queries and verify the actual driver/framework boundary.",
    ),
    (
        "Untrusted data reaches process/shell execution without an adequate safety boundary.",
        ("AST_STATIC", "CALL_GRAPH", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "Constant process execution alone is insufficient; shell/argument semantics matter.",
        "Constant commands and appropriately restricted argument lists can look suspicious.",
        "Indirect process APIs, wrappers and platform-specific shells may be missed.",
        "Restrict executable and arguments and avoid unnecessary shell interpretation.",
    ),
    (
        "Untrusted path/file input reaches filesystem operations without "
        "normalization/confinement.",
        ("AST_STATIC", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "A file call alone is insufficient; normalization is not by itself proof of confinement.",
        "Trusted paths and checked confinement boundaries can resemble unsafe access.",
        "Symlinks, encoded paths and cross-function validation need additional analysis.",
        "Validate, normalize and confine paths to the intended authorized location.",
    ),
    (
        "Known unsafe object deserialization or security-relevant "
        "deserialization of untrusted data.",
        ("AST_STATIC", "CALL_GRAPH", "SEMANTIC_CONTEXT", "DATAFLOW"),
        "Ordinary JSON parsing is not automatically unsafe object deserialization.",
        "Constrained formats and trusted inputs can be mistaken for unsafe deserialization.",
        "Custom serializers and framework-specific object instantiation may be missed.",
        "Use constrained formats and review trust, object types and deserialization settings.",
    ),
    (
        "Attacker-controlled URL/host reaches server-side outbound "
        "network sinks without restriction.",
        ("AST_STATIC", "CALL_GRAPH", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "Constant outbound HTTP is insufficient; URL/host control and "
        "effective restrictions matter.",
        "Constant or adequately allowlisted requests can resemble SSRF sinks.",
        "Redirects, DNS resolution and indirect client wrappers require extra modeling.",
        "Restrict outbound destinations and verify redirects, resolution and trust boundaries.",
    ),
    (
        "Untrusted content reaches HTML/DOM rendering without adequate escaping/sanitization.",
        ("AST_STATIC", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "Generic output is insufficient; escaping is framework and rendering-context specific.",
        "Automatically escaped templates and context-aware sanitizers can appear unsafe.",
        "Dynamic rendering, template composition and framework behavior may be missed.",
        "Use context-appropriate escaping/sanitization and review the actual rendering sink.",
    ),
    (
        "Explicitly weak or security-inappropriate cryptographic primitives in sensitive contexts.",
        ("AST_STATIC", "CALL_GRAPH", "SEMANTIC_CONTEXT", "CONFIGURATION"),
        "Ordinary non-security checksums are not automatically security findings.",
        "Non-security checksums and compatibility-only uses may resemble weak cryptography.",
        "Indirect primitive selection and configuration-dependent behavior may be missed.",
        "Select appropriate cryptographic primitives and review security-sensitive configuration.",
    ),
    (
        "Non-cryptographic randomness is used for security-sensitive tokens, secrets or nonces.",
        ("AST_STATIC", "CALL_GRAPH", "SEMANTIC_CONTEXT"),
        "Ordinary simulation or UI randomness is insufficient evidence of security risk.",
        "Non-security randomization may appear sensitive without usage context.",
        "Indirect token construction or custom randomness providers may be missed.",
        "Use cryptographically secure randomness for security-sensitive values.",
    ),
    (
        "Attacker-controlled or insufficiently constrained data reaches dynamic code evaluation.",
        ("AST_STATIC", "CALL_GRAPH", "DATAFLOW", "TAINT_FLOW", "SEMANTIC_CONTEXT"),
        "Constant and tightly constrained evaluation require distinct contextual treatment.",
        "Constant expressions or effectively constrained evaluation may resemble unsafe execution.",
        "Custom evaluators, generated expressions and interprocedural constraints may be missed.",
        "Avoid unnecessary dynamic evaluation and strictly constrain "
        "permitted inputs and behavior.",
    ),
)


def canonical_rules() -> tuple[SecurityRuleDefinition, ...]:
    return tuple(
        SecurityRuleDefinition(
            rule_id=rule,
            name=name,
            description=d[0],
            evidence_requirements=tuple(EvidenceCapability(c) for c in d[1]),
            supported_languages=tuple(SecurityLanguage),
            limitations=(d[2],),
            false_positive_risks=(d[3],),
            false_negative_risks=(d[4],),
            remediation=d[5],
        )
        for rule, name, d in zip(SecurityRuleId, NAMES, DEFINITIONS, strict=True)
    )


class SecurityRuleRegistry:
    version = REGISTRY_VERSION

    def __init__(
        self,
        rules: Iterable[SecurityRuleDefinition] | None = None,
        detectors: Iterable[SecurityRuleDetector] = (),
    ) -> None:
        self._rules: dict[SecurityRuleId, SecurityRuleDefinition] = {}
        self.detectors = tuple(detectors)
        registrations = {d.registration.id: d.registration for d in self.detectors}
        if len(registrations) != len(self.detectors):
            raise ValueError("duplicate detector identity")
        for rule in canonical_rules() if rules is None else rules:
            rule = SecurityRuleDefinition.model_validate(rule)
            if rule.rule_id in self._rules:
                raise ValueError("duplicate SEC rule identity")
            for detector_id in rule.detector_ids:
                registration = registrations.get(detector_id)
                if registration is None or rule.rule_id not in registration.supported_rule_ids:
                    raise ValueError("implemented detector missing or rule not declared")
            self._rules[rule.rule_id] = rule
        for detector in self.detectors:
            if not callable(detector.analyze):
                raise ValueError("detector must provide an executable analyze method")
            for rule_id in detector.registration.supported_rule_ids:
                declared = self._rules.get(rule_id)
                if declared is None or detector.registration.id not in declared.detector_ids:
                    raise ValueError("detector claims an undeclared or unimplemented rule")
                if not set(detector.registration.supported_languages) <= set(
                    declared.supported_languages
                ):
                    raise ValueError("detector claims undeclared language support")

    def all(self) -> tuple[SecurityRuleDefinition, ...]:
        return tuple(self._rules[r] for r in sorted(self._rules))

    def get(self, rule_id: SecurityRuleId | str) -> SecurityRuleDefinition:
        return self._rules[SecurityRuleId(rule_id)]

    def for_language(self, language: SecurityLanguage) -> tuple[SecurityRuleDefinition, ...]:
        return tuple(r for r in self.all() if language in r.supported_languages)

    def for_capability(self, capability: EvidenceCapability) -> tuple[SecurityRuleDefinition, ...]:
        return tuple(r for r in self.all() if capability in r.evidence_requirements)
