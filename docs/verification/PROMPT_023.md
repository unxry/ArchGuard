# PROMPT 023 — Hybrid development freeze

P023_HYBRID_DEVELOPMENT_TRAINING_COMPLETE

**DEVELOPMENT VALIDATION — NON-FINAL.** Model selection uses the predeclared P020 protocol. These development metrics do not evaluate the thesis hypothesis or the final 300-case benchmark.

## A — Lineage and initial worktree

| Anchor | Commit | Ancestry |
| --- | --- | --- |
| P019 | 2f596fb57b00a1d8374cdcba50a98ab6ffbe4023 | PASS |
| P020_CLOSURE | 1891fa553218200139f027ed9c3a82d100f61462 | PASS |
| P021.A | e82de9d0efc8e7e4dda444626aae86ce7f851628 | PASS |
| P021.B.1 | 4a51a302c0b58ce148797aed14013803bf2a8488 | PASS |
| P021.B | 86f19f50de2f638a57192694e5c73afde3fa50dc | PASS |
| P022 | 8629d728bf80b4a5ba3009e8730ec14062a77abc | PASS |
| P022.LIVE | c416b1c1376009c8591026165323268201882495 | PASS |

Initial HEAD: `c416b1c1376009c8591026165323268201882495`. Actual ancestry and chronological ancestry between these anchors passed. The scientific tree initially had no changes; the sole unrelated change was ` D index(визуал).html`. Its content was not read; its unstaged deletion is preserved. P023 adds only the public-safe files listed by the P023 gate.

## B — DEVELOPMENT input verification

| Inventory | Expected | Bound | Missing | Duplicates |
| --- | --- | --- | --- | --- |
| Structural development cases | 180 | 180 | 0 | 0 |
| Semantic development cases | 100 | 100 | 0 | 0 |
| Total development cases | 280 | 280 | 0 | 0 |
| P022.LIVE structural LLM | 180 | 180 | 0 | 0 |
| P016 GRAPH_GUIDED semantic LLM | 100 | 100 | 0 | 0 |
| Development LLM total | 280 | 280 | 0 | 0 |
| Static/Graph evidence-alignment-v2 | 280 | 280 | 0 | 0 |
| Authoritative development truth | 280 | 280 | 0 | 0 |
| Joined development bundles | 280 | 280 | 0 | 0 |

No provider assessment, Static output, Graph output or Structural V2 fit was regenerated. The join uses stable scientific identifiers and verifies rule bindings, unique source coverage and frozen split membership. LLM order, filename order and array positions never determine a binding. Structural labels come from the P019 oracle; semantic labels come from P015 human ground truth. Construction intent and component/LLM predictions are never labels.

| Frozen source | Fingerprint |
| --- | --- |
| P022.LIVE normalized | da3f8f3f027eeaed0140c9ae2ce3fa137715e274977e5396522be4522855be81 |
| P022.LIVE raw ledger | 0a2a683cb7b9b53649b16510ca0bb82335e288b08d88276f93a57f2c9c9c8a9f |
| P022.LIVE usage | 4f058bdc0d528663af86516ab5bcb8ee92bb5219618e43036bd895041935f3bb |
| P022.LIVE lineage | 9be63a388cf6d56002d9b4958705377f68e5696681afc2552af4e490aa344723 |
| P022.LIVE completion | 7c67c7cc118b33a99e3a559584a975c740ddb11d88a5f9b929b15d13f115dc2c |
| P022.LIVE freeze | 8856006a895018463c76a1a085f84725ae49dcf23c9dad51e8ddf77fda0ca71a |
| P016 normalized | a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273 |
| P019 structural truth | f53ab09564d0481025ffb00a8cbef868a8085b69dca7ceaf2a390d577aeb0e24 |
| P015 semantic human truth | 1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276 |

P022.LIVE historical invocations remain 180 with 180 accepted, zero retries/recoveries/ambiguous attempts, no missing or duplicate bindings. P016 contributes exactly its previously accepted 100 GRAPH_GUIDED records; original categorical decisions and evidence are preserved. Historical invocation counts are not P023 calls.

## C — Frozen project-grouped split

