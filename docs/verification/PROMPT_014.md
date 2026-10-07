# PROMPT 014 — verification report

## A–F. Execution and accounting

**PROMPT_014_COMPLETE**. Provider **openai**, model **gpt-6-luna**, Standard processing. Exactly **120/120** terminal logical assessments from the frozen 40 cases × three strategies; **120** accepted assessments, **0** remaining, **0** technical retries. Experiment attempts: **120**. Total live provider calls including the single source-free connectivity check: **121**.

Connectivity: CONNECTIVITY_SUCCEEDED, HTTP 200, input/output tokens 20/5, latency 2.815s, estimated cost $0.0000045. It is outside the 120 logical assessments and included in combined cost/token accounting. No configuration retries were made.

Approved checkout ancestry and all 120 frozen payload identities were verified before paid experiment calls. Human labels, reviewer rationales, adjudication and detector/V2/Hybrid outputs were unavailable to the blind executor. No accepted assessment was repeated. Invalid responses, abstentions and scientifically inconvenient judgments were not retried. P013 truth was opened by evaluation only after the independent AI freeze.

The frozen protocol remained: LOCAL_ONLY / GRAPH_GUIDED / EXPANDED_BASELINE, one-hop graph, 20,000-character total context cap, 2,000-token output cap, expected output assumption 600 tokens, 32,768 input-token guard, 90-second timeout, at most two technical retries, serial deterministic manifest order. Credential rotation did not regenerate any request.

| Strategy | Logical | Accepted | Attempts | Retries | Failures |
|---|---|---|---|---|---|
| EXPANDED_BASELINE | 40 | 40 | 40 | 0 | {} |
| GRAPH_GUIDED | 40 | 40 | 40 | 0 | {} |
| LOCAL_ONLY | 40 | 40 | 40 | 0 | {} |

## G–H. Independent freezes and lineage

| Artifact | Fingerprint |
|---|---|
| Approved pre-live commit | dcacc6a8ea42231e4d0fb97dcf171caaaae02a56 |
| Experiment/request manifest | 92c4c909e5953d9e0ba07f00126eae75bf8225b128d1eb989a0df02d4c722a04 |
| Context manifest | f9502ddecd8db147c419edd28f3227fb6174a0c8522f59c1b22eb38982e53afe |
| AI assessment freeze | 12442e2207168131cf3738b56d90915d70f7ba4a8a8806b66fc1e328cf84402a |
| Truth join | 500eaa676a8a96a0967b8eec19a308b4c48977e052c66fd13f57f685b00e9015 |
| Evaluation | 00974ff6c64d7bea51a9a7606f76d99451647508c932fc0a7d4415b89a8f3896 |
| Context/usage inventory | 49e6072f953af912718affdc2955bd80c2b5b62d9e48e95047dde4e797125db4 |
| Separate cost accounting | aa140687803f304c31e7c0f254d1b9f421c603610d5bf84ed1ab4d04fc93af34 |
| Post-evaluation receipt | a3f6c7f3a46e32e550229751e18f00117cce550b9eee53f2748223d8ef28b0f0 |
| Pricing assumption | 2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b |

The AI freeze file SHA-256 is `a11f9acb0e148e6567b59aa4ff7368e8e6c56c6797ba00133fc0be4a24383e6b`. Its bytes stayed unchanged after the truth join. Results, join, evaluation and receipts are source-free public artifacts; raw provider text and original source requests are ignored private artifacts.

## I–J. Response distributions and negative/OOS metrics

| Strategy | SUPPORTED | NOT_SUPPORTED | INSUFFICIENT_CONTEXT | NOT_APPLICABLE | Missing/failed |
|---|---|---|---|---|---|
| EXPANDED_BASELINE | 0 | 3 | 31 | 6 | 0 |
| GRAPH_GUIDED | 0 | 4 | 28 | 8 | 0 |
| LOCAL_ONLY | 0 | 3 | 32 | 5 | 0 |

