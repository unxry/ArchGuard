# Thesis architecture core closure

## Scope

Hybrid static, graph and semantic LLM analysis of architecture in Java/TypeScript software. Architecture rules only; SEC001–SEC010 are excluded.

## Definition of CORE THESIS COMPLETE

CORE_THESIS_COMPLETE requires implemented methods/languages/rules, independent frozen truth, pre-truth model/prediction freeze, final N=300 metrics, seven ablations, honest RQ synthesis/hypothesis and reproducibility/traceability. Partial RQ2/RQ6 do not justify stronger answers and do not require further experiments to support the scoped primary hypothesis. Security, UI, deployment, full thesis prose and defense slides are outside this scientific closure. Final acceptance is gated by closure-manifest.json and its quality receipt; generated registries alone do not declare completion.

## Implemented scientific method

Source → Java/TypeScript parser → versioned IAM (files/modules, classes/functions, members/properties where supported) → resolved dependency edges → directed graph → Ca/Ce/coupling/I/SCC/cycles/betweenness/PageRank → rule evidence → Hybrid. JS/TSX parsing is regression-tested, outside the final language strata. Tree-sitter 0.26 Point tuple-unpacking compatibility is preserved. Resolution is static and bounded.

Native Static: ARCH001/002/004/005 (80 final cases). Native Graph: ARCH003 and ARCH101–105 (120). ARCH003 is a direct cycle proof. ARCH201–205 use semantic LLM evidence. Included deterministic Static and ARCH003 proofs cannot be downgraded. Graph anomalies without target specification remain suspicious structures; explicit target specifications support normative conformance violations.

Frozen OpenAI/gpt-6-luna protocol: GRAPH_GUIDED, 1 hop, 20,000 character context, max input 32,768 tokens, max output 2,000, expected output 600, at most two technical retries. Exact request identity and response schema are validated; raw transport and normalized evidence are separate. Human labels/rationales were absent from request material. SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_CONTEXT and NOT_APPLICABLE remain distinct.

H0 uses categorical deterministic precedence. H1 uses TRAIN-only weighted ridge, L2=1; H2 uses TRAIN-only Newton logistic regression, L2=1. Numerical preprocessing uses TRAIN medians/scales and missing indicators. A4=H0, A5=H2@0.5, A6=H2@0.5, A7=H2@0.75; these are separately trained/selected ablations, not zeroed A7. No final fitting, threshold search or selection. Frozen schema has no confidence; severity is not confidence.

## Rules ARCH001–ARCH205

Five normative, five graph and five semantic rules. Exact ownership, implementation/test bindings,
all 15 × 20-case A1–A7 strata and fingerprints: `rule-coverage.json`.

## Languages

Java and TypeScript have final experimental evidence; JS/TSX have parser regression evidence only.

## Benchmark

Final controlled N=300: 150 positive / 150 negative; 150 Java / 150 TypeScript; 100 normative / 100 graph / 100 semantic; 15 rules × 20 cases. 200 independent structural truth units and 100 independent human semantic units. No natural-prevalence inference. TRAIN=196 (193 binary), VALIDATION=84 (83 binary); TRAIN/VALIDATION and DEVELOPMENT/FINAL project overlap=0.

## Experiment chronology

P015 independent development human truth → P019 component baselines → P020 prospective cohort, structural oracle and project splits → P021 independent final human truth → P022 blind development LLM → P023 TRAIN-only fitting and one VALIDATION selection → P024 blind final LLM acquisition → P025 truth-blind closed prediction writer → first final truth open/join → frozen evaluation/ablation/RQ/hypothesis → P026 read-only closure. Two final reviewer slots agreed on 100/100 units (kappa=1), 50 positive / 50 negative; this is agreement on a specially constructed prospective benchmark. Construction intent is not authoritative truth.

## Final results

| Method | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | effective_correctness | definitive_coverage |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| A1 | 40 | 0 | 40 | 110 | 1.000000000000 | 0.266666666667 | 0.421052631579 | 1.000000000000 | 0.000000000000 | 0.733333333333 | 0.266666666667 | 0.266666666667 |
| A2 | 60 | 10 | 50 | 90 | 0.857142857143 | 0.400000000000 | 0.545454545455 | 0.833333333333 | 0.166666666667 | 0.600000000000 | 0.366666666667 | 0.400000000000 |
| A3 | 107 | 7 | 124 | 43 | 0.938596491228 | 0.713333333333 | 0.810606060606 | 0.946564885496 | 0.053435114504 | 0.286666666667 | 0.770000000000 | 0.796666666667 |
| A4 | 100 | 10 | 90 | 50 | 0.909090909091 | 0.666666666667 | 0.769230769231 | 0.900000000000 | 0.100000000000 | 0.333333333333 | 0.633333333333 | 0.666666666667 |
| A5 | 107 | 4 | 128 | 43 | 0.963963963964 | 0.713333333333 | 0.819923371648 | 0.969696969697 | 0.030303030303 | 0.286666666667 | 0.783333333333 | 0.800000000000 |
| A6 | 149 | 7 | 141 | 1 | 0.955128205128 | 0.993333333333 | 0.973856209150 | 0.952702702703 | 0.047297297297 | 0.006666666667 | 0.966666666667 | 0.993333333333 |
| A7 | 149 | 0 | 149 | 1 | 1.000000000000 | 0.993333333333 | 0.996655518395 | 1.000000000000 | 0.000000000000 | 0.006666666667 | 0.993333333333 | 0.996666666667 |

