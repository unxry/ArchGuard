# ArchGuard AI — продуктовая модель и границы Design Lab

Дата: 16 октября 2026. Статус: discovery для изолированного дизайн-прототипа.

Выбранное направление: **STRATA / Evidence Atlas**. Тёмный атлас зависимостей, светлый инспектор доказательств, верхняя навигация **Atlas · Findings · Coverage**. Прототип использует синтетические данные: 12 TypeScript-модулей, три слоя, отдельные стресс-режимы на 40 узлов и 240 записей. Он не запускает анализатор, не подключается к production API и не представляет синтетические числа как измеренные результаты ArchGuard.

## 1. Продуктовая задача

ArchGuard помогает инженеру ответить на три связанных вопроса: «Какие зависимости существуют?», «Какие из них нарушают явно заданные ограничения?» и «Достаточно ли доказательств для вывода?». Главный объект интерфейса — проверяемый вывод с переходом к его источнику. Карта, список и coverage должны описывать один выбранный снимок и сохранять контекст при переходах.

Успех сценария — пользователь находит конкретную зависимость, понимает тип вывода и предел проверки, затем открывает доступное доказательство. Прототип не обещает сокращение числа дефектов, точность AI или экономию времени без измерений. Проверяемые UX-гипотезы: нахождение доказательства без потери фильтров; корректное различение finding, candidate и coverage gap; отсутствие интерпретации «0 findings» как полной безопасности.

## 2. Что подтверждено кодом

Ссылки ниже относительны корню репозитория; номера строк соответствуют исходному discovery-срезу.

| Область | Реализовано | Предел и следствие для интерфейса | Источник |
| --- | --- | --- | --- |
| Языки | Java, TypeScript, JavaScript, TSX в реестрах парсеров и экстракторов | Python в enum не означает поддержку анализа | `src/archguard/parsing/factory.py:10`; `src/archguard/extraction/factory.py:10` |
| IAM | Project/module/package/file, объявления и внешние зависимости | Actual IAM отделён от заданных слоёв и модулей | `src/archguard/iam_building/builder.py:62`; `:91`; `:119`; `:152` |
| Рёбра | IMPORTS, INHERITS, IMPLEMENTS, CALLS, CREATES, USES | Наличие INJECTS/dataflow/security в enum не доказывает реализацию извлечения | `src/archguard/iam_building/builder.py:32` |
| Разрешение ссылок | Консервативное разрешение; отдельные unresolved/ambiguous/external | Dynamic references и unknown receivers не становятся достоверными рёбрами | `src/archguard/extraction/resolution/resolver.py:26`; `src/archguard/iam_building/builder.py:211` |
| Проекции | Component, file, package, target layer, target module | A → B означает «A зависит от B»; CALLS — фильтр отношения, не отдельная проекция | `src/archguard/architecture/graph/enums.py:4`; `docs/architecture/adr/0013-graph-projections-and-bounded-evidence.md:14` |
| Граф | Coupling, instability, PageRank, betweenness, SCC, направленный shortest path, ограниченная окрестность | Один репрезентативный цикл на SCC; не все циклы и не runtime trace | `src/archguard/architecture/graph/models.py:152`; `algorithms.py:102`; `algorithms.py:135` |
| Доказательство ребра | IAM edge IDs, relation, locations, provenance, occurrences, truncation | Нужно показывать ограничение доказательства рядом с ним | `src/archguard/architecture/graph/models.py:33` |
| Нормативная архитектура | Явная спецификация, слои/модули по relative POSIX globs | Пересечение классификаций invalid; inferred labels не заменяют target spec | `src/archguard/architecture/specification/models.py:38`; `docs/architecture/adr/0012-target-specification-and-static-findings.md:13` |
| Discovery | Гипотезы ролей, слоёв и модулей; ambiguous/UNKNOWN допустимы | Coverage присвоения не равно accuracy или вероятности | `docs/architecture/adr/0014-discovery-hypotheses-and-structural-precedence.md:13` |
| AI context | Бюджеты узлов/файлов/фрагментов/символов, стратегия, evidence refs, truncation | Source-free manifest по умолчанию; явный режим просмотра source | `src/archguard/architecture/intelligence/models.py:54`; `src/archguard/ai_cli.py:35`; `:114` |
| Findings | ID, namespace, rule, severity, locations, evidence, trace, detector | Доказательство не теряется при агрегации в UI | `src/archguard/core/findings/model.py:19` |
| Hybrid | Раздельные каналы, alignment, missing/conflicting evidence, completeness | Детерминированное доказательство и severity сохраняются; candidate не получает выдуманную severity | `src/archguard/architecture/hybrid/models.py:195`; `:221`; `:298` |
| CLI | Intake local/ZIP/public Git, IAM, graph, spec validation/check/discovery, bounded AI, offline Hybrid, JSON export | Это готовые Python/CLI-возможности, а не HTTP-интеграция UI | `src/archguard/cli.py:63`; `:83`; `src/archguard/hybrid_cli.py:30` |

