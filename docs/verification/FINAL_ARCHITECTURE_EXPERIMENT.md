# Final architecture experiment — frozen FINAL TEST

**P025_FINAL_ARCHITECTURE_EVALUATION_COMPLETE**. Hypothesis: **SUPPORTED**.

All results below derive from predictions frozen before the first final-truth open. No provider calls, fitting, refitting, preprocessing fitting, threshold tuning, unselected model application, or Security analysis occurred in P025.

## Final cohort and acquisition

| Measurement | Value |
| --- | --- |
| Logical cases | 300 |
| Independent structural truth | 200 |
| Human semantic truth | 100 |
| Positive / negative | 150 / 150 |
| Families | NORMATIVE 100; GRAPH 100; SEMANTIC 100 |
| Languages | JAVA 150; TYPESCRIPT 150 |
| Rule strata | 15 × 20 |
| Accepted semantic LLM | 298 |
| Technical missing | 2 |
| Unexecuted | 0 |
| Missing-positive / missing-negative | 0 / 2 |


## PRIMARY FINAL RESULTS — N=300

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 300 | 40 | 0 | 40 | 110 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 1.000000000000 | 0.000000000000 | 0.733333333333 | 0.266666666667 | 0.266666666667 |
| A2 | 300 | 60 | 10 | 50 | 90 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.833333333333 | 0.166666666667 | 0.600000000000 | 0.366666666667 | 0.400000000000 |
| A3 | 300 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.770000000000 | 0.796666666667 |
| A4 | 300 | 100 | 10 | 90 | 50 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.900000000000 | 0.100000000000 | 0.333333333333 | 0.633333333333 | 0.666666666667 |
| A5 | 300 | 107 | 4 | 128 | 43 | 0.963963963964 | 0.713333333333 | 0.819923371648 | 0.969696969697 | 0.030303030303 | 0.286666666667 | 0.783333333333 | 0.800000000000 |
| A6 | 300 | 149 | 7 | 141 | 1 | 0.955128205128 | 0.993333333333 | 0.973856209150 | 0.952702702703 | 0.047297297297 | 0.006666666667 | 0.966666666667 | 0.993333333333 |
| A7 | 300 | 149 | 0 | 149 | 1 | 1.000000000000 | 0.993333333333 | 0.996655518395 | 1.000000000000 | 0.000000000000 | 0.006666666667 | 0.993333333333 | 0.996666666667 |


Precision=TP/(TP+FP); Recall=TP/(TP+FN); F1=2TP/(2TP+FP+FN); Specificity=TN/(TN+FP); FPR=FP/(TN+FP); FNR=FN/(TP+FN); effective correctness=(TP+TN)/N. Undefined denominators are null. No intermediate rounding; displayed proportions use 12 decimal places, while JSON includes exact numerator/denominator pairs.

Positive abstention, non-applicability and technical missingness count as FN. Negative nondefinitive states count separately and never as TN.

## Coverage, abstention and applicability

| Method | N | Definite + | Definite − | Coverage | Abstention | Nondefinitive | Non-applicable | Technical missing | Negative nondefinitive | Applicability | Unknown applicability |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 300 | 40 | 40 | 0.266666666667 | 0 | 220 | 220 | 0 | 110 | 0.266666666667 | 0 |
| A2 | 300 | 70 | 50 | 0.400000000000 | 0 | 180 | 180 | 0 | 90 | 0.400000000000 | 0 |
| A3 | 300 | 114 | 125 | 0.796666666667 | 57 | 61 | 2 | 2 | 19 | null | 2 |
| A4 | 300 | 110 | 90 | 0.666666666667 | 0 | 100 | 100 | 0 | 50 | 0.666666666667 | 0 |
| A5 | 300 | 111 | 129 | 0.800000000000 | 58 | 60 | 2 | 0 | 18 | 0.993333333333 | 0 |
| A6 | 300 | 156 | 142 | 0.993333333333 | 2 | 2 | 0 | 0 | 2 | 1.000000000000 | 0 |
| A7 | 300 | 149 | 150 | 0.996666666667 | 1 | 1 | 0 | 0 | 1 | 1.000000000000 | 0 |


