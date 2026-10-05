# PROMPT 011 verification — 2026-10-05

> Post-hoc review: DIAGNOSTIC_LEAKAGE_SENSITIVE_SUPERSEDED_FOR_RESEARCH.
> ENGINEERING_SEED_DIAGNOSTIC_RESULT only. See [PROMPT 011.1](PROMPT_011_1.md).
> The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

1. **Status:** Structural Hybrid Calibration & Interpretable Meta-Classifier Foundation complete.
   Separate uncommitted review diff; PROMPT 012 not started.
2. **Git:** fresh audit of 010.1 passed 1056 tests, coverage 94%, Ruff/format/mypy/diff-check.
   Local commit `8e24249313f6eb6b4fb0e623a1f09b44ac18ddde`, message `feat: expand benchmark calibration cohort`, safely pushed to
   origin/main. No force push, reset, credential/config changes or prior-diff loss.
3. **Files:** 24 files changed: portable architecture/hybrid/calibration.py and model decision extensions;
   calibration/models.py, numeric.py, workflow.py; bounded infrastructure/calibration.py;
   calibration_cli.py plus CLI/runtime integration; preregistered experiment and four compact
   result JSON files; structural tests/dependency-boundary extension; research docs/README.
4. **Research versions:** no dependencies added; pyproject/uv.lock unchanged. Native solver protocol
   native-python-v1; weighted-ridge-pivot-v1 and weighted-logistic-newton-v1. macOS Python 3.13.14,
   Docker Linux Python 3.13.16. Portable inference needs only existing Pydantic and standard math.
5. **Dataset:** 1.1.0, schema 1.0, fingerprint `c40fe95b2880ab50ba1464155e16ef19c47cf9aa6c207725dba362294a967c31`.
   Split manifest `1a1b2a2970a7c330a872fc58f00a67dcb0b09655ba5e94b726886ccea88ed4e0`.
   TRAIN `496448e58c1fa0e4da9d5f067cecaeaca13322170d117308460c09efe79f314f`; VALIDATION `0655b06ade4be0e3b33a3c74a366d83c1ab4ae058af4c5de37cf96d0ea713948`;
   TEST `c587beca7564ae7cc928764134ff8a83fdcbe09ac300d5a8c071dcafa6da8779` (computed only after freeze).
6. **Task:** STRUCTURAL_SIGNAL_RETRIEVAL for ARCH101–105 only. Deterministic and semantic truth
   excluded. Graph predictors and Static precedence are separated; no invented Static alignment.
7. **Eligible primary cohort:** TRAIN 4 families / 42 cases / 20 P / 22 N;
   VALIDATION 1 / 4 / 2 / 2; TEST 1 / 4 / 2 / 2. No four-variant duplication or synthetic rows fitted.