Each strategy has 32 human NEGATIVE and 8 human OUT_OF_SCOPE cases. On negatives, NOT_SUPPORTED = TN; SUPPORTED = FP; INSUFFICIENT_CONTEXT = abstention; NOT_APPLICABLE = scope error, never TN. OOS recognition is counted separately. Specificity/FPR use TN+FP; effective correctness and definitive coverage use all human negatives.

Specificity 100% and FPR 0% are conditional on only three or four definitive negative decisions. Negative abstention is 81.25–90.625%; these rates do not establish strong overall negative performance. GRAPH_GUIDED saves 48.92% input tokens versus EXPANDED_BASELINE in this run, with four versus three TN and the same six of eight recognized OOS cases. These are descriptive observations, not an effectiveness or superiority claim.

| Strategy | TN | FP | Abstain | Negative scope error | Specificity | FPR | Effective negative correctness | Definitive coverage | Abstention | OOS recognition |
|---|---|---|---|---|---|---|---|---|---|---|
| EXPANDED_BASELINE | 3 | 0 | 29 | 0 | 100.00% | 0.00% | 9.38% | 9.38% | 90.62% | 75.00% |
| GRAPH_GUIDED | 4 | 0 | 26 | 2 | 100.00% | 0.00% | 12.50% | 12.50% | 81.25% | 75.00% |
| LOCAL_ONLY | 3 | 0 | 29 | 0 | 100.00% | 0.00% | 9.38% | 9.38% | 90.62% | 62.50% |

Per-rule results (ARCH202 supports OOS recognition only; no unified ARCH201–205 F1):

| Strategy | Rule | Negative/OOS | TN/FP/Abstain/Scope | Specificity | FPR | Effective negative correctness | OOS correct |
|---|---|---|---|---|---|---|---|
| EXPANDED_BASELINE | ARCH201 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| EXPANDED_BASELINE | ARCH202 | 0/8 | 0/0/0/0 | null | null | null | 6/8 |
| EXPANDED_BASELINE | ARCH203 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| EXPANDED_BASELINE | ARCH204 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| EXPANDED_BASELINE | ARCH205 | 8/0 | 3/0/5/0 | 100.00% | 0.00% | 37.50% | 0/0 |
| GRAPH_GUIDED | ARCH201 | 8/0 | 1/0/7/0 | 100.00% | 0.00% | 12.50% | 0/0 |
| GRAPH_GUIDED | ARCH202 | 0/8 | 0/0/0/0 | null | null | null | 6/8 |
| GRAPH_GUIDED | ARCH203 | 8/0 | 0/0/6/2 | null | null | 0.00% | 0/0 |
| GRAPH_GUIDED | ARCH204 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| GRAPH_GUIDED | ARCH205 | 8/0 | 3/0/5/0 | 100.00% | 0.00% | 37.50% | 0/0 |
| LOCAL_ONLY | ARCH201 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| LOCAL_ONLY | ARCH202 | 0/8 | 0/0/0/0 | null | null | null | 5/8 |
| LOCAL_ONLY | ARCH203 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| LOCAL_ONLY | ARCH204 | 8/0 | 0/0/8/0 | null | null | 0.00% | 0/0 |
| LOCAL_ONLY | ARCH205 | 8/0 | 3/0/5/0 | 100.00% | 0.00% | 37.50% | 0/0 |

Per-language negative and OOS results, with operational measurements:

