# STRATA / Systems Studio — Design system V2

Дизайн-спецификация для локального V2-прототипа, 17 октября 2026. Палитра и принципы зафиксированы; CSS/UI реализованы; итоговые измерения и screenshots находятся в VALIDATION.md и previews/. Этот документ не удостоверяет browser QA, WCAG conformance или production readiness. Реальные integration boundaries описаны отдельно в `BACKEND_INTEGRATION_BOUNDARIES.md`.

## Визуальная идея

Минеральная тёмная рабочая среда показывает структуру системы; светлое dossier позволяет внимательно читать причину и evidence. В V2 навигационная оболочка постоянна: Проекты, Атлас, Находки, Безопасность, Модели, Запуски. Небольшая навигационная колонка оправдана разными задачами; центральная композиция остаётся пространством исследования, без обязательного ряда KPI-карточек.

Иерархия: источник/режим данных → вопрос текущего пространства → структурный объект → объяснение → evidence/source → доступное действие. `LOCAL_DEMO`, `LOCAL_RESULT` и системное соединение различимы постоянно. Подключённый `/health` не перекрашивает проект в live analysis.

## Палитра и семантика

| Семантическое назначение | Базовое значение | Правило |
|---|---|---|
| Минеральный background | `#142820` | Основная рабочая плоскость |
| Dossier paper | `#f2f1e8` | Причина, evidence, source, scope |
| Lime accent | `#d4e6ac` | Selection, active path, основной локальный action |
| Основной тёмный текст на paper | глубокий зелёный | Контраст проверяется на финальном CSS |
| Основной светлый текст | тёплый off-white | Без эффекта светящегося текста |
| Coral evidence | тёплая терракотовая группа | Конкретное нарушение/проблемное ребро, не весь проект |
| Security channel | blue-grey | Отдельный аналитический канал; не уровень риска |
| Unknown/partial | нейтральный открытый контур + подпись | Никогда не выглядит как confirmed safe |

Три hex выше — утверждённая основа V2. Остальные оттенки подбираются внутри CSS и проверяются на контраст; этот документ не выдумывает отсутствующие CSS custom-property names. В следующем цикле semantic aliases должны отделять текст, поверхность, border, selection, finding и coverage.

Цвет не несёт смысл самостоятельно. Finding имеет текстовый status, rule ID и provenance; graph edge — стрелку, stroke pattern и выбранный evidence; partial coverage — явную подпись. Лайм означает фокус внимания, не отсутствие уязвимости. Severity и strength/confidence показываются разными полями.

## Типографика и плотность

| Роль | Семейство | Проектный ориентир |
|---|---|---|
| Первый вход / editorial title | системный sans, как в CSS | 36–48 px, 1.05–1.15; после входа компактнее |
| Dossier title | системный sans | 26–32 px, 1.15; естественный перенос русского текста |
| Навигация, body, таблицы | системный sans | 13–15 px, 1.45–1.6 |
| Source, ID, rule, version | ui-monospace, SFMono-Regular, Consolas | 11–13 px, 1.5–1.8 |
| Важные graph labels | системный sans | 11.4 px в viewBox; масштабируемый focus + отдельный список и полный inspector |
| Короткая декоративная метка | monospace | может быть компактнее; критический смысл повторяется читаемым текстом |

Размеры — ориентиры реализации, не результаты измерения. Serif не используется. Не превращать имена модулей, пути и неизвестные статусы в нечитаемые micro-labels. Для плотной карты сначала агрегация, затем drill-down; уменьшение всех подписей не является решением масштабирования.

## Сетка, пространство, глубина

Рабочая шкала: 4 / 8 / 12 / 16 / 24 / 32 / 48 px. Сближать label и её значение; отделять независимые смысловые блоки. Dossier ориентировочно 270–350 px desktop, с собственной прокруткой при ограниченной высоте. Source panel сохраняет горизонтальную прокрутку внутри блока. На небольших экранах dossier следует за выбранным объектом в одном потоке.

Тонкие разделители и разные поверхности создают глубину. Тени нужны только для небольшого floating control или временного слоя; без glassmorphism, blur-панелей и glow вокруг каждого node. Радиусы сдержанные: 4–8 px у технических контролов, 10–12 px у крупных контейнеров; pills для фильтров и небольших статусов.

На desktop карта получает максимально доступную площадь. На mobile навигация становится горизонтальной, controls переносятся, findings/текстовый список узлов сохраняют путь к той же информации. Конкретные media queries должны проверяться по фактической композиции; фиксированный breakpoint P038 не переносится автоматически.

## Компоненты и обязательные состояния

