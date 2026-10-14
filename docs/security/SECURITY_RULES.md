# Security rules — sec-rule-registry-v1

Authoritative Security contract: `archguard.security.rules.canonical_rules()` and the frozen `experiments/security/security-foundation-v1/sec-rule-registry.json`. These SEC identities belong to the separate post-thesis product extension.

Historical `docs/architecture/FINDING_CATALOG.md` contains unimplemented reserved SEC placeholders with different labels. P027 explicitly establishes the requested canonical meanings below; that historical scientific document remains unchanged. Consumers must use the versioned SEC registry. This does not change ARCH IDs or the frozen Architecture Hybrid.

All 10 rules: CONTRACT_FROZEN; Java/TypeScript contracts; default severity=null; detector IDs empty. No detector is implemented by P027. A declared evidence requirement is a future dependency, not an implemented capability.

| ID | Canonical name | Expected evidence | Severity default | Status | Languages |
| --- | --- | --- | --- | --- | --- |
| SEC001 | Hardcoded Secret | LEXICAL_STATIC, AST_STATIC, CONFIGURATION | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC002 | SQL Injection Risk | AST_STATIC, CALL_GRAPH, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC003 | Command Injection Risk | AST_STATIC, CALL_GRAPH, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC004 | Path Traversal Risk | AST_STATIC, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC005 | Unsafe Deserialization | AST_STATIC, CALL_GRAPH, SEMANTIC_CONTEXT, DATAFLOW | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC006 | Server-Side Request Forgery Risk | AST_STATIC, CALL_GRAPH, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC007 | Cross-Site Scripting Risk | AST_STATIC, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC008 | Weak Cryptography | AST_STATIC, CALL_GRAPH, SEMANTIC_CONTEXT, CONFIGURATION | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC009 | Insecure Randomness | AST_STATIC, CALL_GRAPH, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |
| SEC010 | Unsafe Dynamic Code Execution | AST_STATIC, CALL_GRAPH, DATAFLOW, TAINT_FLOW, SEMANTIC_CONTEXT | null | CONTRACT_FROZEN | JAVA, TYPESCRIPT |

## SEC001 — Hardcoded Secret

Credible embedded credentials, tokens, API keys or private-key material in source/configuration.

Limit: Arbitrary literals are not secret evidence; no secret entropy or validity detector yet.

False-positive risk: Examples, placeholders and test fixtures may resemble credentials.

False-negative risk: Indirect, encrypted or externally assembled secrets may be missed.

Generic remediation guidance: Remove embedded secret material and use an appropriate secret-management boundary.

## SEC002 — SQL Injection Risk

Untrusted data reaches SQL construction/execution without recognized safe parameterization.

Limit: SQL text alone is insufficient; source/sink and parameterization semantics are required.

False-positive risk: Query text with safe bound parameters can resemble unsafe construction.

False-negative risk: Framework wrappers and interprocedural flows require additional modeling.

Generic remediation guidance: Use parameterized queries and verify the actual driver/framework boundary.

## SEC003 — Command Injection Risk

Untrusted data reaches process/shell execution without an adequate safety boundary.

Limit: Constant process execution alone is insufficient; shell/argument semantics matter.

False-positive risk: Constant commands and appropriately restricted argument lists can look suspicious.

False-negative risk: Indirect process APIs, wrappers and platform-specific shells may be missed.

Generic remediation guidance: Restrict executable and arguments and avoid unnecessary shell interpretation.

## SEC004 — Path Traversal Risk

Untrusted path/file input reaches filesystem operations without normalization/confinement.

Limit: A file call alone is insufficient; normalization is not by itself proof of confinement.

False-positive risk: Trusted paths and checked confinement boundaries can resemble unsafe access.

False-negative risk: Symlinks, encoded paths and cross-function validation need additional analysis.

Generic remediation guidance: Validate, normalize and confine paths to the intended authorized location.

## SEC005 — Unsafe Deserialization

Known unsafe object deserialization or security-relevant deserialization of untrusted data.

