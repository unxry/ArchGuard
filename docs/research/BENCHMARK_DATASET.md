# Benchmark Dataset Foundation — PROMPT 010

`benchmarks/v1/dataset.json` is the versioned **engineering seed**, not the final thesis dataset.
Schema `1.0`, dataset `archguard-benchmark-v1`, version `1.0.0`. Generation definitions are checked
in at `benchmarks/generate_seed.py`; run with `uv run python benchmarks/generate_seed.py`.
Generation establishes labels from scenarios before IAM verification and never reads detector outputs.
Regeneration intentionally replaces the seed files; the mutation CLI writes a new output directory.

## Composition

| Cohort | Repositories | Families | Positive | Negative | Rules |
| --- | ---: | ---: | ---: | ---: | --- |
| Clean/mutant static scenarios, Java and TypeScript | 20 | 5 | 10 | 10 | ARCH001–005 |
| Controlled graph topology, Java and TypeScript | 2 | 1 | 10 | 12 | ARCH101–105 |
| Curated responsibilities, Java and TypeScript | 2 | 1 | 10 | 10 | ARCH201–205 |
| Total | 24 | 7 | 30 | 32 | 15 |

Twelve repositories per language; 31 cases per language. Every static/semantic rule has two positive
and two negative cases. ARCH101/102/104/105 also have two of each; ARCH103 has two positive and four
negative cases (large but isolated, coupled but small).

Family identity includes the clean base, all derived mutations and Java/TypeScript translations of
that scenario. Distinct rule scenarios are independently curated families. Shared tiny syntax
scaffolding is not evidence of independent real-world samples. Approximate clones are not detected.

## Frozen partitions

`sha256-ranked-families-v1`, seed `archguard-seed-v1`: rank SHA-256(seed + ':' + family), reserve
max(1, floor(families/5)) families each for TEST and VALIDATION, remainder TRAIN. Python `hash()` is
never used. Both planner and checked-in `splits.json` must agree with every repository entry.

| Split | Families | Repositories | Cases |
| --- | ---: | ---: | ---: |
| TRAIN | 5 | 16 | 54 |
| VALIDATION | 1 | 4 | 4 |
| TEST | 1 | 4 | 4 |

TEST contains ARCH001, VALIDATION ARCH003; this seed has **no semantic/graph holdout**. Family
isolation takes priority over stratification. It cannot support a scientifically adequate classifier
comparison. Selection is TRAIN/VALIDATION only; TEST is frozen for final evaluation. Foundation
smokes check pipeline mechanics, not parameter/prompt selection or research hypotheses.

Validator rejects cross-partition families, identical source fingerprints, inconsistent mutation
lineage, missing/cyclic ancestors, conflicting truth, path escapes and forged mutation manifests.
Source fingerprint hashes a canonical relative-path → SHA-256(source UTF-8 bytes) map for
Java/TS/TSX/JS. README/manifest changes cannot conceal identical source content. Dataset fingerprint
also covers parsed repository metadata, truth, mutation manifests, splits, target specs and graph
profiles. Manifest comments/whitespace do not affect the logical fingerprint. Runtime paths,
timestamps and invocation IDs are excluded from results.

## CLI

```bash
uv run archguard benchmark validate benchmarks/v1/dataset.json --json
uv run archguard benchmark split benchmarks/v1/dataset.json --output /tmp/split.json
uv run archguard benchmark smoke benchmarks/v1/dataset.json \
  --mode STATIC_ONLY --task CONFIRMED_VIOLATION_DETECTION --output /tmp/static.json
uv run archguard benchmark smoke benchmarks/v1/dataset.json \
  --mode GRAPH_ONLY --task STRUCTURAL_SIGNAL_RETRIEVAL --output /tmp/graph.json
uv run archguard benchmark evaluate benchmarks/v1/dataset.json \
  --mode STATIC_ONLY --task CONFIRMED_VIOLATION_DETECTION --predictions predictions.json
uv run archguard benchmark export-features benchmarks/v1/dataset.json --output /tmp/new-features
```

Evaluation reads a typed saved `PredictionArtifact` bound to the dataset fingerprint. Positive-only
Static/Graph artifacts must explicitly declare `closed_world_complete=true`; failed/skipped execution
cannot stand for negative evidence. Static/Graph smoke rejects incomplete upstream results and skipped
metrics. AI adapter reads an existing source-free `AIAnalysisResult` in Python; no live AI mode exists
in benchmark CLI. Hybrid adapter exports only confirmed deterministic predictions. Calibrated task
is reserved and fails explicitly. All seven ablations have typed configuration identifiers; combined
execution and scientific comparisons remain future work.

Every command emits canonical JSON; `--json` is accepted for consistency. `--split` may limit scoring;
`--limits` reads a typed budget profile. Limits may be lowered from safe ceilings: 2 MiB per manifest,
16 MiB combined referenced manifests, depth 32, 100,000 YAML events, 500 repositories, 20,000 truth
cases, 100 files/1 MiB per source repository and 16 MiB total source. YAML uses SafeLoader with duplicate
keys, aliases and unsafe constructors rejected. Source paths reject absolute paths, traversal and
symlinks. No generated application, package script, JVM or Node program is executed.

## Hybrid export

Separate `train.jsonl`, `validation.jsonl`, `test.jsonl`: exact resolved rule/subject join only, feature
schema `hybrid-evidence-v1`, case and repository/family identities, immutable split, feature fingerprint,
label, annotation provenance and availability. Feature vectors contain no labels/rationales, source,
raw prompts, free-text AI reasons, credentials or absolute paths. Changing labels leaves feature values
and fingerprints unchanged. Unknown labels remain unknown. Cases without truth are omitted.

The default offline export contains 20 records (TRAIN 16 / VALIDATION 2 / TEST 2), **all positive**.
Current Hybrid proposes cases only when a channel supplies an anchor; clean controls and unselected
semantic cases therefore have no vector. Four unannotated graph proposals are omitted. No negative
vector or LLM assessment is fabricated. This export is not ready for fitting; an independently
specified assessment cohort and real saved AI evidence, plus more independent families, are needed
before PROMPT 011. Saved NOT_SUPPORTED assessments can join a curated negative label (contract test).
No fitting, calibrated weights, thresholds, significance testing or final LLM quality metrics exist.
