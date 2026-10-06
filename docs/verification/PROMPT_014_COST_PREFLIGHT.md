# PROMPT 014: offline cost preflight

Status: `COST_PREFLIGHT_COMPLETE; EXECUTION_NOT_AUTHORIZED`.

Model: `openai / gpt-6-luna`, Standard processing. Prepared all 120 contexts offline: **YES**. Live API calls: **0**. No API key was read or required. No assessment, execution ledger, semantic evaluation or structural V2 evaluation was produced.

Baseline HEAD: `17c1292a4d608d5aaf90964d2947fa04919f4e64`. All frozen P013 fingerprints, native review-freeze replay, final case links and freeze-manifest file hashes verified before and after preparation. P013 corpus/sample/catalog/review/ground-truth artifacts remain unchanged.

## Frozen artifacts

- Scientific protocol: `experiments/ai/semantic-context-v1/semantic-context-v1.json`.
- Source-free 120-request inventory: `experiments/ai/semantic-context-v1/context-manifest-v1.json`.
- Research response schema and system prompt: same scientific directory.
- Raw request contexts and provider payloads: `experiments/ai/private/semantic-context-v1/requests/`, ignored by Git.
- Pricing assumptions: `experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json`.
- Accounting and P013 verification: `experiments/preflight/semantic-context-v1/`.

Experiment fingerprint: `92c4c909e5953d9e0ba07f00126eae75bf8225b128d1eb989a0df02d4c722a04`. Context inventory fingerprint: `f9502ddecd8db147c419edd28f3227fb6174a0c8522f59c1b22eb38982e53afe`. Pricing fingerprint: `2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b`.

## Protocol

40 frozen cases × LOCAL_ONLY, GRAPH_GUIDED, EXPANDED_BASELINE = 120 logical requests. Cases ranked by SHA256 of canonical case ID, rotating strategy order per case, serial concurrency 1. Timeout 90 seconds. At most two additional attempts for timeout, connection, rate-limit or transient errors; schema-invalid responses are terminal and never retried for semantic reasons. Maximum 360 attempts.

Each strategy uses the same budgets: hop 1, direction BOTH, 20 nodes, 10 files, 20 fragments, 4,000 characters per fragment, 20,000 model-visible context characters, 120 lines per fragment, 2 surrounding lines before/after. Identical relation filter and resolved dependency evidence policy. No discovery hypotheses, inferred role metrics or spec constraints. Only context selection varies. Input ceiling 32,768 tokens/call; maximum output 2,000 tokens/call.

Prompt `oss-semantic-context-014-v1`; schema `oss-semantic-assessment-014-v1`. Research-only four-way judgment supports NOT_APPLICABLE. Production response DTO and default invalid-IAM guard remain unchanged. No human labels, rationales, reviewer metadata or detector predictions enter requests. The separate lineage verifier reads human artifacts only to verify their identities; its output to the preflight is fingerprints.

## Token estimates and context sizes

No model tokenizer or tokenizer cache was installed locally. No dependency/model/tokenizer was downloaded. Input estimate is ceil(model-visible UTF-8 bytes / 3) + 128, including system instructions, canonical user task/context and response schema. Conservative local planning bound is UTF-8 bytes + 2,048 framing tokens. HTTP routing fields and double JSON escaping are excluded. These are proxies, not provider token counts or billed usage. Exact provider-compatible token counting must be checked before future execution.

| Strategy | Requests | Context chars | Source chars | Estimated input | Mean | Median | Maximum | Conservative input |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| LOCAL_ONLY | 40 | 64182 | 37916 | 58510 | 1462.75 | 1279.5 | 2549 | 242049 |
| GRAPH_GUIDED | 40 | 296625 | 150447 | 135992 | 3399.8 | 2800.0 | 7490 | 474492 |
| EXPANDED_BASELINE | 40 | 653812 | 391199 | 255067 | 6376.675 | 6727.5 | 7593 | 831719 |