A3 retains SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_CONTEXT and NOT_APPLICABLE. Its two acquisition failures have separate technical statuses and no semantic decision. A3 applicability is unknown for those two rows; a complete applicability rate is not fabricated.

## SUPPLEMENTAL RESULTS — native scope and available-only

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1_STATIC_NATIVE | 80 | 40 | 0 | 40 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 0.000000000000 | 0.000000000000 | 1.000000000000 | 1.000000000000 |
| A2_GRAPH_NATIVE | 120 | 60 | 10 | 50 | 0 | 0.857142857143 | 1.000000000000 | 0.923076923077 | 0.833333333333 | 0.166666666667 | 0.000000000000 | 0.916666666667 | 1.000000000000 |
| A3_AVAILABLE_ONLY | 298 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.775167785235 | 0.802013422819 |


Static native scope: ARCH001/002/004/005 (N=80). Graph native scope: ARCH003 plus ARCH101–105 (N=120). A3 available-only N=298 excludes only the two unavailable transport rows and is supplemental. It does not replace N=300.

## Family results — descriptive


### GRAPH

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 100 | 0 | 0 | 0 | 50 | null | 0.000000000000 | 0.000000000000 | 0.000000000000 | 0.000000000000 |
| A2 | 100 | 50 | 10 | 40 | 0 | 0.833333333333 | 1.000000000000 | 0.909090909091 | 0.900000000000 | 1.000000000000 |
| A3 | 100 | 7 | 0 | 34 | 43 | 1.000000000000 | 0.140000000000 | 0.245614035088 | 0.410000000000 | 0.420000000000 |
| A4 | 100 | 50 | 10 | 40 | 0 | 0.833333333333 | 1.000000000000 | 0.909090909091 | 0.900000000000 | 1.000000000000 |
| A5 | 100 | 7 | 0 | 34 | 43 | 1.000000000000 | 0.140000000000 | 0.245614035088 | 0.410000000000 | 0.420000000000 |
| A6 | 100 | 49 | 0 | 50 | 1 | 1.000000000000 | 0.980000000000 | 0.989898989899 | 0.990000000000 | 1.000000000000 |
| A7 | 100 | 49 | 0 | 50 | 1 | 1.000000000000 | 0.980000000000 | 0.989898989899 | 0.990000000000 | 1.000000000000 |

### NORMATIVE

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 100 | 40 | 0 | 40 | 10 | 1.000000000000 | 0.800000000000 | 0.888888888889 | 0.800000000000 | 0.800000000000 |
| A2 | 100 | 10 | 0 | 10 | 40 | 1.000000000000 | 0.200000000000 | 0.333333333333 | 0.200000000000 | 0.200000000000 |
| A3 | 100 | 50 | 3 | 45 | 0 | 0.943396226415 | 1.000000000000 | 0.970873786408 | 0.950000000000 | 0.980000000000 |
| A4 | 100 | 50 | 0 | 50 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 |
| A5 | 100 | 50 | 0 | 49 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 0.990000000000 | 0.990000000000 |
| A6 | 100 | 50 | 3 | 46 | 0 | 0.943396226415 | 1.000000000000 | 0.970873786408 | 0.960000000000 | 0.990000000000 |
| A7 | 100 | 50 | 0 | 50 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 1.000000000000 |

