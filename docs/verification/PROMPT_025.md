# PROMPT 025 — Final blind prediction, first truth open and architecture evaluation

**P025_FINAL_ARCHITECTURE_EVALUATION_COMPLETE**. **READY_FOR_P026_THESIS_CORE_CLOSURE**. STOP.

[Full final scientific report](FINAL_ARCHITECTURE_EXPERIMENT.md) contains primary, supplemental, strata, ablation, paired, resource, RQ and hypothesis tables.

## A — Lineage and worktree

| Measurement | Value |
| --- | --- |
| P020 / P021.B / P023 / P024 / LIVE / LIVE.1 / LIVE.2 | PASS |
| Initial HEAD | 27c53640b16ed9746cac3cbcb93a3610c847f5c1 |
| Prospective P025 infrastructure commit | f17e3946909c2b2f3ba1861fe35f2baed9b67dd9 |
| Scientific tree | clean except authorized unrelated deletion |
| HTML deletion | preserved unread, unchanged and unstaged |
| No reset/amend/rebase/squash/force push | True |


## B — Acquisition input

| Measurement | Value |
| --- | --- |
| Final logical | 300 |
| Accepted LLM | 298 |
| Mismatch technical missing | 1 |
| Ambiguous no-capture missing | 1 |
| Total missing | 2 |
| Unexecuted | 0 |
| Static / Graph rows | 300 / 300 |
| Acquisition freeze | 27bdc88a34165a7c08b394971d63d28abc012e084c0abf67bb86be6d162b17b7 |
| Handoff | f15dfd5edd305c308f001fb81f308f60ed79a0cb09b2950a10f2187ec4e2e37e |


## C — Model lock

| Measurement | Value |
| --- | --- |
| A4 | H0 |
| A5 | H2 / 0.5 |
| A6 | H2 / 0.5 |
| A7 | H2 / 0.75 |
| Selected registry | 269e4fe3cdcab8b3461e8f7b24b4eb9f49b0cf455a843b776fb5e490de53a9df |
| Model lock | d424792a985335b0e259a1fbf9478bf140fb371a7112a40f470661f9c7d1bd57 |
| Refit / threshold tuning / unselected final candidates | NO / NO / NO |


## D — Prediction chronology

| Measurement | Value |
| --- | --- |
| Truth mounted / readable by prediction worker | False |
| Final truth reads before freeze | 0 |
| A1–A7 predictions | YES × 7; 300 stable cases/method |
| Prediction registry | ccb97fa25559d2960be4828c5d06788c9ab187edb355ca11e6fbbc6624a33041 |
| Closed-writer truth-blind receipt | 39e860c4ba64e347775c390686f8b842fcf56bb375170b84e575ffadf321aab6 |
| Model hashes unchanged | True |
| Prediction directories read-only before Phase 2 | True |


## E — Authoritative final truth

| Measurement | Value |
| --- | --- |
| Structural / semantic / total | 200 / 100 / 300 |
| Positive / negative | 150 / 150 |
| Uncertain / OOS / missing / duplicate | 0 / 0 / 0 / 0 |
| Truth fingerprint | fa3edcd8224250e8dfed987a031a75fd1183f67d6544130c6e77435e0b1920f6 |
| Join fingerprint | dee444d363ce5ad199032106a78fa6d3c648b28f63d9b001d540af7116c175a4 |
| Join key | authoritative stable scientific ID; never array/order/filename |


## F — PRIMARY A1–A7

