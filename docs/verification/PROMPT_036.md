# P036 — Security research extension final closure

## A — Lineage

Initial HEAD = origin/main = remote main = `babcba6af3c04be30647820d0d11c03ac5535d96`. P035 complete and READY_FOR_P036 verified. P027–P035 ancestry, exact public index seals, public byte inventories, source/document bindings: PASS.

| Stage | Implementation | Closure | Scientific phase |
|---|---|---|---|
| P027 | 899cec534849a899e7d4ddf28a8cad5672e0fffc | 38778bb25e1fd993ce80fc50c207a76e958d4eaf | Security foundation; no effectiveness experiment |
| P028 | d790da7e50e393ffe0225007182b64efd1db4979 | e93ada51108223e784d38df513183632a48b20ba | Static and bounded intraprocedural V1 |
| P029 | ae99aa94c818f89a4d988bca99c73eb18b6a74cf | 3274504a80abe0ae688796c28322a87f7f5272c9 | Bounded interprocedural V2; historical baseline |
| P030 | 624eb05609e4e24f0cedcc50ce7a3587de0dcf60 | eaaabe47781f63bcad5d83885a5d71b940f9d758 | Prospective controlled benchmark: 300 / DEV 100 / FINAL 200 |
| P031 | See frozen P031 index | 6bbb0e93d353fafc8c9643b9ac66a0329e567fb8 | Independent human A/B review and human-only adjudication; truth freeze |
| P032 | a2f8181a9d5cea11b29dab8ee406f37fb2eaa298 | 7e2cf155038321115cc33bd7f42c84f2701bb6ec | Truth-blind frozen P029 DEV evaluation |
| P033 | 22fbcf6afacc96bd6e405e6ed89fea9512968f4e | 05938c49ef0db278ccf067e916ad7d6201fe658c | DEV-guided generic V3 refinement; one selected candidate |
| P034 | ef2cf4927565606e8d88031c20abc43e5a477637 | e17bb28ca832c59e12f75cc65c88b285051cf73f | OS-isolated truth-blind FINAL prediction freeze |
| P035 | 95f6a949abc4ba469ca18259069acbc2695c71ef | babcba6af3c04be30647820d0d11c03ac5535d96 | Post-freeze truth join and held-out FINAL effectiveness; no tuning |

P035 corrective commit: `dacf423ce69590e9a292b2d3a650cd62ef47ecd7`. Reports [P027](PROMPT_027.md)–[P035](PROMPT_035.md) remain unchanged.

## B — Final scope

P036 performs closure only: no new experiment, metric definition, baseline, candidate, tuning or benchmark analyzer execution. SEC001–SEC010 is a bounded research prototype for Java and TypeScript. Completion does not imply production readiness, general negative classification, UI/UX completion or a completed thesis manuscript.

## C — Architecture separation

CORE_THESIS_COMPLETE=YES. Architecture science and source bindings are unchanged. Security does not feed Architecture Hybrid, rewrite Architecture RQ1–RQ6, or alter its hypothesis. The current import firewall passes.

| Architecture seal | Fingerprint |
|---|---|
| hypothesis | `43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053` |
| primary | `f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e` |
| receipt | `fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6` |
| scientific_registry | `53420d0aa167ebb99814adb498f3b84597b096f73fe1f77c5c467dc7882a8db1` |

## D — Security rule catalog

| Rule | Frozen canonical name |
|---|---|
| SEC001 | Hardcoded Secret |
| SEC002 | SQL Injection Risk |
| SEC003 | Command Injection Risk |
| SEC004 | Path Traversal Risk |
| SEC005 | Unsafe Deserialization |
| SEC006 | Server-Side Request Forgery Risk |
| SEC007 | Cross-Site Scripting Risk |
| SEC008 | Weak Cryptography |
| SEC009 | Insecure Randomness |
| SEC010 | Unsafe Dynamic Code Execution |

SEC006 is abbreviated SSRF Risk; SEC007 is abbreviated XSS Risk. Their full P027 canonical names are preserved. No rule added, removed or renamed.

## E — P027–P029 implementation history

P027 established the Security contract without findings/effectiveness experimentation. P028 added static and bounded intraprocedural V1. P029 added bounded interprocedural V2 and remains a historical frozen baseline; V3 identity is separate.

## F — P030 prospective benchmark

TOTAL=300; DEV=100; FINAL=200. Java=150 and TypeScript=150; ten rules × 30 cases. Cases were not regenerated. Expected private inventory=927, missing=0, unexpected=0. P036 preparation verified opaque pathname metadata only. Historical byte mismatches=0; protected case bytes were not rehashed in P036. The public verification command needs only public files.

## G — P031 independent human truth

Reviewer A=300/300; reviewer B=300/300. Exact agreement=290/300, disagreements=10, raw agreement=0.9666666666666667 (96.67%), Cohen κ=0.9408913583165859 (0.9409). Human-only adjudications=10/10; frozen truth=300/300. Descriptive agreement is not detector accuracy.

| Cohort | N | Positive | Negative | Uncertain | Out of scope | Binary eligible |
|---|---:|---:|---:|---:|---:|---:|
| ALL | 300 | 122 | 158 | 20 | 0 | 280 |
| DEV | 100 | 37 | 52 | 11 | 0 | 89 |
| FINAL | 200 | 85 | 106 | 9 | 0 | 191 |

Original FINAL/DEV/300 truth, review/adjudication responses, rationales and construction intent were not reopened.

