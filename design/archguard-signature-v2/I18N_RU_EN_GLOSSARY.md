# ArchGuard V2 — RU / EN semantic glossary

RU — язык первого входа; EN равноправен по смыслу. Таблицы фиксируют термины и raw statuses для текущих экранов и будущей интеграции; не все строки обязаны быть видимы в каждом артефакте. Backend identifiers не переименовываются: переведённая подпись сопровождает сохранённое исходное значение.

## Рабочие пространства и данные

| EN | RU | Смысл / ограничение |
|---|---|---|
| Projects | Проекты | Источник и открытие результата; не обещание server persistence |
| Atlas | Атлас | Исследование структуры и направленных отношений |
| Findings | Находки | Findings и кандидаты различаются внутри пространства |
| Security | Безопасность | Самостоятельные findings, coverage и scope |
| Models | Модели | Target rules, hypotheses, context, Hybrid |
| Runs | Запуски | В прототипе записи текущей сессии |
| Evidence | Доказательства | Материал, поддерживающий конкретное утверждение |
| Evidence item | Элемент доказательства | Не равен доказательству безопасности проекта |
| Evidence strength | Сила доказательств | Отдельно от severity и confidence |
| Provenance | Происхождение | Источник, версии, scope, snapshot, ограничения проверки |
| Source location | Позиция в исходном коде | Relative path + one-based координаты |
| Source excerpt | Фрагмент исходного кода | Авторский demo либо реально предоставленный фрагмент |
| Snapshot | Снимок | Конкретная входная модель, не всегда Git commit |
| Scope | Область анализа | На что распространяется утверждение |
| Coverage | Покрытие | Что реально было обработано; не процент безопасности |
| Completeness | Полнота | Полнота определённой области/этапа |
| Validity | Валидность | Соответствие контракту; не полнота и не истинность |
| Candidate | Кандидат | Гипотеза, требующая проверки |
| Structural signal | Структурный сигнал | Метрика/порог/топология, не нормативный дефект |
| Normative rule | Нормативное правило | Явное целевое архитектурное ограничение |
| Target architecture | Целевая архитектура | Объявленная модель, не автоматически принятая гипотеза |
| Architecture hypothesis | Гипотеза архитектуры | Inferred structure с неизвестностью |
| Dependency | Зависимость | A зависит от B; стрелка A → B |
| Dependent | Зависящий компонент | Кто зависит от выбранного компонента |
| Direct neighbours | Непосредственные соседи | Одно ребро; не полный change impact |
| Strongly connected component | Сильно связная компонента | SCC; не любой визуально плотный cluster |
| Confidence | Уверенность | Только при известной модели и калибровке; не придуманная вероятность |
| Severity | Серьёзность | Последствия finding, отдельно от доказанности |

## Режимы и доступность

| Raw code | RU | EN | Ограничение |
|---|---|---|---|
| LOCAL_DEMO | Локальная демонстрация | Local demonstration | Синтетические fixtures; анализ не выполнен |
| LOCAL_RESULT | Локальный результат | Local result | Импорт выбранного JSON, без сетевой загрузки |
| LIVE_SYSTEM_ONLY | Только системный API | System API only | Только health + system info; не live analysis |
| BACKEND_ADAPTER_REQUIRED | Нужен backend adapter | Backend adapter required | Реальный маршрут выполнения отсутствует |
| BACKEND_UNAVAILABLE | Сервис недоступен | Backend unavailable | Не меняет dataset mode на demo или safe |
| PROTOTYPE_STRUCTURE_ONLY | Проверена структура прототипа | Prototype structure checked | Не подтверждает evidence provenance или fingerprints |
| API_EXPOSED | Доступно через API | Available through API | Только реально объявленные маршруты |
| CLI_ONLY | Доступно в CLI | Available in CLI | Browser-кнопка не должна имитировать выполнение |
| REAL_INTERNAL_ONLY | Внутренний контракт | Internal contract | Python use case без общего product endpoint |
| REQUIRES_BACKEND_ADAPTER | Требуется интеграция | Backend integration required | Запланированная продуктовая поверхность |
| RESEARCH_ONLY | Исследовательский контур | Research only | Не подключён к user workflow |
| UNAVAILABLE | Недоступно | Unavailable | Причина указана рядом |