| Method | N | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 300 | 40 | 0 | 40 | 110 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 1.000000000000 | 0.000000000000 | 0.733333333333 | 0.266666666667 | 0.266666666667 |
| A2 | 300 | 60 | 10 | 50 | 90 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.833333333333 | 0.166666666667 | 0.600000000000 | 0.366666666667 | 0.400000000000 |
| A3 | 300 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.770000000000 | 0.796666666667 |
| A4 | 300 | 100 | 10 | 90 | 50 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.900000000000 | 0.100000000000 | 0.333333333333 | 0.633333333333 | 0.666666666667 |
| A5 | 300 | 107 | 4 | 128 | 43 | 0.963963963964 | 0.713333333333 | 0.819923371648 | 0.969696969697 | 0.030303030303 | 0.286666666667 | 0.783333333333 | 0.800000000000 |
| A6 | 300 | 149 | 7 | 141 | 1 | 0.955128205128 | 0.993333333333 | 0.973856209150 | 0.952702702703 | 0.047297297297 | 0.006666666667 | 0.966666666667 | 0.993333333333 |
| A7 | 300 | 149 | 0 | 149 | 1 | 1.000000000000 | 0.993333333333 | 0.996655518395 | 1.000000000000 | 0.000000000000 | 0.006666666667 | 0.993333333333 | 0.996666666667 |
| Method | Nondefinitive | Non-applicability | Technical missing |
| --- | --- | --- | --- |
| A1 | 220 | 220 | 0 |
| A2 | 180 | 180 | 0 |
| A3 | 61 | 2 | 2 |
| A4 | 100 | 100 | 0 |
| A5 | 60 | 2 | 0 |
| A6 | 2 | 0 | 0 |
| A7 | 1 | 0 | 0 |


## G — A3 missingness

| Measurement | Value |
| --- | --- |
| Primary N | 300 |
| Semantic evidence | 298 |
| Technical missing | 2 |
| Missing-positive | 0 |
| Missing-negative | 2 |
| SUPPLEMENTAL available-only N | 298 |
| SUPPLEMENTAL available-only Precision | 0.938596491228 |
| SUPPLEMENTAL available-only Recall | 0.713333333333 |
| SUPPLEMENTAL available-only F1 | 0.810606060606 |
| SUPPLEMENTAL available-only effective_correctness | 0.775167785235 |


## H / I — Family, language and 15-rule results

Complete descriptive tables and confusion counts: see the full scientific report and final-family-strata.json / final-rule-strata.json / final-language-strata.json.

| Measurement | Value |
| --- | --- |
| final-family-strata.json | 520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2 |
| final-rule-strata.json | 46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073 |
| final-language-strata.json | 1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795 |


## J / K — Selected ablation and paired A7

| Comparator | Exact A7 − comparator pp |
| --- | --- |
| A1 | {'F1': 57.56028868157015, 'Precision': 0.0, 'Recall': 72.66666666666667, 'definitive_coverage': 73.0, 'effective_correctness': 72.66666666666667} |
| A2 | {'F1': 45.120097294010336, 'Precision': 14.285714285714286, 'Recall': 59.333333333333336, 'definitive_coverage': 59.666666666666664, 'effective_correctness': 62.666666666666664} |
| A3 | {'F1': 18.604945778858824, 'Precision': 6.140350877192983, 'Recall': 28.0, 'definitive_coverage': 20.0, 'effective_correctness': 22.333333333333332} |
| A4 | {'F1': 22.74247491638796, 'Precision': 9.090909090909092, 'Recall': 32.666666666666664, 'definitive_coverage': 33.0, 'effective_correctness': 36.0} |
| A5 | {'F1': 17.673214674713925, 'Precision': 3.6036036036036037, 'Recall': 28.0, 'definitive_coverage': 19.666666666666668, 'effective_correctness': 21.0} |
| A6 | {'F1': 2.279930924432203, 'Precision': 4.487179487179487, 'Recall': 0.0, 'definitive_coverage': 0.3333333333333333, 'effective_correctness': 2.6666666666666665} |
| Comparator | Both correct | A7 only | Comparator only | Neither |
| --- | --- | --- | --- | --- |
| A1 | 80 | 218 | 0 | 2 |
| A2 | 109 | 189 | 1 | 1 |
| A3 | 231 | 67 | 0 | 2 |
| A4 | 189 | 109 | 1 | 1 |
| A5 | 235 | 63 | 0 | 2 |
| A6 | 290 | 8 | 0 | 2 |


