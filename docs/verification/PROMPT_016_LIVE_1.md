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
