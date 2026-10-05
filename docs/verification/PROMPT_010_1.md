# PROMPT 010.1 verification — 2026-10-05

1. **Status:** Expanded Benchmark & Calibration Cohort Foundation complete; separate uncommitted
   reviewable diff. PROMPT 011 not started.
2. **Git:** PROMPT 010 audit passed 1025 tests with 94% overall coverage (branches enabled) before commit.
   HEAD `a1b466dd45a20bbc59f86d3671bdd5e9d7833369`; commit `feat: add benchmark ground truth and mutation dataset foundation` pushed
   to origin/main. No force push, reset or global credential modification. 010.1 is not committed.
3. **Changed files:** 287 files: 273 benchmark generation/source/truth/spec/profile/mutation/split
   files; five source modules; two test files; six documentation files; README. New source modules:
   benchmark/materialization.py, cohort.py, readiness.py and infrastructure/calibration_cohort.py;
   benchmark_cli.py adds readiness/export-cohort. Old mutation-tampering test now chooses a manifest
   referenced by its dataset instead of filesystem glob order; original rejection assertion retained.
4. **Versions:** dataset schema 1.0, expanded dataset 1.1.0; original 1.0.0 files unchanged;
   feature schema calibration-evidence-v1; export calibration-cohort-v1;
   report calibration-readiness-v1.
5. **Composition:** 56 repositories, 18 families, 138 cases: 68 positive, 70 negative, zero unknown.
6. **Splits (families/cases/P/N):** TRAIN 12/90/44/46; VALIDATION 3/24/12/12; TEST 3/24/12/12.
7. **Task coverage (families/P/N):** TRAIN Static 5/10/10, Graph 4/20/22, Semantic 3/14/14;
   VALIDATION and TEST each Static 1/6/6, Graph 1/2/2, Semantic 1/4/4.
