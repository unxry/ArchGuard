# Frozen thesis numeric facts

Final controlled N=300: 150 positive / 150 negative; 150 Java / 150 TypeScript; 100 normative / 100 graph / 100 semantic; 15 rules × 20 cases. 200 independent structural truth units and 100 independent human semantic units. No natural-prevalence inference. TRAIN=196 (193 binary), VALIDATION=84 (83 binary); TRAIN/VALIDATION and DEVELOPMENT/FINAL project overlap=0.

| Method | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 40 | 0 | 40 | 110 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 1.000000000000 | 0.000000000000 | 0.733333333333 | 0.266666666667 | 0.266666666667 |
| A2 | 60 | 10 | 50 | 90 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.833333333333 | 0.166666666667 | 0.600000000000 | 0.366666666667 | 0.400000000000 |
| A3 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.770000000000 | 0.796666666667 |
| A4 | 100 | 10 | 90 | 50 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.900000000000 | 0.100000000000 | 0.333333333333 | 0.633333333333 | 0.666666666667 |
| A5 | 107 | 4 | 128 | 43 | 0.963963963964 | 0.713333333333 | 0.819923371648 | 0.969696969697 | 0.030303030303 | 0.286666666667 | 0.783333333333 | 0.800000000000 |
| A6 | 149 | 7 | 141 | 1 | 0.955128205128 | 0.993333333333 | 0.973856209150 | 0.952702702703 | 0.047297297297 | 0.006666666667 | 0.966666666667 | 0.993333333333 |
| A7 | 149 | 0 | 149 | 1 | 1.000000000000 | 0.993333333333 | 0.996655518395 | 1.000000000000 | 0.000000000000 | 0.006666666667 | 0.993333333333 | 0.996666666667 |

| A7 minus | Precision pp | Recall pp | F1 pp |
| --- | --- | --- | --- |
| A1 | 0.000000000000 | 72.666666666667 | 57.560288681570 |
| A2 | 14.285714285714 | 59.333333333333 | 45.120097294010 |
| A3 | 6.140350877193 | 28.000000000000 | 18.604945778859 |
| A4 | 9.090909090909 | 32.666666666667 | 22.742474916388 |
| A5 | 3.603603603604 | 28.000000000000 | 17.673214674714 |
| A6 | 4.487179487179 | 0.000000000000 | 2.279930924432 |

- RQ1: ANSWERED.
- RQ2: PARTIALLY_ANSWERED.
- RQ3: ANSWERED.
- RQ4: ANSWERED.
- RQ5: ANSWERED.
- RQ6: PARTIALLY_ANSWERED.

The hypothesis is supported on the frozen controlled final benchmark N=300.

Graph-guided context materially reduced LLM input and estimated cost in the controlled strategy comparison, while several quality metrics were modestly lower than expanded context.

Prior P017 resource matched N=99, quality N=96. Frozen reductions: input 52.700049596712%, estimated cost 36.969541052674%. Quality deltas: precision −3.306878306878 pp, F1 −1.814223512337 pp, effective correctness −2.083333333333 pp. Final N=300 has only GRAPH_GUIDED and supplies no Expanded comparison.

300 logical requests / 300 physical invocations; 298 accepted / 2 technical missing; unexecuted=0. Historical terminal failures: TERMINAL_INVALID_REQUEST_ID_MISMATCH and AMBIGUOUS_TRANSPORT_NO_CAPTURE. Neither was retried or semantically imputed. Both missing rows were negative, discovered after freeze/truth open. A3 primary N=300; available-only N=298 is supplemental. Hybrid handled missing indicators using frozen TRAIN preprocessing; technical missingness is not semantic abstention.

Reported input=836148, output=117683, total=953831, cached=0; usage unavailable=1. Known estimated cost USD 0.1424563; reserved uncertainty USD 0.0042768; known-or-reserved USD 0.1467331; invoice=null. These are estimates, not invoice spend. Whole-worker RSS and offline prediction timings were measured in P025; per-method RSS and separate final Static/Graph runtime remain NOT_MEASURED. P026 provider calls=0, connectivity=0, credential reads=0, spend=$0.

Every table/value is rendered from `numeric-facts.json`, copied from these sealed authoritative
P025 aggregates. Twelve decimals are display precision; original floats/exact ratios remain
authoritative.

- `experiments/unified-hybrid/p025-final-results-v1/final-primary-metrics.json` — `f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e`.
- `experiments/unified-hybrid/p025-final-results-v1/final-coverage-metrics.json` — `ceea3dea28a10596aa84530d033bbabfe1b576dd397a16a17b07a13c24b0b1e1`.
- `experiments/unified-hybrid/p025-final-results-v1/final-native-scope-metrics.json` — `fc48e613ce28811ce9ff6e85dd78bc7949ebf308c75419801fffeaeab882d604`.
- `experiments/unified-hybrid/p025-final-results-v1/final-family-strata.json` — `520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2`.
- `experiments/unified-hybrid/p025-final-results-v1/final-rule-strata.json` — `46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073`.
- `experiments/unified-hybrid/p025-final-results-v1/final-language-strata.json` — `1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795`.
- `experiments/unified-hybrid/p025-final-results-v1/final-ablation.json` — `c68adf9b16375a85812308bc8efc403d238c8d105544d5e20cabd8252ab9c2a2`.
- `experiments/unified-hybrid/p025-final-results-v1/final-paired-comparisons.json` — `9c896e89f268eab905caa9c3ce1b64284d2f0e5901fcc7c9610efcb164cbeb7c`.
- `experiments/unified-hybrid/p025-final-results-v1/final-resource-metrics.json` — `870efc24437b19790073e0986c899c4ae09329085dbe5b84f4af4736c170c6d9`.
- `experiments/unified-hybrid/p025-final-results-v1/final-rq-summary.json` — `402d603c6848d5c6866375ae2b919173cc127d2a2c3c15164372630181bcfb2d`.
- `experiments/unified-hybrid/p025-final-results-v1/final-hypothesis.json` — `43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053`.
- `experiments/unified-hybrid/p025-final-results-v1/evaluation-receipt.json` — `fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6`.
- `experiments/unified-hybrid/p025-final-results-v1/final-truth-counts.json` — `47f7491b7b4a1abe409cafd7f864b13228c5a455259d107c035fc20b2d914788`.
- `experiments/unified-hybrid/p025-final-results-v1/prior-context-efficiency.json` — `84dbfa2f8dae7ff903f6fe820e08e687343f4df4950e0efb03dc11ef547d1ba6`.
