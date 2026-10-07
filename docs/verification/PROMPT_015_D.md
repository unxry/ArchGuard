# PROMPT 015.D — Blinded independent third-human handoff

Status after preparation: **WAITING_FOR_ADJUDICATOR**.
Human truth remains **FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN**.

## Approved source lineage and exact membership

History descends from B closure
`439a536b38828bd78926ad6c324c21a4cc38d197` and C closure
`088916a6b57e8c75c8d2753b7e6120cf925ddcf5`.

P015.C frozen-input verification: **PASS**.

| Frozen input | Expected/verified fingerprint |
| --- | --- |
| Exact conflict manifest | `47926ff2491a73194037a2f954b2ae01dfbcf972fb065ae3d2cf67b7a26d2189` |
| Adjudicator-safe index | `fb52bcde381fe4ba3357d18011bcca2c68b072ec5089edb55d8c989e793935db` |
| Agreement analysis | `13cc5a8975ef3e553ae4d729ab81fdaae5fcce818df82d527fd2563dd06a5389` |
| C verification receipt | `d31d8237aca9b93a9aacf5baa6661dda83411da38f478e141ec3a1e7d52411ff` |

The approved state is 100 paired cases, 96 exact agreements and **4** categorical
conflicts. All four manifest rows have A category != B category. The sealed
safe index has exactly the same conflict/scientific-case/rule/language membership.
No agreement case, replacement, rebalance or omission is permitted. Input mismatch
stops with `PROMPT_015_D_BLOCKED`; this stage never rewrites the C conflict set.

## Builder isolation and scientific evidence

The package builder can read only the approved safe index, public frozen case
mapping and guidance, and the four corresponding original frozen source packets.
It cannot read the conflict manifest, either human submission, rationales, notes,
selected evidence, private construction metadata or model/detector results.
The coordinator verifies the manifest separately before invoking the builder.

All original source evidence items, paths, text, hashes, ordering, target component,
target path, rule, language and architecture contract are preserved. No new context
or semantic hint is added after observing disagreement. Limited evidence remains
limited. The entire frozen rule guidance is copied byte-identically and its original
fingerprint is preserved; rule wording is not sharpened or rewritten.

Only opaque identifiers are replaced: adjudicator case IDs and evidence IDs are
derived through domain-separated HMAC-SHA256 with a new private 256-bit blinding key.
Ordering uses a separate HMAC domain and an opaque-ID tie breaker, independent of
A/B presentation order. Original scientific/primary/evidence IDs and project aliases
are absent from the package. Source text is never edited to pass the leakage audit:
any prohibited source hint causes a stop.

The sealed deterministic mapping and blinding key remain outside the directory
given to the third human. That coordinator directory is private/Git ignored,
mode 0700, with its mapping file mode 0600. The key is solely for local blinding;
no API credential or secret env file is read, logged or copied.

## Frozen package and blankness audit

Private handoff directory:
`experiments/semantic-holdout/private/adjudicator-handoff-v1/`.

It contains `README.txt`, source-only `index.html`, `bundle-v1.json`, the exact
`rule-guidance-v1.json`, `submission-schema.json`, blank `response-template.json`
and a deterministic `handoff-freeze.json` with SHA-256 hashes for every file.
Existing handoff/mapping directories cannot be overwritten. Verification reproduces
all bytes from the locked blinding key and original approved inputs.

| Audit | Result after freeze |
| --- | ---: |
| Frozen conflicts / package cases / unique adjudicator IDs | 4 / 4 / 4 |
| Pre-populated decisions | 0 |
| Pre-populated rationales | 0 |
| Pre-populated evidence selections | 0 |
| Pre-populated notes | 0 |
| A/B category or transition leakage | 0 |
| A/B rationale/note/evidence leakage | 0 |
| Construction intent/pair/operator leakage | 0 |
| AI/detector/V2/Hybrid leakage | 0 |
| Human adjudication answers collected | 0 |
| Live AI calls | 0 |