| Strategy | Language | Negative/OOS | TN/FP/Abstain/Scope | Specificity | FPR | Effective | OOS recognition | Input/output tokens | Mean latency s | Context/source chars |
|---|---|---|---|---|---|---|---|---|---|---|
| EXPANDED_BASELINE | JAVA | 16/4 | 1/0/15/0 | 100.00% | 0.00% | 6.25% | 100.00% | 116232/4964 | 3.600 | 372044/255626 |
| EXPANDED_BASELINE | TYPESCRIPT | 16/4 | 2/0/14/0 | 100.00% | 0.00% | 12.50% | 50.00% | 102367/5510 | 3.845 | 281768/135573 |
| GRAPH_GUIDED | JAVA | 16/4 | 2/0/12/2 | 100.00% | 0.00% | 12.50% | 100.00% | 70405/6434 | 4.384 | 207371/124763 |
| GRAPH_GUIDED | TYPESCRIPT | 16/4 | 2/0/14/0 | 100.00% | 0.00% | 12.50% | 50.00% | 41253/5855 | 4.140 | 89254/25684 |
| LOCAL_ONLY | JAVA | 16/4 | 1/0/15/0 | 100.00% | 0.00% | 6.25% | 75.00% | 20471/4980 | 4.377 | 39599/25655 |
| LOCAL_ONLY | TYPESCRIPT | 16/4 | 2/0/14/0 | 100.00% | 0.00% | 12.50% | 50.00% | 17100/4668 | 3.419 | 24583/12261 |

Per-repository descriptive counts (small N; no project superiority inference):

| Strategy | Repository | Negative/OOS | TN/FP/Abstain/Scope | OOS correct | Failed |
|---|---|---|---|---|---|
| EXPANDED_BASELINE | adonisjs-core | 4/1 | 1/0/3/0 | 1/1 | 0 |
| EXPANDED_BASELINE | alibaba-jetcache | 4/1 | 0/0/4/0 | 1/1 | 0 |
| EXPANDED_BASELINE | alibaba-sentinel | 4/1 | 1/0/3/0 | 1/1 | 0 |
| EXPANDED_BASELINE | apache-commons-lang | 4/1 | 0/0/4/0 | 1/1 | 0 |
| EXPANDED_BASELINE | colinhacks-zod | 4/1 | 0/0/4/0 | 0/1 | 0 |
| EXPANDED_BASELINE | google-gson | 4/1 | 0/0/4/0 | 1/1 | 0 |
| EXPANDED_BASELINE | trpc-trpc | 4/1 | 0/0/4/0 | 0/1 | 0 |
| EXPANDED_BASELINE | typestack-class-validator | 4/1 | 1/0/3/0 | 1/1 | 0 |
| GRAPH_GUIDED | adonisjs-core | 4/1 | 1/0/3/0 | 1/1 | 0 |
| GRAPH_GUIDED | alibaba-jetcache | 4/1 | 1/0/3/0 | 1/1 | 0 |
| GRAPH_GUIDED | alibaba-sentinel | 4/1 | 1/0/3/0 | 1/1 | 0 |
| GRAPH_GUIDED | apache-commons-lang | 4/1 | 0/0/3/1 | 1/1 | 0 |
| GRAPH_GUIDED | colinhacks-zod | 4/1 | 0/0/4/0 | 0/1 | 0 |
| GRAPH_GUIDED | google-gson | 4/1 | 0/0/3/1 | 1/1 | 0 |
| GRAPH_GUIDED | trpc-trpc | 4/1 | 0/0/4/0 | 0/1 | 0 |
| GRAPH_GUIDED | typestack-class-validator | 4/1 | 1/0/3/0 | 1/1 | 0 |
| LOCAL_ONLY | adonisjs-core | 4/1 | 1/0/3/0 | 1/1 | 0 |
| LOCAL_ONLY | alibaba-jetcache | 4/1 | 0/0/4/0 | 1/1 | 0 |
| LOCAL_ONLY | alibaba-sentinel | 4/1 | 1/0/3/0 | 1/1 | 0 |
| LOCAL_ONLY | apache-commons-lang | 4/1 | 0/0/4/0 | 1/1 | 0 |
| LOCAL_ONLY | colinhacks-zod | 4/1 | 0/0/4/0 | 0/1 | 0 |
| LOCAL_ONLY | google-gson | 4/1 | 0/0/4/0 | 0/1 | 0 |
| LOCAL_ONLY | trpc-trpc | 4/1 | 0/0/4/0 | 0/1 | 0 |
| LOCAL_ONLY | typestack-class-validator | 4/1 | 1/0/3/0 | 1/1 | 0 |