| Partition | Cases | Projects | Binary eligible | Nonbinary preserved |
| --- | --- | --- | --- | --- |
| TRAIN | 196 | 196 | 193 | {"OUT_OF_SCOPE": 1, "UNCERTAIN": 2} |
| VALIDATION | 84 | 84 | 83 | {"UNCERTAIN": 1} |

TRAIN/VALIDATION project overlap: **0**. DEVELOPMENT/FINAL overlap: **0**, verified by the immutable source-free P020 development certificate, not by opening final project mappings or final case values. Split fingerprint: `159aae41b351cc2e100f082ae91f5eec382329730c7c5f4a4a54b67246f6504a`. No resplitting occurred. The four nonbinary cases remain in private cohort artifacts and descriptive category counts; they are excluded from binary fitting and binary metric denominators without coercion.

## D — Frozen protocol and feature schema

| Definition | Fingerprint |
| --- | --- |
| feature_schema | 1febc401be51406691f4816557e504b0a5f3698b29473951c497adc9e12728f2 |
| hybrid_protocol | 331ffb2bc8d9c9d8b99c2bd4d12fd5e929ba50b584b02eb49360b2e9eba2b77a |
| ablation_protocol | b0f57d269f7c945afa10d9ecd604700d1c1892eb95a98dac2e197fed0dc4b959 |
| selection_rule | 7019b8638d9830ff5bb6a6cf7ae7263d7b9d5ca08d2c2a79f3808139c54d01e2 |

STATIC: `static.positive`, `static.applicable`, `static.evidence_count`, `static.unresolved`.

GRAPH: `graph.positive`, `graph.applicable`, `graph.v2_score`, `graph.Ca`, `graph.Ce`, `graph.coupling`, `graph.I`, `graph.scc_size`, `graph.betweenness`, `graph.pagerank`, `graph.is_cyclic`.

LLM: `llm.supported`, `llm.not_supported`, `llm.abstention`, `llm.not_applicable`, `llm.evidence_available`, `llm.truncated`.

The ordered predictor whitelist contains 21 raw signals. Case/project identity, labels, reviewer identity, source identity, construction role, mutation/control intent, rationale, severity, confidence, usage, latency and cost are excluded. Rule identity only routes frozen scope and direct ARCH003 cycle constraints. H1/H2 encode standardized values and explicit missing indicators in the original P020 order, giving 30, 20, 34 and 42 encoded columns for A4, A5, A6 and A7 respectively.

H0 is deterministic evidence fusion with no learned weights. Each A4–A7 independently fits H1 weighted ridge (unit weights, L2=1) and H2 deterministic Newton logistic regression (unit weights, L2=1, maximum 200 iterations, tolerance 1e-10, 40 line-search steps). The intercept is unpenalized. A1–A3 are component baselines without meta-model fitting. Every learned preprocessing statistic uses only the 193 binary-eligible TRAIN rows, following the existing P020 median/mean/population-scale implementation.

The frozen threshold procedure is **TRAIN in-sample**, not cross-validation: evaluate `[0.25, 0.50, 0.75]` using the unchanged legacy fit function; maximize TRAIN F1, then Precision, then proximity to 0.5. The existing final symmetric threshold tie follows the original tuple comparison. No threshold is tuned on VALIDATION. Family selection maximizes primary VALIDATION F1, then Precision, then effective correctness, rounded to 12 decimals; null ranks below a defined metric, followed by lower complexity H0 < H1 < H2. Recall and coverage do not break ties.

Included explicit Static proof or included direct Graph ARCH003 cycle proof has unconditional positive precedence. An excluded component cannot override a model. When no included component is definitive, the original fusion semantics preserve abstention or non-applicability. Raw LLM `INSUFFICIENT_CONTEXT` remains distinct from `NOT_SUPPORTED` and `NOT_APPLICABLE`; only the common fusion vocabulary represents that abstention as `INSUFFICIENT_EVIDENCE`. No abstention is encoded as a negative decision.

