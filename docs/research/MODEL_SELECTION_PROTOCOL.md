# Frozen structural selection protocol v2

The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

Manifest experiments/calibration/structural-v2.json was written before v2 validation selection.
Experiment fingerprint `50958483c4a17122af76fe605d79a4298e6edad2fb19abbb1b2999433b2899eb`. Independent v2 identity/version, explicit
feature exclusions, consumed TEST lineage, fresh-holdout requirement and administrative tie preference
are recorded. No parameters were adjusted after observing v2 validation.

Dataset 1.1.0 fingerprint `c40fe95b2880ab50ba1464155e16ef19c47cf9aa6c207725dba362294a967c31`;
split manifest `1a1b2a2970a7c330a872fc58f00a67dcb0b09655ba5e94b726886ccea88ed4e0`;
TRAIN `496448e58c1fa0e4da9d5f067cecaeaca13322170d117308460c09efe79f314f`;
VALIDATION `0655b06ade4be0e3b33a3c74a366d83c1ab4ae058af4c5de37cf96d0ea713948`.

1. Verify canonical split/profile/task/eligibility/schema and reject duplicates. Keep complete STRUCTURAL
   cases, including no-candidate positives/negatives. Never load TEST under v2.
2. Extract the versioned numeric whitelist without labels, identities or detector decisions. Fit TRAIN
   medians/population scales/drop decisions/missing flags once. Use the same N/(F*n_family) weights.
3. Fit ridge alpha 0.1, 1, 10 and logistic C 0.1, 1, 10 on TRAIN. The grid is carried forward for machinery
   comparison, not selected to recover old TEST/perfect scores. No oversampling/class balancing.
4. For each candidate, enumerate distinct validation-score midpoints plus outer boundaries
   max(1,abs(min),abs(max))*1e-6; round to 12 decimals. Rank macro-family F1, precision, recall,
   stronger L2, weighted-before-logistic, lower threshold. Retain every candidate and threshold count.
   Weighted-before-logistic is DETERMINISTIC_ADMINISTRATIVE_PREFERENCE, never scientific superiority.
5. Compute Direct Graph Rule Baseline from actual candidate metadata on the identical TRAIN/VALIDATION
   cohorts at fixed presence threshold 0.5. This metadata never enters v2 fitting or inference.
6. Freeze candidate `2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185` as AWAITING_FRESH_HOLDOUT, not production/final/thesis validated.
   No TEST metrics are recorded. Native/portable replay tolerance 1e-9, precision 12; no randomness.

The typed primary_cohort, bounded load_primary file adapter, evaluate_frozen and CLI guard old TEST
reuse. The current v2 protocol blocks all TEST evaluation, including arbitrary renamed files/fake new
lineage. A future version must preregister independently obtained new families, fresh annotation and
lineage before allowing evaluation. Families used by v1/review/v2 design/validation are ineligible.
Do not construct a new synthetic TEST using coefficients or move old families between splits.

V1 manifest/artifact/results remain immutable historical diagnostics. Its score is classified
ENGINEERING_SEED_DIAGNOSTIC_RESULT via separate research-status.json; no post-hoc corrected holdout
claim is made. The v1 evaluator is retained for historical compatibility/unit tests, not research reuse.

A/B and macOS/Linux use TRAIN+VALIDATION-only mounts. Full Hybrid remains NOT_READY. A single validation
family, correlated translations, multicollinear measurements and threshold-derived labels establish
neither external validity, probability calibration nor ML/Hybrid added value over known formulas.
After review, preferred next stage is PROMPT 012 — REAL-WORLD OSS BENCHMARK & INDEPENDENT ANNOTATION
FOUNDATION. It does not start here.