## H — P032 frozen V2 DEV baseline

Truth-blind frozen P029 DEV evaluation, distinct from later V3 development. N=100; binary eligible=89. TP/FP/TN/FN=7/0/0/0; positive nondefinitive=30; negative nondefinitive=52. Effective positive recovery=0.1891891891891892 (18.92%); negative correctness=0; definitive coverage=effective correctness=0.07865168539325842; unified correctness=0.07; nondefinitive rate=0.92. Conditional precision/recall/F1 were each 1.0 on definitive predictions: they do not mean V2 recovered all positives.

## I — P033 DEV-guided V3 refinement

Selected candidate `security-bounded-v3`, `iteration-004`; exactly one selected candidate frozen. DEV_USED_FOR_REFINEMENT=YES: development evidence, not blind evidence. N=100, binary eligible=89. TP/FP/TN/FN=21/0/0/0; positive nondefinitive=16; negative nondefinitive=52. Effective recovery=0.5675675675675675 (56.76%); negative correctness=0; binary coverage=effective correctness=0.23595505617977527; unified correctness=0.21; nondefinitive rate=0.79. Conditional precision/recall/F1 each 1.0 apply only to definitive outcomes. Candidate sources, bounds and anti-memorization bindings remain frozen.

## J — P034 blind FINAL prediction

FINAL N=200; Java=100 and TypeScript=100; 20 cases per rule. OS_LEVEL_ISOLATION=VERIFIED; APPLICATION_CAPABILITY_BOUNDARY=VERIFIED. FINAL_TRUTH_READS_BEFORE_PREDICTION_FREEZE=0; registry frozen and writer closed=YES. Authoritative analyzer invocations=1; technical retries=0. P034 is the historical one-shot blind acquisition. No P036 acquisition or replacement.

| Frozen prediction outcome | Count |
|---|---:|
| DEFINITIVE_NEGATIVE | 0 |
| DEFINITIVE_POSITIVE | 41 |
| FAILED | 0 |
| INSUFFICIENT_EVIDENCE | 0 |
| NOT_APPLICABLE | 0 |
| PARTIAL | 137 |
| POTENTIAL | 12 |
| UNSUPPORTED | 10 |

## K — P035 FINAL evaluation chronology

P035 opened original FINAL truth once, after P034 prediction freeze and writer closure. Joined 200 frozen predictions to 200 frozen truth rows; 191 binary eligible. No analyzer rerun, detector modification, post-FINAL tuning, alternative baseline or metric change. P036 uses frozen public aggregate evidence and opaque private fingerprints.

## L — Final V3 capability matrix

| Rule | Java | TypeScript |
|---|---|---|
| SEC001 | IMPLEMENTED_V3 | IMPLEMENTED_V3 |
| SEC002 | PARTIAL_V3 | PARTIAL_V3 |
| SEC003 | PARTIAL_V3 | PARTIAL_V3 |
| SEC004 | PARTIAL_V3 | PARTIAL_V3 |
| SEC005 | PARTIAL_V3 | CONTRACT_ONLY |
| SEC006 | PARTIAL_V3 | PARTIAL_V3 |
| SEC007 | PARTIAL_V3 | PARTIAL_V3 |
| SEC008 | PARTIAL_V3 | PARTIAL_V3 |
| SEC009 | PARTIAL_V3 | PARTIAL_V3 |
| SEC010 | PARTIAL_V3 | PARTIAL_V3 |

Capability status defines engineering scope independently of scores. The capability artifact records all 20 cells, positive paths, negative completeness, bounds and known limitations. Closed literal-only TypeScript SEC008 completeness grammar exists; it produced no definitive negative benchmark output. No whole-program proof is claimed.

## M — Primary held-out FINAL result

Precision among definitive positives is 92.68%. Under frozen P030 conditional confusion semantics, Recall=1.0 and F1=0.9620 because no definitive negative prediction was emitted. However, 47 of 85 human-positive FINAL cases remained nondefinitive: effective positive recovery is 44.71%, and binary definitive coverage is 21.47%. FN=0 does not mean no missed human-positive cases. Of 106 human negatives, 103 remained nondefinitive and 3 were false positives. Zero definitive negatives and zero true negatives mean definitive negative classification was not demonstrated; effective negative correctness is 0. The conditional FPR=1.0 uses the three definitive negative-truth outcomes, not all 106 human negatives. Controlled benchmark; no production guarantee.

| Frozen metric | Exact value |
|---|---:|
| N | 200 |
| binary_eligible | 191 |
| TP | 38 |
| FP | 3 |
| TN | 0 |
| FN | 0 |
| positive_nondefinitive | 47 |
| negative_nondefinitive | 103 |
| nondefinitive_binary | 150 |
| precision | 0.926829268292683 |
| conditional recall | 1.0 |
| conditional F1 | 0.9620253164556962 |
| conditional specificity | 0.0 |
| conditional FPR | 1.0 |
| conditional FNR | 0.0 |
| effective_positive_recovery | 0.4470588235294118 |
| effective_negative_correctness | 0.0 |
| effective_correctness | 0.19895287958115182 |
| definitive_coverage | 0.21465968586387435 |
| unified_correctness | 0.19 |
| unified_definitive_coverage | 0.205 |
| analysis_coverage | 0.95 |
| applicability_coverage | 0.95 |
| nondefinitive_rate | 0.795 |

