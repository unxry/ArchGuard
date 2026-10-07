# P016.LIVE.1 — prospective blinded recovery

Baseline: `c34ac13caf5e77ffb37ac7417366dd866664c412`. The original incomplete
run has 106 accepted assessments, one unusable response binding, one ambiguous
transport invocation, and 192 unattempted logical requests. Its public closure
and every private historical file remain unchanged.

This operational protocol deviation is introduced after that interruption and
before any truth join, effectiveness evaluation, or subsequent provider call.
The original scientific protocol, 300 logical requests, contexts, prompts,
model, Standard processing, target rules, decision enum, and decoding settings
remain frozen. No human labels, rationales, reviewer decisions, construction
intent, or prior effectiveness results inform recovery.

The amendment applies prospectively to the remaining run. A structurally
unusable response permits one schema recovery; a second schema failure stops
completion. An ambiguous invocation prefers captured raw data or a concrete
persisted response handle with a supported same-response recovery mechanism.
No handle is invented or inferred. Without a handle, one authorized blind
replacement is permitted; another ambiguity stops completion. All recoveries
and transient retries share the original maximum of three attempts per logical
request. Every valid accepted assessment is permanent, including abstentions.

Recovery order is the existing schema failure, the existing pending invocation,
then the original order of the remaining 192 requests. Serial concurrency is
one. Historical invalid output is never repaired, reassigned, or accepted.
The original ambiguous pending event remains permanently preserved; its remote
processing and usage remain unknown unless genuinely recovered. A replacement
therefore carries possible duplicate remote processing. Exactly-once acceptance
is enforced; exactly-once remote processing cannot be claimed.

The adapter captures credential-checked raw responses before decoding. New
attempts, raw responses, captures, accepted results, and lineage are append-only
and private. The final receipt selects accepted result paths without replacing
the original terminal result. The normalized frozen dataset, rather than the
historical `results/` directory alone, defines the complete 300 assessments.

The spend guard includes every recorded attempt and unresolved reservation
before each call. The frozen pricing assumption supplies estimated cost; the
hard cap remains USD 4.50. Actual invoice cost stays null. Unknown usage stays
unknown, with its configured maximum reservation retained separately.

Synthetic tests cover history preservation, all four judgments, uniform future
recovery, bounded attempts, spend reservation, handle checks, crash replay,
determinism, and denial of truth/construction file access. Preparation and
verification use only frozen request material and external opaque truth hashes.
No real evaluator is called. Private responses and credentials remain ignored.

## Pre-live gate

New provider calls: **0** at amendment preparation. The amendment, implementation,
tests, and source-free audit must be committed before execution. Its commit is
bound into every new invocation. Normal push is attempted without rewriting
history. Successful execution requires 300 accepted assessments, 100 per
strategy, before the immutable AI receipt is produced.

The final A–M report will be appended after execution and validation. This
document does not authorize truth join, P017, or effectiveness metrics.

Pre-live validation: 19 recovery-specific tests are included in the 112 passing
combined synthetic tests (510.63 s). Ruff, formatting, strict mypy for all 221
source files, and `git diff --check` passed. Amendment fingerprint:
`4ec308447a8208573e0a4644f67c4a754a68e8d2b280ae66ed05696bd60326aa`.


## Final A–M verification

Operational distributions only. No case-level human data was opened.

### A — Recovery amendment

| Item | Verified value |
| --- | --- |
| A1 incomplete state / lineage | PASS; 106 accepted, 1 schema-invalid, 1 ambiguous, 192 unattempted |
| A2 truth firewall | PASS; opaque fingerprint prerequisite only |
| A3 frozen before new calls | YES; committed before all 196 new provider invocations |
| A4 amendment fingerprint | `4ec308447a8208573e0a4644f67c4a754a68e8d2b280ae66ed05696bd60326aa` |
| A5 amendment commit | `9b675f50eb06c81fef92b83cf2c69a5e36553bdd` |
| A6 amendment push | SUCCESS; normal push to origin/main |
| A7 scientific prompt/context/model changed | NO; frozen scientific payload reused byte-identically |