Primary metrics use all binary-eligible cases in the unified cohort. Every positive non-SUPPORTED outcome counts as FN, including out-of-component-scope positives. TN requires a negative label and NOT_SUPPORTED; a negative abstention/non-applicable outcome is reported separately, not counted as TN. Effective correctness is `(TP+TN)/N`. Specificity and FPR use `TN+FP`; negative nondefinitive counts and coverage expose excluded nondefinitive negatives. Zero denominators yield null. Definitive-only and native-scope views are supplemental. No additional Accuracy definition is introduced.

## E — A1/A2/A3 DEVELOPMENT VALIDATION — NON-FINAL

| Baseline | N | TP | FP | TN | FN |
| --- | --- | --- | --- | --- | --- |
| A1 | 83 | 12 | 0 | 12 | 30 |
| A2 | 83 | 15 | 1 | 14 | 27 |
| A3 | 83 | 32 | 3 | 36 | 10 |

| Baseline | Precision | Recall | F1 | Specificity | FPR | FNR |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 1.000000000000 | 0.285714285714 | 0.444444444444 | 1.000000000000 | 0.000000000000 | 0.714285714286 |
| A2 | 0.937500000000 | 0.357142857143 | 0.517241379310 | 0.933333333333 | 0.066666666667 | 0.642857142857 |
| A3 | 0.914285714286 | 0.761904761905 | 0.831168831169 | 0.923076923077 | 0.076923076923 | 0.238095238095 |

| Baseline | effective_correctness | definitive_coverage | abstention | non_applicability | negative_nondefinitive |
| --- | --- | --- | --- | --- | --- |
| A1 | 0.289156626506 | 0.289156626506 | 0 | 59 | 29 |
| A2 | 0.349397590361 | 0.361445783133 | 0 | 53 | 26 |
| A3 | 0.819277108434 | 0.855421686747 | 12 | 0 | 2 |

## F — A4 (STATIC + GRAPH) candidates

| Candidate | Threshold | Precision | Recall | F1 | Effective correctness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | null | 0.964285714286 | 0.642857142857 | 0.771428571429 | 0.638554216867 | 0.650602409639 |
| H1 | 0.500000000000 | 0.964285714286 | 0.642857142857 | 0.771428571429 | 0.638554216867 | 0.650602409639 |
| H2 | 0.500000000000 | 0.964285714286 | 0.642857142857 | 0.771428571429 | 0.638554216867 | 0.650602409639 |

| Candidate | Fingerprint |
| --- | --- |
| H0 | 79e9d5392699694c83725c2a0944e255c070db5cdaac2d12873f0d196f2e9537 |
| H1 | 894cc2051d781f4f2b7d908c7bb101e21a1f55da329cbf1cbad18fe274e2d573 |
| H2 | 287110d5976c4cfec925033ec2f75b2078487946ed3982133cb294eb76a82a80 |

Selected family: **H0**. All three primary comparison metrics tie at 12 decimals; the predeclared lower-complexity tie-break selects H0. Selected model fingerprint: `79e9d5392699694c83725c2a0944e255c070db5cdaac2d12873f0d196f2e9537`.

## G — A5 (STATIC + LLM) candidates

| Candidate | Threshold | Precision | Recall | F1 | Effective correctness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | null | 0.914285714286 | 0.761904761905 | 0.831168831169 | 0.819277108434 | 0.855421686747 |
| H1 | 0.500000000000 | 0.914285714286 | 0.761904761905 | 0.831168831169 | 0.819277108434 | 0.855421686747 |
| H2 | 0.500000000000 | 0.941176470588 | 0.761904761905 | 0.842105263158 | 0.831325301205 | 0.855421686747 |

| Candidate | Fingerprint |
| --- | --- |
| H0 | c507d61aee3461e6ab68a6a5b56e38ac150dd823bab329316d26649e544371ac |
| H1 | d73a0916cbddcc954335112bc93982df0c14a7aae2fea2730db361607264d659 |
| H2 | b61eaf280d5da054ce48b05c28f6cce58428fa7b1b56b1b9eb3e6c3703ec8641 |

Selected family: **H2**. H2 has the highest primary VALIDATION F1; later tie-breaks are not needed. Selected model fingerprint: `b61eaf280d5da054ce48b05c28f6cce58428fa7b1b56b1b9eb3e6c3703ec8641`.

## H — A6 (GRAPH + LLM) candidates