FN=0 under conditional accounting leaves 47 human-positive cases nondefinitive. All nine UNCERTAIN cases are nondefinitive and excluded from binary metrics. With zero definitive negatives, the analyzer did not demonstrate definitive negative classification on FINAL. No high-specificity, safe-negative certification, comprehensive clean-code detection or general vulnerability exclusion claim is supported.

Thesis-safe numerical block: controlled benchmark 300 (DEV 100, FINAL 200); A/B agreement 96.67%, κ=0.9409; V2 DEV recovery 18.92%; selected V3 DEV recovery 56.76%; blind V3 FINAL recovery 44.71%, binary coverage 21.47%, precision among definitive positives 92.68%, false positives 3, definitive negatives 0, nondefinitive rate 79.5%. Analyzer time 0.538 s for 200 controlled cases; peak worker RSS 62,111,744 bytes. Controlled synthetic/mutation-based material, small strata, frequent abstention and no definitive-negative evidence limit these results; no production or natural-prevalence guarantee.

## N — Rule, language and capability findings

All three false positives occurred in SEC001. Its held-out precision was lower than other rule strata with definitive positives. No case-level explanation or post-FINAL SEC001 fix was attempted. Each rule has N=20 and zero definitive negatives. Conditional stratum P/R/F1 require their own recovery/coverage companions; no causal language comparison or capability-class ranking is justified.

| Rule | TP | FP | Positive recovery | Binary coverage |
|---|---:|---:|---:|---:|
| SEC001 | 3 | 3 | 0.5 | 0.3 |
| SEC002 | 5 | 0 | 0.5 | 0.25 |
| SEC003 | 5 | 0 | 0.5 | 0.25 |
| SEC004 | 6 | 0 | 0.6 | 0.3 |
| SEC005 | 3 | 0 | 0.75 | 0.1875 |
| SEC006 | 4 | 0 | 0.4 | 0.2 |
| SEC007 | 2 | 0 | 0.2857142857142857 | 0.11764705882352941 |
| SEC008 | 2 | 0 | 0.2 | 0.1 |
| SEC009 | 4 | 0 | 0.4 | 0.2 |
| SEC010 | 4 | 0 | 0.5 | 0.2222222222222222 |

| Language | N | Binary N | TP | FP | TN/FN | Positive nondef. | Negative nondef. | Precision | Recovery | Coverage |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| JAVA | 100 | 99 | 16 | 1 | 0/0 | 29 | 53 | 0.9411764705882353 | 0.35555555555555557 | 0.1717171717171717 |
| TYPESCRIPT | 100 | 92 | 22 | 2 | 0/0 | 18 | 50 | 0.9166666666666666 | 0.55 | 0.2608695652173913 |

| Capability | N | Binary N | TP | FP | Nondefinitive | Precision | Recovery | Coverage |
|---|---:|---:|---:|---:|---:|---|---:|---:|
| CONTRACT_ONLY | 10 | 6 | 0 | 0 | 10 | undefined | 0.0 | 0.0 |
| IMPLEMENTED_V3 | 20 | 20 | 3 | 3 | 14 | 0.5 | 0.5 | 0.3 |
| PARTIAL_V3 | 170 | 165 | 35 | 0 | 135 | 1.0 | 0.44871794871794873 | 0.21212121212121213 |

Error accounting: TP=38; FP=3; POSITIVE_NONDEFINITIVE=47; NEGATIVE_NONDEFINITIVE=103; TRUTH_UNCERTAIN=9; UNSUPPORTED=10; FAILED=0. Unsupported is an execution category, not additional disjoint truth cases. Diagnostic gaps overlap: CALL_RESOLUTION_LIMIT=130; CAPABILITY_GAP=10; COMPLETENESS_NOT_PROVEN=200; DATAFLOW_LIMIT=126. They are not mutually exclusive causes.

## O — DEV→FINAL generalization

V3 gains did not collapse completely; FINAL recovery and precision were lower than DEV, while coverage remained similarly low. No blind P029 FINAL comparison exists.

| Frozen FINAL minus DEV delta | Percentage points |
|---|---:|
| definitive_coverage | -2.1295370315900923 |
| effective_correctness | -3.7002176598623455 |
| effective_negative_correctness | 0.0 |
| effective_positive_recovery | -12.050874403815575 |
| nondefinitive_rate | 0.5000000000000004 |
| precision | -7.317073170731703 |

P029_FINAL_EFFECTIVENESS=NOT_EVALUATED. Valid comparisons are V2 DEV→V3 DEV development and, separately, V3 held-out FINAL. No retrospective P029 FINAL experiment was created. Nondefinitive-rate delta is +0.5 pp (frozen floating representation above).

## P — Frozen resources

| P034 authoritative prediction | Exact measured value |
|---|---:|
| analyzer_seconds | 0.5379849630116951 |
| worker_wall_seconds | 0.6030466249794699 |
| process_wall_seconds | 0.8850627089850605 |
| WHOLE_PROCESS_PEAK_RSS_bytes | 62111744 |
| source_bytes | 81889 |
| source_chars | 81889 |
| analysis_failures | 0 |
| technical_retries | 0 |
| timeouts | NOT_MEASURED |

P035 truth_load_seconds=0.0034895830031018704; join_and_metric_aggregation_seconds=0.05391775001771748. These are original frozen measurements. No new runtime measurement or scalability inference.

## Q — Scientific claims and Security research answers

