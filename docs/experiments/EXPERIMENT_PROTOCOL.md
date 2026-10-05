# Architecture experiment protocol

Status: scientific experiment planned; PROMPT 010 supplies an independent engineering seed, scoped evaluator and offline foundation smokes. No final research results.

## Methods and ablation

Основные сравнения: **Static, Graph, LLM, Hybrid**.

| Ablation | Included inputs |
| --- | --- |
| Static | static |
| Graph | graph |
| LLM | semantic |
| Static + Graph | static, graph |
| Static + LLM | static, semantic |
| Graph + LLM | graph, semantic |
| Static + Graph + LLM | full Hybrid |

Поддерживаемые rule families каждого метода фиксируются заранее. Сравнивать на одном основном
ARCH label universe; отсутствие возможности обнаружения считается FN, не скрывается изменением
denominator. Дополнительные per-family сравнения маркируются отдельно. Общая extraction/IAM
инфраструктура и одинаковые source snapshots исключают различия от parser coverage.

## Dataset strategy и split

- Synthetic projects: контролируемые архитектурные ограничения и чистые negative cases.
- Mutation dataset: известные внесённые нарушения, paired originals и documented mutations.
- Real open-source projects: версии/лицензии/provenance и reviewed architecture ground truth.

Split **по repositories/projects**, не по отдельным finding cases. Forks, versions, paired
originals/mutations и template-derived projects одной семьи остаются в одном split. Calibration,
validation и test изолированы. Thresholds, prompts, context policy и fusion decisions выбираются
до финального test. Ground truth test не используется для calibration, prompt tuning или примеров
LLM context. Manifest split version immutable; exact repository commits фиксируются.

Ground truth: stable case key (project/revision/rule/component-or-relation), явные positives и
eligible negatives, independent review и adjudication спорных labels. Semantic labels содержат
обоснование и ambiguity policy. Annotation не принимает detector outputs как истину. Capability,
matching/localization policy и unknown/ambiguous exclusions фиксируются до scoring.

## Metrics

| Metric | Definition |
| --- | --- |
| Precision | TP / (TP + FP) |
| Recall | TP / (TP + FN) |
| F1 | 2TP / (2TP + FP + FN) |
| False Positive Rate | FP / (FP + TN), только при определённом eligible negative universe |
| False Negative Rate | FN / (TP + FN) |
| Analysis Time | measured end-to-end и отдельно stage timings, seconds |
| Memory | peak resident memory процесса/worker, bytes; measurement method recorded |
| LLM Tokens | actual reported input/output tokens; unavailable counts обозначаются missing |
| LLM Calls | actual requests, включая retries/errors, отдельный successful count |

Zero denominator → undefined/null с пояснением, не искусственное 0 или 1. FPR не выводится из
одного positive-only finding list. Заранее определить one-to-one matching findings ↔ cases и
deduplication: duplicate outputs не создают дополнительные TP. Report micro aggregate и macro
по repositories/rule families с явными sample counts. Uncertainty анализируется на repository
level (например paired bootstrap), а не независимостью correlated finding cases.

## Execution и исследовательские вопросы

Одинаковое hardware/runtime, warm/cold cache policy, timeouts, config и dataset revisions.
Фиксировать failed/timed-out runs, не молча исключать их; повторные measured runs и порядок
methods задаются protocol configuration. LLM model/provider/parameters/prompts versioned,
actual token/call usage collected. Determinism LLM не гарантируется seed/temperature.

RQ1–4: overall/per-family correctness и ablation. RQ5: paired full-context versus graph-guided
context при одинаковом model/budget/test split, качество и tokens/calls. RQ6: measured runtime
и memory по росту files/symbols/nodes/edges и project size. Размеры и результаты не придуманы
в foundation. Known provider training-data contamination ограничивает выводы на public repos;
фиксировать доступные сведения и использовать controlled synthetic/mutation families.

**SEC findings не входят ни в Architecture F1, ни в confusion matrix основного эксперимента.**
Security требует отдельного protocol после CORE THESIS COMPLETE.


## PROMPT 010 task semantics and next experiments

[Seed dataset](../research/BENCHMARK_DATASET.md) and [metrics](../research/EVALUATION_METRICS.md)
fix scoped matching, negative controls and family partitions. Graph structural retrieval is a separate
task. AI abstention/unselected targets remain outside the conditional confusion matrix with explicit
coverage, rather than inventing negatives. Full-universe coverage-aware comparisons must be
preregistered before scientific runs; conditional F1 alone is insufficient.

| RQ | Foundation support | Future measurement |
| --- | --- | --- |
| RQ1 | Static controls, explicit constraints and negatives | Reviewed conformance benchmark |
| RQ2 | Known topology and metric thresholds | Signal usefulness on reviewed projects |
| RQ3 | Curated ARCH201–205 pairs | Real saved LLM assessments and independent review |
| RQ4 | Exact Hybrid feature/label joins | TRAIN fit, VALIDATION selection, frozen TEST |
| RQ5 | Existing context strategies/manifests | Real token/cost/coverage comparison |
| RQ6 | Bounded loaders/analysis | Runtime and memory scaling on larger sources |

No RQ is answered by this seed. Expand independent families, semantic/graph holdouts and negative
feature cohort before training. Keep all seven planned ablations; unsupported execution stays explicit.
No fitting, statistical tests, threshold/prompt tuning on TEST or calibrated artifacts in PROMPT 010.


## PROMPT 010.1 readiness boundary

The [expanded partitions](../research/EXPERIMENT_SPLITS.md) and
[calibration cohort](../research/CALIBRATION_DATASET.md) add independent task holdouts and both-class
features. Structural READY permits a subsequent machinery stage; it does not establish sufficient
statistical power or external validity. Full Hybrid remains NOT_READY without real validated provider
assessments and reviewed semantic truth. Family is the experimental unit, and four variants per case
must never be treated as independent observations. Production proposal/AI-target selection flags are
explicit features so future ablations can expose selection bias. No fitting, threshold/prompt selection,
live provider calls or final test experiment occurs in 010.1. PROMPT 011 requires review before starting.


## PROMPT 011.1 leakage correction

V1 is diagnostic/leakage-sensitive and superseded for research. Its old TEST is consumed.
The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

[Protocol v2](../research/MODEL_SELECTION_PROTOCOL.md) fixes raw-graph-only features, TRAIN-only
preprocessing/family-weighted native models and VALIDATION-only selection. Direct Graph baseline
uses separate metadata. V2 freezes AWAITING_FRESH_HOLDOUT and blocks TEST access. A new independently
annotated lineage is required; no v2 TEST evaluation or full Hybrid validity claim exists.
[Formal feature audit](../research/FEATURE_LEAKAGE_AUDIT.md) and
[results](../research/STRUCTURAL_META_CLASSIFIER.md) document descriptive limitations.
