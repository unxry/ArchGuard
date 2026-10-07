# PROMPT 016.LIVE — blind incomplete execution report

Status: **P016_LIVE_INCOMPLETE_PENDING_TRANSPORT** / **P016_LIVE_EXECUTION_INCOMPLETE**.

No complete AI dataset was frozen. P017 is not ready. No further provider calls were made after the unresolved attempt.

## A — Frozen inputs

Repository lineage PASS: pre-live HEAD `c4e2ed358568e8b0992f8cc3838e688443bbfb5d`, descended from P015.F `08082d793d5962cee1bdc51dccc54ca79ac46bfd`. Initial working tree was clean. Private inputs, ledger and credential file remain ignored.

| Artifact | Fingerprint | Check |
|---|---|---|
| analysis-plan.json | `8659f3683603e60218e8baf2d14104f50b86d722caf4d491770e199614739bf5` | PASS |
| context_manifest_fingerprint | `812c5f0e282bb5a8b19b3acb4ed35ba88a77a20e12855036b1c7d48621641fdc` | PASS |
| execution-cases.json | `835416078ae2739b8ed016ebc6e1e3fd2b9bf10fed3c21fbb7319e5753aae420` | PASS |
| execution_freeze_fingerprint | `086244727c8240a4b7f7fec8f6f58a5a7661476be78cdbe973f81d344e90a57d` | PASS |
| prompt-schema.json | `e1cbd3604299b7423966a90f5441a639484e480b5b467798eed74a8aad9e338b` | PASS |
| protocol_fingerprint | `1263e3129c8f60b5c938240af52de91fd786bb6d9738f89689ca185f03344011` | PASS |
| request_manifest_fingerprint | `ec83ee1485a1275846b7c14ecfafad9db4749f0ca15e06d633d6ee9254c071b5` | PASS |
| strategy-config.json | `d161290904e511fe0e9facef7e1307e3086845d3df0a6fda33e8c5d9c2dec784` | PASS |
| truth_fingerprint | `1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276` | PASS |
| Public offline verification | `a9ac2b5f1ffe8946c76bd1bfcdeae135324adf212a8b912ea63ab279487bc4ca` | PASS |
| Public safety verification | `f404069244c612c376194fa8a3808dd3361626082712d48cb412ac0aa0c25220` | PASS |

All 300 frozen contexts and request payloads were verified against their immutable byte manifests; context/request/prompt/strategy drift = 0. Order remained sorted opaque case rank with rotating strategies, serial concurrency 1. Parameters remain 100 cases, 1 hop, 20,000 context characters, 32,768 configured input bound, 2,000 maximum output tokens, 600 expected output tokens, 90-second timeout, maximum 2 technical retries.

Opaque human-truth prerequisite PASS, verified by a separate coordinator process without parsing case decisions:

- Raw truth SHA: `db4872615247e856d416e76653d0396a3aee1c430b5fdd8de33bc5e39afabfd1`.
- Canonical truth fingerprint: `1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276`.
- Private receipt: `3e8596e27f968df9ed6ca3a74d9592d53409da1f1bfa624852077c63ed0da62d`.
- Case-level truth opened by executor: **NO**. Human decisions and construction intent were not decoded.

## B — Authorization / connectivity

- Paid execution approved: YES; hard tracked-spend cap: **USD 4.50**.
- Provider/model/processing: **openai / gpt-6-luna / Standard**. All recorded responses report the expected model and default service tier. The default tier uses Standard pricing/performance per the [OpenAI Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create).
- Connectivity calls: **0**; skipped because the frozen protocol does not require a probe.
- Credential available: YES; printed/logged/hashed/copied/persisted: **NO**.

## C — Execution

| Item | Count |
|---|---:|
| Expected logical requests | 300 |
| Attempted logical requests, including unresolved intent | 108 |
| Recorded terminal logical requests | 107 |
| Valid accepted assessments | 106 |
| LOCAL accepted | 36 |
| GRAPH accepted | 34 |
| EXPANDED accepted | 36 |
| Terminal technical failures | 0 |
| Terminal protocol/schema failures | 1 |
| Unresolved pending outcomes | 1 |
| Detected duplicate executions | 0 |
| Duplicate accepted assessments | 0 |
| Unattempted requests | 192 |
| Assessments still missing for the required 300 | 194 |

