# Security human review custody

P031 is currently **P031_HUMAN_ADJUDICATION_REQUIRED**. Both independent Reviewer A/B response sets are complete (300/300), structurally validated and immutably frozen. Human origin and independence are coordinator-attested, with no cryptographic authorship or noncommunication proof.

Canonical per-case destinations are `experiments/security/security-human-review-v1/private/responses/A/` and `experiments/security/security-human-review-v1/private/responses/B/`. Each file contains only reviewer_slot, case_id, label, rationale, evidence_note, completed and uses the frozen P030 packet destination. Workspaces are drafts, never submissions. Aggregate masters/attestations reside separately in private provenance. Never regenerate human answers or normalize their prose.

Mechanically recomputed agreement: 290/300 (96.6666667%); Cohen kappa=0.9408913583165859. There are 10 unresolved disagreements. Kappa describes reviewer agreement; it is not detector accuracy or proof of objective truth. Complete aggregate counts, cross-tabs, stratified distributions and fingerprints are in `experiments/security/security-human-review-v1/public/` and `docs/verification/PROMPT_031.md`.

Only a real independent human may adjudicate. The private `experiments/security/security-human-review-v1/private/adjudication/index.json` lists 10 evidence packets and final response destinations. Read frozen evidence and both locked reviewer answers. Select one of POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE without AI/LLM, construction intent or detector output. Save completed individual responses to the listed private adjudication destinations, according to the adjacent response.schema.json. Do not alter frozen A/B submissions. Coordinator human-origin attestation and a later validation/freeze step are required before truth derivation.

Human adjudications completed=0. Truth 300/DEV/FINAL remains NOT_FROZEN; there is no partial authoritative truth. No detector predictions, effectiveness metrics, provider calls, credential reads or spend were produced. Architecture science, P029 detector semantics and P030 scientific inputs remain frozen. P032 is NOT_STARTED.