| Candidate | Threshold | Precision | Recall | F1 | Effective correctness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | null | 0.913043478261 | 1.000000000000 | 0.954545454545 | 0.951807228916 | 1.000000000000 |
| H1 | 0.500000000000 | 0.913043478261 | 1.000000000000 | 0.954545454545 | 0.951807228916 | 1.000000000000 |
| H2 | 0.500000000000 | 0.933333333333 | 1.000000000000 | 0.965517241379 | 0.963855421687 | 1.000000000000 |

| Candidate | Fingerprint |
| --- | --- |
| H0 | 958b721b1860414ec3a0589019c5ef7d0b23ef8738640a1b9cd92d99a4439ee8 |
| H1 | 92945c9f3c0e8e02288e307e5406b6a45e4a2beda3e768210833b2b6ee374e77 |
| H2 | f86a7765b926d10d24c5a42c2912c4cce78351014da79d206afa89562b968fce |

Selected family: **H2**. H2 has the highest primary VALIDATION F1; later tie-breaks are not needed. Selected model fingerprint: `f86a7765b926d10d24c5a42c2912c4cce78351014da79d206afa89562b968fce`.

## I — A7 (STATIC + GRAPH + LLM) candidates

| Candidate | Threshold | Precision | Recall | F1 | Effective correctness | Coverage |
| --- | --- | --- | --- | --- | --- | --- |
| H0 | null | 0.913043478261 | 1.000000000000 | 0.954545454545 | 0.951807228916 | 1.000000000000 |
| H1 | 0.750000000000 | 0.976744186047 | 1.000000000000 | 0.988235294118 | 0.987951807229 | 1.000000000000 |
| H2 | 0.750000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 |

| Candidate | Fingerprint |
| --- | --- |
| H0 | d1cf3fa4ebcc3a1bb3c70dc4d326e75a48f6c929228effa4610337c70be6ba9c |
| H1 | 2d4857409738567c73355324e083a60bac0558088b79d18463082a80bbc1b7c4 |
| H2 | fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b |

Selected family: **H2**. H2 has the highest primary VALIDATION F1; later tie-breaks are not needed. Selected model fingerprint: `fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b`.

**FINAL_FULL_HYBRID_MODEL: H2, threshold 0.75.** The selected model is the original TRAIN-fitted candidate; no TRAIN+VALIDATION refit was performed.

| Full hybrid binding | Value |
| --- | --- |
| candidate_fingerprint | fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b |
| preprocessing_fingerprint | 0256c62745ac03b5f8c3a35ad2449761944d35d3d2ef12d0b793c4a68ee4c08c |
| parameter_fingerprint | bd6048cba3b1914da854837ce1884af55c80f2ad98646914c5a60139315baa76 |
| threshold | 0.750000000000 |
| precedence_fingerprint | 91b652b7f39ec05cf2ec3eeb79cc18f0de4e32dc91565ec7c2c6e165bec0bbec |
| implementation_fingerprint | e518280315a20b11d4b970227aecb5b7ff6257bc7e6e9a2c1881c5551dc8fe36 |

## J — Selected ablation registry and descriptive comparison

| Configuration | State/family | Frozen model fingerprint |
| --- | --- | --- |
| A1 | Unmodified STATIC component output | Bound by component evidence fingerprint |
| A2 | Unmodified GRAPH component output | Bound by component evidence fingerprint |
| A3 | Unmodified frozen LLM component output | Bound by LLM evidence fingerprint |
| A4 | H0 | 79e9d5392699694c83725c2a0944e255c070db5cdaac2d12873f0d196f2e9537 |
| A5 | H2 | b61eaf280d5da054ce48b05c28f6cce58428fa7b1b56b1b9eb3e6c3703ec8641 |
| A6 | H2 | f86a7765b926d10d24c5a42c2912c4cce78351014da79d206afa89562b968fce |
| A7 | H2 | fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b |