`BACKEND_ADAPTER_REQUIRED` — wire/result code dev bridge; `REQUIRES_BACKEND_ADAPTER` — классификация возможности. Они похожи по смыслу, но не заменяют друг друга в JSON.

## Security: finding status отдельно от outcome/coverage

| Raw finding status | RU | EN |
|---|---|---|
| CONFIRMED_PATTERN | Подтверждённый паттерн | Confirmed pattern |
| SUPPORTED | Поддержано доказательствами | Supported evidence |
| POTENTIAL | Потенциальная проблема | Potential finding |
| INSUFFICIENT_EVIDENCE | Недостаточно доказательств | Insufficient evidence |
| NOT_APPLICABLE | Неприменимо к области | Not applicable to scope |

Это действующий `SecurityFindingStatus`. NOT_APPLICABLE не означает definitive negative. SUPPORTED не следует переводить «проект небезопасен»: finding ограничен конкретными rule/source/evidence.

| Outcome / coverage code | RU | EN | Смысл |
|---|---|---|---|
| DEFINITIVE_POSITIVE | Подтверждённая проблема в области | Definitive positive in scope | Положительный вывод в установленном scope |
| POTENTIAL | Потенциальная проблема | Potential finding | Неизвестность не снята |
| INSUFFICIENT_EVIDENCE | Недостаточно доказательств | Insufficient evidence | Недостаток материала для вывода |
| PARTIAL | Частичный анализ | Partial analysis | Обработана ограниченная область |
| UNSUPPORTED | Не поддерживается | Unsupported | Анализ данной конструкции/области не выполнен |
| FAILED | Ошибка анализа | Analysis failed | Не нулевой успешный результат |
| DEFINITIVE_NEGATIVE | Проблема отсутствует в подтверждённой области | Definitive negative in certified scope | Требуется подтверждённый узкий scope; не repository safe |
| SUPPORTED_PARTIAL_V2_SCOPE | Поддержанная ограниченная область V2 | Supported partial V2 scope | Raw coverage status; не full language support |
| CONTRACT_ONLY | Только контракт | Contract only | Определение существует, выполнение не поддержано |
| COMPLETE | Полнота области подтверждена | Scope completeness established | Всегда указать scope/certificate type |
| NOT_PROVEN | Полнота не доказана | Completeness not proven | Не интерпретировать как отрицательный finding |

Отсутствие findings: **«Находок нет в предоставленном результате» / “No findings in the supplied result.”** Запрещённая подмена: «Безопасно» / “Secure”. В текущем browser importer ноль SEC findings остаётся partial; наличие metadata не повышает его до certified negative. Узкий SEC008 TypeScript certificate в demo помечен синтетическим.

## Parsing, resolution, architecture, Hybrid

