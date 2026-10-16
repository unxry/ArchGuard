# STRATA — browser inspection и дизайн-ревизия

16 октября 2026. Проверен автономный `design/prototypes/archguard-deluxe-v1/index.html` через реальный Chromium 151.0.7922.34, Playwright, `file://`, offline context. QA не запускал production backend или анализаторы.

## Что изменено после первой браузерной инспекции

1. Первый экран растягивался до 1253 px на 1440×900 из-за длинного dossier. Теперь desktop workspace занимает оставшуюся высоту окна; список и inspector прокручиваются независимо. Финальная высота — 900 px, горизонтального переполнения нет.
2. Подпись ARCH001 пересекала Order service. Нарушающая связь перенесена в верхний канал; label больше не перекрывает модуль.
3. Увеличены node labels (13 px SVG, 15 mobile), role labels (10/11 px) и lane labels. SVG масштабирует эти величины; плотный режим требует zoom/focus, а не обещает все 40 подписей крупными одновременно.
4. Добавлена явная подсказка EVIDENCE BELOW ↓ в sticky header. Доказательство не исчезает из-за ограничения высоты.
5. Mobile начинается с читаемого участка графа. Pan открывает остальные слои, Fit показывает полный граф; список Findings служит текстовой альтернативой. Export доступен и на узком экране.
6. Исправлены сохранение выбранного узла при переходе Atlas → Findings → Atlas и полное отключение issue overlay. После смены coverage/queue selection focus остаётся на соответствующем контроле.
7. Уточнена семантика fixtures: ARCH001 — explicit forbidden dependency, ARCH003 содержит no-cycle policy; ARCH101 связывает семь отношений / шесть соседей. Policy snippets явно illustrative, Security placement не выдаётся за runtime flow.

Первый capture сохранён как `preview-initial.png`; итоговые screenshots получены заново после исправлений. Все PNG — реальные browser captures, без ImageGen и редактирования изображения.

## Итоговая проверка

38 assertions прошли; полный машинный результат — [browser-check-results.json](prototypes/archguard-deluxe-v1/browser-check-results.json), воспроизводимый сценарий — [browser-check.cjs](prototypes/archguard-deluxe-v1/browser-check.cjs). Для повторного QA нужен уже установленный Playwright; для использования HTML он не требуется.

- `file://`, offline: страница, scripts, CSS и SVG загружаются; внешних HTTP(S) requests **0**.
- JavaScript page errors / console errors: **0**.
- Граф: selection, direct-neighbour focus, path highlighting, zoom, pan, Fit, overlay, поиск по module/rule, empty state, сохранение контекста.
- Findings: namespace, evidence state и severity filters; empty/reset; переход к точному source excerpt; 240 synthetic queue repetitions с шестью DOM-строками на страницу; pagination учитывает фильтр.
- Coverage: десять правил; unsupported не называется safe; SEC008 scoped negative требует видимый certificate и не сертифицирует проект.
- Export: реальный download JSON, DEMO DATA / synthetic=true / backendConnected=false.
- Keyboard: `/`, node Enter, arrow traversal, inspector close/focus return, dialog Escape, evidence/source tabs arrows. Pan — pointer interaction; текстовые списки и zoom/Fit доступны с клавиатуры.
- Reduced motion: CSS animation отключена. В density scenario отключены view/graph transitions; нет постоянных loops или simulation.
- Viewports: **1440×900, 1920×1080, 390×844, 320×740, 768×1024**. Проверено отсутствие горизонтального переполнения страницы; desktop 1440×900 помещается по высоте. Mobile source/code имеет собственный горизонтальный scroll.

## Наблюдения производительности

Последний локальный прогон: переключение dense view (40 nodes, 74 edges), включая два animation frames, **18.8 ms**; загрузка сценария 240 records через браузерное действие и два frames — **25.5 ms**. Это единичные измерения на данной машине, не benchmark и не обещание 60 FPS. Размер отображаемого списка — шесть records; pan/zoom меняют один SVG transform через requestAnimationFrame. Случайной физической раскладки, WebGL, CDN, удалённых шрифтов и runtime package dependencies нет.

## Ограничения и следующая проверка

Полноценный screen-reader/WCAG-аудит, 200% browser zoom, touch-device usability и большие production graphs остаются отдельными приёмочными задачами roadmap. Базовые forced-colors стили есть, но системная high-contrast среда отдельно не проверялась. На плотной карте применяется zoom/focus; автоматическое label LOD и minimap не реализованы. Ни один из этих пределов не скрыт за production-ready заявлением.

Вывод ревизии: концепция готова для визуального review координатором. Production frontend, real backend integration и merge не начаты.
