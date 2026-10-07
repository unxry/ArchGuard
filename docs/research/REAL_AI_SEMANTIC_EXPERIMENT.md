# Real AI semantic experiment — PROMPT 014

P013 human truth was frozen before model execution: 40 cases, 32 NEGATIVE and
8 OUT_OF_SCOPE, with zero positives. This cohort supports descriptive negative
correctness, scope recognition and context-efficiency analysis. It cannot establish
violation sensitivity, positive-class F1, significance or overall superiority.

The approved pre-live commit is `dcacc6a8ea42231e4d0fb97dcf171caaaae02a56`.
The immutable experiment is `experiments/ai/semantic-context-v1/`: OpenAI,
`gpt-6-luna`, Standard processing, prompt/schema v1, 40 cases × LOCAL_ONLY,
GRAPH_GUIDED and EXPANDED_BASELINE. The 120 prebuilt request payloads are ignored
private artifacts. Credential rotation changes operational configuration only.

The blind executor `scripts/prompt014_execute.py` reads only these frozen requests,
the protocol, context inventory, pricing assumption and connectivity receipt.
It has no human-truth, review, detector or evaluation dependency. It uses serial,
deterministic manifest order, 90-second timeout, 2,000 output-token cap and at most
two technical retries. It never retries abstentions, inconvenient judgments,
invalid schema/evidence or refusals. Completed assessments are never repeated.

Every attempt gets a durable STARTED/RESULT ledger entry. An interrupted attempt
without a result stops resume because its provider outcome is ambiguous. Terminal
results can be recovered from completed ledger entries without provider calls.
Authentication, billing, model and region errors stop execution immediately.

One source-free connectivity request is accounted separately from the 120 logical
assessments. Real token usage, safe provider identifiers, latency and retry reasons
are retained. Cost is estimated from actual usage using the separate versioned
user-provided pricing assumption; it is not a provider invoice. Unknown usage is
reserved at the configured maximum. Before another call, estimated cumulative
exposure plus that call's maximum must remain below $0.95, protecting the user's
$1 stop boundary. No cache savings are assumed.

All terminal results and accepted judgments are independently frozen in
`experiments/ai/semantic-context-live-v1/real-ai-assessments-v1.json`. Only then may
`scripts/prompt014_evaluate.py` verify that freeze and read P013 truth. The truth
join and evaluation have independent fingerprints; assessment bytes remain
unchanged. Rerunning evaluation is offline and must match existing artifacts.

Raw model text stays in ignored `experiments/ai/private/semantic-context-live-v1/`.
Public artifacts contain validated abstract rationales and opaque evidence refs,
not source payloads, credentials or headers. The secret env file is never an
artifact or fingerprint input. Provider secret echo is blocked before persistence.

No Structural V2, Hybrid or Security evaluation is part of this experiment.
Full Hybrid and primary semantic effectiveness remain NOT_READY. PROMPT 015
requires a separate instruction. See [verification](../verification/PROMPT_014.md),
[metrics](SEMANTIC_EVALUATION_METRICS.md) and
[context protocol](CONTEXT_EFFICIENCY_EXPERIMENT.md).
