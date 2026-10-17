# Frontend migration plan · после выбора

**Статус: production redesign не начат.** Этот документ — порядок переноса выбранного направления, а не выполненная миграция.

## Инварианты

Сохранить P039 adapters, contracts, raw import/export, provenance, meaningful statuses, confidence semantics, scoped coverage, unknown flow и source coordinates. Не менять scientific core, detectors, CLI schemas или backend. LOCAL_DEMO / LOCAL_RESULT / LIVE_SYSTEM_ONLY остаются различными понятиями. Никакого нового анализа или AI-вердикта из визуального эффекта.

## Порядок

1. Пользователь выбирает Precision или Cinematic. Зафиксировать desktop inspector placement и допустимую плотность. Удалить переключатель направлений только после решения.
2. Перенести токены и базовую типографику в отдельный presentation layer. Сохранить маршруты, view state, dataset и выбранные IDs. Не переносить механически большой override-файл: заменить соответствующие старые правила по компонентам.
3. Projects: подключить реальные project/provenance данные к новой композиции. Сохранить source chooser, validation, отмену demo stages, CLI gates, import errors, history и экспорт.
4. Atlas: перенести размер узла, SVG bands, selection feedback, finite trail и cleanup. Повторить fixtures 12/40/216, импорт реального графа, поиск через cluster page, keyboard, pan/zoom/fit/fullscreen и reduced motion. Не заменять стабильные IDs или структуру evidence ради layout.
5. Findings: перенести реестр и dossier. Проверить namespace/status/severity filters, пустой результат, candidate metrics, nullable confidence, evidence tabs, unknown source, переход к узлу и raw export.
6. Security: перенести coverage index и proof/source layout. Удержать различия SUPPORTED / POTENTIAL / INSUFFICIENT_EVIDENCE / UNSUPPORTED / scoped negative. Проверить SEC001–010, неизвестные звенья, сертификат с ограничением области и imported certificate без повышения доверия.
7. Models: отдельная будущая работа. Каталог → rule dossier; assignment → связь с исходной моделью; Context/Hybrid → budget/provenance/каналы. Сохранить все четыре вкладки, rule-to-findings, imported discovery/context/hybrid, offline limits и отсутствие AI verdict. Не отображать неподдерживаемое как готовую функцию.
8. Runs: отдельная будущая работа. Разделить историю и досье артефакта; сохранить session-only history, import diagnostics, compare только доступных результатов, raw provenance и system-only bridge. Связь с сервисом не должна превращать локальный артефакт в live analysis.
9. Приёмка: regression tests P039 + проверки Graphite, desktop/mobile, keyboard/focus, text contrast, accessibility, 4× CPU profile и lifecycle. Реальные большие артефакты только с разрешёнными данными. Зафиксировать screenshots выбранного направления.

## Способ интеграции

`studio.js` в showcase намеренно переиспользует существующие view renderers для Atlas и investigation; HTML/handlers/IDs остаются совместимыми. В production вынести shell, selection bar, graph controls, dossier, proof path, source panel и coverage index в существующий frontend component layer. Не создавать новый state store или network API исключительно ради визуальной миграции.

Импорт не должен незаметно заменять данные fixture-ами. Переход между пространствами не должен терять выбранный объект. Один graph owner на mount; dispose до замены DOM. Сохранить отмену onboarding timers, file-size/schema validation и локальное хранение только разрешённых предпочтений.

После каждого пространства — ограниченный набор сценариев соответствующего модуля. Общий regression run перед завершением миграции. Merge/deploy не входят в эту поставку.
