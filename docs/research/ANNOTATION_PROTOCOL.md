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

Use the final-context catalog and bundles documented in [execution](HUMAN_ANNOTATION_EXECUTION.md).
Historical 013 packets remain immutable. READY_FOR_HUMAN_REVIEW freezes context, not ground truth.
29 active revisions are 2; 11 remain 1. New forms must match the active revision; old drafts/forms
are rejected without copying decisions. All 40 cases remain UNREVIEWED.

Read each Markdown packet and pinned project docs/source. Edit only reviewer_id, label, rationale,
uncertainty and attestation in review-form.json; case/packet hashes are already
filled; evidence selection is empty and must be chosen manually. Submit only completed rows; remove untouched forms from
reviews. Use a pseudonymous actual reviewer ID and HUMAN_REVIEW_COMPLETED only after real inspection.
These declarations are process attestations, not cryptographic proof of a real person's review.

Labels: POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE. Binary labels require nonempty rationale and a
concrete frozen evidence reference. CLEAR/AMBIGUOUS is annotator metadata, not detector confidence.
Context includes declaration plus bounded direct dependencies/dependents and README/documented evidence:
<=7 files and <=128 KiB numbered excerpts. New supplements are <=240 lines per range;
historical ranges are preserved. Aggregate cap is 7×240 lines. Bounds are validated against actual file lines/hashes.
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

Current actual status: ANNOTATION_FROZEN, 39 DOUBLE_REVIEW and 1 ADJUDICATED. Human truth is
P/N/U/OOS=0/32/0/8; binary eligible=32, excluded=8. Two initial humans supplied 80 reviews; a
distinct third human adjudicated the one ARCH202 OOS/NEGATIVE conflict as OUT_OF_SCOPE.
Original A/B exact agreement remains 39/40=97.5%; binary agreement 32/32=100%, kappa null due
to degenerate NEGATIVE-only marginals. The adjudicator is not an additional paired rater.

ANNOTATION_VALID=YES, POSITIVE_CLASS_PRESENT=NO, REAL_AI_EXECUTION_READY=YES,
PRIMARY_BINARY_SEMANTIC_METRICS_READY=NO and PRIMARY_SEMANTIC_EFFECTIVENESS_READY=NO.
Zero positives does not invalidate annotation; this cohort alone cannot support meaningful
violation Recall, positive-class F1 or false-negative rate. Specificity/negative correctness,
abstention/OOS handling, context-mode comparison and resource/false-positive analysis remain
possible in a separately authorized future experiment. Never convert OOS to NEGATIVE or repair
class balance post hoc. A positive-bearing cohort needs a new prospective sampling/freeze protocol.

See the [full lineage freeze](../../experiments/oss/annotation-results/prompt013-f/README.md).
Any annotation correction creates a new explicit version, lineage and freeze. Real AI, Structural
V2 and Hybrid evaluation remain unexecuted; PROMPT 014 is not started by this freeze.
