# Common supplemental context freeze — PROMPT 013.C

Context engineering is **READY_FOR_HUMAN_REVIEW**. Ground truth is pending: 40 UNREVIEWED cases,
zero human reviews, identities, labels, completed attestations or binary-eligible cases; kappa null.
This context freeze is distinct from the later annotation freeze. No model or detector output
enters these artifacts. No live AI, V2/Hybrid evaluation or repository code execution occurred.

## Common source evidence

The separately generated, frozen A/B navigation passes requested context for the same 29 cases:
both=29, A-only=0, B-only=0, neither=11. Their agreement concerns source availability only.
The union contains 31 distinct case/range requests: missing file headers (imports, package,
decorators or comments) and implementation ranges following declaration-only signatures.
Requests were taken solely from the frozen nonsemantic context consensus, never human answers
or assistance prose. Every request passed repository/commit, regular-file, ancestor/leaf symlink,
path-containment, full-file SHA256 and inclusive line-bound checks against the existing cache.
Validation failures: zero. No network, fetching or source execution was needed.

Exactly one revision was appended for each of the 29 cases, combining both requested ranges
where present. Those cases use revision 2; the other 11 retain revision 1. The final catalog has
69 history entries and preserves the original 40 entries as its unchanged prefix. Questions,
review guide, rules, case IDs/order, repository pins and original evidence are unchanged.
Identical supplemental evidence for both humans prevents evidence availability from confounding
their independent judgments. Final A/B presentations may differ; their active packet context does not.

Source-free artifacts in `experiments/oss/annotation/`:

- `review-packet-revisions-final-v1.json`: final catalog.
- `final-context-freeze-v1.json`: base/final/consensus binding, 31 audited requests and per-case lineage.
- `final-context-audit-v1.json`: fresh source coverage audit, ranges, sizes and remaining limitations.
- `human-review-ready.json`: sample, catalog, context/audit, independent assistance and bundle bindings.

Sample: `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`.
Base catalog: `41043606e5e1b2bb2f1aca706110b0370dd4c3f998720199b97283f84a56792a`.
Final catalog: `9d5e3aad6ce60a5d65ed0b1b34976066301be539c220bd8379325884985c0443`.
Context freeze: `d3e9ba5a9132be2074a6f381100f29a91e26242d84020987fef6ce665e971da9`.

## Fresh coverage audit and limits

All 40 cases were audited from final pinned references; historical A/B flags were not reused.
The conservative lexical audit records **0 SUFFICIENT / 37 LIMITED / 3 UNRESOLVED**.
SUFFICIENT requires complete visible balanced implementation coverage and explicit subject-specific
role documentation; ARCH204 additionally requires placement documentation. LIMITED means body
coverage is available but architectural intent, placement or responsibility still needs human
interpretation. ARCH203 abstraction/ownership and ARCH205 substantive responsibilities are kept
LIMITED even with lexical coverage. UNRESOLVED means this audit cannot establish complete body
coverage. These availability states are neither semantic rule answers nor recommendations of labels.
A human can reach a supported decision that differs from the navigation audit.

No visible subject-specific role documentation matched the conservative criterion. General project
README descriptions and names alone cannot establish intended architecture. The three unresolved
cases are `oss-4e6d9b94f40e4369aacd9d44`, `oss-4c9dfda1ee9aebdd8b509244` and
`oss-2f40e81a5bc89e13c836ca41`: the exact requested supplement does not establish complete body
coverage. No arbitrary ranges were added to manufacture sufficiency or binary decidability.
Both final assistance packages have zero repeated header/implementation requests; that does not
remove these substantive limitations. Humans may request additional common pinned revisions.

Displayed context is verified numbered source, with no silent truncation. Per case:

| Measure | Minimum | Average | Maximum |
| --- | ---: | ---: | ---: |
| Lines shown, including repeated/overlapping ranges | 25 | 180.575 | 604 |
| Numbered excerpt bytes | 992 | 8113.85 | 28785 |
| Distinct files | 1 | 2.675 | 7 |

Existing budgets are reused: at most 7 files, 128 KiB numbered excerpts, 240 lines per new range
and aggregate 7×240 lines. Original evidence is retained. Over-budget requests fail with a
smaller-range diagnostic; critical source is never silently trimmed. All 31 requests fit.

## Independent final assistance and human packets

The final catalog/context receipt was written before either fresh source pass. A generation
accepts only corpus/sample/cache/final catalog; B independently invokes source extraction with the
same inputs and has no generated A input. Temporary regression tests mutate copied final A/B
packages and mock human answers under read barriers; regeneration remains identical in both
directions. This shared lexical extractor is not two independent human reviewers.

Local package: `experiments/oss/blinded/prompt013-final-context-v1/`:

- `assistance-a/` and `assistance-b/`: 40 cards and 194 candidate ranges each, independently regenerated.
- `reviewer-a/` and `reviewer-b/`: identical 40 cases, source/questions, final active revisions and blank forms.
- `packet-revisions.json`, context freeze/audit, ready receipt and local `REPORT.md`.

A/B content identity is equal; bundle fingerprints differ because slot metadata differs.
Each form has null reviewer ID, label, uncertainty and attestation, empty rationale/evidence.
Historical original human bundles and A/B assistance remain untouched. Old drafts cannot be
exported with final assistance/catalog/bundles. New imports reject old packet revisions while
historical review events remain replayable; no decisions migrate between revisions.
Excerpts, assistance and drafts stay ignored/local; only source-free metadata is versionable.

## Reproduction and human start

Choose a new output directory. The existing final directory is immutable:

```sh
.venv/bin/archguard benchmark oss review final-context-prepare \
  --catalog experiments/oss/annotation/review-packet-revisions-v1.json \
  --consensus experiments/oss/annotation-assistance/prompt013-context-consensus-v1/context-consensus.json \
  --output /tmp/archguard-final-context-reproduction
.venv/bin/archguard benchmark oss review status \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --ready-directory experiments/oss/blinded/prompt013-final-context-v1
```

Two clean macOS generations and offline Linux using existing `archguard:prompt0111` image produced
byte-identical sets of all 183 canonical files, including receipts/catalogs and complete assistance.
Linux used current source mounted read-only, verified cache read-only and `--network none`; no image
build, package installation or source execution. Historical 477 file hashes remain unchanged.

Two actual humans independently run their own [final wizard](HUMAN_ANNOTATION_EXECUTION.md), inspect
all pinned evidence, choose rationale/evidence/uncertainty and attest only their own completed review.
Keep drafts/submissions separate from frozen bundles. Only after both actual reviews, conflict
adjudication and explicit annotation freeze can a separately authorized real AI evaluation begin.
PROMPT 014 is not started by this preparation.
