# P039.3 · Signature Polish

Продолжение P039.2 `1cba54e` в том же каталоге, без нового renderer с нуля. [HTML](index.html), [visual review / before–after](polish-review.html), [portal WebM](previews/p0393/portal-transition.webm), [general WebM](previews/p0393/motion-showcase.webm). Исходники закреплены в [SHA-256 manifest](P039_3_SOURCE_MANIFEST.json).

## Дизайн и взаимодействие

- Luminous CTA: graphite/amber material, световая грань, однократный hover sweep, tactile press, доступный focus. Beam строится от реального button bounds к реальному node bounds, затем SVG shared transition переносит архитектуру в Atlas. 330 ms beam + 680 ms shared scene. Flow использует фактические edges. Выбранный узел/слой и dataset сохраняются. Повторный click не создаёт второй portal; render, navigation, hidden, reduced отменяют его. Reduced/off дают мгновенную навигацию.
- Платформа выбирается по настоящему SVG path верхней плоскости. Торцы/rim освещаются, другие слои затухают. Модули/edges имеют приоритет. Keyboard focus рисуется по path без прямоугольника. Выбор сохраняется после pan/zoom.
- Pan: порог 4 px, pointer capture после начала drag, release при завершении, подавление случайного click. Drag отменяет auto-camera. Ctrl/Cmd+wheel — smooth zoom к курсору; обычная прокрутка не перехватывается. Fit, focus, layer/path focus, minimap, clusters сохранены.
- Issue signals: подтверждение и severity независимы. Coral halo только для подтверждённых серьёзных выводов, пунктир для uncertain, нейтральный unsupported. До двух сигналов и двух конечных импульсов при сборке; reduced статичен. Tooltip/keyboard/click открывают соответствующее evidence.
- Evidence: компактнее header/properties, связная timeline, выделение известной строки, сохранены scope/unknown/partial и provenance. Отдельный источник не становится доказательством выдуманной связи.
- Motion Settings: компактный dialog, preview учитывает flow/reduced, реальные intensity/speed/flow, restore defaults, replay. Escape и focus restoration проверены.
- New Project: SVG source cards, selected states, steps, validation, явные CLI-only gates и synthetic demo. Live Git/ZIP не заявляются.
- SVG icon system: navigation, settings/help, camera, inspector/fullscreen, replay и sources. Help объясняет настоящие действия и ограничения. Inspector сразу меняет видимость, сообщает состояние через aria-pressed и сохраняет camera/selection; fullscreen имеет enter/exit и CSS fallback.

## Реальные проверки

[Основной browser report](previews/browser-report.json): **52 passed, 0 failed, 0 skipped, 0 JS/console errors**. [Polish report](previews/p0393/report.json): **19 passed, 0 failed, 0 JS/console errors**. Existing adapter/i18n/server native tests: **43 passed, 0 failed**. Изменены только ожидаемые ожидания анимированного zoom и отложенного portal navigation; прежние assertions сохранены.

Desktop screenshots: [1280](previews/p0393/overview-1280.png), [1440](previews/p0393/overview-1440.png), [1920](previews/p0393/overview-1920.png), [2560](previews/p0393/overview-2560.png). [Beam](previews/p0393/beam.png), [layer selection](previews/p0393/layer-selection.png), [evidence](previews/p0393/evidence.png), [settings](previews/p0393/settings.png), [help](previews/p0393/help.png), [onboarding](previews/p0393/new-project.png). Mobile не перерабатывался.

Два последовательных visual checks: материал CTA/beam и компактность dialog; затем platform geometry, issue signals, evidence, четыре desktop sizes и cleanup. Устранён лишний redraw на media-query event без смены узкого режима. Native/browsing tests не обращаются к private research.

## Performance / limits

Chromium 151, 1920×1080, CPU 4×. Flow на 12/40/216 source nodes: p95 **18.4 / 18.0 / 18.1 ms**, 0 intervals >50 ms, 0 long tasks. 216 остаются clustered/paginated, видимо до18. Полная assembly+flow 4891 ms, 0 оставшихся animations, CLS 0.000023. 20 scene cycles: heap 3,399,736 → 3,395,704 bytes после GC.

[Portal profile](previews/p0393/performance.json): 71 sampled frames, p95 **18.6 ms**, **один long task 122 ms** во время scene construction при 4× CPU. Это измеренный предел, а не заявление о постоянных60 FPS. После20 прерванных переходов: 0 bridges, 0 graph, 0 scopes; heap 1,394,100 → 1,640,780 bytes. Рост246,680 bytes включает прогрев функций; отсутствие любых утечек не доказано. Event handlers привязаны к AbortController graph; новые issue handlers регистрируются один раз на instance.

## Delivery state

`P039_3_CINEMATIC_POLISH_COMPLETE = YES`

Luminous CTA, real-geometry beam, context preservation, interrupt/reduced behavior, polygon selection, camera, issue semantics, evidence, settings/onboarding, icons/help/inspector/fullscreen, all four desktop sizes and real WebM подтверждены указанными проверками. Научное ядро/backend/main не изменены. Ветка `design-lab/archguard-cinematic-polish-v4`, обычный commit/push, без merge. По дополнению пользователя следующий этап — P040 integration, без остановки на visual approval прототипа. Production readiness этим отчётом не заявляется.
