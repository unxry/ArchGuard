# UI reference — ArchGuard AI

Исходник `index(визуал).html` сохранён в корне без изменений. Byte-identical reference:
[`archguard-product-preview.html`](archguard-product-preview.html).
SHA256: `d8c4e003447d8f00f03583f4eae14a5e81feef6eeeea8025cb4dc2bfa77dd88d`.

HTML — interactive product preview, не production frontend. Исходный список включает 13 экранов,
script добавляет ещё 6 security/component экранов; текст tour header отражает исходный список.
Prototype содержит локальные demo transitions, граф, filters/export/print и browser-session review.
Они не означают наличие upload, scanner, storage, report generation или backend endpoints.

| Future section / prototype screen | Данные, которые backend впоследствии предоставляет |
| --- | --- |
| Dashboard / Обзор | project/run summaries, independent ARCH/SEC counts, actual status/progress |
| Projects / Проекты | project/repository identity, languages, revision/history, source provenance |
| New Analysis / Новый анализ | source/config selection, supported capabilities, run lifecycle/errors/cancellation |
| Architecture Review | selected run, evidence-linked findings, constraints, component source context |
| Architecture Graph / Граф | versioned nodes/edges, layers, projections, filtered neighborhoods, location links |
| Findings / Нарушения | namespace/rule/severity/confidence/detector filters, paginated findings, recommendations |
| Target Architecture / Архитектура | versioned specs, layers, modules, allowed/forbidden dependencies |
| Компонент | node/symbol details, locations, source snippets, incoming/outgoing relations, evidence/trace |
| AI-анализ | actual semantic evidence, graph-guided context/provenance, model metadata, review candidates |
| Version Comparison / Сравнение | source/target snapshots, stable identity mapping, dependency/finding differences |
| Security / Security Overview / Безопасность | separate SEC run state/candidates, actual capabilities and provenance |
| Security finding | namespace, evidence, location, severity/confidence, recommendations, future review status |
| Data Flow / Потоки данных | real source/propagation/sink trace, trust boundaries, linked code, limitations |
| Dependencies / Зависимости | manifest/resolved versions, advisory provider/id/date; no fictitious advisories |
| Secrets / Configuration | redacted pattern/config evidence, context/exclusion policy, source locations |
| Experiments / Эксперименты | measured ARCH-only comparisons/ablation, dataset/split/config versions, uncertainty |
| Reports / Отчёты | actual findings/results and reproducibility links; generation will be implemented later |
| Settings / Настройки | supported analysis configuration and redacted provider/runtime configuration |
| Component Intelligence | component role/layer/context with independently attributed ARCH and SEC evidence |
| Дизайн-система | UI-only typography/palette/component reference; backend data не нужны |

Один Finding/Evidence/Trace contract обслуживает detail screens; namespace и calibration всегда
явные. Demo counters, components/dependencies, F1, SEC candidates и fictitious advisory examples
остаются исключительно в reference. Они не перенесены в seeds/production fixtures.
Рекомендации после mock parameterization не означают выполненный повторный анализ.

Foundation API предоставляет только `/health` и `/api/v1/system/info`. Остальная таблица — future
data requirements, не обещание реализованных endpoints. Production Next.js frontend отсутствует.
Security screens реализуются только после CORE THESIS COMPLETE.
