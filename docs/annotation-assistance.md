# Local source assistance and human draft workflow

Automated evidence summarization reduces annotation burden, but final semantic ground truth
remains human judgment. PROMPT 013.A supplies deterministic source navigation, not ground truth
or an independent human submission. Extraction uses pinned source only, with no detector,
model, previous answer or network call. Generated excerpts and private drafts stay local in the
ignored `experiments/oss/annotation-assistance/` and `experiments/oss/blinded/` directories.

Both reviewers use the same frozen final packets with independently generated assistance,
without seeing each other's answers. Historical bundles, sample identity, original packet catalog and
review store are preserved.

PROMPT 013.C status: **READY_FOR_HUMAN_REVIEW**, 40 packets, zero human reviews/IDs/labels.
The frozen final catalog is `experiments/oss/annotation/review-packet-revisions-final-v1.json`.
Final assistance lives beside the new bundles in `experiments/oss/blinded/prompt013-final-context-v1/`
as `assistance-a/` and `assistance-b/`. These contain third-party excerpts and stay local.
Old drafts/forms are incompatible with updated revisions; nothing migrates automatically.

## Reviewer A assistance

Generate the immutable package:

```sh
.venv/bin/archguard benchmark oss review assist \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --output /tmp/archguard-a-final-context
```

Open its `index.md` and `ANNOTATION_CHEATSHEET.md`. Each case contains pinned identity, question,
structural role facts, observed calls/control flow/methods, documentation/dependency references,
source shortlist, ambiguity notes and a rule-specific checklist. Unresolved calls are syntax
facts; packet inclusion does not imply dependency direction. Project documentation alone does
not establish a subject's role. No recommended answer or architectural conclusion is supplied.

`assistant_evidence_candidates` includes purpose (SOURCE/DEPENDENCY/DOCUMENTATION), repository,
commit, path, inclusive lines, full-file SHA256, explanation and excerpt. At most eight ranges
are selected, normally six lines each. Tiny packets may have fewer than three useful distinct
ranges; evidence is never invented to fill a quota. Full packets remain available. Fixed lexical
and line rules, canonical JSON and no timestamps make identical inputs byte-identical.

`EXTRA_CONTEXT_RECOMMENDED` lists exact pinned ranges outside the current packet, including
missing file context or implementations following declaration-only overloads. These are
requests, not evidence ready for import. When needed, put their `evidence` objects in a JSON
array and run `review request-extra-context --case CASE_ID --context request.json --output
NEW_DIRECTORY`. Give both reviewers the same supplemental revision, regenerate assistance
using its catalog, and start a new revision-bound draft. Sample identity stays unchanged.

Start the Reviewer A wizard:

```sh
.venv/bin/archguard benchmark oss review wizard \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --assistance experiments/oss/blinded/prompt013-final-context-v1/assistance-a/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-context-v1/reviewer-a \
  --draft experiments/oss/annotation-assistance/drafts/final-context-reviewer-a.json
```

Open each displayed card with the final packet. Manually choose a decision, enter your
stable pseudonymous reviewer ID, rationale and uncertainty, select supporting evidence numbers,
and explicitly attest your personal review. No choice, identity, evidence or attestation has a
default. Binary decisions require rationale and evidence; every decision needs a rationale and
explicit uncertainty. Skip saves no row. Quit, EOF and interruption preserve confirmed rows.
Each confirmed case is atomically autosaved with private file permissions. Repeating the command
resumes unfinished cases. Bundle files and sample/catalog/assistance/packet identity are checked.
One draft belongs to one independent human and cannot be imported as a review form.

Alternatively edit a separate copy of `review-form.json`: only reviewer_id, label, rationale,
uncertainty, attestation and chosen evidence. Preserve fingerprints, revisions and case IDs.
Empty rationale prompts appear in the cheatsheet without supplied answers.

Explicitly export confirmed rows into a new file:

```sh
.venv/bin/archguard benchmark oss review draft-export \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --assistance experiments/oss/blinded/prompt013-final-context-v1/assistance-a/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-context-v1/reviewer-a \
  --draft experiments/oss/annotation-assistance/drafts/final-context-reviewer-a.json \
  --output experiments/oss/annotation-assistance/submissions/final-context-reviewer-a.json
```

Export neither imports reviews nor computes agreement. The human subsequently runs:

```sh
.venv/bin/archguard benchmark oss review validate \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --annotations experiments/oss/annotation-assistance/submissions/final-context-reviewer-a.json
.venv/bin/archguard benchmark oss review import \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --annotations experiments/oss/annotation-assistance/submissions/final-context-reviewer-a.json \
  --output experiments/oss/annotation-assistance/imports/first-human
```