### SEMANTIC

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 100 | 0 | 0 | 0 | 50 | null | 0.000000000000 | 0.000000000000 | 0.000000000000 | 0.000000000000 |
| A2 | 100 | 0 | 0 | 0 | 50 | null | 0.000000000000 | 0.000000000000 | 0.000000000000 | 0.000000000000 |
| A3 | 100 | 50 | 4 | 45 | 0 | 0.925925925926 | 1.000000000000 | 0.961538461538 | 0.950000000000 | 0.990000000000 |
| A4 | 100 | 0 | 0 | 0 | 50 | null | 0.000000000000 | 0.000000000000 | 0.000000000000 | 0.000000000000 |
| A5 | 100 | 50 | 4 | 45 | 0 | 0.925925925926 | 1.000000000000 | 0.961538461538 | 0.950000000000 | 0.990000000000 |
| A6 | 100 | 50 | 4 | 45 | 0 | 0.925925925926 | 1.000000000000 | 0.961538461538 | 0.950000000000 | 0.990000000000 |
| A7 | 100 | 50 | 0 | 49 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 0.990000000000 | 0.990000000000 |


## Java / TypeScript results — descriptive


### JAVA

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 150 | 20 | 0 | 20 | 55 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 0.266666666667 | 0.266666666667 |
| A2 | 150 | 30 | 5 | 25 | 45 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.366666666667 | 0.400000000000 |
| A3 | 150 | 55 | 3 | 63 | 20 | 0.948275862069 | 0.733333333333 | 0.827067669173 | 0.786666666667 | 0.813333333333 |
| A4 | 150 | 50 | 5 | 45 | 25 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.633333333333 | 0.666666666667 |
| A5 | 150 | 55 | 2 | 65 | 20 | 0.964912280702 | 0.733333333333 | 0.833333333333 | 0.800000000000 | 0.820000000000 |
| A6 | 150 | 74 | 3 | 71 | 1 | 0.961038961039 | 0.986666666667 | 0.973684210526 | 0.966666666667 | 0.993333333333 |
| A7 | 150 | 74 | 0 | 75 | 1 | 1.000000000000 | 0.986666666667 | 0.993288590604 | 0.993333333333 | 1.000000000000 |

### TYPESCRIPT

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 150 | 20 | 0 | 20 | 55 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 0.266666666667 | 0.266666666667 |
| A2 | 150 | 30 | 5 | 25 | 45 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.366666666667 | 0.400000000000 |
| A3 | 150 | 52 | 4 | 61 | 23 | 0.928571428571 | 0.693333333333 | 0.793893129771 | 0.753333333333 | 0.780000000000 |
| A4 | 150 | 50 | 5 | 45 | 25 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.633333333333 | 0.666666666667 |
| A5 | 150 | 52 | 2 | 63 | 23 | 0.962962962963 | 0.693333333333 | 0.806201550388 | 0.766666666667 | 0.780000000000 |
| A6 | 150 | 75 | 4 | 70 | 0 | 0.949367088608 | 1.000000000000 | 0.974025974026 | 0.966666666667 | 0.993333333333 |
| A7 | 150 | 75 | 0 | 74 | 0 | 1.000000000000 | 1.000000000000 | 1.000000000000 | 0.993333333333 | 0.993333333333 |


## Rule results — 20 cases/rule, descriptive

| Rule | A1 | A2 | A3 | A4 | A5 | A6 | A7 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ARCH001 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH002 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 0.950000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 0.950000000000 | 1.000000000000 / 1.000000000000 |
| ARCH003 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 0.950000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 0.950000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH004 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 0.869565217391 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 0.869565217391 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH005 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH101 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.450000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.450000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH102 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.350000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.350000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH103 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.200000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.200000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH104 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.250000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.250000000000 | 0.947368421053 / 1.000000000000 | 0.947368421053 / 1.000000000000 |
| ARCH105 | 0.000000000000 / 0.000000000000 | 0.666666666667 / 1.000000000000 | 0.823529411765 / 0.850000000000 | 0.666666666667 / 1.000000000000 | 0.823529411765 / 0.850000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH201 | 0.000000000000 / 0.000000000000 | 0.000000000000 / 0.000000000000 | 0.833333333333 / 0.950000000000 | 0.000000000000 / 0.000000000000 | 0.833333333333 / 0.950000000000 | 0.833333333333 / 0.950000000000 | 1.000000000000 / 0.950000000000 |
| ARCH202 | 0.000000000000 / 0.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH203 | 0.000000000000 / 0.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH204 | 0.000000000000 / 0.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |
| ARCH205 | 0.000000000000 / 0.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 0.000000000000 / 0.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 | 1.000000000000 / 1.000000000000 |


