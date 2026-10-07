# Negative/OOS semantic metrics — PROMPT 014

Only independently frozen AI assessments are joined to P013 human truth. Human
NEGATIVE and OUT_OF_SCOPE are evaluated separately. SUPPORTED, NOT_SUPPORTED,
INSUFFICIENT_CONTEXT and NOT_APPLICABLE remain distinct response classes.

For the 32 NEGATIVE cases per strategy:

| AI judgment | Interpretation |
|---|---|
| NOT_SUPPORTED | TN |
| SUPPORTED | FP |
| INSUFFICIENT_CONTEXT | Abstention |
| NOT_APPLICABLE | Applicability/scope error; never TN |
| Missing/failed/invalid | Execution or acceptance failure; never TN |

Specificity is `TN / (TN + FP)` and FPR is `FP / (TN + FP)`, conditional on
definitive decisions. Definitive coverage is `(TN + FP) / N_negative`.
Effective negative correctness is `TN / N_negative`. Abstention and negative scope
error rates are their respective counts divided by `N_negative`. Missing outcomes
remain in the full negative denominator and are separately reported.

For eight OUT_OF_SCOPE cases, scope recognition is
`NOT_APPLICABLE / N_out_of_scope`. Other judgments are retained in the OOS response
distribution. OOS cases never enter TN/FP or negative denominators. All ARCH202
cases are OOS, so ARCH202 supports scope recognition only.

A zero denominator yields null. With zero human positives, Recall, F1 and FNR are
always null. No positive sensitivity, overall semantic effectiveness, pooled
ARCH201–205 F1 or Hybrid quality is inferred.

Full cohort, complete successful triples, explicit pair completeness, fixed IAM
strata, rule, language and repository breakdowns are retained. Pair transitions
use raw judgments; missing pairs are listed explicitly. Token/cost totals include
technical attempts, while attempt latency and successful logical latency are
reported separately. The latter sums attempt durations for each successful
logical assessment, excluding retry backoff. Pricing is a versioned assumption,
separate from scientific fingerprints and provider invoice accounting.