## K. Paired strategy comparisons

Complete successful triples: **40/40**. Incomplete triple case IDs: `[]`. Quality comparisons use matched successful cases. Operational comparisons retain all 40 requests per strategy, including any retry/failure attempts. No incomplete pairs are silently dropped.

| Comparison | Complete pairs | Agreement | Input reduction | Context reduction | Source reduction | Mean latency from−to s | Cost from−to USD |
|---|---|---|---|---|---|---|---|
| LOCAL_ONLY → GRAPH_GUIDED | 40/40 | 90.00% | 66.35% | 78.36% | 74.80% | -0.364 | -0.0087292 |
| GRAPH_GUIDED → EXPANDED_BASELINE | 40/40 | 92.50% | 48.92% | 54.63% | 61.54% | 0.540 | -0.0097866 |
| LOCAL_ONLY → EXPANDED_BASELINE | 40/40 | 97.50% | 82.81% | 90.18% | 90.31% | 0.176 | -0.0185158 |

**LOCAL_ONLY → GRAPH_GUIDED**: missing pair case IDs `[]`. Matched quality deltas (to−from): `{"FPR": 0.0, "abstention_rate": -0.09375, "definitive_coverage": 0.03125, "effective_negative_correctness": 0.03125, "oos_recognition": 0.125, "specificity": 0.0}`.

| From judgment | To judgment | Count |
|---|---|---|
| INSUFFICIENT_CONTEXT | INSUFFICIENT_CONTEXT | 28 |
| INSUFFICIENT_CONTEXT | NOT_APPLICABLE | 3 |
| INSUFFICIENT_CONTEXT | NOT_SUPPORTED | 1 |
| NOT_APPLICABLE | NOT_APPLICABLE | 5 |
| NOT_SUPPORTED | NOT_SUPPORTED | 3 |

**GRAPH_GUIDED → EXPANDED_BASELINE**: missing pair case IDs `[]`. Matched quality deltas (to−from): `{"FPR": 0.0, "abstention_rate": 0.09375, "definitive_coverage": -0.03125, "effective_negative_correctness": -0.03125, "oos_recognition": 0.0, "specificity": 0.0}`.

| From judgment | To judgment | Count |
|---|---|---|
| INSUFFICIENT_CONTEXT | INSUFFICIENT_CONTEXT | 28 |
| NOT_APPLICABLE | INSUFFICIENT_CONTEXT | 2 |
| NOT_APPLICABLE | NOT_APPLICABLE | 6 |
| NOT_SUPPORTED | INSUFFICIENT_CONTEXT | 1 |
| NOT_SUPPORTED | NOT_SUPPORTED | 3 |

**LOCAL_ONLY → EXPANDED_BASELINE**: missing pair case IDs `[]`. Matched quality deltas (to−from): `{"FPR": 0.0, "abstention_rate": 0.0, "definitive_coverage": 0.0, "effective_negative_correctness": 0.0, "oos_recognition": 0.125, "specificity": 0.0}`.

| From judgment | To judgment | Count |
|---|---|---|
| INSUFFICIENT_CONTEXT | INSUFFICIENT_CONTEXT | 31 |
| INSUFFICIENT_CONTEXT | NOT_APPLICABLE | 1 |
| NOT_APPLICABLE | NOT_APPLICABLE | 5 |
| NOT_SUPPORTED | NOT_SUPPORTED | 3 |

Human-class-separated transition matrices and full matched quality denominators are retained in `evaluation-v1.json`. Resource savings must be read alongside negative correctness and scope recognition; this cohort does not establish sensitivity or overall superiority.

## L. Fixed IAM sensitivity strata

All cases remain in the primary cohort. Strata use frozen diagnostics, with no post hoc repair, exclusion, relabeling or resampling.