## L — Resources

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


## M — RQ1–RQ6

| RQ | Status | Evidence | Answer | Limitations |
| --- | --- | --- | --- | --- |
| RQ1 | ANSWERED | final-primary-metrics.json#A1, final-native-scope-metrics.json#A1_STATIC_NATIVE, final-rule-strata.json, final-language-strata.json | Static primary Precision=1.0, Recall=0.26666666666666666; native N=80, F1=1.0. Native explicit-contract rules do not provide universal architecture coverage. | Controlled benchmark; native rules ARCH001/002/004/005; unified results retain unsupported cases. |
| RQ2 | PARTIALLY_ANSWERED | final-primary-metrics.json#A2, final-rule-strata.json#ARCH003_ARCH101_ARCH105, e39c64ec464c10fc18572f8b74827141b7e957ccd6ac6a851c9cb4d1b59c12b3 | Frozen direct-cycle plus collective V2 model: primary Recall=0.4, native F1=0.9230769230769231. SCC/cycle proof and the collective Ca/Ce/coupling/I/betweenness/PageRank feature mechanism were preserved. No final per-feature selection or ranking was performed. | Aggregate model evidence does not isolate or rank individual graph features. |
| RQ3 | ANSWERED | final-primary-metrics.json#A3, final-family-strata.json#SEMANTIC, final-rule-strata.json#ARCH201_ARCH205, final-coverage-metrics.json, final-native-scope-metrics.json#A3_AVAILABLE_ONLY | A3 primary Precision=0.9385964912280702, Recall=0.7133333333333334; semantic-family F1=0.9615384615384616; accepted acquisition 298/300, with two transport-missing outcomes separate from semantic decisions. | Benchmark-specific human semantic truth; classification quality and transport availability are distinct. |
| RQ4 | ANSWERED | final-primary-metrics.json, final-ablation.json, final-paired-comparisons.json, final-hypothesis.json | Selected A7 Precision=1.0, Recall=0.9933333333333333, F1=0.9966555183946488, effective correctness=0.9933333333333333. Exact individual and ablation deltas and paired N=300 counts determine the observed trade-offs. | Descriptive whole-system comparison; no p-values or causal feature attribution. |
| RQ5 | ANSWERED | 992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091, prior-context-efficiency.json | Prior matched input N=99: reduction=0.5270004959671245; cost reduction=0.3696954105267378. Precision delta=-3.3068783068783025 pp; F1 delta=-1.8142235123367212 pp. Quality preservation is not supported without qualification. | Prior controlled P017 strategy comparison; final N=300 used GRAPH_GUIDED only and cannot establish an Expanded-vs-Graph causal comparison. |
| RQ6 | PARTIALLY_ANSWERED | final-resource-metrics.json | Demonstrated within the evaluated benchmark range: frozen component materialization, 300 final logical requests, reported token/cost totals and measured offline prediction times. Missing resource measurements are NOT_MEASURED. | No asymptotic or universal scalability claim; finite controlled cohort; memory was not systematically measured per method. |


## N — Hypothesis

| Measurement | Value |
| --- | --- |
| Status | SUPPORTED |
| A7 Precision | 1.000000000000 |
| A7 Recall | 0.993333333333 |
| A7 F1 | 0.996655518395 |
| A7 effective_correctness | 0.993333333333 |
| Completeness result | True |
| Precision maintenance | True |
| Rationale | Recall improvement across all individual components: True; exact precision maintenance across all: True. See individual deltas and A7 F1, effective correctness and coverage. |
| Comparator | Exact precision/recall and other deltas pp |
| --- | --- |
| A1 | {'F1': 57.56028868157015, 'Precision': 0.0, 'Recall': 72.66666666666667, 'definitive_coverage': 73.0, 'effective_correctness': 72.66666666666667} |
| A2 | {'F1': 45.120097294010336, 'Precision': 14.285714285714286, 'Recall': 59.333333333333336, 'definitive_coverage': 59.666666666666664, 'effective_correctness': 62.666666666666664} |
| A3 | {'F1': 18.604945778858824, 'Precision': 6.140350877192983, 'Recall': 28.0, 'definitive_coverage': 20.0, 'effective_correctness': 22.333333333333332} |


