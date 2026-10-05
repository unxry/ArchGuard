# PROMPT 011.1 — Calibration Leakage Audit & Protocol Correction

The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

1. **Status:** CALIBRATION_MACHINERY_READY; STRUCTURAL_V2_AWAITING_FRESH_HOLDOUT. Engineering correction,
   not thesis validation. No PROMPT 012, live AI, Security or frontend started.
2. **Git:** base HEAD `8e24249313f6eb6b4fb0e623a1f09b44ac18ddde`, main/origin/main, PROMPT 010.1.
   PROMPT 011 remained uncommitted during review. This correction and machinery belong in one commit,
   `feat: add structural calibration machinery and leakage-safe protocol`; final commit/push receipt
   is reported separately because a commit cannot contain its own hash.
3. **Leakage:** v1 `selection.candidate_present` is an existing detector decision and can reproduce
   the threshold-derived target. It is prohibited as v2 input; retained only as baseline metadata.
4. **Old F1=1:** ENGINEERING_SEED_DIAGNOSTIC_RESULT. Post-hoc feature review consumes the old TEST
   for subsequent methodology; it cannot establish corrected holdout validity or ML added value.
5. **V1 classification:** DIAGNOSTIC_LEAKAGE_SENSITIVE_SUPERSEDED_FOR_RESEARCH. The complete
   RAW_MEASUREMENT / DERIVED_MEASUREMENT / DETECTOR_DECISION / TARGET_DERIVED / IDENTITY / QUALITY /
   MISSINGNESS [audit](../research/FEATURE_LEAKAGE_AUDIT.md) covers predictors, missing outputs and
   excluded cohort fields. Historical hashed v1 artifacts are unmodified.
6. **V2 spec:** `structural-feature-spec-v2`, explicit ordered 15 inputs / 26 frozen outputs.
   Independent structural-v2 manifest fingerprint:
   `50958483c4a17122af76fe605d79a4298e6edad2fb19abbb1b2999433b2899eb`.
7. **Removed:** `selection.candidate_present` and `selection.candidate_present.missing`.
   GraphCandidate flags, graph candidate rules/ARCH booleans, configured thresholds, rule IDs,
   Finding labels, labels/annotation/rationale, split, identities, names/paths remain excluded.
8. **Retained:** graph.Ca, graph.Ce, graph.coupling, graph.I, graph.scc_size, graph.betweenness,
   graph.pagerank, graph.cyclic, graph.source.Ca, graph.source.Ce, graph.source.I,
   graph.target.Ca, graph.target.Ce, graph.target.I, quality.unresolved. Missing flags mean raw
   measurement unavailability. quality.unresolved is analysis quality and dropped as TRAIN-constant.
9. **Detector decisions in v2:** NO. Version-aware whitelist, preprocessing and runtime extraction
   do not consume candidate presence, graph rule flags, thresholds or labels.
10. **Labels/rule IDs/identity in v2:** NO. IDs resolve subjects and seal lineage only. They never
    enter normalized model values. Label/identity changes do not change extracted features.
11. **Term:** GRAPH STRUCTURAL META-CLASSIFIER. Static precedence is runtime bypass. Raw IAM edge
    counts, relation diversity, inheritance, members and provenance were audited; member ownership
    and extraction scope need separately frozen rules. No speculative Static predictor was added.
12. **TRAIN:** 42 cases / 4 families / 20 positive / 22 negative. One complete STRUCTURAL variant
    per eligible graph case. Native ridge/logistic use identical weights N/(F*n_family), total 42,
    each family total 10.5; no-candidate cases are retained. TRAIN alone fits preprocessing/coefficients.
13. **VALIDATION:** 4 cases / 1 diamond family / 2 positive / 2 negative. Only this split selects
    thresholds/hyperparameters/model. All six preregistered candidates are reported, including weaker
    candidates with F1=2/3; no subsequent feature/grid changes recovered perfect results.
14. **TEST:** NOT ACCESSED for v2 preprocessing/fitting/selection/freezing/research evaluation.
    Only train.jsonl and validation.jsonl were copied into the experiment directory and mounted.
    No v2 TEST scores/metrics or heldout.json. Dataset-1.1.0 TEST consumed by v1 is blocked before file
    opening and before typed primary materialization/evaluation. Legacy dataset/export regression
    tests still validate their historical fixtures; they do not feed v2 research selection/evaluation.
