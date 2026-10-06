# Independent human annotation: quick guide

Inspect pinned source, dependencies and project documentation independently. Never use detector,
AI or model assessments as truth. Case selection does not imply that a violation exists.

- **ARCH201**: Implemented behavior conflicts with a documented or structurally evident intended
  role. Establish the role first.
- **ARCH202**: A controller/presentation component makes substantial business decisions,
  calculations, workflow coordination or state-dependent branches. Mapping, validation,
  delegation and error adaptation alone are insufficient.
- **ARCH203**: Domain/application behavior depends on infrastructure implementation details
  across an established boundary. An abstract interface alone is insufficient.
- **ARCH204**: Placement conflicts with documented or manually justified responsibility
  boundaries. Without such evidence use UNCERTAIN or OUT_OF_SCOPE.
- **ARCH205**: Substantial, architecturally distinct responsibilities are combined. Import count
  alone is insufficient.

**POSITIVE:** applicable question, sufficient context, concrete violation evidence.
**NEGATIVE:** applicable question and sufficient source/context to justify absence of that
violation.
**UNCERTAIN:** insufficient context, ambiguous role/boundary or unresolved interpretation.
**OUT_OF_SCOPE:** the question does not apply (for example, a controller question for a library
utility).
An empty form is unreviewed. UNCERTAIN/OUT_OF_SCOPE are never negatives or true negatives.

For each completed row: (1) inspect source and dependencies; (2) inspect relevant pinned docs;
(3) select a label; (4) write your own rationale; (5) copy exact evidence references from
packets.json;
(6) state CLEAR or AMBIGUOUS uncertainty; (7) set a stable pseudonymous reviewer ID;
(8) attest HUMAN_REVIEW_COMPLETED only after your actual review.
Do not include a name or email. No identity or attestation is assigned by this tool.

Fill review-form.json; submit completed rows only. Leave incomplete rows out of the submitted
copy.
Preserve sample fingerprint, packet fingerprint and packet revision. Evidence ranges may be
narrowed.
For additional pinned source, use request-extra-context before import; it creates a new
immutable
packet revision. Record that revision and its fingerprint in your review. Missing context is a
reason
to request more context or choose UNCERTAIN, never a reason to infer a binary label.

Reviewers A and B must work independently without seeing each other's forms. A first review is
provisional. Two distinct reviewers agreeing resolve a case; disagreement requires a distinct
third
human. To correct an imported review, submit a new row with supersedes_review_id equal to the
active review fingerprint. Earlier decisions remain in the history. No labeled OSS examples are
supplied.