| Strategy | Stratum | Negative/OOS | TN/FP/Abstain/Scope | Specificity | FPR | Effective | Definitive coverage | Abstention | OOS recognition |
|---|---|---|---|---|---|---|---|---|---|
| EXPANDED_BASELINE | PARTIAL_INVALID_IAM | 24/6 | 1/0/23/0 | 100.00% | 0.00% | 4.17% | 4.17% | 95.83% | 66.67% |
| EXPANDED_BASELINE | VALID_IAM | 8/2 | 2/0/6/0 | 100.00% | 0.00% | 25.00% | 25.00% | 75.00% | 100.00% |
| GRAPH_GUIDED | PARTIAL_INVALID_IAM | 24/6 | 2/0/20/2 | 100.00% | 0.00% | 8.33% | 8.33% | 83.33% | 66.67% |
| GRAPH_GUIDED | VALID_IAM | 8/2 | 2/0/6/0 | 100.00% | 0.00% | 25.00% | 25.00% | 75.00% | 100.00% |
| LOCAL_ONLY | PARTIAL_INVALID_IAM | 24/6 | 1/0/23/0 | 100.00% | 0.00% | 4.17% | 4.17% | 95.83% | 50.00% |
| LOCAL_ONLY | VALID_IAM | 8/2 | 2/0/6/0 | 100.00% | 0.00% | 25.00% | 25.00% | 75.00% | 100.00% |

## M–N. Real usage, latency and cost

| Strategy | Input | Output | Total | Mean/median/p95/max attempt s | Mean successful logical s | Estimated USD | Context/source chars | Truncated |
|---|---|---|---|---|---|---|---|---|
| EXPANDED_BASELINE | 218599 | 10474 | 229073 | 3.722/3.482/5.123/5.885 | 3.722 | 0.0270969 | 653812/391199 | 40 |
| GRAPH_GUIDED | 111658 | 12289 | 123947 | 4.262/4.146/6.694/9.164 | 4.262 | 0.0173103 | 296625/150447 | 19 |
| LOCAL_ONLY | 37571 | 9648 | 47219 | 3.898/3.412/6.293/17.698 | 3.898 | 0.0085811 | 64182/37916 | 3 |

Attempt latency measures elapsed transport/response processing wall time; successful logical latency sums attempt durations, excluding retry backoff. Mean/median/p95/max token counts and per-request context/usage links are retained in evaluation/context-usage artifacts.

Experiment usage: **367828 input + 32411 output = 400239 tokens**. All live calls including connectivity: **367848 input + 32416 output = 400264 tokens**.

Estimated experiment cost from actual usage: **$0.0529883**; connectivity: **$0.0000045**; combined estimated exposure: **$0.0529928**. Actual provider invoice cost = **null** (not supplied by Responses). Unknown-usage attempts: 0.

Pricing is the separately versioned user-confirmed assumption: short input $0.10/M, output $0.50/M; >272,000 input tokens uses long input $0.20/M and output $0.75/M for the whole request. No cached-input discounts or Batch rates are assumed. Pricing metadata remains separate from the frozen scientific protocol.

Approved preflight: expected $0.0809569; conservative $0.2748260; configured primary $0.5132160; extra retries $1.0264320; absolute configured experiment maximum $1.5396480. Actual retry exposure used: **$0**. The $0.95 pre-call guard did not trigger. $1 covered this completed run; $2 and $5 would also cover it. $1 alone does not cover the theoretical all-retries maximum.

Long-context attempts: **0**; attempts approaching 90% of the 1,050,000-token window: **0**. All output budgets stayed within the frozen 2,000 cap and the model maximum 128,000.

## O–R. Scientific boundaries and P013 immutability

Positive Recall = **null**, F1 = **null**, FNR = **null**. Zero human positives prevent primary semantic effectiveness claims. Structural V2 = **NOT RUN**; Hybrid = **NOT RUN**; Security analysis = **NOT RUN**; PROMPT 015 = **NOT STARTED**; Full Hybrid = **NOT_READY**.