| Компонент | Содержимое и поведение |
|---|---|
| Mode badge | Видимый текущий dataset mode; system connection — отдельный indicator |
| Project source | Название, snapshot/revision когда есть, schema/provenance; неизвестное явно обозначено |
| Onboarding source option | Demo / selected CLI result / Local / ZIP / Git; capability gate для отсутствующего browser intake |
| Source validation | «Формат корректен» отдельно от «доступность проверена»; command preview ничего не исполняет |
| Filters | Namespace / evidence status / severity раздельно; reset предсказуемо восстанавливает список |
| Finding row | Rule, title, source, status; candidate не получает severity из оформления |
| Dossier | Утверждение → provenance → rationale → evidence → source → next investigation |
| Security proof rail | SOURCE → PROPAGATION/SANITIZER/UNKNOWN_FLOW → SINK; incomplete gap остаётся видимым |
| Coverage matrix | Requested / analyzed / supported scope и outcome; ноль findings не становится negative |
| Rule control | Если меняет только demo, это написано рядом с контролом; не имитация backend persistence |
| Import | Выбранный пользователем JSON, проверка до замены current dataset; ошибка сохраняет прежний результат |
| Export | JSON с mode/provenance/limitations; не серверный signed report |
| Empty | Причина: нет совпадений, нет данных данного типа, scope не проанализирован; никогда «всё безопасно» |
| Disabled/unavailable | Причина и конкретный следующий доступный шаг; без бесконечного spinner |
| Error | Класс ошибки, затронутая операция, доступное восстановление; без сырого traceback/source dump |

Hover меняет фон/контур без скачка геометрии. Focus заметен на тёмном и paper; selected отличается от hover. Loading применяется к реальной операции (например, system request или чтение файла); demo progress постоянно подписан synthetic. Partial, unsupported, failed и insufficient evidence — самостоятельные состояния, не варианты успешной зелёной галочки.

## Graph и motion

Detailed source of design intent: `GRAPH_EXPERIENCE_SPEC.md`, `MOTION_SYSTEM.md`. Базовый граф направлен: A → B означает зависимость A от B. CALLS — статический relation filter, не playback реального запроса. Module glyph обозначает роль агрегата; FILE/SYMBOL допускаются только при наличии соответствующей сущности во входных данных.

V2 предполагает 12 узлов для прямого исследования и 40/216 для проверки domain aggregation/drill-down. Imported model имеет отдельные adapter budgets; графовый layout не доказывает полноту codebase. Не привязывать node size к выдуманному risk score.

Motion intent: micro 120 ms, context 220 ms, navigation 300 ms, camera 420 ms; easing `cubic-bezier(.2,.75,.2,1)`. Направленный pulse следует геометрии source → target, конечен, максимум четыре активных paths; он объясняет отношение. Pause, reduced-motion, скрытая вкладка и unmount прекращают движение/animation frames. Фактические frame intervals и ограничения приведены в VALIDATION.md; camera 420 ms, finite pulse window 4000 ms.

## Accessibility и RU/EN

Цели: обычный текст ≥4.5:1, крупный текст и значимые нетекстовые элементы ≥3:1; полный keyboard route, видимый focus, native button/input/select/dialog, skip link, live status при завершении, ошибки рядом с input. Информация SVG доступна через findings/inspector и текстовый список. Цвет/движение не обязательны для понимания.

Интерактивные targets желательно 44 px для touch; компактные элементы должны как минимум оставаться различимыми и иметь достаточные интервалы. Проверить 320/390 px, tablet, 1440 px, 200% zoom, длинные RU strings и reduced-motion. Browser QA и screen reader validation — следующие шаги, не завершённые факты.

RU default, EN переключается без замены dataset/selection. Идентификаторы и пути не переводятся. Числа/даты форматируются Intl по locale; русское множественное число через Intl.PluralRules. Labels, placeholders, aria-labels и error copy входят в локализацию. Словарь `I18N_RU_EN_GLOSSARY.md` фиксирует смысл; его покрытие шире текущих экранов.

## Native implementation contract

Нативные HTML/CSS/JS, без dependency/build chain; обычные script files поддерживают offline index. Runtime state и helpers находятся в `src/core.js`, локализация в `src/i18n.js`/`catalog.js`, импорт и guards в `src/adapters.js`, граф и представления — в соответствующих модулях. User/artifact text экранируется перед HTML insertion.

JSDoc contract names для сопровождения: `DataMode`, `WorkspaceDataset`, `ProjectProvenance`, `FindingView`, `CoverageView`, `GraphNodeView`, `GraphEdgeView`, `SystemConnection`. Это документационные типы; наличие этого списка не означает, что все `@typedef` уже внесены в source. Native JS не предоставляет compile-time enforcement: внешние данные обязаны пройти runtime guards, а unknown enums не получают optimistic fallback. Проверка структуры в browser не заменяет canonical Python validation и проверку происхождения evidence.
