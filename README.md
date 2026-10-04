# ArchGuard AI

**Current stage: Symbol & Dependency Extraction / IAM Builder** · версия **0.1.0**

Магистерская ВКР: «Разработка гибридного метода автоматизированного контроля соответствия
программной архитектуры исходному коду на основе статического, графового и интеллектуального
анализа».

Исследование проверяет, улучшает ли совместное применение Static / Graph / LLM обнаружение
архитектурных нарушений по сравнению с отдельными методами. Система строится как modular monolith
с будущей границей analysis worker.

```text
Source → Repository Intake → Parsing → Extraction → Resolution → language-neutral IAM → graph projections
                                      ├─ Static + Graph + LLM → Hybrid → ARCH
                                      └─ будущий Security pipeline     → SEC
```

ARCH и SEC используют общие Finding / Evidence / Trace, но независимые решения. SEC не поступает
в Hybrid Architecture Decision и не участвует в Architecture F1. Security Engine начинается
только после [CORE THESIS COMPLETE](docs/research/CORE_THESIS_COMPLETE.md).

## Реализовано

- Language-neutral IAM v1.0: Project, Module, Package, SourceFile, Symbol, nodes и edges.
- Typed UUID, SourceLocation, Finding v1.0, Evidence, Trace, Severity и Confidence.
- Инварианты ссылок, namespace, detector source, координат, порядка trace и калибровки confidence.
- Protocol HybridDecisionEngine и валидируемые ARCH-only input/output contracts.
- FastAPI с `/health` и `/api/v1/system/info`, typed settings, stdlib JSON logging.
- Ленивый SQLAlchemy/PostgreSQL foundation, Alembic без application tables и migrations.
- Ruff, strict mypy, pytest/coverage, lockfile, CI, Docker/Compose и исследовательские документы.
- Настоящий Local/ZIP/public HTTPS Git intake, typed physical snapshots, source discovery,
  manifests/lockfiles, exclusions/.gitignore, resource limits, selective content fingerprint и CLI.
- Реальные Tree-sitter Java/TypeScript/JavaScript/TSX parsers, injected registry, diagnostics,
  tolerant/strict mode, runtime/grammar version metadata, sequential coordinator и offline tests.
- Java/TypeScript/JavaScript/TSX syntax extraction, compact declaration/import/reference facts,
  SymbolIndex, conservative resolution, deterministic IAM builder, provenance aggregation и CLI.

Architecture specification, graph algorithms, ARCH rules, LLM calls, hybrid fusion,
Security Engine и production frontend ещё не реализованы. В API нет endpoint анализа.
Synthetic fixtures находятся только в `tests/fixtures`; они не являются результатами анализатора.
HTML-прототип и все его показатели — только design reference.

## Repository discovery

```bash
.venv/bin/archguard repo inspect tests/fixtures/repositories/java_maven
.venv/bin/archguard repo inspect /path/to/project --json
.venv/bin/archguard repo inspect /path/to/project.zip --source zip --json
.venv/bin/archguard repo inspect https://github.com/octocat/Hello-World.git --source git
```

Snapshot — физические файлы/metadata, не IAM. Contents читаются лениво через application
`DiscoverRepository.open()`; `execute()` возвращает inventory и закрывает temporary workspace.
Intake не выполняет repository scripts/build tools и не отправляет source contents наружу.
Git — public HTTPS без credentials; ZIP Slip/symlinks/resource overflows блокируются.
Fingerprint selective: oversized/binary/budget-skipped файлы используют metadata, что ограничивает
обнаружение same-size changes. Подробнее: [Repository Intake](docs/architecture/REPOSITORY_INTAKE.md).

## Syntax parsing

```bash
.venv/bin/archguard parse inspect tests/fixtures/parsing --json
.venv/bin/archguard parse inspect tests/fixtures/repositories/mixed_java_ts
.venv/bin/archguard parse inspect /path/to/project --strict --json
```

`ParseRepository.execute(snapshot, workspace)` возвращает metadata aggregate; `iter_parse()`
выдаёт tree текущего файла внутри существующего `DiscoverRepository.open()` context. Test sources
включены; binary/generated/large/unsupported/docs не парсятся. ERROR/missing nodes дают diagnostics;
strict помечает result invalid, обработка продолжается. JSON не включает source или raw tree.
Syntax tree не является IAM и не разрешает имена/imports/types.
Версии, encoding, lifecycle и ограничения: [Parsing](docs/architecture/PARSING.md).

## IAM generation

```bash
.venv/bin/archguard iam build tests/fixtures/extraction/mixed --output /tmp/iam.json
.venv/bin/archguard iam build /path/to/project --namespace stable-project-id --json
```

`BuildIAM` использует streaming parsing → language-neutral facts → symbol index → conservative
resolver → `ArchitectureModel` schema 1.0. Unknown receiver types и ambiguous references не дают
guessed edges. `--output` сохраняет canonical IAM, `--json` выводит полный build result с diagnostics
и statistics. Для разных repositories задавайте разные стабильные `--namespace`.
Contracts и ограничения: [Extraction](docs/architecture/EXTRACTION.md),
[IAM Builder](docs/architecture/IAM_BUILDER.md).

## Локальный запуск (macOS/zsh)