Frozen inputs: 100 cases, three strategies, 300 logical requests; openai /
gpt-6-luna / Standard; one-hop graph context, 20,000-character cap,
2,000 output tokens, expected-output assumption 600, serial concurrency one,
90-second timeout, maximum two technical retries within three total attempts.

| Unchanged binding | Fingerprint |
| --- | --- |
| Scientific protocol | `1263e3129c8f60b5c938240af52de91fd786bb6d9738f89689ca185f03344011` |
| Execution-case manifest | `835416078ae2739b8ed016ebc6e1e3fd2b9bf10fed3c21fbb7319e5753aae420` |
| Context manifest | `812c5f0e282bb5a8b19b3acb4ed35ba88a77a20e12855036b1c7d48621641fdc` |
| Request manifest | `ec83ee1485a1275846b7c14ecfafad9db4749f0ca15e06d633d6ee9254c071b5` |
| Prompt/schema | `e1cbd3604299b7423966a90f5441a639484e480b5b467798eed74a8aad9e338b` |
| Strategy config | `d161290904e511fe0e9facef7e1307e3086845d3df0a6fda33e8c5d9c2dec784` |
| Analysis/evaluator protocol | `8659f3683603e60218e8baf2d14104f50b86d722caf4d491770e199614739bf5` |
| Private execution freeze | `086244727c8240a4b7f7fec8f6f58a5a7661476be78cdbe973f81d344e90a57d` |
| Original incomplete ledger | `3e819e9438d53a9b3880aa24693852cce51fab8123653b6463ce55013ddef069` |
| Original recorded raw snapshot | `a5149dd05a76dde0784f87e9c4e30e60aa502a8f0fbd7281a42d62b2d41ca107` |
| Original attempt/usage snapshot | `2dcdbca2f13d5a391bc73a3d38666cee95fe2005afbf540b65f15b68c35eed23` |
| Original execution lineage | `77e3c8074eb1003355983cbd8ffbc29b4c9051ef1c522433bc4a0f9ccc09a6c8` |
| Opaque final human truth | `1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276` |

### B — Existing protocol failure recovery

| Item | Verified value |
| --- | --- |
| B1 original invalid raw preserved | YES; original history byte hashes unchanged |
| B2 original answer remapped/repaired | NO |
| B3 recovery provider calls | 1 |
| B4 recovery structurally valid | YES |
| B5 final accepted assessment | YES |

### C — Existing pending recovery

| Item | Verified value |
| --- | --- |
| C1 original pending preserved | YES; permanently retained in historical audit |
| C2 concrete existing response handle | NO; no handle invented or inferred |
| C3 same-response recovery used | NO |
| C4 replacement invocation used | YES; exactly one |
| C5 original provider processing | UNKNOWN |
| C6 possible duplicate provider processing | YES |
| C7 final accepted assessment | YES |

### D — Complete execution

| Item | Verified value |
| --- | --- |
| D1 expected logical requests | 300 |
| D2 provider invocations | 304 |
| D3 unique accepted assessments | 300 |
| D4 LOCAL_ONLY accepted | 100 |
| D5 GRAPH_GUIDED accepted | 100 |
| D6 EXPANDED_BASELINE accepted | 100 |
| D7 unattempted requests | 0 |
| D8 requests without valid assessment | 0 |
| D9 terminal technical failures remaining | 0 |
| D10 terminal protocol failures remaining | 0 |
| D11 blocking unresolved pending outcomes | 0 |
| Historical ambiguous transport invocations | 1 |
| Historical invalid responses | 3 |
| Historical transient failures | 0 |
| Recorded provider responses | 303 |

### E — Operational response distributions

| Strategy | SUPPORTED | NOT_SUPPORTED | INSUFFICIENT_CONTEXT | NOT_APPLICABLE |
| --- | ---: | ---: | ---: | ---: |
| EXPANDED_BASELINE | 54 | 46 | 0 | 0 |
| GRAPH_GUIDED | 56 | 44 | 0 | 0 |
| LOCAL_ONLY | 53 | 44 | 3 | 0 |