8. **ARCH001–205 distribution:** all 15 rules and explicit empty holdouts are in
   [EXPERIMENT_SPLITS](../research/EXPERIMENT_SPLITS.md#rule-distribution).
9. **New graph families:** fan-in, fan-out, diamond, cluster-bridge and stable-core. Adjacency,
   direction and component roles differ; thresholds alone do not define a new family.
10. **New semantic families:** shipping, reporting (Java-only), ledger and UI ordering (TS-only).
    Translated counterparts share their original family and partition.
11. **Hard negatives:** validation/mapping/delegation, abstract persistence, legitimate storage and
    presentation responsibilities, high-coupling single-purpose orchestration. Neutral-name positives
    perform actual business/protocol/persistence responsibility. All semantic truth remains UNREVIEWED.
12. **Evaluation anchors:** exact label-free locators/rules resolve IAM subjects and measure actual
    channels, even without a production candidate. No Findings or Hybrid decisions are synthesized.
13. **Feature exports (records/P/N):** TRAIN 360/176/184; VALIDATION 96/48/48; TEST 96/48/48;
    total 552/272/280. Four variants per case are correlated. Missing values remain missing;
    negatives retain real nonzero metrics. Selection and AI-target flags remain explicit.
14. **Eligibility:** 262 eligible, 290 ineligible across all variants (TRAIN 178/182,
    VALIDATION 40/56, TEST 44/52). Complete STRUCTURAL variant alone: 94 eligible records
    (TRAIN 62, VALIDATION 16, TEST 16). Required genuine channels/metrics, known truth and exact
    schema/provenance binding are enforced. These are engineering eligibility counts, not fitting.
15. **Structural Hybrid:** READY by declared task/family/class composition; Static and Graph READY.
    This makes no statistical sufficiency or final classifier performance claim.
16. **Full Hybrid:** NOT_READY; Semantic NOT_READY. No real assessments or reviewed semantic labels;
    each split has insufficient eligible semantic families/classes. Explicit permanent stage reason:
    REAL_AI_ASSESSMENT_COHORT_AND_SEMANTIC_REVIEW_REQUIRED.
17. **Scripted exclusion:** SCRIPTED_TEST always ineligible with OFFLINE_CONTRACT_ONLY. All three
    semantic decisions are contract-tested; eligibility/source overrides fail. Reserved REAL_PROVIDER
    remains ineligible here. Default exports contain zero real, zero scripted and 552 absent AI records;
    44 future AI manifests have absent provider/model/prompt/context/artifact and unknown usage.
18. **Tests:** 1056 passed, 0 failed, 0 skipped; all previous 1025 retained and 31 new cases.
    Critical coverage includes label flips/AST boundary, no-candidate negatives and missed positives,
    missing/bounded metrics, foreign evidence, unknown/scripted/real eligibility, family isolation,
    single-class/task/family failure, schema/fingerprint/provenance tampering and deterministic CLI.
19. **Coverage:** 94% overall with branch coverage; materialization 100%, cohort 91%, readiness 98%,
    infrastructure cohort 90%. No coverage claim substitutes for independent semantic review.
20. **Gates:** locked uv sync; Ruff check; format check (307 files); strict mypy (177 source files);
    make check; git diff --check all pass. Lockfile/dependencies unchanged. No live AI or fitting.
21. **A/B:** complete expanded regeneration preserves all 402 dataset-root files byte-for-byte.
    Independent CLI A/B exports and readiness stdout are byte-identical; dataset fingerprint
    `c40fe95b2880ab50ba1464155e16ef19c47cf9aa6c207725dba362294a967c31`. Split manifest fixed before scoring.
22. **macOS/Linux:** rebuilt archguard:prompt0101, Python 3.13-slim, nonroot UID/GID 999,
    network disabled, read-only root and dataset mount. Validate, readiness and all five exported
    files match macOS byte-for-byte. No provider or generated Java/Node application is executed.
23. **Limitations:** synthetic/curated engineering seed; correlated translations/mutations/variants;
    only three families per holdout; graph ARCH101–104 and semantic ARCH201/204 lack per-rule
    holdouts; no real OSS validation, semantic review, real provider assessments, fitting, threshold
    tuning, confidence/significance statistics or final ablation. Original manifests remain immutable.
24. **Next:** review 010.1, then explicitly requested PROMPT 011 may implement Static+Graph
    calibration machinery. Full Hybrid requires independent semantic review and validated real AI
    assessments first. No final thesis evaluation may use scripted AI.

## Measured determinism

Canonical file SHA-256 values below match A/B and macOS/Linux. Full runtime exports and logs are
kept outside Git in /tmp. Dataset root is 310,130 bytes; the largest added manifest is 76,379 bytes.
No cache, temporary mutant, log, JSONL cohort or duplicate generated export is added to the repository.

| File | SHA-256 |
| --- | --- |
| ai-assessments.json | `4710c3fe160be3ee9a8455dc544d64aac77a91ffec0fafc171c6c7c525d43573` |
| readiness.json | `9fc045cdaca5ca1aab85b6130c9f11bbcee149393193efdc6e2d802dc06f9b59` |
| test.jsonl | `58c37bf18c24d17203f295e176cd55d551c17c0b8a87efd555b36e272b31ef6a` |
| train.jsonl | `dd7be64b1182a42cb392456006e4222fc96b214f2e1f01551cc9a309c955a375` |
| validation.jsonl | `460583655bbaf2d6d82d4ca981c9c51643cc0f5c43b3a548afa0996c50f0e3d3` |

## Offline mechanics smokes

Expanded STATIC_ONLY conformance smoke: VALID, TP 18, FP 0, FN 4, TN 22. The four ARCH003 positives
require graph conformance and are not emitted by the static-only mode. Graph structural retrieval:
VALID, TP 24, FP 0, FN 0, TN 26, six out-of-scope proposals. These check foundation mechanics only;
no threshold, prompt or weight changed after inspecting them. They are not final benchmark results.

[Dataset](../research/BENCHMARK_DATASET.md), [truth](../research/GROUND_TRUTH.md),
[cohort](../research/CALIBRATION_DATASET.md), [splits](../research/EXPERIMENT_SPLITS.md) and
[protocol](../experiments/EXPERIMENT_PROTOCOL.md) provide the frozen contracts and full tables.