Later imports pass the previous `reviews.json` via `--store` and choose a new output directory.
Existing independence, adjudication and freeze rules apply. Preparation completes no human
reviews. Wizard tests use synthetic source fixtures in temporary directories exclusively.

## Reviewer B assistance

PROMPT 013.B introduced a second source pass. The final pass uses frozen corpus/sample/final catalog,
pinned source cache, original questions and allowed documentation/dependency references. The
shared extraction code rereads those inputs; it does not open generated A assistance, A drafts,
A submissions or human A answers. The fixed `reviewer-b-assistance-v1` strategy displays behavior
and dependencies first and orders candidate dependencies before source and documentation. It
keeps the observed facts and existing rule checks; no differences are forced and no randomness
is used. This is automated source navigation, not an independent human review.

```sh
.venv/bin/archguard benchmark oss review assist-b \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --output /tmp/archguard-b-final-context
```

The B generator has no A assistance input argument. Its sealed artifact contains 40 original
cases, independently derived source candidates and exact pinned context requests. A separate
`context_sufficiency` index records a boolean `extra_context_recommended` for each case; it is
validated against that case's requests. It does not answer any architectural rule question.
Tiny packets are not padded to reach an evidence quota. Every candidate remains inside allowed
packet ranges, with inclusive line numbers and verified full-file SHA256.

`assistance-freeze.json` binds the B artifact, sample, catalog and hashes of all generated cards,
index and cheatsheet. The wizard verifies the receipt and reconstructs the artifact from original
inputs before accepting it. An unfinished generation without a receipt cannot be compared or used
in the B CLI workflow. Identical inputs produce identical package bytes, including the receipt.

## Independence guarantees

B generation and context comparison live in separate modules. B generation cannot accept an A
artifact path. Tests generate B with A absent, create/mutate/delete generated A content and mock
human A answers in temporary directories, and show identical B fingerprints and package bytes.
A read barrier rejects attempts to open those paths during B generation. No real human forms are
used in those tests. Shared code gives reproducible source extraction; agreement between source
context flags is not independent human semantic agreement.

Original A assistance is retained. A drafts bind A assistance and the A bundle; B drafts bind B
assistance and the B bundle. The sample, catalog, packet revisions and assistance fingerprints
remain part of the draft checks. Mismatched bundle/assistance slots are rejected before any form
contents are read. New human decisions use only the final-context packages. Historical packages
remain provenance.

## Context-sufficiency comparison

Historical 013.B comparison (already frozen; do not overwrite):

```sh
.venv/bin/archguard benchmark oss review context-compare \
  --a-assistance experiments/oss/annotation-assistance/prompt013-aid-v1/assistance.json \
  --b-assistance experiments/oss/annotation-assistance/prompt013-b-aid-v1 \
  --output experiments/oss/annotation-assistance/prompt013-context-consensus-v1
```

The comparison verifies B freeze before opening A, verifies A's sealed identity and matching
sample/catalog/case IDs, then retains only case IDs, context flags and pinned requested ranges.
It does not use summaries, ambiguity text, request explanations, human answers or semantic
conclusions. Output lists both needing context, A only, B only, neither and their union. No human
agreement metric is calculated. Both packages remain untouched by comparison.

013.C materialized the 31 unique requests into 29 common revisions; 11 revisions stayed unchanged.
The final audit records 0 SUFFICIENT, 37 LIMITED and 3 UNRESOLVED. No remaining context flags is not
proof of sufficient architecture evidence. See [common freeze](research/SUPPLEMENTAL_CONTEXT_FREEZE.md).

## Human workflow

Reviewer B uses their own final-context bundle and private draft:

```sh
.venv/bin/archguard benchmark oss review wizard \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --assistance experiments/oss/blinded/prompt013-final-context-v1/assistance-b/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-context-v1/reviewer-b \
  --draft experiments/oss/annotation-assistance/drafts/final-context-reviewer-b.json
```

The human opens each card with its final packet, enters their own label/rationale/uncertainty,
selects supporting evidence and explicitly attests their personal review. No default is supplied.
Confirmed rows autosave; repeating the command resumes unfinished cases. Explicit export:

```sh
.venv/bin/archguard benchmark oss review draft-export \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --assistance experiments/oss/blinded/prompt013-final-context-v1/assistance-b/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-context-v1/reviewer-b \
  --draft experiments/oss/annotation-assistance/drafts/final-context-reviewer-b.json \
  --output experiments/oss/annotation-assistance/submissions/final-context-reviewer-b.json
```

Subsequent validate/import stays separate and uses the previously published review store with
`--store` when needed. Real A/B responses remain private and independent. This stage completes no
human reviews; two actual humans now independently complete the final-context packets.
