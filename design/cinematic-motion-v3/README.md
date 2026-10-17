# archguard AI · Cinematic Observatory / P039.2

Desktop-first исследование **Volumetric Architecture + Living Light Connections**. Основа — P039.1 `75d9b9e`; Precision и исходный Cinematic сохранены в соседнем каталоге без изменений.

Откройте **[index.html](index.html)** или **[сравнение до/после](comparison.html)**. HTML работает с диска. Для локального HTTP-просмотра из корня репозитория:

```sh
node design/cinematic-motion-v3/dev-server.cjs
```

`http://127.0.0.1:8782/` — интерфейс, `/comparison.html` — галерея с настоящим WebM. Backend и сборщик не нужны.

## Главное взаимодействие

При первом открытии собирается визуальная модель уже существующей структуры: объёмные слои, модули, геометрия связей, короткая последовательность света, затем покой. Это не прогресс анализа. Выберите слой или модуль; переход в Атлас сохранит выбранный ID. «Проследить цепочку» показывает ограниченную последовательность фактических source → target связей, перемещает камеру и последовательно освещает конечные узлы. Это не runtime trace и не полный анализ достижимости.

«Движение и свет» в sidebar: полное / сдержанное / выключено, отдельный edge flow, три скорости. «Собрать заново» повторяет сборку. Reduced motion приоритетен. На слишком узком окне показывается рекомендация по разрешению; мобильный redesign исключён последним указанием пользователя.

Целевые размеры: 1280×800, 1440×900, 1920×1080, 2560×1440. Три семейства showcase: Projects/Overview, Atlas, Security/Findings. Models/Runs сохраняют функции P039 и явную пометку прежней визуальной реализации. Полный production redesign шести пространств не заявляется.

- [Итоговый отчёт A–L](REPORT.md)
- [Motion и spatial architecture](MOTION_ARCHITECTURE.md)
- [Два visual review passes и сравнение](VISUAL_REVIEW.md)
- [Эволюция бренда](brand/index.html)
- [Browser report](previews/browser-report.json)
- [Media report](previews/media-report.json)
- [Границы исходного backend](../archguard-signature-v2/BACKEND_INTEGRATION_BOUNDARIES.md)

Ограничения: демонстрационные данные синтетические; локальный JSON импортируется без смешения с fixture. Никакой передачи кода наружу. Статусы, nullable confidence, неизвестные звенья, область сертификатов и raw provenance сохранены. Научное ядро, frozen detectors и API contracts не менялись.

## Файлы и проверка

Новый renderer расширяет проверенный SVG graph engine P039.1, сохраняя его импорт, фильтрацию, выбор и camera APIs. `src/motion.js` управляет конечными WAAPI scopes и настройками. `src/spatial.js` задаёт геометрию, свет и сцену. `src/transitions.js` сохраняет пространственный контекст переходов и source/evidence focus. `spatial.css` задаёт материалы, типографику и desktop layouts. Зависимостей WebGL/Three.js нет.

`tests/browser.cjs` — пользовательские сценарии и CPU/heap measurements. `tests/media.cjs` — настоящая запись браузера, свежие baseline captures и дополнительные проверки окончательного света/галереи. Нужен доступный Playwright и запущенный локальный сервер. В tests используются только публичные fixtures P039 из соседнего каталога.

Только отдельная ветка `design-lab/archguard-cinematic-motion-v3`. Остановиться перед merge/deploy; визуальное согласование остаётся за пользователем.
