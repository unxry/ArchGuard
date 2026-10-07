# Prospective semantic holdout — PROMPT 015

`semantic-positive-holdout-v1` is a new controlled dataset: ARCH201–205 each have
ten matched pairs, five Java and five TypeScript. The 100 cases comprise 50
intended mutation candidates and 50 matched controls. Construction intent is
private engineering metadata; **no human ground truth exists yet**.

Ten newly authored projects cover pricing, eligibility, inventory, settlement
and allocation in both languages. Each pair has independent isolated source
instances, with matching project, HTTP fixture framework, interface, domain
contract and surrounding code. The five deterministic v1 operators materially
change responsibility, controller business decisions, direct filesystem usage,
policy placement or ownership of multiple concerns. ARCH201 concerns role
contradiction; ARCH205 requires material ownership of multiple concerns. Rule
overlap is possible and is judged independently for the target question.

This uses original local source, with no copied third-party source, OSS repository
overlap or P013 case reuse. It does not change P013/P014, P011 or any old benchmark.
Construction exhaustively instantiates the fixed recipe matrix. It never reads
AI judgments, detector predictions, Hybrid/V2 predictions or new human outcomes.
Old lineage is recorded through Git tree identities; P013 IDs are an exclusion
list only. The P014 close commit and unsuccessful normal push are recorded in
the frozen lineage.

The public corpus, sample, protocol, reviewer guidance, future analysis plan,
technical validation and context diagnostics are source-free. Private original
source, the blinding seed, mutation receipts, pair/intent provenance and review
bundles stay under ignored `experiments/semantic-holdout/private/`. Both inventories
are independently frozen with SHA-256 file hashes and canonical fingerprints.
The private provenance binds operator IDs/version, preconditions, procedures,
expected construction effects, before/after hashes and immutable validation.
Expected construction effects never become human labels.

Pair-independent case/review/project aliases use HMAC with a private frozen
random seed. Reviewer A/B bundles contain the same 100 source packets in different
deterministic orders, without pair IDs, operator IDs, construction classes, model
results or human answer fields. Reviewers receive only their own bundle and rubric,
not the public generator/catalog or private construction store. They may infer
concerns from source; explicit mutation provenance is withheld.

`future_context_input` accepts only the sealed, closed-schema `BlindedPacket`.
Extra provenance/intent/answer fields are rejected. It has no filesystem or
provenance-store access. This is a source-only capability boundary for a later
AI builder, not authorization to execute one.

Technical VALID requires successful source intake and parse, valid and complete
IAM/graph, resolved source spans and target, extractable dependency neighborhood,
equal dependency replay and passing available native checks. PARTIAL indicates a
remaining engineering condition; INVALID indicates invalid parse. Native tool
availability is recorded separately. Resolver warnings, external stdlib references
and unresolved references remain visible and are not represented as fully resolved.
Technical validation establishes integrity only, never semantic truth.

All 100 cases have actual parse/IAM/graph replay receipts. For TypeScript, Node's
type stripping runs three HTTP integration examples per case. This is runtime
testing, not compilation or type-checking. JDK and the TypeScript compiler were
unavailable: Java compilation and TypeScript type-check are NOT RUN. No dependency
was installed to conceal this limitation.

Offline diagnostics report source characters/spans, one-hop neighborhood size,
IAM validity/completeness, missing evidence and expected source truncation for
LOCAL_ONLY, GRAPH_GUIDED and EXPANDED_BASELINE. Diagnostic source budgets are
20 nodes, ten files, 4,000 characters per fragment and 20,000 total source
characters. These are engineering diagnostics; future actual prompt/token
preflight needs its own authorization. Cases are not adjusted for predicted
model responses.

Two distinct real humans must independently review every case using POSITIVE,
NEGATIVE, UNCERTAIN or OUT_OF_SCOPE, with their own rationale and evidence IDs.
A third distinct real human adjudicates conflicts only and is not another paired
reviewer. No identities, answers or adjudications are fabricated. Review does not
start automatically. After freeze, unfavorable labels or model outcomes cannot
justify case replacement or rebalancing.

The future analysis plan is frozen before outcomes. Binary analysis uses final
human POSITIVE/NEGATIVE; UNCERTAIN and OOS stay separately reported. Definitive
Precision/Recall/F1/Specificity/FPR/FNR are reported together with full-population
coverage, abstention, scope errors, failures and effective positive/negative
correctness. Zero denominators are null. Missing pairs are explicit. Per-rule,
language, IAM strata, pair and context/resource analyses are secondary. No metric
is computed in P015.

P013/P014 remain the real OSS negative/OOS external-validity/context-efficiency
cohort. This controlled construction is not a natural prevalence estimate and
must not be pooled with it. Later positive sensitivity or model/Hybrid comparisons
require independent final human truth, separate authorization and honest reporting
of whatever class balance humans produce. Small template-derived clusters and
synthetic source constrain external validity.

Status: **WAITING_FOR_HUMAN_REVIEW**. Live AI = 0; Structural V2, Hybrid and Security
analysis = NOT RUN; PROMPT 016 = NOT STARTED.

Verify without reconstruction:

```bash
.venv/bin/python scripts/prompt015_holdout.py --verify
```

See [verification](../verification/PROMPT_015.md) and the
[public freeze](../../experiments/semantic-holdout/semantic-positive-holdout-v1/sample-freeze-v1.json).
