# Calibration cohort foundation — PROMPT 010.1

Dataset VALID means schema and provenance invariants hold. READY means the declared engineering
composition requirements for a particular experiment hold. Neither establishes external validity.
The PROMPT 010 seed had seven families, no graph/semantic holdouts and a positive-only 20-record
Hybrid export. Its production proposal universe could not supply negative or missed-positive features.
That original export remains unchanged for baseline reproducibility.

Expanded dataset `1.1.0` is VALID. Static and Graph tasks and Structural Hybrid are READY for the
next machinery stage. Semantic and Full Hybrid are NOT_READY: semantic labels are UNREVIEWED,
no real provider assessments exist, and no eligible semantic families/classes exist in any split.
Real OSS repositories, independent annotation review and additional rule holdouts remain necessary
for final thesis experiments. No fitting, threshold tuning, significance tests or live AI were run.

## Label-free materialization

`EvaluationAnchor` contains repository ID, rule and exact logical subject locators only. It rejects
extra fields including labels. `MaterializeEvaluationCase` resolves IAM subjects uniquely, checks
upstream IAM/graph binding and assembles actual static, graph, discovery and saved AI evidence using
the existing Hybrid assembler. Its benchmark-only COMPOSITE case is not a Finding or HybridDecision
and does not claim detection. Production detectors and precedence policies are unchanged.

All annotated positives and negatives can be materialized, including subjects with no detector
candidate and unselected AI targets. Features are extracted before `join_label` receives ground truth.
Feature/case identities depend on sources, rule, locators and extraction variant; the truth case ID,
label and rationale never enter extraction. AST dependency and label-flip tests enforce that boundary.
The serialized training record carries the label outside `features`. Provenance is the dataset
fingerprint, ground-truth case ID and annotation status, referencing the independent truth manifest.

Feature schema `calibration-evidence-v1` extends the unchanged production `hybrid-evidence-v1` with
`selection.candidate_present`, `selection.static_generated`, `selection.graph_generated`,
`ai.target_selected`, explicit channel availability, task family and separate source/target Ca/Ce/I
and coupling for directed pairs. Pair measurements carry actual graph measurement provenance.
Existing features retain rule IDs, metrics, topology, discovery, AI decisions/context statistics,
quality and missing/skipped indicators. Exact file-pair/SCC/component normalization is retained.

Negative vectors contain measured graph/context evidence, including nonzero coupling. Missing
channels and absent signals retain missing/None values and explicit availability. No zero vectors,
fake NOT_SUPPORTED responses, inferred confidence or proof are created from annotation labels.
`candidate_present=false` is a selection outcome, not negative truth; missed positives retain it too.
`ai.target_selected=false` does not remove a case. Task labels and channel selection indicators are
observable metadata; they must be considered in future leakage/preselection ablations.

## Extraction variants and eligibility

Each of 138 cases has four explicit, correlated variants (552 records): STRUCTURAL complete
extraction, WITHOUT_STATIC, WITHOUT_GRAPH and BOUNDED_METRICS. The bounded variant reruns graph and
discovery with betweenness disabled; skipped ARCH105 measurements stay absent. Partial IAM, missing
required channels or skipped required metrics cannot become eligible. Variants stay in their original
family/split and must not be counted as independent samples or silently pooled in future training.

`calibration_eligible=true` means complete, independently extracted evidence supports the declared
structural task and truth is known. Static rules need their static channel; ARCH003 also needs actual
graph conformance. Graph rules need a complete graph; ARCH105 needs betweenness. Absence of a matched
candidate alone does not make measured structural evidence ineligible. Negative truth does not imply
zero evidence. Readiness uses only the STRUCTURAL variant and requires both classes plus at least two
eligible independent families per TRAIN task and one per VALIDATION/TEST task.

