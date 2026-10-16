# P038 — STRATA / Evidence Atlas

**P038_DELUXE_DESIGN_CONCEPT_COMPLETE**

## A. Product discovery

ArchGuard связывает языконезависимую IAM, направленные зависимости, явные архитектурные ограничения и проверяемое evidence. Его преимущество — объяснимый путь от структуры к конкретному выводу, а не сводный AI score. Static/Graph proofs, structural/semantic candidates и отдельная Security completeness имеют разные основания. Реальные HTTP endpoints пока только `/health` и `/api/v1/system/info`.

[PRODUCT_DISCOVERY.md](PRODUCT_DISCOVERY.md) содержит источники в коде, шесть персон, journeys, ограничения и component/data mapping. Research, human truth и benchmark cases не использованы в демонстрационных данных.

## B–C. Creative exploration и выбранная концепция

Рассмотрены **STRATA / Evidence Atlas**, **FOLIO / Engineering Dossier**, **ORBIT / Systems Observatory**. STRATA выбрана за совпадение основного способа навигации с реальной инженерной моделью ArchGuard: зависимость → правило → proof → source. Folio сильнее в линейном чтении, Orbit выразительнее пространственно, но сложнее для точной ориентировки и доступности.

Тёмный минеральный `#101b19`, тёплый dossier `#eeeade`, лайм `#d5edaa`, терракота `#efab91`. Georgia для редакционного заголовка, system sans для данных, локальный monospace для кода. 120/180/240 ms transitions; камера обновляется через requestAnimationFrame без бесконечной анимации. SVG имеет стабильные слои, направленные стрелки, role glyphs, пунктирные нарушения и контекстное выделение.

Подробности: [CREATIVE_DIRECTION.md](CREATIVE_DIRECTION.md), [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

## D. Working HTML

Открыть двойным кликом [index.html](prototypes/archguard-deluxe-v1/index.html). Оставить рядом `app.js`, `fixtures.js`, `style.css`, `mark.svg`. npm, dev server, API, Docker и подключение к сети не требуются. Временный localhost preview используется только для просмотра в приложении.

## E. Реальные screenshots

Все файлы находятся в `design/prototypes/archguard-deluxe-v1/`:

| Capture | Размер | Содержание |
| --- | --- | --- |
| [preview-overview.png](prototypes/archguard-deluxe-v1/preview-overview.png) | 1440×900 | Главный Atlas и dossier |
| [preview-graph.png](prototypes/archguard-deluxe-v1/preview-graph.png) | 1440×900 | Выбор Checkout, focus, zoom |
| [preview-finding.png](prototypes/archguard-deluxe-v1/preview-finding.png) | 1920×1080 | SEC002 и source evidence |
| [preview-coverage.png](prototypes/archguard-deluxe-v1/preview-coverage.png) | 1920×1080 | SEC008 scoped certificate |
| [preview-mobile.png](prototypes/archguard-deluxe-v1/preview-mobile.png) | 390×844 | Узкая карта |
| [preview-mobile-finding.png](prototypes/archguard-deluxe-v1/preview-mobile-finding.png) | 390×844 | Узкое расследование |
| [preview-dense.png](prototypes/archguard-deluxe-v1/preview-dense.png) | 1920×1080 | 40 nodes / 74 edges |
| [preview-reduced-motion.png](prototypes/archguard-deluxe-v1/preview-reduced-motion.png) | 1920×1080 | Reduced motion |

## F. Что действительно работает

Atlas/Findings/Coverage, выбор node/edge/finding, связанные зависимости, graph search, pan/zoom/Fit, Focus path, issue overlay, inspector open/close, evidence/source tabs, source line highlight, namespace/status/severity filters, empty/reset, pagination, scoped coverage certificate, keyboard navigation, guide dialog и локальный JSON export. Сохраняются selected node, search, filters и камера между режимами; смена stress scenario намеренно сбрасывает контекст.

## G. Backend compatibility

Реальны IAM, graph projections, directed graph queries, Finding/Evidence/Trace, ARCH rule contracts, bounded Security и узкий V3 certificate. Все данные текущего UI — **DEMO DATA**. Short IDs, display statuses, simplified evidence aliases и авторские snippets — UI DTO, не production payload. Их future mapping описан как **PROPOSED_BACKEND_ADAPTER**. Никаких endpoint для analyses/history/source не придумано; реальные integration и frontend не начаты.

## H. Quality

38 browser assertions passed; JS/console errors **0**, external requests **0**. Проверены file:// offline, пять viewport sizes, 40-node density, 240-record pagination, keyboard/focus, reduced motion, synthetic export. Проведён содержательный проход визуальной доработки после первого capture. [DESIGN_REVIEW.md](DESIGN_REVIEW.md) фиксирует изменения, ограничения и точные наблюдения производительности без обещания FPS.

## I. Future implementation

[FRONTEND_IMPLEMENTATION_ROADMAP.md](FRONTEND_IMPLEMENTATION_ROADMAP.md): 11 инженерных стадий, для каждой цель, зависимости, компоненты, backend boundary, ограничения, acceptance и риск. Roadmap в этой задаче не выполняется.

## J. Git и границы

Ветка: `design-lab/archguard-deluxe-concept-v1`. Основание: `5e384141a6f9dbafb6654886e83fcad57def564e`. Commit SHA и результат обычного push приводятся в итоговом сообщении после сохранения. Изменения ограничены `design/` и сохранением ранее согласованного удаления `index(визуал).html`. Основной checkout, origin/main, P036, research, scientific freezes, backend, detector semantics и API contracts не изменялись. Private данные не читались; provider-paid calls не выполнялись.

```text
PRODUCT_DISCOVERY_COMPLETE = YES
THREE_CREATIVE_DIRECTIONS_EVALUATED = YES
SELECTED_VISUAL_DIRECTION = STRATA / Evidence Atlas
INTERACTIVE_HTML_PROTOTYPE = READY
GRAPH_EXPLORER_PROTOTYPE = READY
FINDINGS_EXPERIENCE_PROTOTYPE = READY
MOTION_SYSTEM = IMPLEMENTED_IN_DEMO
DEMO_DATA_CLEARLY_MARKED = YES
REAL_BACKEND_INTEGRATION = NOT_STARTED
PRODUCTION_FRONTEND = NOT_STARTED
FRONTEND_ROADMAP = COMPLETE
P036_SCIENCE_UNCHANGED = YES
PRIVATE_DATA_EXPOSURE = 0
PROVIDER_PAID_CALLS = 0
DESIGN_BRANCH_SAVED = YES
READY_FOR_COORDINATOR_VISUAL_REVIEW = YES
WAITING_FOR_PRODUCTION_FRONTEND_APPROVAL
```
