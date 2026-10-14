# Thesis core reproducibility

## Level 1 — safe verification

From the repository root, with the locked project environment and authorized local frozen evidence:

```sh
.venv/bin/python scripts/prompt026_thesis_closure.py verify
.venv/bin/python -m pytest tests/benchmark/test_thesis_closure.py -q
```

No provider, secrets, credential configuration or paid calls are required. The command checks Git
ancestry, historical source/test/artifact bindings, original P025 public file hashes, private input/
prediction/truth/join seals, closed writer receipt, original model hashes, original human/structural
truth, final metric/RQ/hypothesis fingerprints, claim/rule/capability registries, numeric documents
and closure manifest. Missing private evidence must fail full verification; it is not silently
skipped.
A public-only checkout can inspect aggregate registries but cannot claim full private freeze
verification.

P025 replay status: read-only byte/canonical-seal comparison PASS. No evaluation, model fit,
prediction generation or truth rewrite occurs. A second registry construction must equal the first.
Quality checks use synthetic offline fixtures and fake transports, never provider credentials.

## Level 2 — full scientific reproduction

P015 independent development human truth → P019 component baselines → P020 prospective cohort, structural oracle and project splits → P021 independent final human truth → P022 blind development LLM → P023 TRAIN-only fitting and one VALIDATION selection → P024 blind final LLM acquisition → P025 truth-blind closed prediction writer → first final truth open/join → frozen evaluation/ablation/RQ/hypothesis → P026 read-only closure. Two final reviewer slots agreed on 100/100 units (kappa=1), 50 positive / 50 negative; this is agreement on a specially constructed prospective benchmark. Construction intent is not authoritative truth.

Requirements: pinned Git revisions, locked Python/parser runtime, authorized original private source
snapshots and immutable accepted evidence, independent truth, TRAIN/VALIDATION project split,
frozen selected models, receipts and acquisition ledger. Check each dependency before deterministic
downstream replay in a separate output location; compare canonical hashes without replacing
originals.
P026 does not run that replay or invoke historical mutating stage CLIs.

Historical paid LLM responses are frozen scientific evidence. REPRODUCTION recomputes deterministic
downstream results from this evidence and frozen models. A literal fresh provider rerun is
REPLICATION:
new stochastic/provider outputs and a new experiment needing separate authorization, never an
identical
reproduction. No fresh paid replication is required for core closure.

## Evidence registry

`reproducibility-registry.json` maps stages, commits, public artifacts/fingerprints, private
artifact
classes, input/output dependencies, truth/provider access and safe verification invariants.
Early P001–P004 history is coalesced in the first IAM baseline commit; no separate earlier
commits exist.
Every required P019–P025 anchor and runtime amendment is in `lineage-registry.json`.

## Limits

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

CORE_THESIS_COMPLETE requires implemented methods/languages/rules, independent frozen truth, pre-truth model/prediction freeze, final N=300 metrics, seven ablations, honest RQ synthesis/hypothesis and reproducibility/traceability. Partial RQ2/RQ6 do not justify stronger answers and do not require further experiments to support the scoped primary hypothesis. Security, UI, deployment, full thesis prose and defense slides are outside this scientific closure. Final acceptance is gated by closure-manifest.json and its quality receipt; generated registries alone do not declare completion.
