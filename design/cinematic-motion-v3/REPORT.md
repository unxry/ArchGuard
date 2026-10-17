# P039.2 · Cinematic Observatory — итоговый отчёт

Объёмные архитектурные платформы и направленный живой свет объединены в одну интерактивную desktop-сцену. Реализовано в отдельном showcase поверх завершённого P039.1. Два visual review passes завершены; результат готов к пользовательскому визуальному согласованию.

## A. Motion architecture

Нативные SVG + WAAPI + ограниченные requestAnimationFrame loops. `src/motion.js` владеет scopes, отменой, паузой и настройками; `src/spatial.js` — геометрией и светом; `src/transitions.js` — пространственными переходами и evidence. Тяжёлых зависимостей нет. В покое нет непрерывного flow loop. Полное / сдержанное / выключено, отдельный свет и три скорости сохраняются независимо от P039.1. Системный reduced motion имеет приоритет.

## B. System assembly

`assembling → tracing → resting`: появляются объёмные уровни, размещаются модули, прорисовываются фактические связи, проходит конечный свет. Геометрическая фаза — 2450 ms, весь цикл при обычном темпе измерен как 4895 ms с 4× CPU. Повтор запускается кнопкой «Собрать заново». Смена языка не повторяет тяжёлую сборку. Подпись прямо объясняет, что это визуализация готовой структуры, не ход анализа.

## C. Spatial graph

Три смещённые платформы имеют верхнюю плоскость, торцы, rim, ambient light и контактные тени. Скошенные корпуса модулей получают фаски и локальный свет. Подписи остаются горизонтальными. Выбор слоя согласован с подсветкой incident edges и камерой. Небольшой затухающий параллакс перемещает узлы и связи вместе. Для плотных данных — объёмные кластеры и раскрытие настоящего subset с пагинацией.

## D. Graph flow

Головка движется через `getPointAtLength()` реального SVG path. След использует тот же `d` и заканчивается в координате головки. Проверено совпадение геометрии и реальное computed-opacity затухание: 0.80 → 0.45 в выбранном временном срезе. Target activation использует фактический `target`, не декоративный соседний узел. Цепочка следует связанным endpoint IDs, ограничена четырьмя рёбрами и избегает повторных узлов. Камера вписывает её bounds. Свет означает статическую зависимость, не runtime execution и не полную достижимость.

## E. Branding

Возвращены узнаваемые `archguard` в нижнем регистре и отдельный AI-бейдж; вложенная геометрия продолжает public-safe Deluxe v1 mark. Подготовлены dark/light wordmarks, SVG favicon/application icon и [brand review](brand/index.html). Глобальные брендовые файлы репозитория не менялись.

## F. Main overview

Статичная иллюстрация заменена живой моделью текущего dataset. Крупная сцена занимает основную часть desktop; выбор модуля показывает полный идентификатор и сохраняется при переходе в Atlas. Overview → Atlas / обратно переносит реальный SVG между bounds за 680 ms. Клон имеет отдельные IDs, не перехватывает ввод, удаляется при завершении/отмене. Modules/Runs и существующий intake сохранены.

## G. Security / evidence

Связанный модуль переходит к своему finding с контекстной меткой; независимый Security fixture не получает выдуманной связи с модулем. Proof steps раскрываются последовательно, source входит отдельно. Выбор известного шага подсвечивает точную строку при совпадении path и line. Unknown не превращается в подтверждённый поток. Сохранены unsupported, partial, nullable confidence, scoped-negative и текст области сертификата. Импортированный JSON не смешивается с demo; raw export равен исходному артефакту.

## H. Responsiveness

Реально проверены 1280×800, 1440×900, 1920×1080, 2560×1440: нет горизонтального переполнения, подписи Atlas не меньше 12 screen px. На небольшом desktop скрывается повторяющийся тип модуля, доступны прокрутка и полноэкранный граф. Большой экран получает увеличенную сцену. При ширине ≤1099 px — рекомендация расширить окно; скрытый graph освобождается. Мобильный redesign намеренно исключён поздним указанием пользователя.

## I. Performance

Chromium 151.0.7922.34, desktop 1920×1080, CDP CPU throttle 4×. Один измеренный конечный проход на каждый набор, без записи видео параллельно.