Cells show F1 / definitive coverage. Complete per-rule confusion counts and metrics are preserved in final-rule-strata.json.

## Selected frozen ablations

| Measurement | Value |
| --- | --- |
| A1 | STATIC |
| A2 | GRAPH |
| A3 | LLM |
| A4 | STATIC + GRAPH, H0 |
| A5 | STATIC + LLM, H2 / 0.5 |
| A6 | GRAPH + LLM, H2 / 0.5 |
| A7 | STATIC + GRAPH + LLM, H2 / 0.75 |
| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 300 | 40 | 0 | 40 | 110 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 1.000000000000 | 0.000000000000 | 0.733333333333 | 0.266666666667 | 0.266666666667 |
| A2 | 300 | 60 | 10 | 50 | 90 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.833333333333 | 0.166666666667 | 0.600000000000 | 0.366666666667 | 0.400000000000 |
| A3 | 300 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.770000000000 | 0.796666666667 |
| A4 | 300 | 100 | 10 | 90 | 50 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.900000000000 | 0.100000000000 | 0.333333333333 | 0.633333333333 | 0.666666666667 |
| A5 | 300 | 107 | 4 | 128 | 43 | 0.963963963964 | 0.713333333333 | 0.819923371648 | 0.969696969697 | 0.030303030303 | 0.286666666667 | 0.783333333333 | 0.800000000000 |
| A6 | 300 | 149 | 7 | 141 | 1 | 0.955128205128 | 0.993333333333 | 0.973856209150 | 0.952702702703 | 0.047297297297 | 0.006666666667 | 0.966666666667 | 0.993333333333 |
| A7 | 300 | 149 | 0 | 149 | 1 | 1.000000000000 | 0.993333333333 | 0.996655518395 | 1.000000000000 | 0.000000000000 | 0.006666666667 | 0.993333333333 | 0.996666666667 |


## A7 − comparator deltas — percentage points

| Comparator | Δ Precision | Δ Recall | Δ F1 | Δ effective correctness | Δ coverage |
| --- | --- | --- | --- | --- | --- |
| A1 | 0.000000000000 | 72.666666666667 | 57.560288681570 | 72.666666666667 | 73.000000000000 |
| A2 | 14.285714285714 | 59.333333333333 | 45.120097294010 | 62.666666666667 | 59.666666666667 |
| A3 | 6.140350877193 | 28.000000000000 | 18.604945778859 | 22.333333333333 | 20.000000000000 |
| A4 | 9.090909090909 | 32.666666666667 | 22.742474916388 | 36.000000000000 | 33.000000000000 |
| A5 | 3.603603603604 | 28.000000000000 | 17.673214674714 | 21.000000000000 | 19.666666666667 |
| A6 | 4.487179487179 | 0.000000000000 | 2.279930924432 | 2.666666666667 | 0.333333333333 |


A7 vs A4 describes adding LLM under separately selected models; A7 vs A5 describes adding Graph; A7 vs A6 describes adding Static. These are whole-system comparisons, not causal effects of one feature. A7 remains the predeclared full model regardless of ranking.

## Paired A7 comparisons — same N=300

| Comparator | N | Both correct | A7 only | Comparator only | Neither | Comparator nondefinitive → A7 correct |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | 300 | 80 | 218 | 0 | 2 | 218 |
| A2 | 300 | 109 | 189 | 1 | 1 | 179 |
| A3 | 300 | 231 | 67 | 0 | 2 | 60 |
| A4 | 300 | 189 | 109 | 1 | 1 | 99 |
| A5 | 300 | 235 | 63 | 0 | 2 | 59 |
| A6 | 300 | 290 | 8 | 0 | 2 | 1 |


Correctness means TP or TN only. All four paired cells sum to 300, including nondefinitive and technical-missing rows. No p-values.

## Frozen missing-feature robustness — two rows only

