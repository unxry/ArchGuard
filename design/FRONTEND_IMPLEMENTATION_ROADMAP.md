# ArchGuard AI — дорожная карта production frontend

Дата: 16 октября 2026. Основание: `design/PRODUCT_DISCOVERY.md`. Направление: **STRATA / Evidence Atlas**.

Это план следующих инженерных работ. Текущий Design Lab реализует изолированный интерактивный прототип на synthetic fixtures: 12 TypeScript-модулей, три слоя, режимы 40 узлов и 240 findings. Backend, persistence, production API и provider integrations в этой задаче не меняются.

Сегодня HTTP доступен только для `GET /health` и `GET /api/v1/system/info` (`src/archguard/api/app.py:34`, `:38`). CLI и Python use cases дают основу вычислений, но не заменяют контракты frontend API. Старый прототип `docs/design/archguard-product-preview.html` не принимается за production frontend. Ни один предлагаемый ниже адаптер не объявляется существующим endpoint. Все отсутствующие границы помечены как PROPOSED_BACKEND_ADAPTER в discovery mapping.

## 1. Зафиксировать семантику продукта и сценарии

- **Цель:** согласовать границы actual architecture, target constraints, hypotheses, Security findings и coverage до реализации production UI.
- **Зависимости:** проверенный source inventory, шесть персон и journeys из discovery; независимые владельцы Architecture/Security contracts.
- **Компоненты:** словарь UI-статусов, карта экранов Atlas/Findings/Coverage, annotated prototype, сценарии пустых/неполных/ошибочных результатов.
- **Backend:** только чтение существующих typed models; отсутствующие lifecycle/source/workflow contracts заносятся в backlog.
- **Ограничения:** нулевой результат не означает safe; confidence=null не получает процент; граф показывает статические зависимости.
- **Готово, когда:** каждому видимому утверждению назначены источник, scope и допустимый статус; сценарии позволяют найти proof и увидеть ограничения.
- **Риск:** визуальная сводка смешает доказанный дефект и гипотезу. Контроль — раздельные типы вывода и ревью микротекстов.

## 2. Подготовить frontend foundation и UI-модель

- **Цель:** перенести выбранную композицию в поддерживаемую структуру frontend без привязки компонентов к внутренним Pydantic-моделям.
- **Зависимости:** этап 1; решение о поддерживаемом стеке и размещении frontend в монорепозитории.
- **Компоненты:** app shell, tokens, tabs, resizable inspector, buttons/filters, table, empty/error states, typed UI DTO, fixtures, route/state conventions.
- **Backend:** не требуется для foundation; модель адаптера должна сохранять source IDs, версии и fingerprints.
- **Ограничения:** synthetic/live режимы обозначены явно; отсутствующее значение отделено от нулевого; никаких выдуманных aggregate health scores.
- **Готово, когда:** три экрана и inspector используют общие компоненты, переходы сохраняют selected ID/filters, fixture replacement не требует переделки UI.
- **Риск:** UI DTO потеряет детали provenance. Контроль — проверка отображения representative Finding/Graph/Hybrid records до стабилизации контракта.

## 3. Ввести контракт доступа к данным и системный статус

- **Цель:** построить типизированную границу между UI и сервером с проверкой схемы, ошибок и доступности.
- **Зависимости:** этап 2; договорённость о версионировании API и deployment origin.
- **Компоненты:** API client, query state, schema/error adapters, service status, retry/cancel handling, diagnostics surface.
- **Backend:** подключить только существующие `/health` и `/api/v1/system/info`; отдельно спроектировать read contracts для результатов анализа, не маскируя их fixtures под реальный ответ.
- **Ограничения:** healthy process не гарантирует доступность analysis features; несовместимая schema останавливает отображение результата с понятной причиной.
- **Готово, когда:** реальные system responses корректно отображаются; timeout, offline, version mismatch и sanitized errors проверены; никакие secrets не попадают в UI-лог.
- **Риск:** readiness будет ошибочно воспринята как успешный анализ. Контроль — отдельные service и run statuses.

## 4. Реализовать repository/snapshot и жизненный цикл запуска

