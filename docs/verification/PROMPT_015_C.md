# PROMPT 015.C — Inter-reviewer agreement and conflict freeze

Status after freeze: **INTER_REVIEWER_AGREEMENT_FROZEN / READY_FOR_ADJUDICATOR_HANDOFF**.
Human truth remains **FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN**.

## Approved immutable inputs

Both accepted `frozen-v1/submission-v1.json` snapshots are the sole human inputs.
Their raw SHA-256, source-free acceptance receipt seals, canonical validated
fingerprints, slot/bundle binding, counts and unique IDs are verified before comparison.
Mutable `completed-response.json` files are never read.

| Slot | Submitted SHA-256 | Acceptance receipt | Canonical submission |
| --- | --- | --- | --- |
| A | `b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e` | `58488f51c3050266ecdc930e8c24814d7d4040ba1101765ed2180d8a1c0ffb08` | `5c9e97870a96b195eee3d2331f3003918cdf30ad30236922b56b93b16cf114d2` |
| B | `dd3d7d4f97bd088eeca6e9cedbfec6a6d9732d6e05a906863f91df44e757be9f` | `c6463eeb506130de7d4b02a2e511abec5e99cb299edb64791e8a8ecdc06d451d` | `edb3a7abb78adedb7a3fc45689d713569e762ad4ede1d2c93d6982f39a6cc8db` |

A verification: **PASS**. B verification: **PASS**. Each has 100 responses and
100 unique blinded IDs. Both map to the same 100 scientific cases; missing and
duplicate counterparts: **0**. Frozen P015 `sample-v1.json` supplies the common
`case_id ↔ blinded_id` mapping. Each reviewer has a separately ordered presentation
of those same IDs. Comparison joins through that mapping, never array position.

B workflow closure commit: `439a536b38828bd78926ad6c324c21a4cc38d197`.
P015 sample freeze: `b291e47d6b5ed7ffcbbac967b221b5dee7366fa2d559031b19bc5b3d751b3dfb`.

## Primary exact categorical agreement

N = **100**; exact agreements = **96**; disagreements = **4**; agreement = **96%**.
Observed agreement p_o = **0.96**; expected chance agreement p_e = **0.4543**;
ordinary unweighted Cohen's κ = **0.9266996518233461** (denominator population 100).

Rows are Reviewer A, columns are Reviewer B. All four categories remain distinct.

| A / B | POSITIVE | NEGATIVE | UNCERTAIN | OUT_OF_SCOPE |
| --- | ---: | ---: | ---: | ---: |
| POSITIVE | 49 | 2 | 1 | 0 |
| NEGATIVE | 0 | 43 | 0 | 0 |
| UNCERTAIN | 0 | 1 | 3 | 0 |
| OUT_OF_SCOPE | 0 | 0 | 0 | 1 |

κ = (p_o − p_e)/(1 − p_e), with p_e = Σ(A marginal × B marginal)/N².
Calculations use exact rational arithmetic before serializing numeric results.
Undefined κ is null for no paired cases or p_e = 1, with the exact reason.
No confidence intervals or qualitative κ interpretation labels were introduced.

## Secondary binary-only view

Only cases where both independently selected POSITIVE/NEGATIVE qualify.
Eligible **94**; excluded nonbinary **6**; agreements **92**; disagreements **2**;
agreement **97.87234042553192%**; p_o **0.9787234042553191**;
p_e **0.5018107741059303**; binary κ **0.9572921399363925**.

| A / B | POSITIVE | NEGATIVE |
| --- | ---: | ---: |
| POSITIVE | 49 | 2 |
| NEGATIVE | 0 | 43 |

These are agreement categories; neither reviewer is reference truth.

## Disagreement taxonomy

| Symmetric transition | Count |
| --- | ---: |
| NEGATIVE↔OUT_OF_SCOPE | 0 |
| NEGATIVE↔UNCERTAIN | 1 |
| POSITIVE↔NEGATIVE | 2 |
| POSITIVE↔OUT_OF_SCOPE | 0 |
| POSITIVE↔UNCERTAIN | 1 |
| UNCERTAIN↔OUT_OF_SCOPE | 0 |

No direction is interpreted as an error.

## Descriptive stratification

Marginal tuples below are (POSITIVE, NEGATIVE, UNCERTAIN, OUT_OF_SCOPE).
All strata are descriptive: small N, no population inference or superiority claim.
Stratum κ is reported only with N ≥ 2, variation in both marginals and p_e < 1.