| Selected configuration | TP | FP | TN | FN | F1 | Effective correctness | Coverage |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 12 | 0 | 12 | 30 | 0.444444444444 | 0.289156626506 | 0.289156626506 |
| A2 | 15 | 1 | 14 | 27 | 0.517241379310 | 0.349397590361 | 0.361445783133 |
| A3 | 32 | 3 | 36 | 10 | 0.831168831169 | 0.819277108434 | 0.855421686747 |
| A4 | 27 | 1 | 26 | 15 | 0.771428571429 | 0.638554216867 | 0.650602409639 |
| A5 | 32 | 2 | 37 | 10 | 0.842105263158 | 0.831325301205 | 0.855421686747 |
| A6 | 42 | 3 | 38 | 0 | 0.965517241379 | 0.963855421687 | 1.000000000000 |
| A7 | 42 | 0 | 41 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 |

Selected registry fingerprint: `269e4fe3cdcab8b3461e8f7b24b4eb9f49b0cf455a843b776fb5e490de53a9df`. DEVELOPMENT prediction registry fingerprint: `5e663cf3890d19fb89cac2dc0672091ef4a85249ab7eb7040ea1844b07bd6632`. The private prediction freeze covers TRAIN and VALIDATION for all component baselines, all 12 multi-component candidates and selected A4–A7. Final predictions: 0.

Paired DEVELOPMENT diagnostics compare the selected A7 with each baseline/selected ablation; these are descriptive aggregate counts without p-values or significance claims.

| A7 vs | Both correct | A7 only correct | Comparison only correct | Neither correct |
| --- | --- | --- | --- | --- |
| A1 | 24 | 59 | 0 | 0 |
| A2 | 29 | 54 | 0 | 0 |
| A3 | 68 | 15 | 0 | 0 |
| A4 | 53 | 30 | 0 | 0 |
| A5 | 69 | 14 | 0 | 0 |
| A6 | 80 | 3 | 0 | 0 |

Full categorical coverage/abstention transitions, rule/family/language strata, TRAIN diagnostics and supplemental definitive-only/native-scope metrics are preserved in the public aggregate JSON. They do not alter selection or justify thesis effectiveness claims. TRAIN tables are labeled TRAIN_DIAGNOSTIC_ONLY.

## K — One-pass selection chronology and technical correction

The authorized coordinator freezes the DEVELOPMENT truth join and writes a closed development input root. The TRAIN worker can read only TRAIN and metadata; it cannot open validation labels or any final/reviewer data. Both independently fitted TRAIN candidate sets were frozen in isolated primary/reproduction output subtrees before the worker opened VALIDATION performance. The worker then reads validation labels exactly once, performs one primary selection pass, and checks an identical reproduction replay using the same cached validation rows. There are no fits after that read. Subsequent verification reads sealed files without fitting, prediction generation or selection.

| Audit | Result |
| --- | --- |
| All TRAIN candidates frozen before VALIDATION comparison | YES |
| Validation label file opened once by fit/selection worker | YES |
| Primary selection passes | 1 |
| Identical reproduction comparison replay | 1 |
| Validation-driven feature modification | NO |
| Validation-driven solver modification | NO |
| Post-selection TRAIN+VALIDATION refit | NO |
| Final-test access | NO |
| Selection receipt fingerprint | e4220400f08739d5ec71bec0747b23e2ab412b01b40236e5b03c4bcb0ec3cb7d |

The first complete make check reported one architecture-boundary failure: the new benchmark helper imported calibration. After scientific freeze, the helper was relocated intact into `src/archguard/calibration/hybrid_development.py`; its bytes are identical to the executed module. Scientific orchestration function ASTs, including input preparation and fit_runs, are unchanged. Only imports and read-only implementation verification/closure handling changed. Original execution sources are preserved privately with the original implementation binding. A separately sealed technical correction binds current source hashes to the unchanged models and results. No actual TRAIN fit, validation selection, threshold construction, parameter update or metric regeneration followed this correction. Correction regressions reject calibration-body, fit-body or legacy-solver drift.

Original scientific implementation binding: `e518280315a20b11d4b970227aecb5b7ff6257bc7e6e9a2c1881c5551dc8fe36`. Technical boundary correction receipt: `d851ea5086b1da8dcf04859d64f1c6e05c03786b5076975f2ac64575cea701ae`. Original execution source freeze: `0ca734e2e1799353935527401ef5ed0becb65fcbd91e81ca8efdfe878922d300`. Scientific aggregate freeze remains `458ce5a8fcf1a95e9f80eed737ff75eb32e0c716b8dbc7d8af7f77eecd23af21`. A persistent execution-start marker rejects automatic restart of an interrupted unfinished run; completed execution is verification-only.