Eligibility is validated at construction and again at readiness validation. Empty reasons, unknown
truth, task/schema mismatch, feature fingerprint/type mismatch, channel/source overrides, inconsistent
truth/family/split/version binding and duplicate (case,variant) records fail closed. Ineligibility
reasons include UNKNOWN_TRUTH, INCOMPLETE_IAM, STATIC_CHANNEL_UNAVAILABLE,
GRAPH_CHANNEL_UNAVAILABLE, GRAPH_CONFORMANCE_UNAVAILABLE and REQUIRED_METRIC_SKIPPED.

Semantic records require real validated assessments and independent review. SCRIPTED_TEST always
has OFFLINE_CONTRACT_ONLY and is ineligible, even for SUPPORTED/NOT_SUPPORTED/INSUFFICIENT_CONTEXT.
The REAL_PROVIDER category is reserved for a future validated ingestion workflow and is ineligible
here with REAL_AI_NOT_VALIDATED. Relabeling a saved source or flipping the eligibility boolean cannot
enable Full Hybrid. Readiness always retains REAL_AI_ASSESSMENT_COHORT_AND_SEMANTIC_REVIEW_REQUIRED.

## Canonical export coverage

These counts include all four variants. AI real/scripted/absent is per-record provenance, not a
provider-quality measure. Export eligibility totals are not a prescribed future fitting cohort.

| Split | Records | Positive | Negative | Eligible | Ineligible | AI real/scripted/absent |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TRAIN | 360 | 176 | 184 | 178 | 182 | 0/0/360 |
| VALIDATION | 96 | 48 | 48 | 40 | 56 | 0/0/96 |
| TEST | 96 | 48 | 48 | 44 | 52 | 0/0/96 |
| TOTAL | 552 | 272 | 280 | 262 | 290 | 0/0/552 |

Every record has dataset ID/version/fingerprint, repository/family/split, ground-truth and Hybrid
case IDs, rule/task, feature schema/fingerprint/vector, independent label/status, variant, channel
availability, AI provenance, eligibility and reasons. Canonical JSONL uses stable repository/case/
variant ordering. It excludes source bodies, absolute runtime paths, secrets, prompts and AI reasons.
Full vectors are runtime exports (about 5.4 MB total), not committed duplicate artifacts.

`ai-assessments.json` contains one future manifest per semantic truth case (44). Provider, model,
prompt version, context strategy/fingerprint and source-free saved artifact reference are absent by
default. Actual token/call usage is unknown/null, not zero. Relative artifact paths reject traversal.
LOCAL_ONLY, GRAPH_GUIDED and EXPANDED_BASELINE bounded context construction is tested without any
provider call. Real ingestion, real usage collection and semantic review are future work.

## CLI and reproducibility

```bash
uv run archguard benchmark validate benchmarks/v1/dataset-1.1.json --json
uv run archguard benchmark readiness benchmarks/v1/dataset-1.1.json
uv run archguard benchmark readiness benchmarks/v1/dataset-1.1.json --json
uv run archguard benchmark export-cohort benchmarks/v1/dataset-1.1.json --output /tmp/new-cohort
```

Export requires a new directory and writes train.jsonl, validation.jsonl, test.jsonl,
ai-assessments.json and readiness.json. Valid datasets may return NOT_READY with explicit reasons
and a successful CLI exit; malformed data still fails. The human report includes composition,
classes, tasks, record counts and separate Structural/Full Hybrid statuses.

Repeated exports and regeneration are byte-identical. macOS and nonroot, network-disabled Docker
Linux match validate, readiness and all five export files. See
[verification](../verification/PROMPT_010_1.md) and [frozen splits](EXPERIMENT_SPLITS.md).


## Subsequent structural machinery

PROMPT 011.1 keeps the 010.1 dataset/export immutable. V2 uses 42 TRAIN / 4 VALIDATION graph cases;
TEST NOT ACCESSED for v2. The four graph TEST cases were consumed by v1 and cannot be a fresh holdout
after feature review. V1 is superseded engineering diagnostic history; v2 is AWAITING_FRESH_HOLDOUT.
[Leakage audit](FEATURE_LEAKAGE_AUDIT.md) excludes candidate decisions/identities/labels from predictors.
Full Hybrid remains NOT_READY. New holdout families must be unused by v1, review, v2 design or validation.
