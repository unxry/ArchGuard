# Scoped evaluation metrics — v1

Separate tasks: CONFIRMED_VIOLATION_DETECTION (ARCH001–005), STRUCTURAL_SIGNAL_RETRIEVAL
(ARCH101–105), SEMANTIC_CANDIDATE_DETECTION (ARCH201–205). CALIBRATED_HYBRID_DETECTION is a
reserved contract and cannot execute. Review-required Hybrid decisions are never confirmed positives.

Match rule + exact resolved subjects + direction. Identical logical state predictions are deduplicated
with a diagnostic; contradictory states abstain instead of selecting a convenient answer. Candidate
means positive only in candidate/signal tasks. Rule-family mismatch is rejected.

| Truth | Positive/candidate | Negative | Abstain | Missing |
| --- | --- | --- | --- | --- |
| POSITIVE | TP | FN | ABSTAIN | Static/Graph FN; AI/Hybrid NO_PREDICTION |
| NEGATIVE | FP | TN | ABSTAIN | Static/Graph TN; AI/Hybrid NO_PREDICTION |
| UNKNOWN | OUT_OF_SCOPE | OUT_OF_SCOPE | OUT_OF_SCOPE | UNKNOWN_TRUTH |

Static/Graph positive-only evaluation is explicitly closed-world after successful complete execution.
An unselected/failed AI call is not NOT_SUPPORTED. Saved requested NOT_SUPPORTED is a negative
assessment. INSUFFICIENT_CONTEXT is abstention, never TN. Outside annotation scope predictions do
not enter precision. Unresolved truth is a dataset problem, excluded and reported as PARTIAL.

| Metric | Formula |
| --- | --- |
| Precision | TP/(TP+FP) |
| Recall | TP/(TP+FN) |
| F1 | 2TP/(2TP+FP+FN), only when precision and recall are defined |
| FPR | FP/(FP+TN), only for the explicit negative universe |
| FNR | FN/(FN+TP) |
| Abstention rate | ABSTAIN/eligible known resolved cases |
| Prediction coverage | classified known cases/eligible known resolved cases |

Zero denominator → JSON null, including F1 when P or R is undefined. If additional positives in a
fully annotated region count as extra FP outside explicit negative controls, FPR is null: the negative
universe is not completely enumerated. No invented all-node-pair TNs. Extra FP do not increase
prediction coverage. UNKNOWN and unresolved cases are excluded from eligible denominator.

Recall/FNR exclude abstentions and missing AI predictions: they are **conditional classification
metrics** and must be reported alongside coverage/abstention and raw counts. They cannot support
an apparent quality improvement by abstaining on difficult cases. Full common-universe scientific
comparison needs a preregistered coverage-aware protocol; this foundation makes no superiority claim.

Micro aggregates counts. Per-rule, per-language and per-repository groups retain counts; mixed-language
repositories use MIXED once. Macro rule/project means average each defined metric, excluding null
values without converting them to zero. Unannotated groups may expose only exclusion counts/nulls,
not fabricated performance. No weighted macro, p-values, confidence intervals or significance tests.

Handcrafted independent predictions produce TP=8, FP=2, FN=2, TN=8: P=R=F1=0.8, FPR=FNR=0.2.
The real seed Static smoke yields TP=8, FP=0, FN=2, TN=10 (ARCH003 belongs to Graph); the Graph
conformance smoke finds the two cycles. Structural signal retrieval yields TP=10, FP=0, FN=0,
TN=12 with unannotated candidates excluded. These are **foundation smokes on deliberately controlled
sources**, not thesis findings. Scripted AI is used only to verify saved-artifact decision mapping;
no scripted/live LLM quality metric is reported.