All four judgments remain distinct. These counts have no correctness interpretation.

### F — Retries / recovery

| Item | Verified value |
| --- | --- |
| F1 ordinary transient retries | 0 |
| F2 schema recovery invocations | 3 |
| F3 ambiguous recovery invocations | 1 |
| F4 maximum attempts/request | 2 |
| F5 requests reaching three attempts | 0 |
| F6 attempt-limit violations | 0 |

The three schema recoveries comprise the original failure and two later failures.
The same prospectively committed rule handled all three. No accepted result was replayed.

### G — Duplication semantics

| Item | Verified value |
| --- | --- |
| G1 confirmed duplicate accepted assessments | 0 |
| G2 confirmed repeated completed provider executions | 3 |
| G3 possible duplicate provider processing due ambiguity | 1 |
| G4 hidden/unavailable result used for selection | NO |

G2 records authorized additional generations following unusable schema/binding
responses. G3 records uncertainty about the original pending invocation. Neither
is a duplicate accepted assessment. Exactly-once remote processing is not claimed.

### H — Measured usage / versioned cost

The following values cover recorded responses. The original ambiguous invocation
has unknown input, output, total tokens, latency, and invoice cost. Its USD 0.0042768
reservation remains in exposure; it is never treated as zero usage.

| Phase | Recorded responses | Input | Output | Total tokens | Latency total, s | Estimated USD |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| AMBIGUOUS_TRANSPORT_RECOVERY | 1 | 1540 | 329 | 1869 | 5.857 | 0.0003185 |
| ORDINARY_TRANSIENT_RETRY | 0 | 0 | 0 | 0 | 0.000 | 0 |
| ORIGINAL_PRE_STOP | 107 | 259972 | 36379 | 296351 | 501.968 | 0.0441867 |
| RESUMED_UNATTEMPTED | 192 | 478948 | 60037 | 538985 | 778.578 | 0.0779133 |
| SCHEMA_RECOVERY | 3 | 4840 | 880 | 5720 | 12.518 | 0.0009240 |

| Strategy | Recorded responses | Unknown invocations | Input | Output | Total tokens | Latency total / mean / median, s | Estimated USD |
| --- | ---: | ---: | ---: | ---: | ---: | --- | ---: |
| EXPANDED_BASELINE | 100 | 0 | 441956 | 32753 | 474709 | 429.622 / 4.296 / 3.955 | 0.0605721 |
| GRAPH_GUIDED | 102 | 1 | 208491 | 34400 | 242891 | 445.558 / 4.368 / 3.869 | 0.0380491 |
| LOCAL_ONLY | 101 | 0 | 94853 | 30472 | 125325 | 423.741 / 4.195 / 3.611 | 0.0247213 |

### H — Totals

| Item | Verified value |
| --- | --- |
| H1 original known input/output | 259972 / 36379 |
| H2 schema + ambiguous recovery input/output | 6380 / 1209 |
| H3 resumed original requests input/output | 478948 / 60037 |
| H4 known input tokens | 745300 |
| H5 known output tokens | 97625 |
| H6 known total tokens | 842925 |
| Full usage across every invocation | null; one historical invocation unknown |
| Known HTTP latency total / mean / median, s | 1298.921 / 4.287 / 3.822 |
| H7 frozen-rate known usage estimate, USD | 0.1233425 |
| Unknown usage reservation, USD | 0.0042768 |
| Conservative tracked exposure, USD | 0.1276193 |
| H8 actual invoice cost | null; billing source not consulted |
| H9 hard cap, USD | 4.50 |
| H10 cap exceeded | NO |
| Pricing assumption fingerprint | `2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b` |

Standard processing uses the frozen user-supplied versioned pricing assumption.
No cached-input savings are assumed. Estimated cost is separate from provider
token usage and from actual billing. No connectivity probe was added.

### I — Immutable AI freeze

