# Graph structural calibration machinery — PROMPT 011.1

The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

Readiness: CALIBRATION_MACHINERY_READY; STRUCTURAL_V2_AWAITING_FRESH_HOLDOUT;
FULL_HYBRID_NOT_READY. This GRAPH STRUCTURAL META-CLASSIFIER uses raw graph measurements and
analysis quality. Static precedence is not a Static predictor. It is neither a normative violation
classifier nor a validated full Static+Graph+LLM experiment. No live AI, security or frontend changes.

## Versioned features and cohort

V1 remains immutable diagnostic/leakage-sensitive history, superseded for research. V2 has the
separate `structural-feature-spec-v2` whitelist: graph.Ca, graph.Ce, graph.coupling, graph.I, graph.scc_size, graph.betweenness, graph.pagerank, graph.cyclic, graph.source.Ca, graph.source.Ce, graph.source.I, graph.target.Ca, graph.target.Ce, graph.target.I, quality.unresolved.
`selection.candidate_present` and its missing indicator are removed. Candidate/rule booleans,
configured thresholds, specific rule IDs, labels, annotation/rationale, split, all identities,
names/paths and Findings never enter v2. [Formal audit](FEATURE_LEAKAGE_AUDIT.md) covers every
predictive input/output and excluded cohort field, including raw IAM measurement feasibility.

Dataset 1.1.0 and committed materialization remain unchanged. Exactly one eligible complete STRUCTURAL
variant per STRUCTURAL_SIGNAL_RETRIEVAL case: TRAIN 42 / 4 families / 20 positive / 22 negative;
VALIDATION 4 / 1 family / 2 positive / 2 negative. Other variants and AI are excluded.
TEST NOT ACCESSED for v2. Dataset-1.1 TEST was consumed by v1 and is not fresh after this review.
CLI, file adapter and typed workflows block v2 TEST before opening/materialization. No v2 TEST metric
exists. Fresh holdout must use new independent families unused in v1, review, v2 design or validation;
resplitting or coefficient-informed synthetic cases cannot restore independence.

## Preprocessing and runtime

TRAIN-only median imputation, population mean/std, all-missing/constant dropping and explicit 0/1
missing indicators are frozen. Unweighted preprocessing precedes identically family-weighted fitting:
N/(F*n_family), total N and total N/F per family. Native ridge/logistic fit TRAIN only, select VALIDATION
macro-family F1 only, retain all candidates, then freeze portable coefficients without research imports.
V2 has 15 inputs and 26 output columns. quality.unresolved is
constant and dropped; constant SCC/cyclic value parts are dropped, varying missingness retained.
Missingness can still proxy subject scope; correlations and threshold-derived truth limit interpretation.

Runtime requires an explicit `--structural-policy`; default Hybrid remains DeterministicPrecedencePolicy.
V2 loads only as an AWAITING_FRESH_HOLDOUT research candidate. Exact version/schema/order, preprocessor,
coefficient and artifact fingerprints validate. Static proofs bypass scoring and preserve Findings/severity.
Unsupported semantic tasks and AI evidence are rejected. ARCH101–105 outputs remain structural signal
states with separate model_score/artifact fingerprint; confidence=null and no normative Finding.
Logistic sigmoid is not established probability calibration; ridge scores are unrestricted.

## TRAIN/VALIDATION-only commands

Use already exported TRAIN/VALIDATION files in a directory containing no TEST. Do not rerun the
all-split export command for v2: it materializes consumed TEST unnecessarily.

```bash
uv run archguard calibration train --train /tmp/cohort/train.jsonl \
  --manifest experiments/calibration/structural-v2.json --output /tmp/training.json
uv run archguard calibration select --training /tmp/training.json \
  --validation /tmp/cohort/validation.jsonl --output /tmp/selection.json
uv run archguard calibration freeze --selection /tmp/selection.json --output /tmp/policy.json
uv run archguard calibration baseline --train /tmp/cohort/train.jsonl \
  --validation /tmp/cohort/validation.jsonl --manifest experiments/calibration/structural-v2.json \
  --output /tmp/baseline.json
uv run archguard hybrid analyze path/to/repository --without-ai \
  --structural-policy /tmp/policy.json
```

Outputs cannot overwrite existing files. No v2 evaluate command is permitted under this protocol.
[Selection protocol](MODEL_SELECTION_PROTOCOL.md), [descriptive results](STRUCTURAL_META_CLASSIFIER.md)
and [verification](../verification/PROMPT_011_1.md) retain limitations and lineage.