The terminal protocol failure returned a mismatched request_id. It was rejected without correction, reassignment or retry. The subsequent pending request has no captured raw response or completed attempt event. Whether the provider processed it is unknown. The original exception detail was not persisted by the runtime masking path; no timeout, connection failure or provider error is inferred. The pending intent remains unchanged and automatic resumption is blocked.

107 provider responses are confirmed; one additional invocation has an unresolved transmission/processing outcome. The 108 count denotes attempted invocations, not 108 confirmed completed provider responses.

## D — Response distribution

Accepted assessments only; these counts measure model responses, not correctness.

| Strategy | SUPPORTED | NOT_SUPPORTED | INSUFFICIENT_CONTEXT | NOT_APPLICABLE |
|---|---:|---:|---:|---:|
| EXPANDED_BASELINE | 20 | 16 | 0 | 0 |
| GRAPH_GUIDED | 20 | 14 | 0 | 0 |
| LOCAL_ONLY | 19 | 15 | 2 | 0 |

## E — Retries

First-attempt successes = 106; one-retry successes = 0; two-retry successes = 0; total retry attempts = 0; maximum retries = 0; retry policy violations = 0. Accepted INSUFFICIENT_CONTEXT assessments were preserved. Neither the invalid binding nor the unresolved attempt was repeated.

## F — Provider usage

Measured values below cover only the 107 recorded responses. Pending usage and latency are unknown. GRAPH has 35 recorded responses plus one unresolved invocation.

| Strategy | Recorded calls | Input | Output | Total | Mean input | Mean output | Latency total / mean / median, s | Estimated USD |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| EXPANDED_BASELINE | 36 | 159034 | 12181 | 171215 | 4417.61 | 338.36 | 162.539 / 4.515 / 3.919 | 0.0219939 |
| GRAPH_GUIDED | 35 | 67330 | 13082 | 80412 | 1923.71 | 373.77 | 176.748 / 5.050 / 4.380 | 0.0132740 |
| LOCAL_ONLY | 36 | 33608 | 11116 | 44724 | 933.56 | 308.78 | 162.680 / 4.519 / 3.660 | 0.0089188 |

**Known usage:** input 259,972; output 36,379; total 296,351 tokens. Full-run usage = **null** because the pending call is unknown. Connectivity usage = 0/0/0; retry usage = 0/0/0. Raw provider usage, including cache/reasoning detail fields, remains in the private attempts.

## G — Spend

| Item | USD |
|---|---:|
| Known-usage scientific estimate | 0.0441867 |
| Connectivity estimate | 0 |
| Retry estimate | 0 |
| Combined known-usage estimate | 0.0441867 |
| Unresolved configured reservation | 0.0042768 |
| Conservative tracked exposure including pending | 0.0484635 |
| Full scientific usage estimate | null |
| Actual invoice cost | null |
| Hard cap | 4.50 |

Cap exceeded: **NO**. The run stopped for an unresolved outcome, not spend. Estimates use the separate versioned assumption `gpt-6-luna-standard-user-assumption-2026-10-06-v1`, fingerprint `2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b`: short input/output $0.10/$0.50 per million; long input/output $0.20/$0.75, cutoff >272,000 input tokens for the whole call. No cached-input savings were assumed. This is not invoice evidence. Known long-context responses = 0; frozen requests remain below the short-context boundary.

Frozen planning estimates remain: expected $0.175724; conservative $0.6070626; primary maximum $1.28304; maximum with two retries $3.84912. No limit, strategy, prompt or model was increased.

## H — Operational comparison

Use the 35 cases with recorded usage for all three strategies, including any protocol-invalid response usage. This avoids comparing unequal 35/36 request totals.

| Strategy | Matched input tokens | Reduction vs EXPANDED |
|---|---:|---:|
| LOCAL_ONLY | 32695 | 78.8528% |
| GRAPH_GUIDED | 67330 | 56.4509% |
| EXPANDED_BASELINE | 154607 | — |