| Claim | Status | Scope and evidence |
|---|---|---|
| SCLM001 | SUPPORTED_WITHIN_CONTROLLED_BENCHMARK | Bounded static/interprocedural analysis produces high-precision definitive positives for a subset of SEC001–SEC010 patterns; FINAL precision 92.68%; recovery 44.71%; binary coverage 21.47% |
| SCLM002 | SUPPORTED_WITH_LIMITATIONS | Generic DEV-guided V3 refinement increased observed DEV positive recovery; 18.92% to 56.76% on DEV; development evidence, not blind FINAL comparison |
| SCLM003 | SUPPORTED_WITH_LIMITATIONS | Frozen V3 retained partial positive-detection capability on held-out FINAL; 44.71% recovery; 47 positive nondefinitive; 21.47% binary coverage |
| SCLM004 | NOT_SUPPORTED | Reliable definitive negative Security decisions; Zero definitive negatives; effective negative correctness 0 |
| SCLM005 | NOT_ESTABLISHED | Generalization to natural real-world vulnerability prevalence; Controlled synthetic/mutation-based benchmark |

| Security question | Answer |
|---|---|
| Q-SEC-A | YES within controlled FINAL evidence and definitive-positive subset |
| Q-SEC-B | YES on DEV: effective positive recovery 18.92% to 56.76% |
| Q-SEC-C | NO full persistence: held-out recovery 44.71%, below DEV 56.76% |
| Q-SEC-D | NOT DEMONSTRATED: zero definitive negatives on FINAL |
| Q-SEC-E | NO production completeness |

These are Security-extension questions, not new thesis RQ numbers or replacements for Architecture RQ1–RQ6.

## R — Authoritative limitations

1. L1: Controlled benchmark; not natural vulnerability prevalence.
2. L2: TOTAL=300, DEV=100, FINAL=200.
3. L3: Per-rule FINAL N=20.
4. L4: Java and TypeScript only.
5. L5: TypeScript SEC005 remains CONTRACT_ONLY.
6. L6: Human UNCERTAIN truth is excluded from binary metrics; FINAL has nine such cases.
7. L7: Bounded static/interprocedural analysis intentionally abstains often.
8. L8: FINAL nondefinitive rate is 79.5%.
9. L9: No definitive negative FINAL outputs; negative classification not demonstrated.
10. L10: Conditional P/R/F1 do not represent recovery over all positives; 47 remained nondefinitive.
11. L11: Effective positive recovery is 44.71%.
12. L12: Definitive binary coverage is 21.47%.
13. L13: Three FINAL false positives, all within SEC001.
14. L14: DEV was used for V3 refinement; DEV results are development evidence.
15. L15: FINAL truth was blind to detector tuning until prediction freeze; no post-FINAL tuning.
16. L16: P029 has no unbiased FINAL baseline; P029 FINAL effectiveness NOT_EVALUATED.
17. L17: Controlled benchmark family includes synthetic/mutation-based material.
18. L18: No production Security guarantee.
19. L19: No proof of whole-program soundness or completeness.
20. L20: Completeness certificates are rule-scoped and bounded; no benchmark negatives certified.
21. L21: No natural-prevalence or causal-effect claim, including language/capability comparisons.
22. L22: No scalability conclusion beyond measured controlled executions.

## S — Privacy, custody and provider boundary

Public Git/staged-path and public-content audit: no private human identities/responses/rationales, case truth, predictions, joins/errors, construction intent, credentials, private source mapping or absolute user paths published. Private scientific directories and quality logs remain ignored. Original human data were not reopened. Actual P036 original truth/review/adjudication/intent/credential reads, provider/OpenAI/LLM/network-provider calls, paid spend, tuning and benchmark analyzer executions: all 0. Git publication is the only authorized network activity. The CLI denies protected opens, analyzer calls and non-Git subprocesses; full pytest uses the closure custody/offline guard. Synthetic non-benchmark tests remain allowed.

The P030 opaque inventory was checked by pathname metadata during preparation. Protected bytes were not rehashed: hidden data custody relies on historical frozen receipts and opaque pins. This limitation is explicit; public verification does not independently prove unavailable private bytes.

## T — Reproducibility

Level 1: public Git, sealed public receipts, fingerprints and aggregates; no private human/case data. Level 2: authorized custodian replay of frozen prediction/truth join, metrics and aggregates without analyzer execution or input mutation. P036 did not perform this replay. Level 3: new experiment execution with original private source/candidate/runtime is a replication, not replacement of historical P034. The one-shot P034 blind acquisition must not be casually rerun.

Runtime: CPython 3.13.14, macOS; historical P034 Seatbelt sandbox-exec. Existing repository dependencies; no installation or provider access. Private source bundle, prediction/truth artifacts and custody inventories are required for authorized replay; their contents, sandbox host profiles and quality logs must not enter Git.

```sh
.venv/bin/python scripts/prompt036_security_closure.py verify
.venv/bin/python scripts/prompt036_security_closure.py verify-published
env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONHASHSEED=0 PYTHONDONTWRITEBYTECODE=1 PYTEST_PLUGINS=archguard.infrastructure.security_closure_test_guard make check
```

## U — Scientific fingerprints

Canonical sorted JSON and SHA-256 exclude operational timestamps. Historical pins are copied unchanged. The final closure index binds all P036 artifact bytes, source/test/script/guard bindings, this report, quality, lineage and the Architecture separation.

### P027

Public index: `477d3e44d4dbd19de25ebf05780818739eb710e9497c08ebc6163272b02ef40a`.