P013 fingerprints, native review freeze, immutable file hashes, case universe and annotation lineage were reverified after execution. Ground truth and human rationales were not modified. P011/old experiment artifacts remain unchanged.

| P013 object | Unchanged fingerprint |
|---|---|
| all_frozen_p013_fingerprints_verified | True |
| catalog | 9d5e3aad6ce60a5d65ed0b1b34976066301be539c220bd8379325884985c0443 |
| corpus | fe31539b44938fb1f87bcbc914d08af6cbdb2f7f25f23420fb92b09b0d6a9143 |
| corpus_freeze | 61a87204f96a7c67981db2e6f3093ddc7708d3e05318f04b7a60b07b26c5e789 |
| freeze | 6ed86e0806de70b797fff5d28a0d9a6417f65ba9cbcb85c131621aba73653a5f |
| native_freeze | 7bc1dd4f4e48f6a32e9b29071e460effe8c5f8eb79e38ea33bcf13e5f504f2a3 |
| report | d77b39c7a05899460ec2c7c5b86da428e3ea66ba29a01ae09803bc7daa9868f6 |
| sample | 3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9 |
| store | 684577a73716e15792e04cee77c8220bd4bd5e6c4363cbd1880b886f50eb957b |
| truth | 14e8de64c7b0d1ccaa11dc6d0fed247ea723abc6bca2a1445f8f8298895ca0e4 |

Limitations: all-negative/OOS cohort; small per-rule/repository strata; partial invalid IAMs and truncation; context does not prove absence of a violation; provider/model nondeterminism and changing load/cache effects; serial timing remains observational. No confidence, significance, causality, positive detection or overall superiority claim is made.

## S–T. Validation, security and Git

Before paid experiment calls: `make check` passed Ruff, formatting, mypy and **1194 tests** (93% total coverage); targeted provider/executor tests passed **12 tests**. After evaluator and paired/operational metrics were finalized, `make check` passed again: **1194 tests**, Ruff/mypy green, 93% coverage. Freeze integrity, immutable truth join, stored request identities and P013 lineage checks passed. `git diff --check` passed. Tests use fake transports; they do not add live provider calls or execute V2/Hybrid experiments.

Security audit: current credential and distinctive fragments were checked only in process memory against indexed/intended artifacts and execution logs. No key, credential, authorization value or secret-bearing env file was persisted. `.env.ai.local` remains ignored and was never hashed, diffed, staged or serialized. Source-bearing request/answer material remains under ignored private directories. No provider authentication header is recorded.

[Security verification receipt](../../experiments/ai/semantic-context-live-v1/security-verification-v1.json): 1,374 files checked, including 973 indexed files, 140 intended untracked files, 243 private JSON files and 18 logs; zero credential-pattern findings. No secret or secret-derived fingerprint is stored in that receipt.

Final HEAD: `dcacc6a8ea42231e4d0fb97dcf171caaaae02a56`. Execution implementation/result diff is **uncommitted for review**, as required by PROMPT 014; no new commit or push. Expected working tree: README status update and new P014 scripts, metrics/tests, research/verification docs, connectivity and source-free live experiment artifacts. No frozen P013 or preflight file changes.

Artifacts: [AI freeze](../../experiments/ai/semantic-context-live-v1/real-ai-assessments-v1.json), [truth join](../../experiments/ai/semantic-context-live-v1/truth-join-v1.json), [evaluation](../../experiments/ai/semantic-context-live-v1/evaluation-v1.json), [context/usage](../../experiments/ai/semantic-context-live-v1/context-usage-v1.json), [cost accounting](../../experiments/ai/semantic-context-live-v1/cost-accounting-v1.json), [verification receipt](../../experiments/ai/semantic-context-live-v1/post-evaluation-verification-v1.json).