Recorded mean latencies: LOCAL 4.519 s, GRAPH 5.050 s, EXPANDED 4.515 s. These partial operational statistics make no claim about accuracy or quality preservation.

## I — AI freeze

- All 300 accepted before freeze: **NO**.
- AI_ASSESSMENT_LEDGER_FROZEN: **NO**.
- Raw ledger freeze / normalized dataset / usage freeze / AI freeze receipt fingerprints: **null**.
- Freeze-before-truth-join: not applicable; no freeze and no truth join.
- Raw responses recorded: 107, byte integrity PASS.

The following hashes are diagnostic snapshots of an **unfrozen incomplete ledger**, not a complete scientific dataset:

- unfrozen_ledger_snapshot_fingerprint: `3e819e9438d53a9b3880aa24693852cce51fab8123653b6463ce55013ddef069`.
- recorded_raw_snapshot_fingerprint: `a5149dd05a76dde0784f87e9c4e30e60aa502a8f0fbd7281a42d62b2d41ca107`.
- recorded_attempt_usage_snapshot_fingerprint: `2dcdbca2f13d5a391bc73a3d38666cee95fe2005afbf540b65f15b68c35eed23`.
- execution_lineage_fingerprint: `77e3c8074eb1003355983cbd8ffbc29b4c9051ef1c522433bc4a0f9ccc09a6c8`.
- fingerprint: `f951172fd27562e25b5be5b66ea34bc3b88c65a2f49896cc543c8bdd5eaf25ec`.

Runtime source hashes captured during execution are preserved in the source-free verification JSON. Subsequent public infrastructure changes add safe exception-type diagnostics for future unresolved attempts and remove ordinary-prose matches from the generic credential-prefix detector. They do not reconstruct this missing response, alter its pending intent or authorize a retry.

## J — Blindness / leakage

Truth / reviewer / construction / V2-Hybrid provenance leakage findings: **0 / 0 / 0 / 0**. Executor case-level human access: NO. Construction intent decoded: NO. Scoped path/open guards deny all external experiment data; each frozen payload is also audited for prohibited metadata. Real request/response artifacts remain private and ignored.

## K — Evaluation boundary

Human truth joined: NO. TP/FP/TN/FN, Precision, Recall, F1, specificity, FPR/FNR and effectiveness/coverage against truth calculated: NO. P017 started: NO. Structural V2, Static/Graph experiments, Hybrid, ablation, Security and UI work: NO. Full-suite tests use synthetic fixtures; no provider calls were issued as tests.

## L — Quality

- Targeted P016 live/execution/offline suite: **78 passed**, 26.70 s.
- Full make check: **1656 passed**, 165.26 s; coverage **92%**. Ruff and format PASS (431 files); strict mypy PASS (220 source files).
- Offline manifest and opaque P015 final-truth verification: PASS.
- Incomplete ledger snapshot and all 106 accepted bindings: PASS.
- Complete live freeze verification: unavailable; complete freeze was deliberately refused.
- Privacy/secret audit: PASS for private run artifacts and public-safe outputs.
- Git diff check: PASS.

Commands executed:

```text
.venv/bin/python -m pytest -q tests/intelligence/test_semantic_positive_live.py tests/intelligence/test_semantic_positive_execution.py tests/intelligence/test_semantic_positive_offline.py
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy src
make check
.venv/bin/python scripts/prompt016_live.py --verify
git diff --check
```

The verification command performs opaque human lineage hashing in a separate process, frozen request/context verification and private ledger snapshot verification. It does not load credentials, call the provider or invoke the evaluator. The ordinary offline coordinator was not used because it parses human decisions.

## M — Git closure

Only public-safe implementation, synthetic tests, source-free incomplete-run audit and this report are eligible for the closure commit. Private payloads, raw responses, accepted assessments, pending intent and credential file remain ignored. Commit SHA, normal origin/main push result and final working-tree state are supplied in the final closure response.

**STOP: P016_LIVE_INCOMPLETE_PENDING_TRANSPORT. No complete dataset freeze; no automatic provider resumption; no truth join; no P017.**