- **Цель:** связать конфигурацию пользователя с воспроизводимым снимком и результатом анализа.
- **Зависимости:** этап 3; backend design для jobs, хранения и безопасного repository intake.
- **Компоненты:** repository/revision selector, config/spec review, run state, progress diagnostics, cancellation, retry, run identity header.
- **Backend:** новый lifecycle adapter над существующими use cases; контракт job state, cancellation, result location, namespace и snapshot identity. Persistence/history требуют отдельной реализации.
- **Ограничения:** progress основан на реальных событиях; remote Git/provider действия требуют явного контекста; незавершённый run не маркируется COMPLETE.
- **Готово, когда:** один разрешённый источник проходит intake → analysis → result; отмена и повтор не смешивают результаты; snapshot/config/spec fingerprints сохраняются.
- **Риск:** устаревший result окажется под новой revision. Контроль — immutable run identity и явный stale state.

## 5. Подключить Evidence Atlas к actual graph

- **Цель:** дать исследование зависимостей и доказательств без изменения значения исходного графа.
- **Зависимости:** этапы 2–4; read contract для `GraphAnalysisResult` и IAM ID mapping.
- **Компоненты:** graph canvas, node/edge selection, search, projection/relation filters, layer grouping, pan/zoom/reset, neighbourhood/path panel, graph legend.
- **Backend:** adapter для graph result; read-only обёртка над `shortest_path` и `neighbourhood` с budgets. Источники: `src/archguard/architecture/graph/algorithms.py:102`, `:135`.
- **Ограничения:** A → B = depends on B; CALLS не runtime trace; target layer/module требуют valid classification; truncation, excluded externals и unavailable metrics видимы.
- **Готово, когда:** выбранное ребро раскрывает исходные proofs, фильтры воспроизводимы, 40-node fixture читаем; API-budget overflow имеет явное состояние.
- **Риск:** визуальная агрегация создаст ложное ребро или скроет направление. Контроль — traceability каждого отображаемого edge к IAM proofs.

## 6. Подключить Findings и очередь ручного разбора

- **Цель:** обеспечить поиск, фильтрацию и переход к нужному кейсу при росте числа результатов.
- **Зависимости:** этапы 3–5; раздельные контракты confirmed findings, graph candidates и semantic candidates.
- **Компоненты:** dense list/table, namespace/rule/status/severity filters, search, deterministic sorting, pagination или virtualized view, selected row, clear-filters state.
- **Backend:** versioned read adapter; стабильные IDs; при серверной фильтрации — документированные sort/filter/paging semantics. Assignment/suppression не добавляются без workflow-модели.
- **Ограничения:** candidate не получает придуманный severity; counts относятся к понятной выборке; filter-empty отличается от run-empty и incomplete run.
- **Готово, когда:** 240-record fixture фильтруется без потери выделения и заметной задержки; deep link/refresh восстанавливает доступный выбранный кейс; totals проверяемы.
- **Риск:** сортировка смешает разные шкалы статусов. Контроль — явный тип вывода и сортировка только сопоставимых полей.

## 7. Реализовать evidence inspector и навигацию по source

- **Цель:** сделать любой вывод проверяемым до принятия инженерного решения.
- **Зависимости:** этапы 4–6; согласованная source authorization/revision policy.
- **Компоненты:** proof groups, locations, trace, relation details, supporting/contradicting/missing refs, detector/version, limitations, source preview с line anchors.
- **Backend:** ID-preserving join Finding ↔ Graph ↔ IAM ↔ Hybrid; новый read-only source adapter с revision binding и path validation. Сейчас source endpoint отсутствует.
- **Ограничения:** canonical result source-free; источник открывается отдельно; недоступный evidence ref не заменяется сгенерированным текстом; bounded provenance помечается.
- **Готово, когда:** every available evidence link ведёт к правильному объекту/строке нужной revision; stale/missing/unauthorized source имеет отдельное состояние; длинные пути не ломают layout.
- **Риск:** показать source другой revision или лишний файл. Контроль — серверная проверка доступа и snapshot/path identity.

## 8. Подключить Coverage и Security semantics

- **Цель:** показать, что проверено, что пропущено и какой вывод допустим для конкретного Security rule.
- **Зависимости:** этапы 1, 4, 6, 7; production coverage/outcome adapter, согласованный с Security owner.
- **Компоненты:** coverage matrix, language/rule coverage, unresolved/ambiguous/skipped sections, Security finding status, отдельный outcome, scoped certificate details.
- **Backend:** публичный versioned adapter для coverage/outcomes; исследовательские mapping semantics могут информировать дизайн, но не используются как production HTTP-контракт.
- **Ограничения:** CONFIRMED_PATTERN/SUPPORTED/POTENTIAL/INSUFFICIENT_EVIDENCE/NOT_APPLICABLE отделены от coverage и outcome. V2 zero findings остаётся partial. Definitively safe разрешён лишь узкому SEC008 TypeScript certificate; остальное не апгрейдится автоматически.
- **Готово, когда:** fixtures для partial zero findings, unsupported rule, insufficient evidence и узкого safe certificate дают разные правильные тексты; экран не выдаёт repository-wide safe.
- **Риск:** зелёный цвет или нулевой счётчик станет утверждением безопасности. Контроль — scope рядом с outcome, semantic assertions в contract tests. Основание: `src/archguard/security/domain.py:314`; `src/archguard/security/completeness_v3.py:67`.