### Каталог ARCH и смысл статусов

| Семейство | Правила | Продуктовое обозначение |
| --- | --- | --- |
| ARCH001–005 | Forbidden dependency; layer dependency; circular dependency; reverse dependency; module boundary | Подтверждённое нарушение только при наличии явного правила и actual resolved evidence. Severity берётся из spec, confidence отсутствует |
| ARCH101–105 | Excessive Coupling; Dependency Hub; Potential God Component; Unstable Dependency; Architecture Bottleneck | Структурный candidate; пороги явные и по умолчанию выключены; `not_calibrated=true`, `confidence=null` |
| ARCH201–205 | Responsibility Mismatch; Business Logic in Controller; Infrastructure Leakage; Misplaced Component; Suspicious Cross-Layer Responsibility | Semantic candidate: SUPPORTED, NOT_SUPPORTED или INSUFFICIENT_CONTEXT; evidence refs, assumptions и limitations доступны отдельно |

Источники: `src/archguard/architecture/specification/models.py:113`; `:140`; `:156`; `:162`; `:167`; `src/archguard/architecture/graph/config.py:39`; `src/archguard/architecture/graph/candidates.py:23`; `src/archguard/architecture/intelligence/models.py:25`; `:198`; `:316`.

Hybrid не является общим «AI score». CONFIRMED_DETERMINISTIC сохраняет исходные Finding IDs. REVIEW_REQUIRED и INSUFFICIENT_EVIDENCE остаются самостоятельными решениями. Структурный model score с артефактом политики не является calibrated confidence. CLI запрещает комбинацию structural policy и AI как `FULL_HYBRID_NOT_READY`. Источники: `src/archguard/architecture/hybrid/models.py:298`; `src/archguard/hybrid_cli.py:75`.

### Security: отдельные измерения

Каталог текущего продуктового аудита: SEC001 secret, SEC002 SQL injection, SEC003 command injection, SEC004 path traversal, SEC005 unsafe deserialization, SEC006 SSRF, SEC007 XSS, SEC008 weak cryptography, SEC009 insecure randomness, SEC010 eval. Отображение каталога не обещает одинаковую глубину анализа всех языков и всех правил.

Finding status: **CONFIRMED_PATTERN / SUPPORTED / POTENTIAL / INSUFFICIENT_EVIDENCE / NOT_APPLICABLE**. Эти значения нельзя объединять с coverage или outcome в одну шкалу риска. CONFIRMED_PATTERN означает подтверждённый распознаваемый паттерн, а не автоматически доказанный exploit. NOT_APPLICABLE не является синонимом «безопасно». Источники: `src/archguard/security/domain.py:45`; отдельные severity/evidence strength — `:53`, `:59`; каталог — `src/archguard/security/rules.py:20` и `docs/security/SECURITY_RULES.md`.

Вывод definitively safe допустим только для узкого текущего сертификата SEC008 TypeScript: один файл, crypto import и один вызов с буквальным разрешённым сильным алгоритмом. Он относится только к выбору алгоритма в целиком ограниченном source unit; не утверждает корректность всей криптографии или безопасность репозитория. Для V2 ноль findings остаётся **partial coverage**. В прототипе эти границы — явные пояснения, а не зелёная сводка «Secure». Источники: `src/archguard/security/completeness_v3.py:67`; upgrade guard — `:128`; `src/archguard/security/domain.py:314`; V2 limitations — `docs/security/SECURITY_ANALYSIS_V2.md:73`. Outcome mapping требует отдельного адаптера; не считать исследовательский протокол production HTTP-контрактом.

