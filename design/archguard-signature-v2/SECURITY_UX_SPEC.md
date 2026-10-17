# Security investigation

The workspace separates rule coverage, finding outcome, evidence strength, proof continuity and evaluated scope. The permanent statement is that zero findings does not establish repository safety. No vulnerability rate, recall, effectiveness score or CVSS is invented.

## Layout and interaction

The coverage rail contains SEC001–010 in the authored demo and exactly the requested rules for imports. Each item has a text outcome and a state indicator. Selecting a rule opens its scope, diagnostics context and findings. Multiple findings for one rule remain individually selectable. Findings show supplied severity/status, analyzer channel, evidence strength, evidence references and source coordinates. Missing source text is an explicit state; selecting a file coordinate does not read the local filesystem.

SEC002 demo shows request source → local construction → SQL sink. SEC006 shows a potential SSRF path with an unknown boundary; SEC007 retains insufficient evidence. These are synthetic examples. Path movement in Atlas is a static architecture relation, not a taint execution trace. Security path steps are independently rendered from `flow.steps` and evidence references; no arbitrary join to module graph.

## Outcome invariants

| Outcome | Meaning / visual behavior |
| --- | --- |
| CONFIRMED_PATTERN / SUPPORTED | Positive evidence inside the stated bounded analysis, not proof of exploitable production behavior |
| POTENTIAL | A plausible issue with unresolved obligations; unknown step is dashed and explicitly labelled |
| INSUFFICIENT_EVIDENCE | Evidence cannot support the stronger conclusion; never promoted to confirmed |
| PARTIAL | Incomplete scope, including supported V2 runs with no findings |
| UNSUPPORTED | Capability/rule not evaluated in this implementation |
| FAILED | Execution failure takes priority over unsupported/empty presentation |
| NOT_APPLICABLE | Supplied finding result; separate from unsupported |
| Scoped negative | Demo certificate is visibly synthetic and limited to SEC008 TypeScript V3 grammar |

Imported certificate metadata is shown as **reported, not revalidated**. Browser validation checks structure/reference consistency; it does not reconstruct AST proofs or authenticate provenance. Therefore an imported empty result remains partial rather than becoming a verified negative. Full engine-backed certificate verification is an integration task. Claimed scope is retained for inspection, not widened.

`UNKNOWN_FLOW`, incomplete flow uncertainty, interprocedural boundaries and evidence references are preserved. Incomplete paths cannot claim SUPPORTED; complete paths cannot contain unknown roles. Confidence is not substituted for Security `evidence_strength`.

## Evidence and data limits

SecurityFinding has its own schema, repository/snapshot IDs, language and analyzer version. Result partition checks requested/analyzed/applicable/unsupported relationships. V1/V2/V3 are version-sensitive; Java and TypeScript support is bounded. No generalized JavaScript/TSX Security support is implied. Diagnostics and original metadata remain available in Runs/export. Canonical backend model validation of three authored V2 artifacts passed; no real repository was scanned for this design task.

Browser evidence: `security-supported.png`, `security-unknown.png`, `security-scoped-certificate.png`, `mobile-security.png`; regression receipt in `previews/browser-report.json`.