| Frozen scientific pin | Fingerprint |
|---|---|
| sec-rule-registry.json | `9389a584676333887efb1d0e259078ecf8837dfe3f0492bf6c6907640e1c5320` |
| security-analysis-boundary.json | `ccd79bd21f87eaa4e868cfc93379dd97182d8e3b39fa2af3a5b5c522d1df27b0` |
| security-boundary-receipt.json | `4de191d80be96c2fbd46d4486e6a5b093a3285cc0ba11136817338ff0f94ef43` |
| security-capability-matrix.json | `76c634aa9abde653784ad3d6f0e49805fb1f55b8c6288b8af370645803c264bb` |
| security-domain-model.json | `4330b32e557a4f8e6670f4deecb442d0bcb04763ddf750e6cb00c78409efe9ac` |
| security-foundation.json | `0b83e2ff509249829c9c61a2b32cb800805ed186fb8b7b67d2ae8f3d75e0fc5f` |
### P028

Public index: `d5716eb5119044c0fa0f4095f36633706278b250988d4a3cc5d65aed8480d9c2`.

| Frozen scientific pin | Fingerprint |
|---|---|
| analysis-boundary.json | `92c24315c03f78b5f21941d112c16edf3778b7396bb810f03ce3708aa09ea6f9` |
| analysis-protocol.json | `8515ef759a9cd890fff18aab20b68f80b6d61a254d7fede0404cae22927d23d2` |
| detector-registry.json | `3a7a31f8515de16f44de1e98416e3e89151e05db226bb4a6b465ff3b19100ab0` |
| fixture-inventory.json | `1c7dad3b267644cf7ce501e4931787567253d22c0c6ed72d283881cb7e970b9a` |
| quality-verification.json | `b231b6b32e54afa3cd7818ef93ef3ee20dd12882dcbdd5f603eab97860e619f2` |
| security-analysis-v1.json | `79a0274183d276f9c32b8c5a1f76f8ecc776ee12f61dd008987b4cb50683f708` |
| security-api-registry.json | `ebffa8579e93b3502d8bc686beb50940dd694617063fa33d6532bd44fe7c4741` |
| security-capability-matrix.json | `69431d3646e67596010c09f9d24e791b8fefa575f88231809c44d91585a6d8da` |
### P029

Public index: `e15635d73f6acad2fc66926b1e38fecc4d297346beac377343a84adc85120419`.

| Frozen scientific pin | Fingerprint |
|---|---|
| analysis-boundary-v2.json | `a89d108f8a2ca144da959adcb707a611fd6c8648c04ef34400bbea8aa000130c` |
| call-resolution-protocol.json | `a9441b152dd0f1dd618b6e3deb3ef5c62818ebc33c3a09dd507870ed58259560` |
| detector-registry-v2.json | `822701f320cc0e604053c3d70556de0e43867de66695a329db201982a70897ab` |
| fixture-inventory.json | `1c25575be16bfe4b22ea0733264707e8c7eb0b73697872cd774e14d39db8f79c` |
| framework-pack-registry.json | `8af448d672af6cb8ce9462bf8032bcc1ec4d6b2fae0f10d09d52c658f3302283` |
| quality-verification.json | `f7524e365859a0f7a9f21a1537dcc937742d2dc4d33cf312e5114ce0222efada` |
| security-analysis-v2.json | `c74ab979768cd597ffaa91567a7e6424a1ec4e28938a32889f8fd4572c35e2c7` |
| security-capability-matrix-v2.json | `863c33fe50134ef653c6f3b5bad261e0f68668c8a805acc4eb16d8b56e874a24` |
| security-proof-registry.json | `71c878c72406a3856e6a4f9e6e3a0c7ac2bee45f79c503b1186f7abe4335332a` |
| summary-protocol.json | `d7df5af8fa93344b62c2fc54927a15a2b5b49aef0ffb358643556422f24d0388` |
### P030

Public index: `62872f473fb733e0c0ef657f226e82533e6b2a45b69bfe64fea156926a63bf15`.