| Measurement | Value |
| --- | --- |
| Truth polarity | 0 positive; 2 negative |
| A5 | {'INSUFFICIENT_EVIDENCE': 1, 'NOT_SUPPORTED': 1} |
| A6 | {'INSUFFICIENT_EVIDENCE': 1, 'NOT_SUPPORTED': 1} |
| A7 | {'NOT_SUPPORTED': 2} |
| Semantic imputation | False |


No new or semantic imputation was used. Selected H2 models retain their frozen TRAIN-median numeric preprocessing and missing indicators; this does not invent an LLM semantic decision. The two-row diagnostic is descriptive only.

## Resource and cost evidence

| Measurement | Value |
| --- | --- |
| Logical requests | 300 |
| Physical invocations | 300 |
| Accepted / technical missing | 298 / 2 |
| Input / output / total reported tokens | 836148 / 117683 / 953831 |
| Cached | 0 |
| Usage unavailable | 1 |
| Known estimated USD | 0.1424563 |
| Reserved uncertainty USD | 0.0042768 |
| Known-or-reserved USD | 0.1467331 |
| Invoice | null |
| P025 calls / spend | 0 / USD 0 |
| Provider transport latency — recorded invocations | 299 |
| Provider transport seconds — sum / mean | 1713.684602575056 / 5.731386630686 |
| Combined component materialization seconds | 4.177361660637 |
| Separate Static / Graph analysis runtime | NOT_MEASURED / NOT_MEASURED |
| Per-method memory/RSS | NOT_MEASURED |
| Prediction-worker peak RSS bytes | 72286208 |
| RSS attribution | WHOLE_PREDICTION_WORKER; NOT_METHOD_ATTRIBUTABLE |
| Method | Measured offline prediction seconds |
| --- | --- |
| A1 | 0.000106667008 |
| A2 | 0.000099124998 |
| A3 | 0.000099209006 |
| A4 | 0.000301124994 |
| A5 | 0.000802666997 |
| A6 | 0.001374832995 |
| A7 | 0.001415249993 |


Offline prediction times include categorical output normalization and differ from analyzer runtime and provider latency. Peak RSS covers the whole worker, not one method. Historical ambiguous usage/latency remain unknown. Costs are versioned estimates, never invoices.

## PRIOR CONTEXT-EFFICIENCY EXPERIMENT — not FINAL N=300

| Measurement | Value |
| --- | --- |
| P017 source fingerprint | 992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091 |
| Matched input/cost N | 99 |
| Binary quality comparison N | 96 |
| Graph input reduction percent | 52.700049596712 |
| Graph cost reduction percent | 36.969541052674 |
| Δ Precision pp | -3.306878306878 |
| Δ F1 pp | -1.814223512337 |
| Δ effective correctness pp | -2.083333333333 |


Graph-guided context materially reduced inputs/cost, while several quality measures were lower. An unqualified preserved-quality claim is unsupported. No Expanded final calls were made.

## DEVELOPMENT VALIDATION — NON-FINAL

P023 TRAIN fitting and one-pass VALIDATION selection produced the frozen configurations above. Development metrics are not included in any final performance table. See [PROMPT_023.md](PROMPT_023.md) for the separate non-final record.

## RQ1–RQ6 evidence synthesis