| Source modules | Видимых узлов после раскрытия | RAF frames | p95 интервал | Интервалы >50 ms | Long tasks |
|---:|---:|---:|---:|---:|---:|
| 12 | 12 | 144 | 17.5 ms | 0 | 0 |
| 40 | 6 | 144 | 17.5 ms | 0 | 0 |
| 216 | 18 | 144 | 17.6 ms | 0 | 0 |

216 — размер исходного dataset, **не 216 одновременно отрисованных корпусов**: производительность обеспечивается агрегацией и страницами. Сборка со светом: 4895 ms, 0 long tasks, CLS 0.000023, 0 оставшихся WAAPI animations. Heap после GC до/после 20 циклов mount/unmount: 3,334,364 → 3,332,472 bytes. Это локальная проверка cleanup, не гарантия отсутствия любой утечки. RAF intervals не являются измерением GPU/compositor FPS. Другие браузеры/GPU отдельно не профилировались.

HTML/CSS/JS/SVG — около 330 KB без PNG/WebM. Настоящий WebM — 3,936,951 bytes (~3.75 MiB), сценарий записи ~34 s, 1920×1080. Проверены декодирование и воспроизведение. Reduced motion и hidden lifecycle проверены отдельно; hidden тест использует контролируемый visibility event.

## J. Browser tests

- [Основной прогон](previews/browser-report.json): **52 passed, 0 failed, 0 skipped, 0 JS errors, 0 console errors**, нет внешних сетевых запросов.
- [Media / visual artifacts](previews/media-report.json): **7 passed, 0 failed, 0 JS errors**.
- Preview static routes: **5 passed** — обе публичные baseline-папки доступны, traversal отклонён, отсутствующий файл даёт 404.

Проверены assembly/replay/rest, слои, selection, arrow-key navigation, edge selection, zoom/pan/minimap/fit/fullscreen, 40/216 clusters/pages/search, переходы, source focus, unknown/unsupported/certificates, RU/EN, шесть сохранённых пространств, onboarding validation/cancel, 10 public CLI fixtures, raw export, reduced/off/restrained/speed, hidden, rapid routes, desktop sizes, narrow advisory, CPU/heap и offline file:// HTML. Скрипты: `tests/browser.cjs`, `tests/media.cjs`. Запуск — Node + доступный Playwright при работающем локальном preview.

## K. Artifacts

Все пути ниже относительно этого каталога; абсолютные clickable paths предоставляются в сообщении о сдаче, чтобы не включать персональный путь машины в публичный Git.

- [Работающий desktop HTML](index.html)
- [Сравнение P039.1 → P039.2 и видеоплеер](comparison.html)
- [WebM](previews/motion-showcase.webm)
- Overview PNG: [1280](previews/overview-1280.png), [1440](previews/overview-1440.png), [1920](previews/overview-1920.png), [2560](previews/overview-2560.png)
- Atlas PNG: [1280](previews/atlas-1280.png), [1440](previews/atlas-1440.png), [1920](previews/atlas-1920.png), [2560](previews/atlas-2560.png)
- [Световой путь](previews/after-path.png), [evidence](previews/security-trace.png), [unknown](previews/security-unknown.png), [reduced motion](previews/reduced-motion.png)
- Пять свежих baseline captures: `previews/before-*.png`, сделаны из неизменённого P039.1.
- [Motion architecture](MOTION_ARCHITECTURE.md), [два visual review passes](VISUAL_REVIEW.md), [статусы](STATUS.md).

HTML открывается с диска. Для HTTP из корня checkout: `node design/cinematic-motion-v3/dev-server.cjs`, затем `http://127.0.0.1:8782/`. Сервер — локальный preview, deployment не выполняется.

## L. Git / isolation

Ветка: `design-lab/archguard-cinematic-motion-v3`. База: P039.1 `75d9b9ec9ef5c37a63144eb1219a16146683af73`. Итоговый commit и подтверждение normal push передаются в сообщении о сдаче. Изменения ограничены новым `design/cinematic-motion-v3/`; backend, scientific core, исходные public fixtures и прежние showcase сохранены. В копии dev-server добавлены только static mounts двух публичных baseline-каталогов и порт preview; upstream bridge contract не менялся.

Проверенные исходные refs: P039 `4a73d9d56205ab040e0cc6e324959b3b2add0402`; P039.1 `75d9b9e`; local main и origin/main `5e384141a6f9dbafb6654886e83fcad57def564e`. Личные изменения основного checkout не затрагивались. Без force push, merge и deploy. Следующий этап — визуальная оценка пользователем.
