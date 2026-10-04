# Architecture experiment protocol

Status: planned; foundation contains no experiment runner or results.

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