15. **Weighted v2 VALIDATION:** alpha=10, threshold=0.398762395289; TP=2 FP=0 FN=0 TN=2;
    micro/macro P=R=F1=1, FPR=FNR=0, coverage=1. At that threshold TRAIN TP=20 FP=4 FN=0 TN=18,
    micro F1=0.9090909091 / macro F1=0.9583333333.
16. **Logistic v2 VALIDATION:** C=0.1, threshold=0.501913645754; same confusion and metrics.
    TRAIN at its selected threshold also TP=20 FP=4 FN=0 TN=18.
17. **Selected:** Weighted Linear alpha=10. Macro F1/P/R and L2 tie with logistic; weighted-first
    is DETERMINISTIC_ADMINISTRATIVE_PREFERENCE, not scientific model superiority.
18. **Direct Graph baseline:** identical TRAIN/VALIDATION fingerprints/counts, candidate metadata
    replay only. TRAIN TP=20 FP=0 FN=0 TN=22; VALIDATION TP=2 FP=0 FN=0 TN=2; both micro/macro F1=1.
    V2 matches the baseline on validation and is weaker on training. Known threshold approximation
    and this one small validation family do not establish ML/Hybrid added value.
19. **V2 artifact:** `2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185`,
    frozen-structural-policy-v2, version 2.0.0, status AWAITING_FRESH_HOLDOUT.
20. **Fresh holdout required:** new independently annotated families unused by v1, post-hoc review,
    v2 design or validation. No resplit/renaming of consumed data or coefficient-informed synthetic
    TEST. Current v2 evaluation is hard-blocked until a new lineage/protocol is independently defined.
21. **V1 artifact:** `fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395`,
    original SHA-256 `5be4a82caa63f552d59ee3439dd45f281e56cfb3ac2c6ebfe452cc19e07ad1ee`
    unchanged. Separate research-status.json marks diagnostic/leakage-sensitive/superseded. Runtime
    requires explicit artifacts; no experimental model is activated by default.
22. **Regression tests:** candidate presence flips; add/remove GraphAnalysisResult candidates with
    identical raw metrics for positive and negative anchors; label and repository/family/case/rule
    changes; no-candidate feature availability; stages with TEST physically absent; typed/file/CLI
    reuse guards before opening, with no result/receipt created; same-cohort baseline; immutable v1;
    v2 whitelist and research status tamper rejection. Calibration module: 18 passed.
23. **Static bypass:** v1/v2 preserve deterministic Finding/severity; score sentinel is never called.
    The calibration regression uses a TRAIN Static fixture, not the consumed graph holdout.
24. **Semantic guard:** ARCH202 without deterministic proof rejected under both v1/v2; AI evidence
    and static,graph,ai calibration remain FULL_HYBRID_NOT_READY. No semantic model fitting.
25. **Tests:** 1074 passed / 0 failed / 0 skipped in 94.16s. All prior 1067 tests remain green;
    seven additional parameterized regression cases. Calibration-only module: 18 passed.
26. **Coverage:** 94% overall with branch coverage enabled (9943 statements / 3036 branches).
27. **Quality gates:** make check green: Ruff, format (321 files), strict mypy (184 source files),
    full pytest/coverage. git diff --check green. No dependency changes.
28. **Reproducibility:** A/B and macOS Python 3.13.14 / Linux Python 3.13.16 are byte-identical for
    training/preprocessing, validation selection, candidate freeze and baseline. Nonroot Docker,
    network none, read-only filesystem, only TRAIN+VALIDATION+manifest mounts; no TEST mount.
29. **Full Hybrid:** FULL_HYBRID_NOT_READY unchanged; requires real AI assessments and independent
    semantic annotation. Structural machinery does not establish full Hybrid readiness.
30. **Next:** after review only, PROMPT 012 — REAL-WORLD OSS BENCHMARK & INDEPENDENT ANNOTATION
    FOUNDATION: frozen OSS versions, licensing/provenance, independent annotation and fresh holdout.
    Not started.

Commands and evidence: `make check`; calibration-only pytest;
`experiments/calibration/structural-v2.json`; `experiments/calibration/feature-leakage-audit.json`;
`experiments/results/structural-v2/{training,selection,policy,baseline}.json`.
Transient logs and exported rows remain outside Git under /tmp. Native solvers and portable inference
remain separate, source-free, schema/fingerprint validated; no estimator/pickle dependency added.
