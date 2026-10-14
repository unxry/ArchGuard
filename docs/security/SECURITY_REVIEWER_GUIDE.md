# Security reviewer guide — independent human review

Review only the supplied static evidence and target SEC rule. These are inert source examples; do not execute them, install libraries, call URLs or validate credential-shaped values against services. All embedded values were fabricated; assess source-level credential embedding according to the rule rather than treating synthetic provenance as an automatic negative.

Select POSITIVE when sufficient source evidence supports the rule, NEGATIVE when the rule applies and evidence supports absence of that finding, UNCERTAIN when evidence cannot support reliable binary judgment, or OUT_OF_SCOPE when the case cannot be judged under its declared language/framework/rule scope. A missing external/custom implementation can justify uncertainty; do not guess a wrapper contract. Ordinary JSON is not automatically unsafe object deserialization. Consider only this target rule, not incidental issues or exploitability claims.

Use your assigned slot A or B, opaque case ID, label and completed=true. Optional rationale/evidence_note can cite file and line plus source, sink, trust boundary or restriction. No name, PII or confidence field is requested. Do not use AI/LLM/Astra to generate labels/rationales. Do not discuss or exchange responses with the other reviewer before both initial submissions lock. Return each case exactly once to your independent response destination; validate against review-response.schema.json. Do not infer a label from case ordering or detector behavior. You should receive only your own evidence directory, this guide and schemas.

## Rule criteria

### SEC001 — Hardcoded Secret

Credible embedded credentials, tokens, API keys or private-key material in source/configuration.

Identify credible credential/token/key embedding and its use; distinguish public identifiers, checksums, placeholders and ordinary labels. Do not test credential validity.

### SEC002 — SQL Injection Risk

Untrusted data reaches SQL construction/execution without recognized safe parameterization.

Follow untrusted data into executable SQL structure. Distinguish actual driver bind parameters from string building, query text alone and an unknown wrapper.

### SEC003 — Command Injection Risk

Untrusted data reaches process/shell execution without an adequate safety boundary.

Follow untrusted input to executable, shell command or arguments. Distinguish shell interpolation from separate argv; absence of a shell does not automatically constrain dangerous executable/argument semantics.

### SEC004 — Path Traversal Risk

Untrusted path/file input reaches filesystem operations without normalization/confinement.

Follow path data to a file sink and review the authorized root, canonicalization, dominating containment check and exact checked variable. Normalization alone is not confinement; no symlink/race runtime evidence is supplied.

### SEC005 — Unsafe Deserialization

Known unsafe object deserialization or security-relevant deserialization of untrusted data.

Judge trust and object-deserialization semantics. ObjectInputStream/readObject and opaque custom object loaders require different evidence from JSON trees or plain string construction. Language-specific scope can justify OOS, but do not infer it from detector support.

### SEC006 — Server-Side Request Forgery Risk

Attacker-controlled URL/host reaches server-side outbound network sinks without restriction.

Follow URL/host control to outbound HTTP and inspect exact parsed host restrictions, checked/sink variable identity and pseudo-allowlists. Runtime DNS, redirect and full network policy are not shown.

### SEC007 — Cross-Site Scripting Risk

Untrusted content reaches HTML/DOM rendering without adequate escaping/sanitization.

Follow untrusted content to actual HTML interpretation. Distinguish text output, constant HTML, recognized sanitizer output and recontamination. Unknown render wrappers require their supplied evidence rather than a name-based inference.

### SEC008 — Weak Cryptography

Explicitly weak or security-inappropriate cryptographic primitives in sensitive contexts.

Judge security-sensitive cryptographic purpose and explicit algorithm/mode. Distinguish DES/RC4/ECB or weak password/signature hashing from strong choices and nonsecurity checksums; algorithm strings alone are insufficient.

### SEC009 — Insecure Randomness

Non-cryptographic randomness is used for security-sensitive tokens, secrets or nonces.

Judge randomness receiving purpose such as session/reset token versus simulation/sampling. Review the supplied RNG semantics and helper/field flow; random use alone does not establish a security finding.

### SEC010 — Unsafe Dynamic Code Execution

Attacker-controlled or insufficiently constrained data reaches dynamic code evaluation.

Follow input into evaluated script/dynamic code and distinguish constants, reflection and opaque wrappers. A reflective name alone does not prove eval-like execution.

## Conflicts and evidence limits

Initial labels and rationales remain locked. Agreement (including UNCERTAIN/OOS) is preserved. Disagreements go to a separate real human adjudicator with case evidence and both locked rationales. Detector output, generator construction intent and AI labels cannot break ties. There is no answer key in this guide. P030 has collected no human responses and establishes no effectiveness result.
