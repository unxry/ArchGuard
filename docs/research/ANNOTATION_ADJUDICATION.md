# Independent adjudication and agreement

Two distinct humans review the same source questions independently. Their identities are
pseudonyms supplied by the humans. Infrastructure validates distinct IDs and attestations; it
cannot prove that two pseudonyms belong to different people or that inspection actually occurred.

Only actual imported conflicts can be exported. A fresh empty cohort produces an error and no
adjudication directory. The adjudicator's bundle contains source context and both actual review
labels/rationales/event fingerprints. Independent A/B bundles never include those responses.

```bash
uv run archguard benchmark oss review adjudication-export \
  --catalog experiments/oss/blinded/import-b-v1/packet-revisions.json \
  --store experiments/oss/blinded/import-b-v1/reviews.json \
  --output experiments/oss/blinded/adjudication-v1
```

A distinct third human completes `adjudication-v1/review-form.json`. The adjudicator identifies
the current two review IDs, explicitly records packet revision, own label/rationale/evidence,
uncertainty and completed human attestation. No automated tie-breaker is provided. Import this
form using the same `review import` command with `--store` pointing at the preceding snapshot
and a **new output directory**. An adjudicator cannot be either initial reviewer.

Adjudication corrections require `supersedes_adjudication_id`, the same adjudicator/case and the
same review pair. Earlier adjudications remain recorded. After a reviewer amendment, a fresh
adjudication must address the new active pair. Stale adjudications remain provenance but cannot
resolve current conflicts. If the amended pair agrees, it becomes DOUBLE_REVIEW without an
invented adjudication.

`AnnotationReviewReport` includes paired-case counts, binary/nonbinary pair denominators, binary
agreements, agreement rate and Cohen's kappa, overall and by question/language/repository.
Primary agreement includes only cases with two actual POSITIVE/NEGATIVE decisions; disagreement
is included so the agreement measure remains meaningful. It measures reviewers before adjudication.
This denominator differs from binary evaluation eligibility, which requires resolved labels.
UNCERTAIN/OUT_OF_SCOPE pairs are reported separately and excluded from binary metrics.

For n binary pairs: observed agreement = agreeing pairs/n; expected agreement = sum of marginal
label-frequency products/n²; kappa = (observed−expected)/(1−expected). No pairs or expected
agreement=1 yields null, never a fabricated zero. Cohen's kappa is also null when a group contains
multiple distinct rater pairs; their pooled rate remains descriptive. Reviewer IDs orient each
pair consistently. No current agreement/kappa value exists because actual paired reviews=0.

Once all 40 cases have independent agreement or completed adjudication, freeze explicitly:

```bash
uv run archguard benchmark oss review freeze \
  --catalog experiments/oss/blinded/resolved-v1/packet-revisions.json \
  --store experiments/oss/blinded/resolved-v1/reviews.json \
  --output experiments/oss/blinded/annotation-frozen-v1
uv run archguard benchmark oss review status \
  --catalog experiments/oss/blinded/resolved-v1/packet-revisions.json \
  --store experiments/oss/blinded/resolved-v1/reviews.json \
  --freeze-receipt experiments/oss/blinded/annotation-frozen-v1/annotation-freeze.json
```

`resolved-v1` denotes the final actual import snapshot, including adjudication if needed. The
freeze binds corpus and corpus-freeze fingerprints, sample, packet catalog, full append-only
store, every review/adjudication fingerprint and resolved case decisions. It records that future
model receipts are required; it contains no model outputs. Unreviewed, single-review or unresolved
conflict cases block freeze. Agreed/adjudicated UNCERTAIN/OOS may finish annotation while remaining
ineligible for binary scoring. No partial final freeze is exposed by the primary workflow.

A frozen snapshot remains immutable. Later human corrections must preserve the old lineage,
produce a new snapshot and explicitly freeze a new receipt. Full Hybrid remains NOT_READY;
fresh Structural V2 and real AI evaluation require separately authorized subsequent work.
