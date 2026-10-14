# Security extension architecture

Architecture is SCIENTIFIC_CORE_COMPLETE (P026). Security is FOUNDATION_READY; SEC001–SEC010 are
CONTRACT_FROZEN. Concrete detector set is empty. UI is NOT_STARTED. This is a separate product
extension; frozen P001–P026 architecture evidence, RQs, hypothesis and A1–A7 metrics do not change.

Generic parsing/IAM infrastructure feeds sibling Architecture and Security domains. Security reads
existing IAM and source references; it does not fork IAM, mutate parser semantics, import the
Architecture Hybrid, fit an architecture model or create an ARCH+SEC score. Architecture, benchmark
and calibration code cannot import Security. Import/dependency tests and hashes bind this boundary.

`security/domain.py` defines SEC-only SecurityFinding, SecurityEvidence, source references, flow
contracts, diagnostics, coverage and the distinct SECURITY report section. Finding identity is UUID5
of repository/snapshot, rule, concrete primary/sink source and flow; prose, severity and detector
version do not determine identity. Evidence references must resolve, primary locations must be bound,
languages/analysis versions must match, and flow uncertainty is explicit. Identical same-ID findings
collapse; conflicting same-ID findings fail pending an explicit future merge policy.

Severity INFO/LOW/MEDIUM/HIGH/CRITICAL is independent from qualitative LOW/MEDIUM/HIGH evidence
strength. CONFIRMED_PATTERN confirms only the cited pattern, not exploitability. SUPPORTED denotes
an evidence-supported risk within the declared context. POTENTIAL needs further confirmation;
INSUFFICIENT_EVIDENCE marks uncertainty; NOT_APPLICABLE denotes lack of relevant applicability.
There is no numeric confidence, Architecture H2 probability or CVSS model. Remediation is optional,
static generic guidance, never LLM-generated or claimed universally sufficient.

`security/ports.py` defines a detector's stable identity/version, explicit rule/language/capability
scope and typed result. Registration rejects duplicate identities, undeclared scopes and rules that
claim an absent executable detector. The analyzer validates context, result scope, source bindings
and output versions, and narrows each detector to requested rules. Supplied IAM is revalidated and
passed through a separate context snapshot. No production detector is registered in P027.

`security/analysis.py` returns zero findings, zero evaluated/applicable rules, all requested rules
unsupported and a RULE_NOT_EVALUATED diagnostic. An empty requested rule set stays empty. Evaluated,
applicable, unsupported, candidate evidence and emitted findings are different concepts. No emitted
finding does not mean that code is secure. SecuritySummary metadata is separate from Architecture
findings and Hybrid summaries; no combined score or overloaded namespace is introduced.

`security/dataflow.py` contains only typed source/sink/sanitizer/sensitive-API registry mechanics.
The production registry is empty; synthetic entries test mechanics only. FlowPath defines source,
propagation, sanitizer, sink, interprocedural boundary and unknown flow, with explicit uncertainty.
No taint solver, interprocedural analysis, sanitizer recognizer or sink/source discovery is implemented.

Configuration references explicitly name JSON/YAML/PROPERTIES/ENV_ASSIGNMENT categories. No file
intake is widened and no configuration file or API credential is read. Source/test/example/generated/
vendor categories are metadata only; no automatic exclusion heuristic or secret scanning exists.
Evidence carries references, not raw secret values. Future detectors must redact secret-bearing
content rather than serialize it into summaries or metadata.

The existing HTTP API exposes health/system metadata, not analysis findings, so no endpoint/OpenAPI
or persistence change is required. Security contracts serialize independently without changing
Architecture responses. Persistence and Alembic migration: NOT_REQUIRED_P027. No new infrastructure,
provider prompts, live LLM calls, paid preflight, benchmark or UI is introduced.

Protocol versions: security-foundation-v1, sec-rule-registry-v1, empty-detector-set-v1,
security-api-registry-v1 and security-dataflow-contract-v1. The public foundation manifest, capability
matrix and boundary receipt bind implementation/schema hashes and unchanged P025/P026 evidence.

P028 may implement tested applicable static/dataflow evidence with its own scope and gates. P027
stops at READY_FOR_P028_SECURITY_STATIC_AND_DATAFLOW_ANALYSIS and does not start P028.