## 9. Подключить bounded AI и Hybrid review

- **Цель:** объяснять дополнительные сигналы и противоречия, сохраняя первенство детерминированного proof.
- **Зависимости:** этапы 6–8; отдельное решение о provider policy, budgets, consent и источниках saved AI artifacts.
- **Компоненты:** context manifest preview, truncation/budget view, candidate assessment, channel tabs, agreements/conflicts/missing evidence, policy/version labels.
- **Backend:** адаптер существующих AI/Hybrid contracts; live AI требует отдельного оркестратора и явной политики remote source. Offline Hybrid не превращается в неявный provider call.
- **Ограничения:** `confidence=null` остаётся отсутствием calibrated confidence; structural score показывается отдельно; severity deterministic proof сохраняется; structural policy + AI остаётся неподдерживаемой комбинацией до развития backend.
- **Готово, когда:** conflicting AI не скрывает confirmed Finding; insufficient context видно без раскрытия дополнительных секций; context fingerprints проверяются; provider-disabled путь полноценен.
- **Риск:** AI-текст визуально перевесит proof. Контроль — proof-first hierarchy и отдельные labels candidate/policy/model score. Источник: `src/archguard/architecture/hybrid/models.py:298`; `src/archguard/hybrid_cli.py:75`.

## 10. Проверить доступность, адаптивность и масштаб

- **Цель:** сделать граф и evidence flows пригодными для реальной ежедневной работы.
- **Зависимости:** этапы 5–9; репрезентативные безопасные fixtures, согласованные performance budgets.
- **Компоненты:** keyboard graph/list navigation, focus restoration, accessible labels/announcements, alternate list path, reduced motion, responsive inspector, loading/skeleton boundaries.
- **Backend:** корректная поддержка budgets/paging/cancellation; измерение размеров реальных payload без вывода source или secrets в telemetry.
- **Ограничения:** stress fixtures 40 nodes/240 findings — проверка UI, не доказательство capacity production engine; large-graph limits остаются явными.
- **Готово, когда:** ключевые journeys выполняются клавиатурой, focus видим, контраст проверен, узкий viewport сохраняет доступ к evidence; performance budgets измерены и соблюдены.
- **Риск:** улучшение рендера уберёт доказательства из доступной навигации. Контроль — accessibility и interaction checks вместе с performance checks.

## 11. Подготовить управляемый pilot и production release

- **Цель:** выпустить проверяемый frontend с ясными эксплуатационными границами и возможностью отката.
- **Зависимости:** принятые этапы 3–10; deployment/auth/retention policy; ownership для API и frontend.
- **Компоненты:** release config, feature availability, error reporting, sanitised diagnostics, user-facing limitations, onboarding, compatibility checks.
- **Backend:** авторизация repository/source/result access, version compatibility, storage/retention, observability и rollback; history/comparison включаются только после собственного контрактного этапа.
- **Ограничения:** никаких accuracy/benchmark claims без отдельного подтверждения; telemetry не содержит source, raw prompts, credentials или private truth; demo mode не попадает в production results.
- **Готово, когда:** pilot проходит end-to-end journeys на разрешённых проектах; доказана изоляция доступа; проверены schema mismatch, backend outage, partial run и rollback; нет неработающих обещанных действий.
- **Риск:** расширение scope до collaboration/history скроет незавершённую основу. Контроль — feature gates по готовым контрактам и выпуск только принятых возможностей.

## Последовательность и критерий перехода

1 → 2 → 3 → 4 задают семантику, UI foundation и реальные данные. После этого 5 и 6 можно разрабатывать параллельно на согласованных DTO; 7 связывает их доказательствами. Этапы 8 и 9 требуют отдельных владельцев семантики. Этап 10 начинается на foundation и завершается на интегрированных сценариях; 11 допускается после приёмки контрактов и ограничений.

Для текущей задачи завершение означает готовые discovery, дизайн-направление, интерактивный synthetic prototype и его UI-проверки. Ни один этап этой roadmap не считается выполненным только потому, что соответствующая кнопка нарисована в Design Lab.