Limit: Ordinary JSON parsing is not automatically unsafe object deserialization.

False-positive risk: Constrained formats and trusted inputs can be mistaken for unsafe deserialization.

False-negative risk: Custom serializers and framework-specific object instantiation may be missed.

Generic remediation guidance: Use constrained formats and review trust, object types and deserialization settings.

## SEC006 — Server-Side Request Forgery Risk

Attacker-controlled URL/host reaches server-side outbound network sinks without restriction.

Limit: Constant outbound HTTP is insufficient; URL/host control and effective restrictions matter.

False-positive risk: Constant or adequately allowlisted requests can resemble SSRF sinks.

False-negative risk: Redirects, DNS resolution and indirect client wrappers require extra modeling.

Generic remediation guidance: Restrict outbound destinations and verify redirects, resolution and trust boundaries.

## SEC007 — Cross-Site Scripting Risk

Untrusted content reaches HTML/DOM rendering without adequate escaping/sanitization.

Limit: Generic output is insufficient; escaping is framework and rendering-context specific.

False-positive risk: Automatically escaped templates and context-aware sanitizers can appear unsafe.

False-negative risk: Dynamic rendering, template composition and framework behavior may be missed.

Generic remediation guidance: Use context-appropriate escaping/sanitization and review the actual rendering sink.

## SEC008 — Weak Cryptography

Explicitly weak or security-inappropriate cryptographic primitives in sensitive contexts.

Limit: Ordinary non-security checksums are not automatically security findings.

False-positive risk: Non-security checksums and compatibility-only uses may resemble weak cryptography.

False-negative risk: Indirect primitive selection and configuration-dependent behavior may be missed.

Generic remediation guidance: Select appropriate cryptographic primitives and review security-sensitive configuration.

## SEC009 — Insecure Randomness

Non-cryptographic randomness is used for security-sensitive tokens, secrets or nonces.

Limit: Ordinary simulation or UI randomness is insufficient evidence of security risk.

False-positive risk: Non-security randomization may appear sensitive without usage context.

False-negative risk: Indirect token construction or custom randomness providers may be missed.

Generic remediation guidance: Use cryptographically secure randomness for security-sensitive values.

## SEC010 — Unsafe Dynamic Code Execution

Attacker-controlled or insufficiently constrained data reaches dynamic code evaluation.

Limit: Constant and tightly constrained evaluation require distinct contextual treatment.

False-positive risk: Constant expressions or effectively constrained evaluation may resemble unsafe execution.

False-negative risk: Custom evaluators, generated expressions and interprocedural constraints may be missed.

Generic remediation guidance: Avoid unnecessary dynamic evaluation and strictly constrain permitted inputs and behavior.

Regex or AST patterns alone do not solve SQL/command injection, traversal, SSRF, XSS or unsafe dynamic execution in general. Source-to-sink, context, safety boundaries, framework semantics and conservative uncertainty are required. JSON parsing, SQL text, constant commands/HTTP calls, file calls, ordinary randomness and non-security checksums alone are insufficient.

No complete Java/Spring/Node/Express API model, Security ground truth, Security benchmark or Security Precision/Recall/F1 exists. Engineering fixture tests verify contracts only. No CVSS compliance, exploitable-vulnerability guarantee or numeric probability is claimed.

## P028 executable scope

The P027 contract above is historical and unchanged. The separate
[Security analysis V1](SECURITY_ANALYSIS_V1.md) documents executable detectors,
partial API/dataflow coverage and diagnostics. P028 receipts are versioned under
`experiments/security/security-static-dataflow-v1/`; historical P027 artifacts remain frozen.
No Architecture/Hybrid behavior, effectiveness claims, HTTP API or persistence is changed.

## P029 V2 scope

The separately versioned [Security analysis V2](SECURITY_ANALYSIS_V2.md) adds bounded
call summaries, field aliases and tested framework/proof subsets. P027 meanings and
P028 JSON/source/fixture history remain frozen. P029 does not change Architecture/Hybrid,
create a Security effectiveness benchmark, call a provider or start P030/UI.