| Stratum | N | Exact | Disagreement | Agreement % | A marginals | B marginals | κ |
| --- | ---: | ---: | ---: | ---: | --- | --- | ---: |
| ARCH201 | 20 | 17 | 3 | 85 | 12/8/0/0 | 9/10/1/0 | 0.716981132075 |
| ARCH202 | 20 | 20 | 0 | 100 | 10/10/0/0 | 10/10/0/0 | 1.000000000000 |
| ARCH203 | 20 | 19 | 1 | 95 | 10/8/1/1 | 10/9/0/1 | 0.911894273128 |
| ARCH204 | 20 | 20 | 0 | 100 | 10/10/0/0 | 10/10/0/0 | 1.000000000000 |
| ARCH205 | 20 | 20 | 0 | 100 | 10/7/3/0 | 10/7/3/0 | 1.000000000000 |
| JAVA | 50 | 48 | 2 | 96 | 26/21/2/1 | 24/22/3/1 | 0.928926794598 |
| TYPESCRIPT | 50 | 48 | 2 | 96 | 26/22/2/0 | 25/24/1/0 | 0.924242424242 |

## Independently sealed artifacts

| Artifact | Fingerprint | Visibility |
| --- | --- | --- |
| Agreement analysis | `13cc5a8975ef3e553ae4d729ab81fdaae5fcce818df82d527fd2563dd06a5389` | Public aggregate |
| Exact conflict manifest | `47926ff2491a73194037a2f954b2ae01dfbcf972fb065ae3d2cf67b7a26d2189` | Private / Git ignored |
| Adjudicator-safe index | `fb52bcde381fe4ba3357d18011bcca2c68b072ec5089edb55d8c989e793935db` | Private / Git ignored |
| Verification receipt | `d31d8237aca9b93a9aacf5baa6661dda83411da38f478e141ec3a1e7d52411ff` | Public source-free |

Public directory: `experiments/semantic-holdout/inter-reviewer-agreement-v1/`.
Private directory: `experiments/semantic-holdout/private/inter-reviewer-agreement-v1/`.

The exact conflict manifest contains all **4** categorical disagreements and no
agreement case. It retains stable conflict IDs, scientific/A/B blinded IDs,
rule/language, both categories and original source/A/B freeze lineage.
Conflict IDs derive only from sample fingerprint and scientific case ID.
Rows are deterministically sorted by scientific case ID. Every artifact is
separately fingerprinted; existing freeze directories cannot be overwritten.

The separate adjudicator-safe index has exactly those 4 case/conflict IDs and
rule/language with source lineage. It contains no reviewer decisions, identity,
rationale/note text, evidence selections, source code or construction relation.
No full adjudicator handoff package was created. Private outputs remain mode 0700
and covered by the existing private-directory Git ignore rule.

## Future deterministic human-truth rule — documented only

- For an exact A/B agreement: future final category is the unchanged agreed category.
- For a disagreement: future final category is the separately authorized third-human adjudicated category.

Construction intent never participates in the final category. This rule was not
executed: no final truth file, automatic resolution, majority vote or adjudication
was produced. All 4 conflicts remain unresolved and require a third human.

## Isolation and verification

P013/P014/P015 artifacts and both accepted A/B snapshots/receipts remain unchanged.
Original public/private P015 inventories are verified by hashes. Private
construction/provenance bytes are hashed for integrity only; their contents
are never decoded, projected into agreement inputs or joined to human decisions.
The calculation consumes only case mapping, target rule/language and A/B categories.

Live AI calls: **0**. Structural V2, Hybrid, semantic effectiveness metrics,
P015.D and P016 were not executed. No secret env file was loaded or committed.

- Targeted tests: **41 passed** (synthetic frozen-input guards, identity join,
  matrices/κ, binary eligibility, taxonomy, complete conflicts, deterministic IDs,
  safe index isolation, immutable artifacts, no network/truth and old inventories).
- Targeted Ruff, formatting check and strict mypy: **PASS**.
- Full `make check`: **PASS**, Ruff/format, strict mypy, **1328 tests passed**,
  93% coverage.
- `scripts/prompt015c_agreement.py --freeze`: **PASS**, one-time freeze.
- `scripts/prompt015c_agreement.py --verify`: **PASS**, all four artifacts byte-exact.
- `scripts/prompt015_holdout.py --verify`: **PASS**, complete original inventories.
- `git diff --check`, new-file whitespace and public privacy scan: **PASS**.

Intended changes: two agreement modules, one offline script, synthetic tests,
this report and two public aggregate/receipt files. Exact conflicts and all
human submissions remain ignored. Commit message:
`feat: freeze inter-reviewer agreement conflicts`.
All seven changed/untracked files are intended P015.C infrastructure or public-safe
aggregate reports; unrelated files: **0**. The public artifact schema contains
no case-level mapping, identity, rationale/note text, source or evidence selections.
Commit SHA, normal push result and clean working tree are reported after closure.

**STOP before P015.D, adjudication, final human truth or P016.**