Total estimated input: **449,569**. Total conservative input: **1,548,260**. Largest individual conservative input: **24,442**. Largest model-visible context: **19,963 characters**.

Expected output: **600/call**, **72,000** total, a planning assumption rather than observed output. Maximum configured output: **2,000/call**, **240,000** primary tokens, **720,000** including every allowed retry. Reasoning tokens, if billed as output, must fit within this output allowance.

## Versioned cost assumption

Prices and model limits were supplied by the user, retained as a dated assumption, and were not fetched from OpenAI or verified against an account. Standard short-context: input $0.10/M and output $0.50/M. Input greater than 272,000 switches the entire individual request to long-context: input $0.20/M and output $0.75/M. Cached-read/write rates are retained separately in pricing metadata. No cached-input savings are assumed and no cache-write request is configured.

| Scenario | Input basis | Output basis | USD |
|---|---|---|---:|
| A. Expected, primary calls | 449,569 estimated | 72,000 expected | 0.0809569 |
| B. Conservative, primary calls | 1,548,260 byte-based upper | 240,000 configured | 0.2748260 |
| C. Maximum primary exposure | 3,932,160 configured | 240,000 configured | 0.5132160 |
| Additional maximum retry exposure | 7,864,320 configured | 480,000 configured | 1.0264320 |
| Absolute configured maximum, including retries | 11,796,480 configured | 720,000 configured | 1.5396480 |

Every request is priced individually. Long-context requests: **0**; approaching 90% of the 1,050,000-token context window: **0**. Largest conservative input + configured output is 26,442 tokens. Configured output 2,000 is below the model maximum 128,000. All configured input ceilings also remain below the 272,000 short-context cutoff.

**$1** covers expected, conservative and maximum primary costs, but **does not cover every configured retry**. **$2 and $5** cover absolute configured maximum including all retries under this pricing/token assumption. These are estimated API costs, not actual invoices or account credit requirements.

## Context limitations

Six cached IAMs have a global INVALID_IAM parser status. The research-only opt-in preserves this invalid state, admits only existing raw resolved dependency/source data, and emits CONTEXT_INVALID_IAM_PARTIAL_DATA for all 90 affected requests. It rejects other graph errors or mismatched IAM/project fingerprints. The diagnostic is visible to the model; it is not used to mark the IAM valid.

Context truncation occurs in 3 LOCAL_ONLY, 19 GRAPH_GUIDED and 40 EXPANDED_BASELINE requests. All targets retain source evidence. Larger context is bounded and does not establish completeness or correctness of future assessments. Truncation status is included in the untrusted context.

## Reproduction

Run from the repository root with the existing pinned source cache and raw graph inputs:

```sh
.venv/bin/python scripts/prompt014_cost_preflight.py \
  --cache /Users/bendasroman/.cache/archguard/oss \
  --graph-inputs /Users/bendasroman/.cache/archguard/oss-analysis/oss-corpus-v1
```

All output paths are immutable; an existing output is rejected. To repeat, pass new --private-output, --output, --accounting-output and --pricing-output paths. The script blocks socket creation, provider transport/factory and credential settings construction. It verifies frozen P013 lineage before and after building. HEAD must descend from the pinned P013 baseline; the frozen artifact fingerprints remain mandatory after a pre-live commit.

Execution remains pending explicit approval. No full PROMPT 014 completion or model-effectiveness result is claimed.

## Validation

- `make check`: Ruff, formatting and mypy green; **1181 passed**, coverage **93%**.
- Architecture dependency boundaries and source-free OSS annotation isolation preserved.
- Repeat offline preparation: all 120 private request payloads, scientific artifacts and accounting byte-identical.
- Stored request fingerprints, pricing/protocol/context links and absence of human-answer fields verified.
- At offline preflight completion, `git diff --check` was clean and HEAD was `17c1292a4d608d5aaf90964d2947fa04919f4e64`; P013 artifacts unchanged.
- No live execution occurred during preflight. The subsequent pre-live review and freeze are documented in `PROMPT_014_PRE_LIVE_FREEZE.md`.
