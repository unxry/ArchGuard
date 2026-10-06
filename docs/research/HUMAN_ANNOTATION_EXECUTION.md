# Human annotation execution

PROMPT 013 provides the execution workflow for the frozen 40-case OSS sample. Current state:
**WAITING_FOR_HUMAN_REVIEW**. Human reviewers, labels and binary-eligible cases: **0**.
Completed annotation freeze, Structural V2 evaluation and live AI assessments: **none**.
Full Hybrid remains **NOT_READY**. No case is treated as a negative merely because it is unreviewed.

## Give each human their own bundle

From `/Users/bendasroman/Downloads/ArchGuard`, the prepared local bundles are:

- Reviewer A: `experiments/oss/blinded/prompt013-final-v1/reviewer-a/index.md`
- Reviewer B: `experiments/oss/blinded/prompt013-final-v1/reviewer-b/index.md`

Each directory contains 40 Markdown cases, README quick guide, an index, `packets.json` with
pinned evidence, a blank `review-form.json`, packet quality checks and a bundle manifest.
The two bundles contain identical context/questions; only manifest slot metadata differs.
They contain no detector classifications, candidate flags, model scores, AI/Hybrid outputs,
prefilled labels, human IDs, rationales or completed attestations. Do not give either human
the other person's responses. Neither independent export reads any existing responses or store.

Each actual human opens their own index/guide, inspects source/dependencies/docs, then fills
**their own `review-form.json`**. Keep only completed rows in the submitted copy. Set a stable
pseudonymous reviewer ID (no real name/email), own rationale, exact evidence, uncertainty and
`HUMAN_REVIEW_COMPLETED` only after actual inspection. Binary labels require nonblank rationale
and at least one evidence reference. Nonbinary decisions also require a rationale. References
can be copied from `packets.json` and narrowed to relevant lines; full-file hashes remain unchanged.
Preserve each row's packet fingerprint/revision and the top-level sample fingerprint.

Templates are intentionally invalid as completed reviews: null labels/IDs/attestations are rejected.
Partial submissions are allowed by removing unfinished rows; they leave other cases unreviewed.
Operational timestamps may be kept in external submission logs, never in ground-truth identity.

## Validate and import real submissions

All commands below are run at the project root. They use the persistent verified source cache
`/Users/bendasroman/.cache/archguard/oss`; an explicit `--cache` can select another verified cache.
No fetching, detectors or model evaluation run during these commands.

```bash
uv run archguard benchmark oss review status
uv run archguard benchmark oss review validate \
  --catalog experiments/oss/blinded/prompt013-final-v1/packet-revisions.json \
  --annotations experiments/oss/blinded/prompt013-final-v1/reviewer-a/review-form.json
uv run archguard benchmark oss review import --dry-run \
  --catalog experiments/oss/blinded/prompt013-final-v1/packet-revisions.json \
  --annotations experiments/oss/blinded/prompt013-final-v1/reviewer-a/review-form.json
uv run archguard benchmark oss review import \
  --catalog experiments/oss/blinded/prompt013-final-v1/packet-revisions.json \
  --annotations experiments/oss/blinded/prompt013-final-v1/reviewer-a/review-form.json \
  --output experiments/oss/blinded/import-a-v1
uv run archguard benchmark oss review import \
  --catalog experiments/oss/blinded/prompt013-final-v1/packet-revisions.json \
  --store experiments/oss/blinded/import-a-v1/reviews.json \
  --annotations experiments/oss/blinded/prompt013-final-v1/reviewer-b/review-form.json \
  --output experiments/oss/blinded/import-b-v1
uv run archguard benchmark oss review status \
  --catalog experiments/oss/blinded/import-b-v1/packet-revisions.json \
  --store experiments/oss/blinded/import-b-v1/reviews.json
```

Every import validates the whole batch before publishing an immutable new snapshot directory.
One invalid row rejects the batch. Dry-run and validate perform no canonical writes. Publishing
stages all files in the destination filesystem and renames the directory only after successful
serialization. Existing output directories are rejected. Keep the preceding snapshot and pass
`--store` to every continuation; omitting it explicitly starts a new empty lineage.
Snapshot files: `reviews.json`, `packet-revisions.json`, `review-report.json`, `pending-freeze.json`.
There is no completed annotation freeze in an import snapshot.

## More source context without changing the sample

If a packet needs more context, prepare `extra-context.json`: an array of references with
`repository_id`, exact `commit_sha`, canonical relative `path`, full-file `sha256`, inclusive
`start_line`/`end_line`, and `purpose` SOURCE, DEPENDENCY or DOCUMENTATION. Use files from the
verified pinned source cache, never current upstream HEAD. A dependency reference describes
source imports/calls only; it carries no classification. No unpinned web content is accepted as
hash-verified evidence. Omitted nonregular files cannot be used; choose materialized pinned docs.

```bash
uv run archguard benchmark oss review request-extra-context \
  --catalog experiments/oss/blinded/prompt013-final-v1/packet-revisions.json \
  --case CASE_ID --context extra-context.json \
  --output experiments/oss/blinded/supplement-v1
uv run archguard benchmark oss review prepare \
  --catalog experiments/oss/blinded/supplement-v1/packet-revisions.json \
  --output experiments/oss/blinded/supplemented-bundles-v1
```

The case ID, frozen original packet, rule, corpus and sample remain unchanged. A supplemental
revision appends source references, links its predecessor and preserves the review question/guide.
The human reads the new case and records its **new packet fingerprint and revision**. An imported
review using extra evidence without its registered packet revision is rejected. Never substitute
a new revision automatically into an already completed human decision. If the human changes that
decision after inspecting more context, submit an explicit amendment.

The versioned packet fingerprint binds the original packet identity, commit, actual rendered
question, guide fingerprint, additional context and revision ancestry. Bundle identity also binds
all rendered files. Timestamps and filesystem locations are excluded. Original PROMPT 012
packet/sample fingerprints stay valid.

## History, readiness and freeze

History is append-only. Amend a review by including `supersedes_review_id` equal to its active
event fingerprint in `reviews.json`, retaining the same reviewer/case. All prior events persist.
Stale references, silent overwrites, duplicate rows and a third independent review slot are rejected.
Amendments invalidate adjudication of an obsolete pair; agreement and eligibility are recomputed.

- UNREVIEWED: no decision; no label.
- SINGLE_REVIEW: provisional decision; final label remains NOT_ANNOTATED; ineligible.
- DOUBLE_REVIEW: two distinct reviewers agree. Only POSITIVE/NEGATIVE are binary-eligible.
- ADJUDICATION_REQUIRED: disagreement; no final binary label.
- ADJUDICATED: a distinct third human resolves the active pair; only binary labels are eligible.

Independently agreed UNCERTAIN/OUT_OF_SCOPE are terminal annotation decisions, always excluded
from binary evaluation/TN counts. Counts are reported overall and by question, language and repository.
Readiness progresses through WAITING_FOR_HUMAN_REVIEW, FIRST_REVIEW_IN_PROGRESS/COMPLETE,
SECOND_REVIEW_IN_PROGRESS/COMPLETE, ADJUDICATION_REQUIRED and explicit ANNOTATION_FROZEN.

See [adjudication](ANNOTATION_ADJUDICATION.md) for conflict export, metric denominators and final
freeze. Final freeze requires every sampled case to have two independent reviews and all conflicts
resolved. Passing a completed receipt to `review status --freeze-receipt` verifies the entire lineage.
Full Hybrid still requires separately authorized real AI assessments and model receipts afterward.
PROMPT 014 does not start automatically.
