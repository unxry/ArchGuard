# ArchGuard AI

**Current stage: Architecture Discovery & Structural Classification** · версия **0.1.0**

Магистерская ВКР: «Разработка гибридного метода автоматизированного контроля соответствия
программной архитектуры исходному коду на основе статического, графового и интеллектуального
анализа».

Исследование проверяет, улучшает ли совместное применение Static / Graph / LLM обнаружение
архитектурных нарушений по сравнению с отдельными методами. Система строится как modular monolith
с будущей границей analysis worker.

```text
Source → Repository Intake → Parsing → Extraction → Resolution → language-neutral IAM
                                                       + architecture.yaml → Static + Graph → ARCH
        IAM → Graph → observations / metrics / candidates
        IAM + Graph → Discovery → actual architecture hypotheses
Future: IAM → Graph + LLM + Static → Hybrid → ARCH
        IAM / graph → separate Security pipeline → SEC
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

- Architecture specification YAML v1, bounded safe loader, deterministic layer/module classification.
- Static rule registry и реальные ARCH001/ARCH002/ARCH004/ARCH005 findings из resolved IAM edges,
  с едиными Finding/Evidence/Trace contracts, file-pair aggregation, JSON export и application/CLI.

- NetworkX dependency projections, bounded SCC/cycle proofs, directed metrics и path/neighbourhood API.
- Explicit ARCH003 circular-dependency findings и отдельно ARCH101–105 candidates по заданным порогам.
- Structural architecture discovery: role/layer hypotheses, feature module candidates, evidence,
  dependency matrices, unknown/ambiguous semantics и assignment coverage.

LLM semantic analysis, graph-guided LLM context, hybrid fusion/calibration, Security Engine и production frontend
ещё не реализованы. В API нет endpoint анализа; IAM/findings persistence отсутствует.
Synthetic IAM fixture находится в `tests/fixtures/synthetic_iam.json`; реальные conformance fixtures
проходят весь pipeline и создают findings из исходного кода.
HTML-прототип и все его показатели — только design reference.

## Static architecture conformance

```bash
.venv/bin/archguard architecture validate examples/architecture/layered-clean.yaml --json
.venv/bin/archguard architecture check tests/fixtures/conformance/clean/java \
  --spec examples/architecture/layered-clean.yaml
.venv/bin/archguard architecture check tests/fixtures/conformance/violating/typescript \
  --spec examples/architecture/layered-clean.yaml --json --output /tmp/result.json
```

`CheckArchitecture` переиспользует intake → streaming parsing → extraction → resolution → IAM.
Target YAML не меняет actual IAM. Overlap selectors — configuration diagnostic, а не code finding.
Exit codes: 0 CONFORMANT, 1 NON_CONFORMANT, 2 invalid input/spec/classification/IAM,
3 INCOMPLETE без подтверждённых нарушений. Неполнота также отражается отдельно в `is_complete`.
CONFORMANT означает отсутствие реализованных нарушений для указанной valid target spec в доступном
IAM scope; это не оценка идеальности архитектуры или security safety. Unclassified nodes и неизвестные
references ограничивают покрытие. Для разных проектов выбирайте разные стабильные `--namespace`.
DSL и границы: [Specification](docs/architecture/ARCHITECTURE_SPECIFICATION.md),
[Static Conformance](docs/architecture/STATIC_CONFORMANCE.md).
Результаты quality gate, manual fixtures и macOS/Linux comparison:
[PROMPT 005 Verification](docs/architecture/STATIC_VERIFICATION.md).

## Graph analysis

```bash
.venv/bin/archguard graph analyze tests/fixtures/graph/cyclic/java --json
.venv/bin/archguard graph analyze tests/fixtures/graph/cyclic/java \
  --spec examples/architecture/circular-component.yaml --json --output /tmp/graph.json
.venv/bin/archguard graph analyze tests/fixtures/graph/hub \
  --config examples/graph/research-demo.json
```

`A → B` означает, что A зависит от B. Без explicit `circular_dependency` cycles остаются observations;
ARCH003 создаётся только по enabled rule в valid spec, по одному finding на cyclic SCC.
Candidates отключены по default, имеют `confidence: null`, `not_calibrated: true` и не являются
violations. Demo thresholds исследовательские, не production defaults.
`--projection` и `--relations` переопределяют соответствующие поля bounded typed JSON `--config`.
Остальные intake flags совпадают с IAM CLI; target `layer`/`module` требуют classification spec.
Exit codes: 0 COMPLETE без ARCH003, 1 confirmed ARCH003, 2 INVALID, 3 INCOMPLETE без findings.
`architecture check` объединяет static и explicit graph conformance, строя IAM один раз.

Contracts/limits: [Graph Engine](docs/architecture/GRAPH_ENGINE.md),
[Metrics](docs/architecture/GRAPH_METRICS.md), [Candidates](docs/architecture/GRAPH_CANDIDATES.md).
Проверки: [PROMPT 006 Verification](docs/architecture/GRAPH_VERIFICATION.md).

## Architecture discovery

```bash
.venv/bin/archguard architecture discover tests/fixtures/discovery/mixed
.venv/bin/archguard architecture discover tests/fixtures/discovery/mixed \
  --config examples/discovery/structural-baseline.json --json --output /tmp/discovered.json
```

Discovery формирует hypotheses об actual architecture без target spec и ARCH findings. Generic
Component/Injectable не означают Service; conflicting layers остаются ambiguous, неизвестные роли
UNKNOWN допустимы. Strength/coverage не probability/accuracy; profile NOT CALIBRATED.
Java annotations и TS decorators используются как name hints без arguments. Graph position —
secondary evidence; modules — package/directory candidates с явной size/strength policy и cohesion.
`--spec` не принимается, architecture.yaml не создаётся. IAM/Graph строятся по одному разу.
Exit 0 COMPLETE, 2 INVALID, 3 INCOMPLETE; hypothesis ambiguity сама по себе не processing failure.

[Discovery](docs/architecture/ARCHITECTURE_DISCOVERY.md),
[Classification](docs/architecture/STRUCTURAL_CLASSIFICATION.md),
[Modules](docs/architecture/MODULE_DISCOVERY.md),
[PROMPT 007 Verification](docs/architecture/DISCOVERY_VERIFICATION.md).

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
  architecture/        specification, classification, conformance, rules; future graph/intelligence
  security/            future boundary; implementation gated by thesis milestone
  application/         DiscoverRepository, ParseRepository, BuildIAM, CheckArchitecture, AnalyzeGraph, DiscoverArchitecture
  experiments/         reproducibility contract
  reports/             future boundary
  infrastructure/      settings, logging, SQLAlchemy, Local/ZIP/Git adapters
  cli.py               repository inspection, parsing, IAM build, architecture validate/check/discover, graph analyze
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

Следующий вероятный этап после review: **PROMPT 008 — Graph-Guided Context Construction & AI Architecture Analysis Foundation**.
Далее — graph-guided semantic
analysis, hybrid decision, benchmark и ablation. После CORE THESIS COMPLETE — отдельный Security
Engine. Frontend реализуется отдельными этапами по реальным backend contracts.
