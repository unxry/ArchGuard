# Local source assistance and human draft workflow

Automated evidence summarization reduces annotation burden, but final semantic ground truth
remains human judgment. PROMPT 013.A supplies deterministic source navigation, not ground truth
or an independent human submission. Extraction uses pinned source only, with no detector,
model, previous answer or network call. Generated excerpts and private drafts stay local in the
ignored `experiments/oss/annotation-assistance/` directory.

Both reviewers use the same assistance alongside their original packets, without seeing each
other's answers. Original bundles, sample identity, packet catalog and review store are preserved.

Generate the immutable package:

```sh
.venv/bin/archguard benchmark oss review assist \
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --output experiments/oss/annotation-assistance/prompt013-aid-v1
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

Start the wizard (reviewer B uses reviewer-b and their own private draft):

```sh
.venv/bin/archguard benchmark oss review wizard \
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --assistance experiments/oss/annotation-assistance/prompt013-aid-v1/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-v1/reviewer-a \
  --draft experiments/oss/annotation-assistance/drafts/reviewer-a.json
```

Open each displayed card with the original packet. Manually choose a decision, enter your
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
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --assistance experiments/oss/annotation-assistance/prompt013-aid-v1/assistance.json \
  --bundle experiments/oss/blinded/prompt013-final-v1/reviewer-a \
  --draft experiments/oss/annotation-assistance/drafts/reviewer-a.json \
  --output experiments/oss/annotation-assistance/submissions/reviewer-a.json
```

Export neither imports reviews nor computes agreement. The human subsequently runs:

```sh
.venv/bin/archguard benchmark oss review validate \
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --annotations experiments/oss/annotation-assistance/submissions/reviewer-a.json
.venv/bin/archguard benchmark oss review import \
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --annotations experiments/oss/annotation-assistance/submissions/reviewer-a.json \
  --output experiments/oss/annotation-assistance/imports/first-human
```

Later imports pass the previous `reviews.json` via `--store` and choose a new output directory.
Existing independence, adjudication and freeze rules apply. Preparation completes no human
reviews. Wizard tests use synthetic source fixtures in temporary directories exclusively.