## O — Scientific boundary

| Measurement | Value |
| --- | --- |
| provider calls | 0 |
| connectivity probes | 0 |
| credential reads | 0 |
| model fitting | 0 |
| preprocessing fitting | 0 |
| threshold tuning | 0 |
| prediction mutation after truth | 0 |
| Security | 0 |
| new human annotation | 0 |
| intent used as truth | 0 |


## P — Quality

| Measurement | Value |
| --- | --- |
| P025 targeted tests | 28 |
| Combined P025/P023/P024/LIVE.2/P021.B/P020 regressions | 367 |
| Static/Graph component regressions | 79 |
| Truth-blind chronology / prediction freeze / model immutability | PASS |
| Truth join / metric semantics / technical missing / strata / ablation / paired | PASS |
| Two offline evaluations identical; no repredict | PASS |
| Privacy / secret audit | PASS; no credentials persisted |
| Ruff / format / strict mypy | PASS |
| make check | PASS |
| Full tests | 2290 |
| Coverage percent | 85 |
| git diff --check | PASS excluding authorized unrelated HTML deletion |


## Q — Freezes

| Measurement | Value |
| --- | --- |
| Q1 prediction registry | ccb97fa25559d2960be4828c5d06788c9ab187edb355ca11e6fbbc6624a33041 |
| Q2 truth-blind receipt | 39e860c4ba64e347775c390686f8b842fcf56bb375170b84e575ffadf321aab6 |
| Q3 truth | fa3edcd8224250e8dfed987a031a75fd1183f67d6544130c6e77435e0b1920f6 |
| Q4 stable join | dee444d363ce5ad199032106a78fa6d3c648b28f63d9b001d540af7116c175a4 |
| Q5 final-primary-metrics.json | f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e |
| Q6 final-coverage-metrics.json | ceea3dea28a10596aa84530d033bbabfe1b576dd397a16a17b07a13c24b0b1e1 |
| Q7 final-native-scope-metrics.json | fc48e613ce28811ce9ff6e85dd78bc7949ebf308c75419801fffeaeab882d604 |
| Q8 final-family-strata.json | 520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2 |
| Q9 final-rule-strata.json | 46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073 |
| Q10 final-language-strata.json | 1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795 |
| Q11 final-ablation.json | c68adf9b16375a85812308bc8efc403d238c8d105544d5e20cabd8252ab9c2a2 |
| Q12 final-paired-comparisons.json | 9c896e89f268eab905caa9c3ce1b64284d2f0e5901fcc7c9610efcb164cbeb7c |
| Q13 final-resource-metrics.json | 870efc24437b19790073e0986c899c4ae09329085dbe5b84f4af4736c170c6d9 |
| Q14 final-rq-summary.json | 402d603c6848d5c6866375ae2b919173cc127d2a2c3c15164372630181bcfb2d |
| Q15 final-hypothesis.json | 43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053 |
| Q16 final evaluation receipt | fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6 |


## R — Git closure

| Measurement | Value |
| --- | --- |
| Infrastructure commit | f17e3946909c2b2f3ba1861fe35f2baed9b67dd9 |
| Final closure SHA | provided at delivery; recover with git log -1 -- docs/verification/PROMPT_025.md |
| Publication | normal push origin/main; post-push equality verified at delivery |
| Scientific tree | clean except authorized unrelated HTML deletion |
| HTML deletion | preserved unstaged |


Private predictions, case-level truth, stable-ID joins and missing-case identities remain Git-ignored. Models/predictions/truth/metric definitions were not altered after truth open. Public JSON contains aggregate values and opaque fingerprints only.

**READY_FOR_P026_THESIS_CORE_CLOSURE. STOP.**