## 3. Персоны

| Персона | Рабочее решение | Главная потребность | Ошибка, которую UI должен предотвращать |
| --- | --- | --- | --- |
| Архитектор / staff engineer | Поддержать или изменить границу слоя | Actual зависимости рядом с target constraint и proof | Принять inferred layer за утверждённую архитектуру |
| Разработчик / code owner | Локализовать причину finding | Точное место, направленное ребро, relation и применённое правило | Исправлять предположение AI как доказанный дефект |
| Tech lead / reviewer | Выбрать следующий кейс для ручного разбора | Фильтры, детерминированный приоритет, сохранённый контекст | Смешать structural candidate и confirmed violation |
| AppSec engineer | Оценить security evidence и границы проверки | Rule/status, доказательство, coverage, отдельный outcome | Принять CONFIRMED_PATTERN за exploit или 0 за safe |
| Engineering manager | Понять объём проверенного и непросмотренного | Сводка по текущему снимку с явными пропусками | Сравнить несопоставимые снимки или выдуманный health score |
| Исследователь качества архитектуры | Проверить происхождение и предел вывода | Метод, версия модели, fingerprints, пропуски evidence и отсутствие калибровки | Подменить научную эффективность demo-метриками |

## 4. Ключевые journeys

1. **Понять структуру.** Atlas → выбрать слой или модуль → увидеть входящие/исходящие зависимости → выбрать ребро → прочитать locations и provenance. Направление стрелок обозначено постоянно; фильтр CALLS не называется runtime call graph.
2. **Разобрать нарушение.** Findings → ARCH rule/severity/status filters → запись → inspector с нормативным правилом и supporting edges → переход к узлам Atlas. Фильтры, selected ID и положение пользователя сохраняются.
3. **Разобрать гипотезу.** Candidate → measurements или semantic assessment → supporting/contradicting/missing evidence → понять необходимость ручного review. Никаких процентов уверенности из null или model score.
4. **Проверить полноту.** Coverage → языки/правила/пропуски → unresolved, ambiguous, skipped metrics, truncation → связанный ограниченный результат. Нулевой finding count не скрывает partial coverage.
5. **Проверить Security.** Security-фильтр Findings → точный SEC rule и finding status → evidence → отдельные coverage/outcome. Узкий safe certificate показывается только со своим scope и основанием.
6. **Подготовить реальный запуск — будущая интеграция.** Выбрать repository/revision → policy/spec → показать local/remote source boundary → запуск → диагностика → результат. В Design Lab это описание будущего процесса, без загрузки файлов, provider calls или фиктивного job runner.

## 5. Информационная архитектура STRATA

- **Atlas:** центральный граф, три группировки слоёв, поиск модулей, pan/zoom/reset; relation filters предусмотрены roadmap; выбранный узел/ребро раскрывается в светлом inspector. Синтетическая модель отделяет ID, label, layer, relation и evidence.
- **Findings:** таблица/список с namespace, rule, типом вывода и доступной severity; выбор открывает тот же inspector. Пустой результат фильтра имеет сброс фильтров и не выглядит как отсутствие проблем во всём проекте.
- **Coverage:** доступность анализа, ограничения, unknown/unresolved, статус метрик и область проверок. Не использовать единый процент «здоровья» или «безопасности».
- **Inspector:** стабильный заголовок объекта, краткий вывод, evidence, locations, related dependencies, limitations. Наличие длинных названий и многострочных путей не ломает ширину.
- **Demo control:** явные режимы 12 узлов, 40 узлов, 240 findings. Масштабный режим проверяет взаимодействие и компоновку, не производительность реального backend.

## 6. Реальное и предлагаемое подключение

Аудит существующего HTTP-слоя подтверждает только `GET /health` и `GET /api/v1/system/info` (`src/archguard/api/app.py:34`, `:38`; `apps/api/README.md`). Старый UI-прототип не является действующим production frontend (`apps/web/README.md`). Jobs, history, persistence, source endpoints и API для analysis results не реализованы; здесь они перечислены как требования.