Нужны [uv](https://docs.astral.sh/uv/getting-started/installation/) и `make`.
`.python-version` и `requires-python` фиксируют Python 3.13. `uv` при необходимости загрузит runtime.

```bash
make install
cp .env.example .env
make run
```

API: `http://127.0.0.1:8000`; OpenAPI: `http://127.0.0.1:8000/docs`.

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/system/info
```

`/health` — liveness процесса. Он не проверяет БД и не обещает готовность analysis worker.
БД для запуска этих двух endpoints не нужна. `.env` не входит в Git. Пароли в `.env.example`
и Compose — публичные учебные значения для локальной разработки.
Версия `0.1.0` и API status `foundation` сохранены для совместимости существующего контракта.

| Команда | Назначение |
| --- | --- |
| `make install` | `uv sync --locked --extra dev` |
| `make lint` | `.venv/bin/python -m ruff check .` и проверка форматирования |
| `make typecheck` | `.venv/bin/python -m mypy src` |
| `make test` | `.venv/bin/python -m pytest --cov=archguard` |
| `make check` | lint, typecheck, tests |
| `make run` | Uvicorn app factory с reload на loopback |
| `make migrate` | `.venv/bin/python -m alembic upgrade head` |
| `make docker-up` | `docker compose up --build -d` |
| `make docker-down` | `docker compose down` (том БД сохраняется) |

Без uv: `python3.13 -m venv .venv`, затем `.venv/bin/python -m pip install -e '.[dev]'`.
Этот путь использует ranges из `pyproject.toml`; для точных версий нужен committed `uv.lock`.
Стандартные команды из таблицы работают и без Makefile после установки.

## Docker и БД

```bash
docker compose config --quiet
make docker-up
curl http://127.0.0.1:8000/health
docker compose exec api python -m alembic upgrade head
make docker-down
```

API и PostgreSQL имеют healthchecks; порты по умолчанию доступны только на `127.0.0.1`.
Compose передаёт API адрес БД с hostname `postgres`, локальный процесс использует `localhost`.
Образ устанавливает runtime из `uv.lock` и Git CLI для intake, запускается от непривилегированного пользователя.
В foundation нет application tables и revision files: `upgrade head` лишь проверяет миграционный
фундамент, Alembic может создать свою служебную таблицу. Domain и будущие ORM records разделены.
Решение объяснено в [ADR 0006](docs/architecture/adr/0006-deferred-persistence.md).

Проверено 2026-10-03 с Docker Desktop: build и Compose config, оба сервиса healthy,
оба API endpoints HTTP 200, online Alembic и PostgreSQL `SELECT 1`. Local/ZIP/public Git CLI
проверены внутри runtime image. После проверки выполнен `docker compose down`; volume БД сохранён.

## Структура

```text
apps/                  entrypoint notes и future web boundary
src/archguard/
  api/                 transport и composition root
  core/                domain, identifiers, locations, findings, evidence, traces
  repository/          physical snapshot contracts, source/workspace ports, policy/errors
  parsing/             syntax adapter protocol, registry, Tree-sitter adapters/diagnostics
  extraction/          language extractors, compact facts, symbol index, conservative resolver
  iam_building/        deterministic mapping, structural validation, serialization
  iam/                 language-neutral snapshots
  architecture/        rules, graph, intelligence, hybrid contracts
  security/            future boundary; implementation gated by thesis milestone
  application/         DiscoverRepository, ParseRepository, BuildIAM и use cases
  experiments/         reproducibility contract
  reports/             future boundary
  infrastructure/      settings, logging, SQLAlchemy, Local/ZIP/Git adapters
  cli.py               developer repository inspection, parsing и IAM build
tests/                 unit, integration, explicitly synthetic fixtures
migrations/            Alembic environment; no application revisions
experiments/           separate dataset, ground-truth, result locations
docs/                  architecture, ADR, research, experiments, UI reference, thesis
docker/, scripts/      image и quality-check entrypoint
.github/workflows/     project CI, no deployment
```

Направление зависимостей: transport/infrastructure → application/IAM/core; domain не импортирует
FastAPI, SQLAlchemy, настройки, БД, SDK или UI. Worker ещё отсутствует: будущий job передаёт
AnalysisId, repository revision и versioned analysis config, сохраняет IAM/results через adapters.

## Документы и roadmap

- [Архитектура](docs/architecture/ARCHITECTURE.md), [контракты](docs/architecture/CONTRACTS.md),
  [данные](docs/architecture/DATA_MODEL.md), [каталог правил](docs/architecture/FINDING_CATALOG.md).
- [Research specification](docs/research/RESEARCH_SPECIFICATION.md),
  [протокол эксперимента](docs/experiments/EXPERIMENT_PROTOCOL.md),
  [воспроизводимость](docs/experiments/REPRODUCIBILITY.md).
- [UI reference](docs/design/UI_REFERENCE.md): исходный HTML сохранён без изменений.

Следующий этап: **PROMPT 005 — Architecture Specification & Static Conformance Foundation**.
Далее — graph projections/algorithms, ARCH rules, graph-guided semantic
analysis, hybrid decision, benchmark и ablation. После CORE THESIS COMPLETE — отдельный Security
Engine. Frontend реализуется отдельными этапами по реальным backend contracts.