| Raw code | RU | EN | Контекст |
|---|---|---|---|
| PARSED | Файл разобран | Parsed | Syntax diagnostics могут оставаться |
| INVALID | Невалидный результат | Invalid | Parser/result context указан рядом |
| SKIPPED | Пропущено | Skipped | Показывать причину |
| UNSUPPORTED | Не поддерживается | Unsupported | Parser или coverage, не verdict |
| FAILED | Ошибка обработки | Processing failed | Сохранить остальные результаты |
| RESOLVED | Цель разрешена | Resolved | Статическая связь |
| AMBIGUOUS | Неоднозначно | Ambiguous | Несколько допустимых целей |
| UNRESOLVED | Цель не разрешена | Unresolved | Не рисовать точное ребро |
| EXTERNAL | Внешняя зависимость | External dependency | Namespace/package, не вымышленный symbol |
| EXACT | Точная локальная цель | Exact local target | Security call resolution |
| UNAMBIGUOUS_LOCAL | Однозначная локальная цель | Unambiguous local target | Не глобальная runtime гарантия |
| CONFORMANT | Соответствует заданным правилам | Conformant to declared rules | Установленный scope |
| NON_CONFORMANT | Нарушает заданные правила | Non-conformant | Есть подтверждённый finding |
| INCOMPLETE | Неполный результат | Incomplete | Отдельно от validity |
| UNKNOWN | Неизвестно | Unknown | Корректный результат, без optimistic fallback |
| STRONG / MODERATE / WEAK | Сильный / умеренный / слабый сигнал | Strong / moderate / weak signal | Discovery strength, не calibrated confidence |
| CANDIDATE | Кандидат | Candidate | View/demo label; не generic production FindingStatus enum |
| CONFIRMED | Подтверждённое правило | Confirmed rule proof | View/demo label; provenance обязателен |
| IMPORTED | Импортировано | Imported | Происхождение загрузки, не доказанность |
| CONFIRMED_DETERMINISTIC | Подтверждено детерминированно | Deterministically confirmed | Hybrid: explicit proof has precedence |
| REVIEW_REQUIRED | Требуется проверка | Review required | Hybrid decision, не confirmed violation |
| SUPPORTED_BY_CALIBRATED_POLICY | Поддержано калиброванной политикой | Supported by calibrated policy | Указана policy/calibration version |
| REJECTED_BY_CALIBRATED_POLICY | Отклонено калиброванной политикой | Rejected by calibrated policy | Не подтверждение безопасности |
| STRUCTURAL_SIGNAL_SUPPORTED | Структурный сигнал поддержан | Structural signal supported | Не нормативное доказательство |
| STRUCTURAL_SIGNAL_NOT_SUPPORTED | Структурный сигнал не поддержан | Structural signal not supported | Не definitive negative |
| UNCALIBRATED | Не калибровано | Uncalibrated | Не показывать процент вероятности |
| CALIBRATED | Калибровано | Calibrated | Нужна ссылка на калибровку |
| DETERMINISTIC | Детерминированное | Deterministic | Характер источника/решения |

## Proof path и severity

| Raw code | RU | EN |
|---|---|---|
| SOURCE | Источник данных | Data source |
| PROPAGATION | Передача данных | Propagation |
| SANITIZER | Правило обработки данных | Sanitizer |
| SINK | Чувствительная операция | Sink |
| INTERPROCEDURAL_BOUNDARY | Граница вызова функции | Interprocedural boundary |
| UNKNOWN_FLOW | Неустановленный участок потока | Unknown flow |
| TAINTED | Данные из недоверенного источника | Tainted |
| UNTAINTED | Не помечено в этой модели | Untainted in this model |
| SANITIZED | Обработано для этого правила | Sanitized for this rule |
| INFO | Информационная | Informational |
| LOW | Низкая | Low |
| MEDIUM | Средняя | Medium |
| HIGH | Высокая | High |
| CRITICAL | Критическая | Critical |

Sanitizer и UNTAINTED ограничены моделью и правилом; не универсальная защита. Стрелки proof path описывают статическое заключение. Формулировка: **«Не runtime-исполнение» / “Not runtime execution.”**

## Правила локализации

- Не переводить ARCH/SEC IDs, JSON keys, paths, branch/ref, hashes, package/symbol names, schema versions и сырые статусы в exported JSON.
- UI copy, empty/error/partial states, titles, labels, tooltips, aria labels и placeholders переводить вместе. Термины из imported source показывать как данные, без машинного переписывания.
- RU/EN менять только presentation; dataset identity, selection и filters не должны сбрасываться. Language preference можно хранить локально; source/results/tokens — нет.
- Плюрализация: `1 модуль / 2 модуля / 5 модулей`; `1 запись / 2 записи / 5 записей`; EN one/other. Числа и даты через Intl, идентификаторы без locale formatting.
- Неизвестный enum показывать исходным значением с «Неизвестный статус / Unknown status»; не заменять зелёной галочкой. Отсутствующее значение — «Не предоставлено / Not supplied», не zero.
- Длина русских строк проверяется в финальном browser QA. Наличие glossary не означает, что все UI strings уже прошли этот контроль.