| Prototype component | Реальный backend capability | API/data requirement | Design Lab / Production readiness |
| --- | --- | --- | --- |
| Service availability / system version | `/health`, `/api/v1/system/info` | Typed client, error/schema handling | Real capability; не подключено |
| Snapshot / IAM / analysis results | Python use cases, CLI canonical JSON | Версионированный run/result envelope и read API | Adapter needed · PROPOSED_BACKEND_ADAPTER |
| Graph | `GraphAnalysisResult`, `ArchitectureGraph` | Graph/IAM join, projection/query boundary | Adapter needed · PROPOSED_BACKEND_ADAPTER |
| Neighbourhood / shortest path | Python graph algorithms | Read-only query adapter с budgets | Adapter needed · PROPOSED_BACKEND_ADAPTER |
| Findings / Hybrid evidence | Finding и Hybrid contracts | ID-preserving join и source-of-truth mapping | Adapter needed · PROPOSED_BACKEND_ADAPTER |
| Source navigation | Relative locations и revision identity | Авторизованный read-only source endpoint | Proposed · PROPOSED_BACKEND_ADAPTER |
| Security workspace | SecurityAnalysisResult, per-rule coverage, V3 certificate | Separate rule/language/scope outcome DTO; preserve unsupported/partial/failed | Adapter needed · PROPOSED_BACKEND_ADAPTER |
| Runs / history / comparison | Нет текущего HTTP-контракта | Lifecycle, cancellation, storage, snapshot compatibility | Proposed · PROPOSED_BACKEND_ADAPTER |
| Reviews / assignments / suppressions | Нет текущего product-контракта | Отдельная workflow-модель и аудит изменений | Proposed · PROPOSED_BACKEND_ADAPTER |

Необходимые UI-инварианты: исходные IDs и fingerprints сохраняются; null не превращается в zero; absent metric отличается от нулевой; projected edge раскрывает исходные IAM proofs; target module не подменяется файловой папкой; unsupported/partial/truncated видны рядом с результатом.

## 7. Приёмка дизайн-прототипа

Пользователь может найти модуль, выбрать узел и ребро, изменить фильтр, перейти между Atlas/Findings/Coverage и открыть доказательство без перезагрузки. Стресс-режимы проверяют переполнение, фильтрацию и читаемость. Клавиатура, видимый focus, контраст, reduced motion и узкий viewport учитываются при реализации.

Все данные обозначены synthetic demo. Ни один экран не утверждает production integration, calibrated confidence, полноту Security или готовую возможность analysis API. Следующий инженерный шаг описан в `design/FRONTEND_IMPLEMENTATION_ROADMAP.md`.

### Поля будущего адаптера

Prototype fixtures — UI DTO, не готовые сериализованные Pydantic records. Adapter должен выполнять явное преобразование:

| Prototype field | Production input / требование |
| --- | --- |
| `node.id`, `edge.id/source/target` | Typed IAM/graph UUIDs и mapping projected → original IDs; demo short IDs не отправлять backend |
| `layer`, `role`, `x/y` | Проверенная target classification или явно inferred/unknown; координаты принадлежат UI layout |
| `rule`, `namespace`, `severity` | `rule_id`, namespace, severity из Finding; candidate остаётся отдельной моделью без выдуманной severity |
| `status=CONFIRMED` | Presentation mapping из deterministic proof/Hybrid decision, не поле универсального Finding |
| `detector`, confidence text | Реальный Detector source/version; Confidence nullable с calibration metadata, не display string |
| `evidence.type/title/detail` | Canonical Evidence.type/message/properties; demo RULE/SOURCE/SINK/UNKNOWN_FLOW — UI aliases, не production enum |
| `path/line/startLine/code` | SourceLocation с one-based inclusive coordinates, snapshot identity и отдельное разрешённое чтение source; excerpt не гарантирован Evidence |
| `outcome`, `certificate` | Rule/language/scope coverage + V3 completeness certificate; outcome derivation — PROPOSED_BACKEND_ADAPTER |

Встроенные policy excerpts намеренно помечены illustrative notation: это не готовые architecture.yaml. ARCH001 изображает explicit forbidden rule; ARCH003 — explicit no-cycle rule. SEC source examples независимы от module graph: положение связанных модулей демонстрационное, не извлечённый dataflow.