| Frozen scientific pin | Fingerprint |
|---|---|
| aggregate-inventory.json | `bb274b687638314ad3452e033a6dece48cfac64cc991a64c40d5b78db5458993` |
| benchmark-manifest.json | `4493c00d125240cd64ce53dfb84820bbda0eaa9c5ef19c3fc6240f0c70df51c5` |
| benchmark-protocol.json | `96a226fd76b97ecb752f308200f33e65dae1688df7ef85b00d74994d284fe6c6` |
| construction-validation.json | `cb6be92eaaad51952d3b4547b301a3778b1838a75b56f2a829deb37e03c6092b` |
| human-review-protocol.json | `8ac81d1526f2c6077f90d6bb35c90e5a0030f194f110cf48e04f89e4fd965189` |
| leakage-audit.json | `5bfc0664c39c6c0ee325e42cfb4fcd133a4a39986af96462db28d0ac80ebcc79` |
| p031-human-review-handoff.json | `2112f265a3ab0ece4a9ca65f4b82d7111694cb9be28b629ca25a1574b2e2c055` |
| private-fingerprint-manifest.json | `1fe25b7465d358149b5c53a4a22d70d49cd3a92a1ec7f470471f8547e53ba578` |
| quality-verification.json | `ac8aa8d043a9cbbe001390d260f31ac6be3e0c4ba5e4f9012eedb783b6e17f90` |
| review-packet.schema.json | `f5bd067f34ce7229c7a7677e6ca511423e4820f957cefed527de15a2164841f7` |
| review-response.schema.json | `269acd35d9313773d67b6daad3b21604384ccd11bb1ccc0453c44e54ab0f5713` |
| security-metric-protocol.json | `389f190ee490c1eba54d7f80ebaee6c37fdaf7fbf4b6140edc0e3fd2e9435d92` |
| split-separation-certificate.json | `7b240db07b992893f65474c412f7cdd41c603546d0d9618f932a46e394f0d6b5` |
| SECURITY_BENCHMARK_CASE_INVENTORY_FINGERPRINT | `db3f1e60dfeb644a12403b59a1205fe9f89973187699b5babc75901611e4d232` |
| SECURITY_BENCHMARK_PROTOCOL_FINGERPRINT | `96a226fd76b97ecb752f308200f33e65dae1688df7ef85b00d74994d284fe6c6` |
| SECURITY_DEV_COHORT_FINGERPRINT | `75201588fa3ee94cf6226a5cbd0512f28995569ab4cb2c5f0c7371d60d1f19f3` |
| SECURITY_DEV_FINAL_SEPARATION_FINGERPRINT | `7b240db07b992893f65474c412f7cdd41c603546d0d9618f932a46e394f0d6b5` |
| SECURITY_FINAL_COHORT_FINGERPRINT | `57bb9c3a349c2cf85fe69546aafa1f10be8f05d56e5211fecb7c992e9febe307` |
| SECURITY_HUMAN_REVIEW_PROTOCOL_FINGERPRINT | `8ac81d1526f2c6077f90d6bb35c90e5a0030f194f110cf48e04f89e4fd965189` |
| SECURITY_METRIC_PROTOCOL_FINGERPRINT | `389f190ee490c1eba54d7f80ebaee6c37fdaf7fbf4b6140edc0e3fd2e9435d92` |
| SECURITY_REVIEWER_A_PACKET_SET_FINGERPRINT | `fb4955544a76e6b8284bd7499f691bd5086639d078a5297b5187bc33d6b55f18` |
| SECURITY_REVIEWER_B_PACKET_SET_FINGERPRINT | `1c69e33686a71db1d3b15636401cdd8dbb2417231d51c232668f7bc58efcf47d` |
| SECURITY_REVIEW_PACKET_SCHEMA_FINGERPRINT | `f5bd067f34ce7229c7a7677e6ca511423e4820f957cefed527de15a2164841f7` |
| SECURITY_REVIEW_RESPONSE_SCHEMA_FINGERPRINT | `269acd35d9313773d67b6daad3b21604384ccd11bb1ccc0453c44e54ab0f5713` |
| construction_intent_ledger_fingerprint | `96eeeada1876daa122aee0ddbd8798e119e81c7f802497ed0976bd401c2671af` |
| private_bundle_fingerprint | `64dc06b81192004b44b7e99e9324bc14667c4bee3d94d30ec7ae8a2c457a3e56` |
### P031

Public index: `032ab3d9312ed11bc0226013940272257b782b02b0f91c3597d4cdc8c8bdf84f`.

| Frozen scientific pin | Fingerprint |
|---|---|
| DEV_truth | `bec967a2e197906cf3c7bd3e9b2cb74970ee0d0d20658b13d2c35ec5f1ce4319` |
| FINAL_truth | `00fc038bff72a6ce0d5d7ccb72ff295938f02abf3ccd78c700397f3586150340` |
| adjudication_response_set | `9682bbbbcaed4750faf2b240ac8ea6524ecebd5af44068e1ba6275829d431379` |
| final_truth_custody | `e04ac90be27e18a36058764df3d9e6bbeabd5f1a34ea015730e82d0f17f645d0` |
| human_truth_300 | `4c60a98e2c2b0c77c5b30ed1356228028b5626f4a6ed4f1a786a58159e4f2fad` |
| truth_closure | `c7481bcafa5adb540777d7b507e13f6fcae50d6368bddaaa307b8a8a5c3d7528` |
### P032

Public index: `3af4c82d9a42b38d20397e7be005fea76820929ee3f5cc972e4caea9863d04ad`.

| Frozen scientific pin | Fingerprint |
|---|---|
| CAPABILITY_SUMMARY | `9abe3fee8736b3c775830433dc30690329760e600e3ab5c7a31398b1f16b93e6` |
| ERROR_INVENTORY | `02ac7f8cfa291f5cf52bd14429c6a6d7963b85a210d22c7eeb89abe993cf8b74` |
| EVALUATION_RECEIPT | `bad62811e22a2b66ef7cc7203b8d6d19848b9765918aba834462527dd7d2c8e6` |
| INPUT | `2ce11fa476274e8c99e9d55d70a4b57518dbbcbe55abe8799b7d726d55f66879` |
| JOIN | `6dade76354fa2bf1dd51e80339c3af0b3762f463f1f11c028ed9b2641d6f0ead` |
| LANGUAGE_METRICS | `22caeda215ef12a452f15210e2d18937df2def448828b3c3228c7b2d9e488738` |
| PREDICTION_REGISTRY | `4ff53d50735b7af1032a4cd2e5a7768e4830815fbbedf30f7d4ec8fe09f5662a` |
| PRIMARY_METRICS | `870cadb51268e77196276457251599664034c7b697e30805de594fb6c7e20905` |
| RAW_PREDICTION | `212ecdbecf5e4460c5c24edafad5668d40d78a09836f6c30489526e06267b88b` |
| RESOURCE_SUMMARY | `98190586aa2d3e5514f8188bbf0ff86cc2783726e8e87798d59394f0698be0b8` |
| RULE_METRICS | `9c7f6add347f422d5a2abdbe6fcf6d0572daa0530af0b74751051733b08e03dd` |
| TRUTH_BLIND_RECEIPT | `8fc2ad4db84c59d3d816c98cf8b32c6872427764feef1165ea89dce1263ab7b7` |
### P033

