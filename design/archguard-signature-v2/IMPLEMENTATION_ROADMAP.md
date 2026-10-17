# V2 — Implementation roadmap

План развития от reviewable local prototype к production integration. Даты и оценка времени не выдумываются: следующий этап зависит от проверки предыдущего и согласованного backend scope. Production-код в P039 не меняется.

## Сейчас

Есть безопасный аудит production capabilities, отдельная V2 worktree, native frontend modules в реализации, синтетические данные, guarded local artifact adapters и additive system-only dev bridge. Native bridge tests прошли 23/23. Browser QA, actual-backend exercise и финальные acceptance records ещё не подтверждены этим документом.

Не считать показанный экран реализованным backend workflow. Главные долги — проверка фактического поведения UI, contract coverage импортов, читаемость плотных графов и сохранение truth/completeness distinctions.

## Этап 1 — закончить и проверить локальный продукт

**Scope:** шесть пространств, onboarding gates, demo run/cancel, imported result isolation, source/evidence navigation, session records/export, RU/EN, graph interaction/motion. Без production API edits и provider calls.

**Критерии завершения:**

- Offline index открывается без network dependency/build installation; HTTP preview сохраняет те же локальные функции.
- Каждый primary action имеет результат; unavailable capability объясняет причину и доступный следующий шаг.
- Import validation выполняется до замены current state; rejected file сохраняет текущий dataset. LOCAL_RESULT не смешивается с demo.
- 12-node case читается напрямую; 40/216-node synthetic studies используют aggregation/drill-down. No-results, zero-node, long label и unsupported relations не ломают layout.
- Graph direction, selected node/edge, finding provenance, evidence/source и return context согласованы. Static pulses не выглядят как runtime execution.
- RU/EN покрывают controls/errors/empty states/aria labels; locale switch сохраняет контекст. Длинные RU строки не обрезают действия.
- Keyboard route, focus return, reduced-motion/pause, 320/390/tablet/desktop widths и 200% zoom проверены в browser. Значимые graph labels остаются читаемыми.
- Export содержит mode/provenance/limitations; в localStorage только language/motion preferences. Отсутствие findings никогда не подписано как безопасность.

**Артефакты приёмки:** воспроизводимые команды native tests, browser interaction record, ключевые screenshots, recorded motion sample при доступности инструмента, список выявленных ограничений. Не заявлять FPS/масштабирование без измерения на фактическом build.

## Этап 2 — укрепить artifact contract

Зависимость: этап 1. Реализуется сначала в независимом frontend adapter/test слое.

1. Зафиксировать поддержанные canonical envelopes и version matrix. Bare IAM и IAMBuildResult — разные payloads; graph result и graph projection также различаются.
2. Привязать каждый adapter branch к public-safe synthetic fixtures, построенным из реальных Python schemas; отдельные negative tests на unknown version, dangling IDs, wrong source binding, malformed proof, contradictory coverage и oversize.
3. Разделить structural validation, fingerprint verification и provenance trust. До появления реальной verification оставить `PROTOTYPE_STRUCTURE_ONLY` и `fingerprints_verified:false`.
4. Уточнить coverage display для импортированных artifact types. Не выводить completeness из отсутствующих metadata и не поднимать imported negative без проверяемого certificate/scope.
5. Внести JSDoc contract types в native modules, сверить guards с ними; фиксировать причины, почему browser acceptance может быть строже backend.

**Gate:** поддержанные fixtures импортируются детерминированно; ошибочные отвергаются до rendering; source текст безопасно экранируется; fuzzed size/depth/key cases не блокируют UI и не смешивают результаты. Полнота validation явно ограничена.

## Этап 3 — подтвердить ограниченную реальную интеграцию

Зависимость: этап 1; изменение production API не требуется.

Запустить canonical app с безопасно явно заданными настройками, не читая private runtime files. Подключить `dev-server.cjs --backend` к literal loopback URL. Убедиться, что backend действительно возвращает `/health` и `/api/v1/system/info`, а bridge показывает реальное name/version/schema/status.

**Gate:** успех отображается только как LIVE_SYSTEM_ONLY; отключение сервиса, timeout и schema mismatch отображаются честно; demo/imported project data не меняются. Отсутствуют запросы к несуществующему analyze/project/history API. Проверить network log без публикации private data.

## Этап 4 — согласовать production execution adapter

Зависимость: подтверждённые contracts и отдельное согласование backend work. Не реализуется скрыто внутри design lab.

| Work package | Что требуется | Acceptance boundary |
|---|---|---|
| Source request | Versioned local/ZIP/Git request, validation, limits, exclusion policy | Browser path не означает server filesystem authority; URL syntax не заменяет network policy |
| Workspace lifecycle | Materialization, cleanup, revision/snapshot identity, source access lifetime | Ошибка/cancel очищает temporary workspace; source viewer не читает новый revision |
| Run orchestration | Typed task selection/config, job ID, status/progress/error/cancel semantics | Progress имеет реальный denominator либо честный indeterminate state |
| Result transport | Versioned typed envelopes, immutable snapshot binding, diagnostics | Valid/complete/resolved/coverage не объединены в один success flag |
| Rule/config integration | YAML validation, canonical fingerprint, explicit target vs inferred state | Изменение policy требует понятного нового запуска, не переписывает прошлый result |
| Source references | Разрешённые relative paths, bounded snippets, snapshot binding | Artifact text не является командой чтения arbitrary files |
| Persistence/auth | Отдельный storage и доступ к projects/runs/results | Наличие database_url или IAM Project не считается готовой реализацией |

Не задавать в дизайне фиктивные endpoint names как существующие. Публичные пути, schema/versioning, retention и access rules фиксируются backend design review перед подключением UI.

## Этап 5 — аналитическая глубина и масштабирование

После реального result transport: profile layouts на representative разрешённых models, virtualized/paginated findings, stable graph aggregation, bounded neighbourhood navigation, accessible text equivalents, context-preserving filtering. Производительность проверяется по input size и конкретным операциям, а не демонстрационному числу узлов.

Actual vs inferred architecture хранить раздельно; cycle observation не равен ARCH003 violation без explicit rule/proof. Candidate thresholds и calibration provenance не скрывать. Security framework/call/dataflow scope остаётся отдельной осью; узкий SEC008 negative certificate не масштабируется визуальным названием на repository safety.

Remote AI — отдельный поздний этап с существующим explicit opt-in/budgets/context policy. UI не вызывает provider во время загрузки проекта или по hover. Отсутствующий provider допускает полноценное static/evidence исследование без фиктивного verdict.

## Очерёдность по пользовательской ценности

Сначала завершённый offline investigation и достоверный import; затем проверенный system-only connection; затем безопасный real analysis adapter; после этого persisted runs/comparison и согласованная AI-интеграция. На каждом шаге пользователь должен видеть источник данных, границы анализа и доступное следующее действие.

Research calibration/benchmark/human review не включается в product roadmap автоматически. Изменения detector semantics, frozen experiments и private truth остаются отдельными работами. Не переносить design-lab branch в основную рабочую директорию или `origin/main` без отдельного согласования.
