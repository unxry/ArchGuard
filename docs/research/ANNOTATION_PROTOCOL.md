# Independent blinded annotation protocol v1

Ground truth must come from actual human source inspection, documented boundaries/responsibilities and
manually verified dependencies. Static Finding, GraphCandidate, SemanticCandidate, V2 prediction and
HybridDecision cannot become annotation truth. No reviewers or labels are invented by this foundation.

## Independent sampling and blinding

Frozen protocol seed 12012, five unique CLASS/INTERFACE/FUNCTION locators per repository. Rank the whole
source-derived IAM universe by raw dependency degree into LOW/MEDIUM/HIGH count terciles (ties use
locator hash), then round-robin select by SHA256(seed,repository,locator). Include low-degree controls
and unknown/ambiguous responsibilities; no candidate presence/model/AI score enters the sampler.
Terciles can contain equal degree values and do not imply defect thresholds. Test/helper declarations
can appear because the frozen frame includes eligible source, not only suspected production components.

Selected subjects receive ARCH201–205 questions in fixed order, one per question per repository.
Questions address documented responsibility mismatch, business logic beyond delegation, infrastructure
leakage, misplaced components and cross-boundary responsibility. A controller-specific question may be
OUT_OF_SCOPE for a library component. Without documented role/placement, UNCERTAIN is appropriate.
This sample is not promised binary-balanced. Scope is exactly repository + locator + question;
non-annotated predictions are OUT_OF_SCOPE, in-scope unreviewed subjects are NOT_ANNOTATED, never NEGATIVE.

40 packets / 20 Java / 20 TypeScript / 8 per question; LOW=16, MEDIUM=16, HIGH=8.
Sample fingerprint `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`. Corpus/sample freezes precede human labels and all
real AI. Packet DTO is extra-forbid, carries only subject/question/license/instructions/hash/line
references. No candidate/model/AI/Hybrid output or V2 artifact fingerprint is shown. Export takes only
sample + source cache; it has no private-analysis path. Private Graph/Discovery artifacts cannot enter
human export. Changing mock inference metadata does not change frame/sample. Source snippets are local.

## Human workflow

Read each Markdown packet and pinned project docs/source. Edit only reviewer_id, label, rationale,
uncertainty and attestation in review-form.json; declaration evidence and case/packet hashes are already
filled. Add referenced evidence where needed. Submit only completed rows; remove untouched forms from
reviews. Use a pseudonymous actual reviewer ID and HUMAN_REVIEW_COMPLETED only after real inspection.
These declarations are process attestations, not cryptographic proof of a real person's review.

Labels: POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE. Binary labels require nonempty rationale and a
concrete frozen evidence reference. CLEAR/AMBIGUOUS is annotator metadata, not detector confidence.
Context includes declaration plus bounded direct dependencies/dependents and README/documented evidence:
<=7 files, <=128 KiB excerpts, <=240 lines each. Bounds are validated against actual file lines/hashes.
If context is insufficient, inspect more pinned source and request a separately versioned packet with
additional hash/line references; do not force a binary answer. Schema versions are
oss-annotation-packet-v1 and oss-annotation-result-v1, with separate fingerprints.

## Review and adjudication

No rows -> UNREVIEWED/NOT_ANNOTATED. One actual review -> SINGLE_REVIEW/provisional label. Two distinct
reviewers agreeing -> DOUBLE_REVIEW. Disagreement -> ADJUDICATION_REQUIRED/NOT_ANNOTATED until explicit
third independent adjudicator decision -> ADJUDICATED. Store both reviews separately, never overwrite;
previous imported result is replay-validated against actual review history. Unknown case, wrong sample,
wrong packet/source hash, fake subject, missing labels/evidence, duplicate reviewer or fake transition
are rejected. Export independent forms before reviewers see each other's completed labels.

Raw agreement and Cohen's kappa use paired categorical cases from two actual reviewers only;
no paired cases or kappa's zero denominator yields null. No real agreement value exists now.
Future readiness criterion is DOUBLE_REVIEW agreement or ADJUDICATED, with explicit task eligibility;
UNCERTAIN/OUT_OF_SCOPE remain excluded from binary evaluation. Single review is not externally validated.
The annotation freeze receipt links corpus freeze, sample and annotation-result fingerprints; a future
separate evaluation receipt must also pin the model. Nothing evaluates V2 or changes Full Hybrid readiness.

## Target architecture and task meaning

Provenance supports DOCUMENTED/MANUALLY_DERIVED/NONE, source hashes/line references, rationale and
review status. Current repositories have NONE: no architecture.yaml was invented from Discovery.
ARCH001–005 require documented constraints; common layered conventions are not a target spec.
Cycle existence is a graph fact; a forbidden cycle violation requires a constraint. ARCH101–105 raw
STRUCTURAL_SIGNAL and human ARCHITECTURAL_QUALITY_JUDGMENT are distinct packet tasks. High coupling
is not automatically a defect. A future threshold-derived structural holdout comparison is secondary
and cannot substantiate the central Hybrid semantic/architectural-quality claim.

Current actual status: all 40 UNREVIEWED, no human reviewer identities or completed labels.
