# Research & Engineering Foundation v1

Архитектурное научное ядро:

```text
Static Analysis + Graph Analysis + AI / LLM Semantic Analysis
                         ↓
             Hybrid Architecture Decision Engine
                         ↓
                    ARCHxxx findings
```

Будущий общий processing foundation:

```text
Source Code → Repository Processing → Parsing → IAM
                                              ↓
                                 Program / Dependency Graph
                                   ├─ Architecture → ARCHxxx
                                   └─ Security     → SECxxx
```

Security — независимое расширение после архитектурного метода и эксперимента.
Проект не ставит целью заменить CodeQL, Semgrep или SonarQube.

## Модули и зависимости

| Boundary | Ответственность | Допустимые зависимости внутри проекта |
| --- | --- | --- |
| `core` | Value/domain models, IDs, location, findings/evidence/trace | только `core` |
| `iam` | language-neutral graph snapshot, consistency validation | `core`, `iam` |
| `repository` | physical snapshot contracts, policy, errors, source/workspace ports | `core`, `repository` |
| `parsing` | syntax adapter ports/registry, Tree-sitter trees/diagnostics; future extraction отдельно | `core`, `repository`, `parsing` |
| `architecture/rules` | будущие deterministic rules | `core`, `iam` |
| `architecture/graph` | будущие algorithms/metrics/projections | `core`, `iam` |
| `architecture/intelligence` | будущий graph-guided semantic context | `core`, `iam`, application ports |
| `architecture/hybrid` | ARCH-only contracts, будущая fusion | `core`, `iam` |
| `security` | отдельный будущий SEC pipeline | общий domain/IAM, собственные решения |
| `experiments` | reproducibility contract, будущий benchmark | `core`, будущие analysis ports |
| `reports` | будущие представления measured results | `core`, application ports |
| `application` | orchestration/use cases, DiscoverRepository/ParseRepository | `core`, `iam`, `repository`, `parsing` ports |
| `infrastructure` | configuration/logging/database, Local/ZIP/Git adapters | domain/application |
| `api` | transport и composition root | application, infrastructure, API schemas |

Domain использует stdlib и Pydantic v2 как библиотеку валидации, без FastAPI/SQLAlchemy/SDK/UI.
Physical repository contracts не импортируют filesystem, subprocess, ZIP или IAM implementation.
Подробности intake: [REPOSITORY_INTAKE](REPOSITORY_INTAKE.md).
Parsing boundary: [PARSING](PARSING.md), native Tree-sitter types не входят в IAM/core.
Модели ORM будут отдельными; mapping выполняет infrastructure. App factory получает Settings
явно, не создаёт global engine, не открывает PostgreSQL и не запускает анализаторы.
Тест архитектурных границ защищает domain от обратных зависимостей.

## Modular monolith и worker

Один Python package и один API deployable сейчас. Будущий analysis worker будет отдельным
entrypoint того же modular monolith, с теми же contracts и application use cases.
Job boundary: AnalysisId, ProjectId/repository revision, versioned analysis configuration.
Будущие adapters отвечают за доставку задания, progress/status, cancellation, artifact storage и
transaction boundaries. Объекты HTTP/ORM не передаются worker/domain. Очередь и scheduler
пока не выбраны; Celery/Redis и отдельные микросервисы не требуются на этом этапе.

## Graph projections

Один гигантский обязательный граф не нужен. Логические projections используют общие IDs:

| Projection | Будущее содержимое |
| --- | --- |
| Architecture Dependency Graph | dependency/import/use/inheritance и module/layer aggregation |
| Call Graph | вызовы функций/методов, выбранная гранулярность |
| Data Flow Graph | propagation, reads/writes и переходы данных |
| Security Graph | security-relevant sources/sinks/trust boundaries |

Snapshots могут содержать общий набор nodes/edges или отдельные материализованные projections.
Projection metadata в будущем фиксирует selection policy, granularity и analysis config version.
Связи data-flow/taint сейчас только зарезервированы в enum, вычислений нет.

## Решения, уверенность и научная целостность

Доказанные deterministic ARCH violations сохраняются независимо от LLM interpretation.
Graph anomalies — structural/heuristic candidates; пороги и interpretation подлежат эксперименту.
LLM используется для semantic context, не отменяет explicit constraints.
Confidence отделена от Severity; отсутствующая confidence не заменяется на 1.0.
SEC evidence запрещена в Hybrid input, SEC findings запрещены в его output.
Ни HTML demo data, ни synthetic test fixtures не используются как backend seeds или результаты.

См. [contracts](CONTRACTS.md), [data model](DATA_MODEL.md), [ADRs](adr/0001-modular-monolith.md)
и [research specification](../research/RESEARCH_SPECIFICATION.md).
