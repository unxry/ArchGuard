# STRATA / Systems Studio — продуктовая архитектура V2

17 октября 2026. Решение принято после нового аудита публичного кода и до V2 frontend implementation.

Шесть пространств соответствуют инженерным решениям, а не внутренним Python-пакетам:

1. **Проекты** — первый вход, происхождение данных, открытие демо, безопасный импорт CLI JSON, onboarding Local/ZIP/Git с реальным capability gate, конфигурация и demo-run.
2. **Атлас** — структура, направления, раскрытие кластеров, ближайшие зависимости, relation filters, поиск и evidence. 12 узлов открываются напрямую, 40/216 через доменные агрегаты и drill-down; нельзя сжать все подписи до точек.
3. **Находки** — подтверждённое, кандидаты и неопределённое; namespace/severity/state filters; источник, нормативная причина и следующая проверка. Один результат, без смешения runs.
4. **Безопасность** — матрица знаний SEC001–010 и отдельная цепочка source → transformation/unknown → sink. Coverage, finding status и scoped certificate независимы.
5. **Модели** — каталог правил, actual/inferred vs target architecture, offline context budgets и Hybrid evidence channels. Никакого фиктивного AI verdict; LLM unavailable по умолчанию.
6. **Запуски** — session-only локальные записи, происхождение/версии/ограничения, JSON export и локальная проверка совместимости сравнения; отдельная system-only connection.

Из P038 сохраняется связь тёмной карты и тёплого dossier. Меняется вся продуктовая оболочка: компактная постоянная навигация, command/search affordance, источник результата в header, полноразмерный graph canvas, самостоятельный onboarding и Security proof workspace. На mobile навигация превращается в горизонтальный список, расследование — последовательный поток; карту можно заменить читаемым списком узлов.

Режимы: LOCAL_DEMO (авторские fixtures), LOCAL_RESULT (проверенный импорт; ничего из demo не подмешивается), LIVE_SYSTEM_ONLY (проверены только health/system). Последний статус не переводит проект в live analysis.

Открытый результат и selection сохраняются между пространствами; импорт полностью заменяет модель. Locale/motion preferences сохраняются локально; source, tokens и реальные results в localStorage не записываются. Project intake и remote provider invocation остаются REQUIRES_BACKEND_ADAPTER, где реального безопасного public entrypoint нет.