| Artifact | Frozen fingerprint |
| --- | --- |
| Package | `cec7af09c40b78e6afca5626f87b860a2e591fb6153eea0f0795fad83be488ac` |
| Blank response template (raw SHA-256) | `ba9d11aee3e19c00e255a45d9e4fe67306645928b905ef9db6edd5bd1ad125d1` |
| Private mapping | `fa0e5c568ca255129bd5e44435e69f48736072f0227b5cbf1e9cf62822e9d24f` |
| Public verification receipt | `b7b66eeb7905729fe0d0f76cf924974f03cda5852925f6694058bc85506406c5` |

Guidance fingerprint:
`fa1175d98aa94ede7df428e13cbf9ed2e08a4719fcc0470ffe8327bc9ae4a8ff`.

Source-free public audit:
`experiments/semantic-holdout/adjudicator-handoff-verification-v1.json`.
Private coordinator mapping:
`experiments/semantic-holdout/private/adjudicator-coordinator-v1/adjudicator-mapping-v1.json`.
Neither the public audit nor this report includes any case-level ID, source,
reviewer identity, private key, rationale, note or selected evidence.

## Third-human instructions and private return

Give only this complete directory privately to the third distinct real human:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/adjudicator-handoff-v1/`

Open first:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/adjudicator-handoff-v1/README.txt`

Then open `index.html` locally and fill a copy of `response-template.json`.
Each case requires exactly one of POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE,
a nonblank independent rationale and explicit nonempty evidence references with
`evidence_id`, inclusive integer `start_line` and `end_line`. Notes are optional.
Evidence must belong to that case and fit its frozen source lines. All four
categories remain allowed, including one selected by neither primary reviewer.
The third human is not voting for A or B.

After independently completing all four, the human supplies their own nonblank
`reviewer_identity` and exact `REAL_HUMAN_INDEPENDENT_ADJUDICATION` attestation.
They must be neither A nor B, use no AI/detector assistance and not communicate
case answers with either primary reviewer before completing/freezing their own
submission. Identity, distinct-person status, authorship and independence are
self-declared; no external identity verification is claimed.

Return the completed copy privately to:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/adjudicator-submissions-v1/completed-response.json`

The separate append-only return directory is empty, mode 0700 and Git ignored.
No completed response file or accepted adjudication is initialized. The frozen
package must not be changed after any answer is collected.

## Future final-truth rule — documented only

- For the 96 exact-agreement cases: future category = unchanged A/B agreed category.
- For the 4 frozen conflicts: future category = independently submitted third-human category.

Construction intent never participates. This rule is not executed here. Final
truth can be materialized only after separately authorized validation/freeze of
the third-human submission in P015.E. No case is adjudicated or automatically
resolved in P015.D; no semantic effectiveness, V2, Hybrid or P016 execution occurs.

## Executed checks and public Git boundary

- Targeted synthetic adjudication tests: **59 passed**.
- Targeted Ruff, formatting check and strict mypy: **PASS**.
- Full `make check`: **PASS**, **1387 tests passed**, 93% coverage.
- `scripts/prompt015d_adjudicator.py --prepare`: **PASS**, one-time private freeze.
- `scripts/prompt015d_adjudicator.py --verify`: **PASS**, all package/mapping bytes exact.
- `scripts/prompt015_holdout.py --verify`: **PASS**, complete original inventories.
- `scripts/prompt015c_agreement.py --verify`: **PASS**, four C artifacts and A/B inputs.
- `git diff --check`, new-file whitespace and public privacy scan: **PASS**.

Only two workflow modules, the offline preparation script, synthetic tests,
this source-free report and the source-free audit are intended public changes.
All six changed/untracked files are intended P015.D files; unrelated files: **0**.
All human/source-bearing material, blinding/mapping data and credentials remain
private and excluded from Git. Prior P013/P014/P015/A/B/C freezes remain unchanged.
Commit message: `feat: prepare blinded semantic adjudication handoff`.
Commit SHA, normal push result and clean working tree are reported after closure.

**STOP: WAITING_FOR_ADJUDICATOR / FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN.**
Do not adjudicate, accept/freeze any response, execute P015.E or start P016.