8. **Whitelist:** 16 predefined structural metrics/pair measurements/candidate-present/quality fields;
   no identity, paths, names, specific rule IDs, labels, rationale, task or AI/context predictors.
   [Feature rationale](../research/HYBRID_CALIBRATION.md#structural-feature-spec-v1).
9. **Drops:** quality.unresolved entirely constant on TRAIN; constant scc_size/cyclic values removed
   while varying missing indicators retained. Output has 28 ordered columns. No VALIDATION drop fitting.
10. **Missingness:** TRAIN median plus explicit 0/1 indicators. All-missing fields drop; no fake zero.
    Frozen missing strategy also applies to runtime skipped metrics.
11. **Scaling:** TRAIN-only population mean/std after imputation; frozen values/order/fingerprint.
    Statistics are unweighted; objective uses equal-family weighting. Inputs follow canonical cohort
    precision; no coefficient rounding occurs inside either fitting algorithm.
12. **Weights:** N/(F*n_family), total 10.5 per TRAIN family and 42 overall. Same weights in both
    models; no class_weight balancing, oversampling, SMOTE or black-box model.
13. **Weighted:** alpha 0.1/1/10; all candidates VALIDATION micro/macro F1=1. Selected alpha=10;
    threshold=0.448695558199. Intercept and learned coefficients are in
    [coefficient table](../research/STRUCTURAL_META_CLASSIFIER.md#learned-coefficients-of-the-selected-candidate-in-each-model-family).
14. **Logistic:** C 0.1/1/10; all candidates VALIDATION micro/macro F1=1. Selected C=0.1;
    threshold=0.502382406274. Weighted Newton log loss, unpenalized intercept, max 200 iterations,
    tolerance 1e-10; convergence errors invalidate fitting. No probability recalibration.
15. **Winner:** Weighted Linear via preregistered macro-F1 → macro-precision → macro-recall →
    stronger L2 → weighted-before-logistic → lower threshold. Both best models tied at L2=10,
    so the model-family preference resolved the tie. No superiority claim.
16. **Frozen artifact:** `fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395`;
    Weighted Linear, alpha=10, threshold=0.448695558199. Preprocessor/coefficients/threshold,
    TRAIN/VALIDATION/experiment provenance and validation metrics are immutable and hashed.
17. **Held-out:** ENGINEERING_SEED_HELDOUT_EVALUATION: TP=2, FP=0, FN=0, TN=2;
    P/R/F1=1, FPR/FNR=0, coverage=1; macro-family metrics equal micro on the single TEST family.
    The separate result references the exact policy fingerprint and contains no policy update.
18. **TEST isolation:** real TEST export was opened only by evaluate after successful freeze,
    pre-heldout proof and macOS/Linux fitting reproduction. Training/selection APIs cannot accept
    TEST or TEST metrics. Linux had only TRAIN/VALIDATION file mounts. Policy file SHA-256
    `5be4a82caa63f552d59ee3439dd45f281e56cfb3ac2c6ebfe452cc19e07ad1ee` existed before evaluation and remained unchanged afterward.
    One real seed evaluation ran; a local fingerprint receipt blocks accidental repeats in that
    directory. Unit TEST checks use synthetic rows, not actual held-out sources/labels.
19. **Chosen-model comparison:** TRAIN TP/FP/FN/TN=20/0/0/22, VALIDATION=2/0/0/2,
    TEST=2/0/0/2; micro/macro-family F1=1 in all. TRAIN reporting did not select the model.
20. **Interpretation:** correlated coupling/pair/missingness features and candidate_present can
    reproduce the curated topology oracle/preselection. Coefficients are conditional predictive
    associations, not causal importance. Perfect tiny seed scores show no established added value.
21. **Runtime:** graph review cases produce STRUCTURAL_SIGNAL_SUPPORTED/NOT_SUPPORTED,
    separate model_score/artifact fingerprint, null confidence/severity and no new Finding.
    Actual CLI smoke on TRAIN fan-in produced supported ARCH101/102; no confirmed Finding IDs.
22. **Static bypass:** real ARCH002 proof preserved original Finding/severity with score() replaced
    by a failing sentinel. Classifier was not invoked. Graph-conformance ARCH003 uses same precedence.
23. **Semantic guard:** ARCH202 is typed incompatible; AI evidence/AI channels fail.
    Existing scripted-eligibility hard guards remain green and scripted evidence cannot fit.
24. **Tests:** 1067 passed, 0 failed, 0 skipped, including all previous 1056 and 11 new calibration
    cases. Covers native solver checks, same family weights, label/test/preprocessing isolation,
    whitelist, frozen provenance/immutability, duplicate/profile guard, threshold rank, portable
    replay, runtime/static/semantic behavior and CLI repeat/full-Hybrid protection.
25. **Coverage:** 94% overall with branch measurement; portable contracts/policy 93%, research
    models 96%, native solvers 90%, workflow 89%, CLI 98%, file adapter 95%.
26. **Gates:** locked dev sync, make check, Ruff, final format check (320 files), strict mypy (184 source
    files) and diff-check pass. No research extra required; dependency/lock files unchanged.
27. **Reproducibility:** two independent macOS training/selection/freezes and nonroot network-disabled
    read-only Docker reproduce training.json, selection.json and policy.json byte-for-byte. Thus
    model family, coefficients, parameters, threshold and portable predictions match. Docker did not
    repeat the real TEST evaluation. Native Python patch versions differ as recorded above.
28. **Limitations:** only four TRAIN and one family in each structural holdout; correlated translations;
    no ARCH101–104 rule-level holdout; synthetic/curated oracle and preselection bias; no reviewed
    semantic/OSS validation, final seven-way ablation, probability/confidence calibration, significance
    tests, bootstrap intervals, stability study, production jobs/API, security or frontend.
29. **Full Hybrid:** NOT_READY, unchanged 010.1 readiness. No real AI assessments/review introduced.
30. **Next:** review 011, then choose explicitly between Real AI Assessment Cohort & Semantic Review
    or Expanded Real-World OSS Benchmark Foundation. Neither starts automatically.

[Calibration contracts](../research/HYBRID_CALIBRATION.md),
[all candidates and coefficients](../research/STRUCTURAL_META_CLASSIFIER.md),
[selection protocol](../research/MODEL_SELECTION_PROTOCOL.md) and
[portable results](../../experiments/results/structural-v1/policy.json).