Public index: `2c3325e52a6b9205b8bff133988b336c4e4be145dfda575bceb92b36a4032381`.

| Frozen scientific pin | Fingerprint |
|---|---|
| SECURITY_P033_CANDIDATE_CALL_RESOLUTION_FINGERPRINT | `597f5522594243a98200cfd1c5ed629992bf593d272598dcf52977c4ea25318b` |
| SECURITY_P033_CANDIDATE_CAPABILITY_MATRIX_FINGERPRINT | `667673ab7aabb5aa44f91dfee89d738e1fd1a6285b4ddc165554518648d1491f` |
| SECURITY_P033_CANDIDATE_DETECTOR_REGISTRY_FINGERPRINT | `ae4fa6759ab6f66fc4eb13c62093073e3bbfd4d6a4b394620630b21113b032cf` |
| SECURITY_P033_CANDIDATE_FRAMEWORK_REGISTRY_FINGERPRINT | `0104c47ed96788519cdbb770aa9098e4685f429ff7a555526d1e277367abedf7` |
| SECURITY_P033_CANDIDATE_LIMITS_FINGERPRINT | `7707f68ac392237e5f01a5c4e1f07e2d93707b414958585b2bcf2e04bc02556d` |
| SECURITY_P033_CANDIDATE_MANIFEST_FINGERPRINT | `fa9ff988ef6f46a342ccd5b4a6c24330abd4cd616935d88b5261732572f00e6f` |
| SECURITY_P033_CANDIDATE_PROOF_REGISTRY_FINGERPRINT | `457f371d6256570250e86da5b3895e89a50f24c4a830863b0a6609b640571f90` |
| SECURITY_P033_CANDIDATE_SOURCE_FINGERPRINT | `2a7d0b7573321b1724503e6b5fe7a0d101e11f9929e9ba2a4e64d3694d246afe` |
| SECURITY_P033_CANDIDATE_SUMMARY_PROTOCOL_FINGERPRINT | `9abd080d0a617baf2392c9b4211af906e7ea516eec73c12887906aa5c14f8e66` |
| SECURITY_P033_DEV_ERROR_INVENTORY_FINGERPRINT | `e95799e1ba336fe9a0d860b0b8c592745c13234ca67cf40d661e8f691aeb3355` |
| SECURITY_P033_DEV_LANGUAGE_METRICS_FINGERPRINT | `f6e04bde47a1464a76e0631284c935672f47ea86c9b3dc8a566b30fff94cc176` |
| SECURITY_P033_DEV_PREDICTION_FINGERPRINT | `a599836c48203f36715d39515b94034aa11bb1047aa8baf875dffa53aec8ae3e` |
| SECURITY_P033_DEV_PRIMARY_METRICS_FINGERPRINT | `0e6f07c86c8b4932d896dbe72dcea89af868357083e91ac21662f1dd13122873` |
| SECURITY_P033_DEV_RESOURCE_SUMMARY_FINGERPRINT | `39f44acd427fa018c7bb99033fb97708611a51df45d5825045550659db71850b` |
| SECURITY_P033_DEV_RULE_METRICS_FINGERPRINT | `a9b2583ce33c6979d803c494aa5cbe3cc6c71b94ed0bc6cab2e31557b319abf2` |
| SECURITY_P033_FINAL_BLINDNESS_RECEIPT_FINGERPRINT | `321a341855f2fa2b6262c064d9c490b56b9225ba26bfe0b3bead69fe070f98c1` |
| SECURITY_P033_REFINEMENT_PROTOCOL_FINGERPRINT | `8305a3dd7452c6c62d170a5a8e7bab344bf0deb11ed20e98b0ded95e042c7e4a` |
| SECURITY_P033_SELECTION_RECEIPT_FINGERPRINT | `af4903a48496445d54eeef2c5f7f8a0ce76143634962f38db8ebb3cba977ca31` |
### P034

Public index: `26ef920afcde4180e831b48924f75dffa6cbf348a4edb2d1ff7b7ee55d4921c1`.