## L — Reproducibility

| Configuration | First run | Second run | Candidate/selected fingerprint identical |
| --- | --- | --- | --- |
| A4 | H0 | H0 | YES |
| A5 | H2 | H2 | YES |
| A6 | H2 | H2 | YES |
| A7 | H2 | H2 | YES |

Both runs consume identical frozen development inputs. Their independent candidate fits, preprocessing, coefficients, threshold states, feature matrix fingerprints, validation metrics, prediction fingerprints, selections and selected registry are identical. Twelve candidate fingerprints per run agree exactly. Scientific fingerprints contain no timestamps. The second TRAIN fit completed before any validation performance was opened; the reproduction check does not retrain after selection. Reproducibility receipt: `cb0531f86317a32b1811363667894cf971cca9671ad56a5d3f8e07a4bbf72d7c`.

## M — Scientific and paid-action boundary

| Boundary | P023 result |
| --- | --- |
| P021.B final semantic truth read | NO |
| Final structural truth read | NO |
| Final evidence used for preprocessing/fitting | NO |
| Final truth mounted in training input root | 0 |
| Final case-level truth reads | 0 |
| Final LLM calls | 0 |
| Final Hybrid/ablation predictions | 0 |
| Provider calls | 0 |
| Connectivity calls | 0 |
| Spend | $0 |
| Security | NO |
| Final benchmark evaluation | NO |
| Hypothesis conclusion | NO |
| Paid execution approved | NO |

The previous $2.31 approval covered the completed P022 development calls and is expired in scope. No credentials or secret env files were accessed. The offline audit denies network/provider transport, credential files, final roots, final coordinator artifacts, reviewer intake, and all undeclared worker input paths. A source-free P020 development overlap certificate establishes separation without final case-level access. Human development truth and labels remain private. The next paid stage requires new explicit human approval.

## N — Quality

P023 synthetic tests and architecture boundary: **54 passed** (53 P023 tests plus the boundary test). Targeted frozen-protocol/LLM/component/truth regressions: **333 passed**. The first full check: **2144 passed, 1 boundary failure**; that technical dependency error was corrected without changing scientific artifacts. Final full make check: **2149 passed, coverage 86%, PASS**. Ruff check, format check (479 files), and strict mypy (237 source files) passed. Public/private and secret-pattern audits passed for prepared inputs, frozen models, execution source archive and intended public artifacts; completion receipt will record final checks.

Commands actually run:

```text
.venv/bin/pytest -q --tb=short tests/benchmark/test_hybrid_development.py tests/unit/test_boundaries.py
.venv/bin/pytest -q --tb=short tests/benchmark/test_unified_hybrid.py tests/intelligence/test_development_llm_executor.py tests/benchmark/test_component_holdout.py tests/benchmark/test_semantic_final_truth.py tests/benchmark/test_semantic_holdout.py tests/intelligence/test_semantic_positive_execution.py
.venv/bin/ruff check <P023 sources and tests>
.venv/bin/ruff format <P023 sources and tests>
.venv/bin/mypy src/archguard/infrastructure/hybrid_development.py src/archguard/calibration/hybrid_development.py
make check
.venv/bin/python scripts/prompt023_hybrid_development.py prepare
.venv/bin/python scripts/prompt023_hybrid_development.py execute
.venv/bin/python scripts/prompt023_hybrid_development.py verify
git diff --check -- . ":(exclude)index(визуал).html"
```

Data-join verification confirms 280 joined cases/LLM rows/truth bindings, stable-ID coverage, frozen feature schema, split separation, zero final rows, unchanged candidate/selection/registry fingerprints and no post-selection refit. Positive/negative/UNCERTAIN/OUT_OF_SCOPE remain distinct; raw LLM one-hot signals must match their original decisions. Leakage tests reject identities, intent, labels, correctness and provider metadata as predictors. Solver tests assert unit weights/L2 and missing-indicator ordering. Full make check includes P020/P022/P019/P016/P015 and privacy regressions. No live provider test is invoked. Final verification details are in `experiments/unified-hybrid/p023-verification-v1.json`.

