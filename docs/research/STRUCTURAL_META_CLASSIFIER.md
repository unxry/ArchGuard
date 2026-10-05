# Graph structural meta-classifier v2 — descriptive machinery results

The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

V2 uses raw Graph measurements and analysis quality; Static bypass is not a Static predictor.
Ridge minimizes sum(w*(y-z)^2)+alpha*||beta||²; logistic minimizes weighted binary log loss plus
(1/C)*||beta||²/2. Both use unpenalized intercept, identical family weights and TRAIN-only preprocessing.
Deterministic pivoted ridge and Newton logistic with stable sigmoid/softplus and backtracking retain
max iterations 200/tolerance 1e-10. No research estimator dependency, random fitting or calibrated confidence.

## All validation candidates

Only four cases in one diamond family select thresholds/models. TEST NOT ACCESSED for v2.

| Model | L2 | Threshold | Macro F1 | Macro P | Macro R | Thresholds tried |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WEIGHTED_LINEAR | 0.1 | -0.371057107775 | 0.666666666667 | 0.5 | 1.0 | 3 |
| WEIGHTED_LINEAR | 1.0 | -0.063473659364 | 0.666666666667 | 0.5 | 1.0 | 3 |
| WEIGHTED_LINEAR | 10.0 | 0.398762395289 | 1.0 | 1.0 | 1.0 | 3 |
| LOGISTIC_REGRESSION | 10.0 | 0.501913645754 | 1.0 | 1.0 | 1.0 | 3 |
| LOGISTIC_REGRESSION | 1.0 | 0.247025629416 | 1.0 | 1.0 | 1.0 | 3 |
| LOGISTIC_REGRESSION | 0.1 | 0.019978103599 | 0.666666666667 | 0.5 | 1.0 | 3 |

Selected ridge alpha=10, threshold=0.398762395289. Selected logistic C=0.1,
threshold=0.501913645754. The weighted-before-logistic tie is administrative,
not evidence of superiority. No grid/feature change followed these results.

## Same-cohort descriptive comparison

| Method | Split | TP | FP | FN | TN | Micro F1 | Macro F1 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| WEIGHTED_LINEAR | TRAIN | 20 | 4 | 0 | 18 | 0.9090909090909091 | 0.9583333333333334 |
| WEIGHTED_LINEAR | VALIDATION | 2 | 0 | 0 | 2 | 1.0 | 1.0 |
| LOGISTIC_REGRESSION | TRAIN | 20 | 4 | 0 | 18 | 0.9090909090909091 | 0.9583333333333334 |
| LOGISTIC_REGRESSION | VALIDATION | 2 | 0 | 0 | 2 | 1.0 | 1.0 |
| Direct Graph Rule Baseline | TRAIN | 20 | 0 | 0 | 22 | 1.0 | 1.0 |
| Direct Graph Rule Baseline | VALIDATION | 2 | 0 | 0 | 2 | 1.0 | 1.0 |

Direct baseline replays GraphCandidateEngine presence from separately retained metadata, never a
v2 predictor. Coverage=1. The models match a rule baseline on this tiny validation; this does not
establish ML/Hybrid added value. Threshold-derived labels can turn even leakage-free raw input fitting
into approximation of a known formula. Pair/component missingness and algebraically related Ca/Ce/I
remain scope proxies/correlations; coefficient magnitude/sign is neither causal importance nor proof
of generalization. No independent rule-level holdout, stability analysis, significance or OSS validation.

## Portable selected-family coefficients

Weighted intercept 0.5252725147; logistic intercept
0.096019337155. Values multiply TRAIN-standardized measurements;
missing indicators remain 0/1. Exact medians/scales/drop decisions and coefficients are in JSON.

| Feature | Weighted coefficient | Logistic coefficient |
| --- | ---: | ---: |
| graph.Ca | 0.138527419084 | 0.339559930225 |
| graph.Ca.missing | 0.012232903951 | 0.043093311856 |
| graph.Ce | 0.105993070194 | 0.330848719054 |
| graph.Ce.missing | 0.012232903951 | 0.043093311856 |
| graph.coupling | 0.206783877132 | 0.578819610502 |
| graph.coupling.missing | 0.012232903951 | 0.043093311856 |
| graph.I | -0.033259689409 | -0.056109746788 |
| graph.I.missing | 0.025345985617 | -0.005180028849 |
| graph.scc_size.missing | 0.012232903951 | 0.043093311856 |
| graph.betweenness | -0.024065106325 | 0.056640688651 |
| graph.betweenness.missing | 0.012232903951 | 0.043093311856 |
| graph.pagerank | -0.004952180821 | 0.226811801915 |
| graph.pagerank.missing | 0.012232903951 | 0.043093311856 |
| graph.cyclic.missing | 0.012232903951 | 0.043093311856 |
| graph.source.Ca | 0.018435125623 | 0.066626787319 |
| graph.source.Ca.missing | -0.012232903951 | -0.043093311856 |
| graph.source.Ce | -0.017431170947 | -0.085991320895 |
| graph.source.Ce.missing | -0.012232903951 | -0.043093311856 |
| graph.source.I | -0.012721575679 | -0.065373083193 |
| graph.source.I.missing | -0.012232903951 | -0.043093311856 |
| graph.target.Ca | -0.132581345835 | -0.410414401299 |
| graph.target.Ca.missing | -0.012232903951 | -0.043093311856 |
| graph.target.Ce | 0.071107176307 | 0.247541908447 |
| graph.target.Ce.missing | -0.012232903951 | -0.043093311856 |
| graph.target.I | 0.071107176307 | 0.247541908446 |
| graph.target.I.missing | -0.012232903951 | -0.043093311856 |

Artifact `2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185` is AWAITING_FRESH_HOLDOUT. No v2 heldout.json or TEST metric exists.
V1 artifact `fdbb6eaeeb2e7099265c391c05b4996fb264d1f0398d1112be8b5012392d8395` and
historical heldout F1=1 remain ENGINEERING_SEED_DIAGNOSTIC_RESULT only, superseded for research.
Fresh evaluation requires independently annotated new families unused by v1/review/design/validation.