| Frozen scientific pin | Fingerprint |
|---|---|
| SECURITY_P034_CUSTODY_INVENTORY_FINGERPRINT | `2c6876a992c7d645e7968262560d7ad2f1b41f5be0e825a38684fcdba78b24a7` |
| SECURITY_P034_FINAL_BLINDNESS_RECEIPT_FINGERPRINT | `ef23a333dd60da43b19e9846585f218a436aa64d325421d1406f10472691842d` |
| SECURITY_P034_FINAL_CAPABILITY_SUMMARY_FINGERPRINT | `0f0d7882ddffd43185408cbca9293ce6f7911517a28599dee19d1e5d648c5ec3` |
| SECURITY_P034_FINAL_INPUT_FINGERPRINT | `82f7b21d8f2f50eefeecba6325fd2ba20809360542b3308a64b040590517e276` |
| SECURITY_P034_FINAL_LANGUAGE_SUMMARY_FINGERPRINT | `f91346b757e6e8eccc866a88a5a0ef8e061aabcc7da6d61659c1c7a14b879b87` |
| SECURITY_P034_FINAL_PREDICTION_FREEZE_RECEIPT_FINGERPRINT | `e2d0c0e790bdca3a43589d6368d4c7fa198e043b824d6d0ca0483d5fcedefa54` |
| SECURITY_P034_FINAL_PREDICTION_OUTCOME_SUMMARY_FINGERPRINT | `23902c7a99a2cb41d9fb0913e775259b2d985d3acbb7c3e585a759b0f1540552` |
| SECURITY_P034_FINAL_PREDICTION_REGISTRY_FINGERPRINT | `f91cc15fe26ddfae51c4f1887cce80004c1ba02aeaa155b506b66eb52f8bb9f0` |
| SECURITY_P034_FINAL_RAW_PREDICTION_FINGERPRINT | `57ca4648cbeb7d2d7a7e6c280c7938e9e3ca962e1872753956c3231a3bb17b0b` |
| SECURITY_P034_FINAL_RESOURCE_SUMMARY_FINGERPRINT | `5c95f45c3d520b8a826d536822000d658d9a57ad638d576fd26a7014de1513c1` |
| SECURITY_P034_FINAL_RULE_SUMMARY_FINGERPRINT | `3b4239596fc76b220b93f2c1ef30a1f1d013171bfd61c4de02f11bb48af66532` |
| SECURITY_P034_OS_ISOLATION_PREFLIGHT_FINGERPRINT | `aea53560dd92fbdea34e77f65784d417490ee6cfb543cde029c89d2ddebaa2a7` |
### P035

Public index: `3e19eb2b2fd3ba1500a452ec672e200a56d74ff88af80481f08659767976ac20`.

| Frozen scientific pin | Fingerprint |
|---|---|
| SECURITY_P035_DEV_FINAL_GENERALIZATION_FINGERPRINT | `a383468d36f64be372b633ae95053580f8088e00bfe0592cd69a0931981d4fcf` |
| SECURITY_P035_FINAL_CAPABILITY_METRICS_FINGERPRINT | `fefb2b29692dcf60cdee139c0c9a1aadad8b1af981afb8fcac7f9e858314f318` |
| SECURITY_P035_FINAL_CUSTODY_INVENTORY_FINGERPRINT | `89fa9942cab6b9fee0380a84a31ee48c9ddcfd181c244d4095ba1225ca8e692e` |
| SECURITY_P035_FINAL_EFFECTIVENESS_FINGERPRINT | `7eb149d705d56a1ea754ba86c613243b8abddc2c3525c40afd75d9957bb66098` |
| SECURITY_P035_FINAL_ERROR_INVENTORY_FINGERPRINT | `2597895307e656e202e00d58409f6159a2e0ff1b123b103a7dedb386684d829e` |
| SECURITY_P035_FINAL_EVALUATION_RECEIPT_FINGERPRINT | `f944873098c3ccea63c037a539444c1c498e3e43a9aa6de2dbcd77699a9181a3` |
| SECURITY_P035_FINAL_JOIN_FINGERPRINT | `03e42278501bfa4c404ca6e4f43b03a64138124c90c19fb22572609a089bf47f` |
| SECURITY_P035_FINAL_LANGUAGE_METRICS_FINGERPRINT | `5e571dec83df88508834746bdd1df65eb0525e1cce1fd65195cd87e2321a8901` |
| SECURITY_P035_FINAL_OUTCOME_CROSSTAB_FINGERPRINT | `02c9ddfc5a37e78023564cc613a40247887878d5dcb1474fe5cc580a967704b3` |
| SECURITY_P035_FINAL_PRIMARY_METRICS_FINGERPRINT | `cb2e461eb89b3578ad6d59e1ec013e71dd732b627ae7785e8a2d5e101044b81e` |
| SECURITY_P035_FINAL_RULE_METRICS_FINGERPRINT | `76ef9f59c88f9cedd6599dfe5e463c4116d5762df44d016cd78295e87f4c62eb` |
| SECURITY_P035_FINAL_TRUTH_OPEN_RECEIPT_FINGERPRINT | `134dae2383229425eff4f871cd1a58fbf9468e2b69f9b2da2a4ae9b151dd8ed3` |

### P036

Quality-dependent closure fingerprints are pending; no completion declaration yet.

## V — Quality

Historical P035 successful make check: 3278 passed, 28 guarded skips, coverage 81%. Historical `archguard` module-not-measured warning is preserved; no evidence ties it to Security scientific metrics. P035 initial collection failure and corrective commit remain documented in P035.

P036 targeted tests: 60 passed. Ruff, format and strict mypy on new modules: PASS. Initial P036 preparation used an incorrect public Architecture result directory and failed with FileNotFoundError; corrected before final preparation. Initial local Ruff checks found formatting/unused-import issues, corrected before commit. No scientific input changed.

Full make check pending. P036_QUALITY_INCOMPLETE; SECURITY_EXTENSION_COMPLETE not declared.

## W — Git publication

Initial HEAD/origin/main/remote equality: `babcba6af3c04be30647820d0d11c03ac5535d96`. Only public-safe P036 code/tests/docs/artifacts are staged. The unrelated HTML deletion is preserved and never read, hashed, staged, restored or committed. Normal push only.

## X — Final completion status

P036 prepared; quality and publication required before completion. CORE_THESIS_COMPLETE=YES; SECURITY_EXTENSION_COMPLETE not yet declared.
