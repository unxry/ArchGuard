# PROMPT 008 verification

Date: 2026-10-05. Stage: Graph-Guided Context & AI Architecture Analysis Foundation.
Code remains an uncommitted reviewable diff; next stage has not started.

## Git and delivery

PROMPT 007 committed as `6f06414a33371017b883bfb1c4143e7d1de37429`
(`feat: add architecture discovery and structural classification`). `HEAD` / `origin/main` agree.
Origin: [unxry/ArchGuard](https://github.com/unxry/ArchGuard).
Initial HTTPS push was rejected for missing `workflow` scope; existing SSH host verification
was unavailable. After the user updated GitHub auth, safe existing keyring auth included workflow
scope and normal `main` push succeeded. No force push, credential stored in repo/config/output,
global identity change or rewritten history. Credential helper was command-local.

Changes: intelligence contracts/context/selection/fragments/prompts/validation/analyzer;
application coordinator; CLI and typed profiles; real OpenAI infrastructure adapter;
offline test helpers/regressions; README/catalog/architecture/research/ADR/verification docs.
Additional narrowly scoped extraction/parsing fix is described below.

## Context comparison: actual measurements

Fixture `tests/fixtures/discovery/java-layered`, explicit `UserController`, default namespace,
default context budgets, default Discovery. These are local context construction measurements;
there were zero LLM calls. Chars = canonical untrusted JSON Unicode chars, not tokens or bytes.

| Strategy | Hops | Nodes | Files | Fragments | Context chars | Source chars | Truncated |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| LOCAL_ONLY | n/a | 1 | 1 | 1 | 1793 | 186 | false |
| GRAPH_GUIDED | 1 | 2 | 2 | 2 | 4569 | 375 | false |
| GRAPH_GUIDED | 2 | 3 | 3 | 3 | 7265 | 493 | false |
| EXPANDED_BASELINE | n/a | 6 | 6 | 6 | 12968 | 789 | false |

Fingerprints, respectively:

```text
1ec43bfb25f725cc6b1b5dba80a45d2fc91313b53995b7fb9a58b3b33d2ac294
dae87f1375807d81e7125783a067230ded9256c36d61000b395a64ed95c53a86
2a78e0965fbf8970e92e5094bd9ceef332b06059f228ceb4ef91cc3d9936d809
c0b47e1de90aa2d986c5d16d5f71baf5cd3889b782a8aa01a8aa5518614049d3
```

Extra manual dry runs:

- `discovery/conflict`: ambiguous PaymentController selects ARCH204 and ARCH202 questions;
  each pack: 1 node / 1 file / 1 fragment / 1576 chars / no truncation;
  fingerprint `88dc014b5e830398c68f0860c6663d1a773a5093705a89f6fc882e08377fa3c9`.
- `graph/hub` with `examples/ai/graph-candidates.json`: two ARCH205 target questions;
  packs 5/5/5/10250 and 6/6/6/13401 (nodes/files/fragments/chars), no truncation.
  Fingerprints `42d4bcb25e6b21038b719ac82100ad43c80dbb0eb0a053904156f43c350ff70a`
  and `dca56e84f26b0f3f66472529c2e7d1f26d582b32f28092a14c9ae06c4f060136`.

One fixture comparison does not prove efficiency or quality. Provider tokens, cost and LLM latency
for these dry runs are unavailable. No token estimate is presented as provider measurement.

## Offline semantic/provider verification

Manual DI run on the Java fixture: UserController, OrderService, PaymentRepository;
test-only ScriptedLLMProvider; COMPLETE; 3 calls;
one SUPPORTED, one NOT_SUPPORTED, one INSUFFICIENT_CONTEXT.
All input/output/total token counts and cost are null. This is **scripted/offline pipeline
verification**, not a real LLM quality result. All five ARCH201–205 contracts and all three
decisions also have parameterized offline tests.

Real adapter implemented: **yes, OpenAI Responses API**, stdlib transport, no vendor SDK dependency.
Actual wire payload/response parsing, refusal/incomplete/auth/rate/transient/timeout/size boundaries
verified with stubbed transport. Positive CLI opt-in also reaches the real adapter through a stub.
Production fake provider absent. Optional live smoke test: **not executed**; no live opt-in given.
Absence of that test is not a failure and provider/model suitability is not claimed live-verified.

Privacy: default remote denied; explicit `--allow-remote-ai` required. Dry-run ignores configured keys
and makes zero calls. Config alone cannot authorize CLI upload. Default artifacts/logs exclude source
text fields and credentials. Source pack is transient; `--show-source` is explicit local debugging.
Optional redactor has version identity; failed redaction or changed line alignment drops fragments
with sanitized diagnostics. Default secret detection/redaction is not implemented.

Prompt/schema versions and strict required/nullable fields verified. Unknown/duplicate refs,
unknown subjects, wrong requested rule, static/SEC codes, extra code fields, code delimiters,
free-text invented paths/lines, malformed/oversized responses rejected. Prompt injection comment
appears only in actual untrusted request data, never system/task instructions. External model
resistance and free-text semantic correctness remain unmeasured.

Logical candidate IDs ignore API request/run identity and stochastic assessment prose/decision.
Usage is provider-reported or null; exact preflight token caps fail closed if counting unavailable.
Failed attempts consume call/token reservation. Middle provider failure preserves other successes;
budgets skip remaining targets with diagnostics; truncation/failures/skips produce PARTIAL/INCOMPLETE.
IAM/Graph/Discovery each run once for multiple targets, verified with spies.

## Determinism and Linux

Repeated canonical context manifest A/B bytes identical. Unselected physical source comment change
does not change selected fingerprint; selected source change does. Canonical dry-run export:

```bash
archguard ai analyze tests/fixtures/discovery/java-layered \
  --target UserController --hops 2 --dry-run --json
```

macOS and non-root Docker/Linux `archguard:prompt008`: **8411 bytes**, byte-identical via full `cmp`.
SHA-256 of both complete exports:
`789a1f7a5e07a352f489df3a68c50f17b5c39b0414b1e048e0a3a45de6723ad2`.
Docker ran with `--network none --read-only`, read-only fixture mount and tmpfs `/tmp`.
Context fingerprint inside: `2a78e0965fbf8970e92e5094bd9ceef332b06059f228ceb4ef91cc3d9936d809`.
This verifies targets/order/ranges/fragment hashes/budgets/schema metadata across platforms;
it does not assert deterministic live LLM output.

## Tree-sitter coordinate regression

The new real 20000-line method-window test initially exposed heap corruption in pinned
py-tree-sitter 0.26.0 Point attribute access. The
[upstream binding source](https://github.com/tree-sitter/py-tree-sitter/blob/v0.26.0/tree_sitter/binding/point.c)
shows row/column getters returning borrowed tuple items. Local reproduction returned a corrupted
end line and caused a Python segmentation fault; tuple unpacking remained correct for repeated access.
`extraction/common.location` and syntax diagnostics now use tuple access, retaining coordinate
semantics and existing dependency pins. Tests cover source parsing/extraction with line and column
above 256, syntax error coordinates, and a real large-file method context using bounded streaming.
The large-file test forbids whole-file context `.read()` and stops before the trailing half of the file.

## Quality gate

`uv sync --locked --extra dev`: passed; dependency/lockfile unchanged.
`make check`: **842 passed, 0 failed, 0 skipped**, 10.57 s; **94%** overall branch coverage.
All original **704** tests retained; **138** new offline AI/context/coordinate regressions.
Ruff passed; **253** Python files formatted; strict mypy passed for **152** source files;
`git diff --check` passed. Docker build passed.

Critical coverage: context **95%**, selection **97%**, fragment extraction **98%**, models **98%**,
semantic analyzer **98%**, prompt/validation **100%**, provider ports **100%**;
application coordinator **100%**. No previous test was removed or weakened.

## Limits and next stage

Confirmed: provider abstraction, three strategies, deterministic bounded context, strict reference
validation, ARCH201–205 uncalibrated candidates, privacy opt-in, offline partial-failure coverage,
source-free CLI export, documented scientific boundaries.
No Hybrid fusion/arbitrary weights, calibration, LLM-quality benchmark, Security, health score,
DB response persistence, analysis jobs/API or frontend implementation.
Structural resolution/projection limitations propagate; source windows can omit necessary evidence;
semantic truth and injection resistance are unmeasured. OpenAI adapter has no tokenizer/billed cost,
no retry/streaming and no live smoke verification. Custom synchronous provider must honor its timeout.
After review: possible PROMPT 008.1 boundary refinement, then PROMPT 009 Hybrid foundation;
neither starts automatically.
