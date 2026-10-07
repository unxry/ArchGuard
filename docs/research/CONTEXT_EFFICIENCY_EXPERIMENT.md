# Frozen context-efficiency protocol — PROMPT 014

The same 40 independently annotated cases receive three frozen contexts:
LOCAL_ONLY, GRAPH_GUIDED and EXPANDED_BASELINE. GRAPH_GUIDED uses one-hop BOTH
traversal. All use the frozen budgets: 20 nodes, 10 files, 20 fragments,
4,000 characters per fragment, 20,000 total context characters, 120 lines per
fragment and two lines of surrounding context. Output is capped at 2,000 tokens.
Frozen source material contains no human labels, reviewer rationale, adjudication
or detector/Structural V2/Hybrid predictions.

This is a research-only resolved-topology context path. Six of eight IAMs have
global INVALID diagnostics; 30 cases and 90 requests retain these diagnostics.
They are neither repaired after seeing answers nor excluded from the full cohort.
Ten cases/30 requests form VALID_IAM. Fixed VALID_IAM and PARTIAL_INVALID_IAM
strata describe sensitivity to context validity; they do not redefine truth.

The request/context inventory records each request fingerprint, context and source
characters, selected topology, truncation diagnostics and offline input estimates.
Estimated input tokens were a UTF-8 proxy because no exact model tokenizer was
locally available. Actual provider input/output counts supersede that proxy for
execution accounting. Context characters and source characters have distinct
definitions and are reported separately.

Compare LOCAL_ONLY → GRAPH_GUIDED, GRAPH_GUIDED → EXPANDED_BASELINE and LOCAL_ONLY
→ EXPANDED_BASELINE across the same case identifiers. Report all four judgment
classes, transitions, agreement, explicit missing pairs and complete successful
triples. Quality comparisons use successful matched observations; full-cohort
quality and missing outcomes remain visible. Operational totals include all
attempts, including retries and terminal failures.

Report input/output/total tokens, context/source characters, mean/median/p95/max
latency, successful logical latency and estimated actual cost by strategy, plus
Java/TypeScript breakdowns. For GRAPH_GUIDED versus EXPANDED_BASELINE, reduction is
`1 - GRAPH_GUIDED / EXPANDED_BASELINE`; latency/cost deltas are GRAPH_GUIDED minus
EXPANDED_BASELINE. Inspect negative correctness and OOS recognition alongside
resource savings; fewer tokens alone do not establish better detection.

Serial execution and rotating deterministic strategy order reduce concurrency and
ordering confounds. Provider load, caching, transport and model nondeterminism
still limit causal latency/quality interpretation. Small per-repository and
per-rule strata support descriptive counts only. No significance, equivalence or
project-level superiority is inferred.
