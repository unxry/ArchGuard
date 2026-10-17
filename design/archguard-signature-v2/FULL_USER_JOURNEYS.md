# Полные пользовательские маршруты

| Пользователь / задача | Маршрут | Что реально происходит | Граница |
|---|---|---|---|
| Новый пользователь | Проекты → новый проект → демо → конфигурация → demo-run → Атлас | Согласованные synthetic results; прогресс явно demo; отмена локального таймера | Не настоящий backend job |
| Разработчик / свой локальный код | Local/ZIP/Git onboarding → проверка формы → CLI handoff → импорт JSON | Browser validates names/URL/ref; показывает безопасный аргументный план без исполнения; принимает проверенный экспорт | Нет произвольного доступа к ФС, clone или upload API |
| Архитектор | Атлас → relation filter → node → upstream/downstream → edge → evidence | Статическая зависимость и её proof, без runtime claims | Неразрешённые edges не восстанавливаются догадкой |
| Tech lead | Находки → подтверждённое/high → источник → правило → export | Severity/decision независимы; null confidence остаётся отсутствием | Нет auto-fix, assignments или suppressions |
| Security engineer | Безопасность → SEC002/006/007 → proof steps → known/unknown boundary → source | Поддержанный путь, potential и missing evidence различимы | Ноль findings не означает safe |
| Security coverage review | SEC005 → неподдержка; SEC008 → scoped certificate | Язык/область и certificate явно ограничены | Не repo-wide security verdict |
| Исследователь архитектуры | Модели → discovery → context budget → Hybrid channels | Демонстрирует hypotheses, bounded scope и deterministic precedence | Нет научных метрик, human truth или оплаченного LLM |
| Инженер интеграции | Запуски → проверить сервис → schema versions; импорт CLI output | Live health/system only; отдельно валидированный локальный результат | Не analysis API и не history service |
| Менеджер | Проекты → состояние текущего результата → ограничения → export | Видит scope/provenance, не непрозрачный health score | Сравнение допустимо только с совместимой идентичностью |

Ошибки: invalid JSON/schema, oversize, duplicate/dangling graph references, unsafe Git URL/ref/path, unavailable service, empty filters и canceled demo-run имеют конкретное восстановление. Переход в другую область не теряет текущую находку. RU/EN переключаются без reload; пути, code и rule IDs остаются неизменными.