| Item | Verified value |
| --- | --- |
| I1 300 accepted before freeze | YES |
| I2 raw attempt ledger fingerprint | `3da8f912c440da854d08df6a248cf6986f699c503a38d041b20fdad60d5cb219` |
| I3 normalized 300-assessment fingerprint | `a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273` |
| I4 usage ledger fingerprint | `bce262982fbaa9a70193599d1488a3b266099caabea591238099448e20b5c3b6` |
| I5 execution lineage fingerprint | `50bc6bc4ee363f18eedfcbdc8f0b7f27ea0f1be046bbaa0e30939cfa735c5d3e` |
| I6 recovery amendment fingerprint | `4ec308447a8208573e0a4644f67c4a754a68e8d2b280ae66ed05696bd60326aa` |
| I7 AI freeze receipt fingerprint | `3ff09ed8f27012929412e9c801084ecc552feb2edd1d355a421c9cf58280a4eb` |
| I8 AI_ASSESSMENT_LEDGER_FROZEN | YES |
| Complete public verification fingerprint | `67d3a635a649789bbfd4dc23e64a8a05dc3d3013de71b02b6fe1beb57e1faebe` |

The receipt covers all original and new private raw responses, attempts, intents,
captures, errors, accepted results, and amendment lineage. Accepted-path selection
is explicit. Original 106 accepted files, original schema-invalid raw/result, and
original pending event retain their exact byte hashes. No historical file is replaced.

### J — Blindness

| Item | Verified value |
| --- | --- |
| J1 truth leakage findings | 0 |
| J2 reviewer leakage findings | 0 |
| J3 construction leakage findings | 0 |
| J4 V2/Hybrid leakage findings | 0 |
| J5 case-level human truth accessed | NO |
| J6 construction intent decoded | NO |

### K — Evaluation boundary

| Item | Verified value |
| --- | --- |
| K1 truth joined | NO |
| K2 TP/FP/TN/FN calculated | NO |
| K3 Precision calculated | NO |
| K4 Recall calculated | NO |
| K5 F1 calculated | NO |
| K6 P017 started | NO |
| Other effectiveness metrics / V2 / Hybrid / Security | NOT EXECUTED |

### L — Quality

| Item | Result |
| --- | --- |
| L1 recovery-specific tests | 19 PASS; rerun within post-freeze full suite |
| L2 combined targeted tests | 112 PASS before new calls; 510.63 s |
| L3 post-freeze `make check` | PASS |
| L4 full tests | 1,675 PASS; 952.29 s |
| L5 coverage | 92% |
| L6 Ruff | PASS |
| L7 formatting | PASS; 436 files |
| L8 strict mypy | PASS; 221 source files |
| L9 offline manifest / opaque truth verification | PASS through recovery verification gates |
| L10 complete live freeze verification | PASS; 300 exact accepted identities |
| L11 privacy / secret audit | PASS; no private artifacts tracked, no credentials persisted |
| L12 `git diff --check` | PASS |

All tests use synthetic transports. Full checks ran after the complete AI freeze;
no provider invocation or real truth join was added by tests or verification.

`scripts/prompt016_recovery.py --verify`: PASS after the complete freeze. This
verifies the unchanged P016 offline manifest and wire payloads, opaque final-human
truth lineage, amendment implementation binding, original history, all accepted
results, raw hashes, complete receipt, and recomputed aggregate statistics.
No real evaluator or provider call occurs in verification.

### M — Git

M1 amendment commit: `9b675f50eb06c81fef92b83cf2c69a5e36553bdd`; normal push SUCCESS.
M2 completion commit: the commit containing this completed report and public audit;
its exact SHA is supplied in the final response after creation.
M3 completion normal push result and M4 final clean-tree check are supplied there.
Private source-bearing payloads, raw responses, private ledgers, and `.env.ai.local`
remain ignored. No history rewrite, force push, rebase, reset, or amend is used.

### Final status

`P016_LIVE_EXECUTION_COMPLETE`
`AI_ASSESSMENT_LEDGER_FROZEN`
`READY_FOR_P017_EVALUATION`

STOP before truth join, P017, and effectiveness metrics.