A1 has perfect observed precision in its narrow deterministic scope and low unified recall. A2 supplies graph coverage with nonzero false positives. A3 extends semantic/normative reach, with false positives, abstention and technical missingness. A6 has near-complete recall with residual false positives. A7: 149 TP, 0 FP, 149 TN, 1 FN; perfect observed precision and near-complete recall, with one negative abstention. It is not perfect overall correctness or F1. ARCH104 has one positive miss (Recall=0.900000000000, F1=0.947368421053). Java has one positive miss (Recall=0.986666666667, F1=0.993288590604); TypeScript has no positive miss (Recall=1.000000000000, F1=1.000000000000) and one negative abstention. All rule/language/family A1–A7 strata remain in thesis-results.json.

## Ablation

A1 Static; A2 Graph; A3 LLM; A4 Static+Graph; A5 Static+LLM; A6 Graph+LLM; A7 full Hybrid.

| A7 minus | Precision pp | Recall pp | F1 pp |
| --- | --- | --- | --- |
| A1 | 0.000000000000 | 72.666666666667 | 57.560288681570 |
| A2 | 14.285714285714 | 59.333333333333 | 45.120097294010 |
| A3 | 6.140350877193 | 28.000000000000 | 18.604945778859 |
| A4 | 9.090909090909 | 32.666666666667 | 22.742474916388 |
| A5 | 3.603603603604 | 28.000000000000 | 17.673214674714 |
| A6 | 4.487179487179 | 0.000000000000 | 2.279930924432 |

No new significance tests or causal attribution.

## RQ1–RQ6

- RQ1: ANSWERED.
- RQ2: PARTIALLY_ANSWERED.
- RQ3: ANSWERED.
- RQ4: ANSWERED.
- RQ5: ANSWERED.
- RQ6: PARTIALLY_ANSWERED.

## Hypothesis

Joint Static + Graph + Semantic LLM analysis improves architectural violation recall/completeness while maintaining precision compared with individual methods.

The hypothesis is supported on the frozen controlled final benchmark N=300. All three strict Recall gains and exact nondecreasing Precision comparisons
were frozen in P025. No universal proof or natural-prevalence claim.

## Graph-guided efficiency result

Graph-guided context materially reduced LLM input and estimated cost in the controlled strategy comparison, while several quality metrics were modestly lower than expanded context.

Prior P017 resource matched N=99, quality N=96. Frozen reductions: input 52.700049596712%, estimated cost 36.969541052674%. Quality deltas: precision −3.306878306878 pp, F1 −1.814223512337 pp, effective correctness −2.083333333333 pp. Final N=300 has only GRAPH_GUIDED and supplies no Expanded comparison.

## Resource and reliability evidence

300 logical requests / 300 physical invocations; 298 accepted / 2 technical missing; unexecuted=0. Historical terminal failures: TERMINAL_INVALID_REQUEST_ID_MISMATCH and AMBIGUOUS_TRANSPORT_NO_CAPTURE. Neither was retried or semantically imputed. Both missing rows were negative, discovered after freeze/truth open. A3 primary N=300; available-only N=298 is supplemental. Hybrid handled missing indicators using frozen TRAIN preprocessing; technical missingness is not semantic abstention.

Reported input=836148, output=117683, total=953831, cached=0; usage unavailable=1. Known estimated cost USD 0.1424563; reserved uncertainty USD 0.0042768; known-or-reserved USD 0.1467331; invoice=null. These are estimates, not invoice spend. Whole-worker RSS and offline prediction timings were measured in P025; per-method RSS and separate final Static/Graph runtime remain NOT_MEASURED. P026 provider calls=0, connectivity=0, credential reads=0, spend=$0.

## Reproducibility

See [safe verification guide](THESIS_CORE_REPRODUCIBILITY.md). Registries are generated twice and
compared without altering original evidence. All numbers below are copies of frozen P025 JSON.

## Threats and limitations

- Controlled/synthetic benchmark: Natural prevalence and real deployment performance remain unknown.
- OSS-derived methodology is not natural prevalence: No population prevalence inference.
- Finite N=300: No universal generalization.
- Only 20 cases per rule: Descriptive strata; no p-values.
- Java/TypeScript only: No final JS/TSX or all-language effectiveness claim.
- Single frozen provider/model: Provider/model dependence and nondeterminism.
- GRAPH_GUIDED-only final strategy: No final strategy causal comparison.
- Two technical-missing rows: No semantic imputation; one usage value unknown.
- Prior graph-guided comparison is a separate cohort: Quality modestly lower; no unconditional preservation claim.
- Human semantic truth is benchmark-specific: Not universal natural annotator agreement.
- RQ2 feature attribution limitation: No causal individual feature ranking.
- RQ6 scalability limitation: No asymptotic scaling experiment.
- No per-method RSS: NOT_MEASURED by method.
- No final separate Static/Graph runtime: Separate runtimes NOT_MEASURED.
- Small rule strata and no significance inference: No p-values or significance claims.
- Whole-system ablation is not causal attribution: No feature-causal inference.

## Security boundary

Security is PLANNED / OUTSIDE_ARCHITECTURE_CORE; not included in Hybrid results.

## Future engineering work

Security, orchestration polish, frontend/graph UX, report UX, packaging, deployment and performance
hardening are future engineering scope. UI is NOT_PART_OF_SCIENTIFIC_CORE.

## Final closure status

The accepted boolean and mandatory gate results are in `closure-manifest.json`.
P026 stops after scientific closure and normal Git publication, before Security/UI/new experiments.

## Authoritative sources

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