| RQ | Question | Status | Evidence | Answer | Limitations |
| --- | --- | --- | --- | --- | --- |
| RQ1 | Какова эффективность статического анализа при выявлении архитектурных нарушений? | ANSWERED | final-primary-metrics.json#A1, final-native-scope-metrics.json#A1_STATIC_NATIVE, final-rule-strata.json, final-language-strata.json | Static primary Precision=1.0, Recall=0.26666666666666666; native N=80, F1=1.0. Native explicit-contract rules do not provide universal architecture coverage. | Controlled benchmark; native rules ARCH001/002/004/005; unified results retain unsupported cases. |
| RQ2 | Какие графовые характеристики наиболее полезны для обнаружения архитектурных аномалий? | PARTIALLY_ANSWERED | final-primary-metrics.json#A2, final-rule-strata.json#ARCH003_ARCH101_ARCH105, e39c64ec464c10fc18572f8b74827141b7e957ccd6ac6a851c9cb4d1b59c12b3 | Frozen direct-cycle plus collective V2 model: primary Recall=0.4, native F1=0.9230769230769231. SCC/cycle proof and the collective Ca/Ce/coupling/I/betweenness/PageRank feature mechanism were preserved. No final per-feature selection or ranking was performed. | Aggregate model evidence does not isolate or rank individual graph features. |
| RQ3 | Какие архитектурные нарушения требуют семантического анализа? | ANSWERED | final-primary-metrics.json#A3, final-family-strata.json#SEMANTIC, final-rule-strata.json#ARCH201_ARCH205, final-coverage-metrics.json, final-native-scope-metrics.json#A3_AVAILABLE_ONLY | A3 primary Precision=0.9385964912280702, Recall=0.7133333333333334; semantic-family F1=0.9615384615384616; accepted acquisition 298/300, with two transport-missing outcomes separate from semantic decisions. | Benchmark-specific human semantic truth; classification quality and transport availability are distinct. |
| RQ4 | Повышает ли Hybrid качество относительно отдельных методов? | ANSWERED | final-primary-metrics.json, final-ablation.json, final-paired-comparisons.json, final-hypothesis.json | Selected A7 Precision=1.0, Recall=0.9933333333333333, F1=0.9966555183946488, effective correctness=0.9933333333333333. Exact individual and ablation deltas and paired N=300 counts determine the observed trade-offs. | Descriptive whole-system comparison; no p-values or causal feature attribution. |
| RQ5 | Снижает ли graph-guided context объём LLM-контекста без снижения качества? | ANSWERED | 992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091, prior-context-efficiency.json | Prior matched input N=99: reduction=0.5270004959671245; cost reduction=0.3696954105267378. Precision delta=-3.3068783068783025 pp; F1 delta=-1.8142235123367212 pp. Quality preservation is not supported without qualification. | Prior controlled P017 strategy comparison; final N=300 used GRAPH_GUIDED only and cannot establish an Expanded-vs-Graph causal comparison. |
| RQ6 | Как масштабируется разработанный метод с ростом программной системы? | PARTIALLY_ANSWERED | final-resource-metrics.json | Demonstrated within the evaluated benchmark range: frozen component materialization, 300 final logical requests, reported token/cost totals and measured offline prediction times. Missing resource measurements are NOT_MEASURED. | No asymptotic or universal scalability claim; finite controlled cohort; memory was not systematically measured per method. |


Evidence section names correspond to the frozen aggregate JSON artifacts under experiments/unified-hybrid/p025-final-results-v1. Each source fingerprint is recorded in final-rq-summary.json.

## Architecture hypothesis conclusion

| Measurement | Value |
| --- | --- |
| HYPOTHESIS | Joint Static + Graph + Semantic LLM analysis improves architectural violation recall/completeness while maintaining precision compared with individual methods. |
| FINAL_STATUS | SUPPORTED |
| A7 Precision | 1.000000000000 |
| A7 Recall | 0.993333333333 |
| A7 F1 | 0.996655518395 |
| A7 effective correctness | 0.993333333333 |
| Completeness claim across components | True |
| Exact precision maintenance across components | True |
| Input metric fingerprint | 3694bf7ff75071770a658614b6a2555386318b48ba8d0389950fc6312951ab6b |
| Rationale | Recall improvement across all individual components: True; exact precision maintenance across all: True. See individual deltas and A7 F1, effective correctness and coverage. |
| Individual comparator | Recall improved | Precision maintained | Exact deltas pp |
| --- | --- | --- | --- |
| A1 | True | True | {'F1': 57.56028868157015, 'Precision': 0.0, 'Recall': 72.66666666666667, 'definitive_coverage': 73.0, 'effective_correctness': 72.66666666666667} |
| A2 | True | True | {'F1': 45.120097294010336, 'Precision': 14.285714285714286, 'Recall': 59.333333333333336, 'definitive_coverage': 59.666666666666664, 'effective_correctness': 62.666666666666664} |
| A3 | True | True | {'F1': 18.604945778858824, 'Precision': 6.140350877192983, 'Recall': 28.0, 'definitive_coverage': 20.0, 'effective_correctness': 22.333333333333332} |