## O — Freeze fingerprints

| Freeze | Fingerprint |
| --- | --- |
| DEVELOPMENT_LLM_EVIDENCE | 9d74fcd1207543092867f259a93a61f92eb602d475ae11d1281839c2bf17db3c |
| DEVELOPMENT_COMPONENT_EVIDENCE | d2f7084cba5d11d15658c72b9149e85e336677d40f986ebb1afa90b70457b304 |
| DEVELOPMENT_TRUTH_BINDING | 8128d60c6ce3d3c8f55ee4167c5b3cc43ab7fbe5a07531af398b626c4af39e7c |
| DEVELOPMENT_EVIDENCE_JOIN | 3e3708f1a6615eb8f6f714d232dffa7cf7524e246b818da37ce063583d55352d |
| TRAIN_FEATURE_MATRIX | 42436f1f4753329253d41de0f6290fe1392ce758c09437628db42d2c43a071ee |
| TRAIN_LABELS | 5403eb450708747a6cd5ba698f380ebd677998068afd0c7d0411596f93fef3b1 |
| VALIDATION_FEATURE_MATRIX | 1dbfc97435121d5ac1bd46389f7046c0bccaee1709646d7662e16f2e0de2cdec |
| VALIDATION_LABELS | f3b99b4085ed50fa6102d87828d197b030d324e8c5e3ba96796e586f693486ac |
| VALIDATION_SELECTION_RECEIPT | e4220400f08739d5ec71bec0747b23e2ab412b01b40236e5b03c4bcb0ec3cb7d |
| HYBRID_SELECTED_MODEL_REGISTRY | 269e4fe3cdcab8b3461e8f7b24b4eb9f49b0cf455a843b776fb5e490de53a9df |
| DEVELOPMENT_PREDICTION_REGISTRY | 5e663cf3890d19fb89cac2dc0672091ef4a85249ab7eb7040ea1844b07bd6632 |
| FINAL_FULL_HYBRID_MODEL | fb908199217bad69ff2fd41770ad6756065828a9c9837b124fe96a05d2f7101b |
| SCIENTIFIC_AGGREGATE | 458ce5a8fcf1a95e9f80eed737ff75eb32e0c716b8dbc7d8af7f77eecd23af21 |
| TECHNICAL_BOUNDARY_CORRECTION | d851ea5086b1da8dcf04859d64f1c6e05c03786b5076975f2ac64575cea701ae |

Private ignored freezes hold case-level truth, mappings, feature matrices, preprocessing parameters, coefficients/intercepts, thresholds and predictions. Public JSON contains only aggregate views, family names, solver configuration and opaque fingerprints. Coefficients, source snippets, reviewer data, human rationale and case-level outcomes are not published. The original execution source archive and start marker are ignored as well.

## P — Git closure and stop boundary

Commit scope: P023 calibration/infrastructure/CLI/tests, aggregate result, technical boundary correction, verification receipt and this document. Commit title: `feat: freeze hybrid development model selection`. Normal push to origin/main only. The final delivery records the new commit SHA and actual push result; this document belongs to that commit and therefore cannot contain its own hash. The expected final scientific tree is clean with only the authorized unstaged HTML deletion.

Final status after quality and Git closure:

```text
P023_HYBRID_DEVELOPMENT_TRAINING_COMPLETE
DEVELOPMENT_EVIDENCE_JOIN_FROZEN
HYBRID_CANDIDATES_FITTED
VALIDATION_SELECTION_COMPLETE
FULL_HYBRID_MODEL_FROZEN
ABLATION_MODELS_FROZEN
NO_POST_SELECTION_REFIT
FINAL_HOLDOUT_UNTOUCHED
FINAL_HOLDOUT_LLM_NOT_EXECUTED
PROVIDER_CALLS = 0
SPEND = $0
PAID_EXECUTION_APPROVED = NO
READY_FOR_P024_FINAL_LLM_PREFLIGHT
STOP
```