The interpretation rule was committed before first final-truth access. SUPPORTED requires strict A7 recall improvement against each A1/A2/A3 and precision at least each comparator, without a tolerance band. The conclusion concerns this frozen controlled architecture benchmark.

## Threats and limitations

- Controlled synthetic cases using an OSS-derived analysis/alignment methodology; this is not an estimate of natural violation prevalence.
- Finite cohort N=300, 20 cases/rule, 15 architecture rules, Java/TypeScript only.
- Human semantic truth is benchmark-specific; structural truth is an independent mechanical oracle.
- LLM evidence is available for 298/300 cases: one ID mismatch and one historical ambiguous invocation without capture. Neither was repeated or semantically imputed.
- One frozen provider/model (OpenAI/gpt-6-luna), STANDARD processing, GRAPH_GUIDED final strategy, 1 hop and the frozen 20,000-character cap.
- The final cohort does not compare context strategies. Expanded-vs-Graph efficiency evidence comes from the prior controlled P017 experiment.
- Native-scope and available-only results are supplemental; primary comparison remains all N=300.
- Ablation differences concern independently selected whole systems, not isolated causal feature effects. Small strata are descriptive; no p-values.
- No new feature ranking, threshold sensitivity search or final-data calibration was performed.
- Runtime and RSS are reported only when measured. Frozen component time combines Static/Graph evidence materialization; per-method memory was not systematically instrumented.
- Results demonstrate feasibility within the evaluated range, not universal or asymptotic scalability.

## Scientific result fingerprints

| Measurement | Value |
| --- | --- |
| Prediction registry | ccb97fa25559d2960be4828c5d06788c9ab187edb355ca11e6fbbc6624a33041 |
| Truth-blind receipt | 39e860c4ba64e347775c390686f8b842fcf56bb375170b84e575ffadf321aab6 |
| Truth | fa3edcd8224250e8dfed987a031a75fd1183f67d6544130c6e77435e0b1920f6 |
| Stable prediction → truth join | dee444d363ce5ad199032106a78fa6d3c648b28f63d9b001d540af7116c175a4 |
| final-ablation.json | c68adf9b16375a85812308bc8efc403d238c8d105544d5e20cabd8252ab9c2a2 |
| final-coverage-metrics.json | ceea3dea28a10596aa84530d033bbabfe1b576dd397a16a17b07a13c24b0b1e1 |
| final-family-strata.json | 520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2 |
| final-hypothesis.json | 43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053 |
| final-language-strata.json | 1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795 |
| final-native-scope-metrics.json | fc48e613ce28811ce9ff6e85dd78bc7949ebf308c75419801fffeaeab882d604 |
| final-paired-comparisons.json | 9c896e89f268eab905caa9c3ce1b64284d2f0e5901fcc7c9610efcb164cbeb7c |
| final-primary-metrics.json | f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e |
| final-resource-metrics.json | 870efc24437b19790073e0986c899c4ae09329085dbe5b84f4af4736c170c6d9 |
| final-rq-summary.json | 402d603c6848d5c6866375ae2b919173cc127d2a2c3c15164372630181bcfb2d |
| final-rule-strata.json | 46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073 |
| final-truth-counts.json | 47f7491b7b4a1abe409cafd7f864b13228c5a455259d107c035fc20b2d914788 |
| prior-context-efficiency.json | 84dbfa2f8dae7ff903f6fe820e08e687343f4df4950e0efb03dc11ef547d1ba6 |
| Evaluation receipt | fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6 |


**READY_FOR_P026_THESIS_CORE_CLOSURE. STOP.** No Security or UI stage was started.
