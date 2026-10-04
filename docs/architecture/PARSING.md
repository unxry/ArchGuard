# Language Parsing Foundation — schema 1.0

```text
RepositorySnapshot + RepositoryWorkspace.open_source_file()
  → ParseRepository
  → ParserRegistry
  → ParserAdapter (Java / TypeScript / JavaScript / TSX)
  → ParsedSourceFile (native syntax tree + metadata + diagnostics)
  → Extraction → IAM Builder
```

Tree-sitter — технология синтаксического parsing, не научный метод архитектурного анализа.
Метод ВКР находится выше: Static + Graph + LLM → Hybrid → ARCH. Future SEC независим;
parsing не принимает ARCH/SEC решений и не создаёт IAM entities, symbols или dependencies.

## Dependencies и совместимость

Проверены официальные Python bindings/API и PyPI wheels; версии закреплены в pyproject.toml
и uv.lock. На CPython 3.13.14 / macOS ARM64 все четыре grammar capsules реально загружены и
построили корректные trees. Используется `Language(capsule)` и `Parser(language).parse(bytes,
encoding="utf8")`, без legacy set_language/build_library/convenience packages.

| Package | Version | Grammar entry point | ABI |
| --- | --- | --- | --- |
| tree-sitter | 0.26.0 | runtime; compatible grammar ABI 13–15 | — |
| tree-sitter-java | 0.23.5 | language() | 14 |
| tree-sitter-typescript | 0.23.2 | language_typescript() / language_tsx() | 14 / 14 |
| tree-sitter-javascript | 0.25.0 | language() | 15 |

Grammar packages используют stable ABI wheels (cp39/cp310 abi3), runtime имеет cp313 wheel.
Python minimum в package metadata совместим с 3.13; compatibility дополнительно проверяется
реальными adapter tests, а не только version constraints. Optional grammar extras `core` не нужны:
runtime задан явно. [Bindings/API](https://github.com/tree-sitter/py-tree-sitter),
[runtime](https://pypi.org/project/tree-sitter/0.26.0/),
[Java](https://pypi.org/project/tree-sitter-java/0.23.5/),
[TypeScript/TSX](https://pypi.org/project/tree-sitter-typescript/0.23.2/),
[JavaScript](https://pypi.org/project/tree-sitter-javascript/0.25.0/).

## Boundaries и identity

`parsing/` содержит Protocol, registry, config, diagnostics, runtime metadata и native adapters.
Tree-sitter Tree/Node разрешены только внутри parsing boundary; core/repository/IAM/Finding/
Evidence/Trace остаются language-neutral. `application/parse_repository.py` использует registry
и существующий workspace port; source reader, repository identity и path normalization не дублируются.
AST queries, visitors для extraction, IAM construction и semantic analysis отсутствуют.

`ParserRegistry` — instance с dependency injection, не mutable singleton. `register/get/supports/
supported_languages` возвращают deterministic language order; duplicate language/parser ID и
missing language дают typed errors. Для `.tsx` выбирается отдельный ParserLanguage.TSX;
RepositoryFile.language остаётся существующим TYPESCRIPT. `.jsx` обслуживает JavaScript grammar.
Список discovery extensions не расширен: `.mjs/.cjs` пока UNKNOWN.

Стабильные IDs: java-tree-sitter, typescript-tree-sitter, javascript-tree-sitter, tsx-tree-sitter.
ParserRuntimeInfo содержит implementation version 1.0.0, grammar package/version/ABI и runtime
package/version. Installed distribution metadata читается централизованно и кешируется; новая
runtime instance не меняет публичный parser identity.

FileParseMetadata ссылается на существующие SnapshotId и RepositoryFile (path, sha256/hash_status,
size и classification). Hash не пересчитывается. ParsedSourceFile — frozen dataclass с metadata и
native tree; JSON сериализует только metadata. Repository aggregate сохраняет snapshot fingerprint,
config, ordered outcomes, statistics, language stats и parser versions. Invariants проверяют
identity, ordering, counters и version consistency; metadata JSON round-trip поддержан.
Volatile timings, native node IDs и timestamps в result metadata не включены.

## Lifetime и memory

`ParseRepository.execute(snapshot, workspace)` возвращает ParseRepositoryResult **только с metadata**.
Он последовательно читает один eligible file, парсит, сохраняет metadata и освобождает tree.
Не сохраняются list[bytes] и syntax trees всего проекта. Native Tree-sitter Tree сам удерживает
source bytes, поэтому trees нельзя помещать в aggregate без увеличения memory по размеру проекта.

`iter_parse(snapshot, workspace)` выдаёт `ParsedSourceFile | FileParseMetadata`: tree для PARSED/
INVALID, metadata для SKIPPED/UNSUPPORTED/FAILED. Это будущий путь extraction: consumer обрабатывает
дерево текущего файла и переходит к следующему. Если consumer сохраняет все trees/list(iterator),
memory растёт с общим объёмом sources/trees; это его явный выбор.

Workspace принадлежит caller; parsing не закрывает переданный shared capability. Использовать его
внутри `DiscoverRepository.open()`. Source handles закрываются до выдачи tree. После закрытия
repository уже полученное дерево остаётся доступным, но нового file access нет. Для раннего выхода
закрыть iterator (`contextlib.closing`) и repository context. ZIP/Git temporary cleanup остаётся
ответственностью существующего intake context, включая strict mode и downstream exceptions.

```python
from contextlib import closing

from archguard.application.parse_repository import ParseRepository
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.factory import create_parser_registry
from archguard.parsing.models import ParsedSourceFile
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

source = RepositoryInput(source_type=RepositorySourceType.LOCAL, location="/path/to/project")
parser = ParseRepository(create_parser_registry())
with create_discovery().open(source) as repository:
    result = parser.execute(repository.snapshot, repository.workspace)
    with closing(parser.iter_parse(repository.snapshot, repository.workspace)) as outcomes:
        for outcome in outcomes:
            if isinstance(outcome, ParsedSourceFile):
                root = outcome.root  # future extraction receives the current syntax tree
```

## Selection, encoding и limits

Главный gate — RepositoryFile.analysis_eligible: binary/generated/large/docs/config/manifest и
excluded files не парсятся; TEST source files включены. Excluded files вообще отсутствуют в
inventory. Non-target source/UNKNOWN получают UNSUPPORTED diagnostic; остальное ineligible —
SKIPPED. Missing registry adapter даёт UNSUPPORTED без открытия file. Disabled dialect — SKIPPED.

ParserConfig: ordered enabled_languages (все четыре по умолчанию), max_source_file_bytes = 2 MiB,
collect_error_nodes = true, strict_syntax_errors = false, max_diagnostics_per_file = 100.
Override byte limit может дополнительно ужесточать выбор, но не возвращает eligibility excluded/
large files. Read ограничен limit + 1; adapters повторно проверяют flags/kind/dialect/extensions,
enabled language, byte size и agreement с RepositoryFile. NUL payload отвергается. POSIX safe
reader и concurrent change checks сохраняются из intake.

UTF-8 проверяется strict decode без replacement; native parser получает original bytes.
Invalid UTF-8 → FAILED / PARSER_DECODING_ERROR с byte position; следующий файл обрабатывается.
UTF-8 BOM не удаляется, offsets сохраняются; grammar root может начинаться после BOM.
UTF-16/other legacy encodings не конвертируются. Intake binary heuristic может исключить UTF-16
ещё до parsing. Unicode paths и Unicode source text покрыты tests.

## Diagnostics и modes

Internal cursor walk итеративный, посещает named/anonymous ERROR и missing nodes за O(tree nodes),
без visitor framework и recursion limits. `syntax_error_nodes` считает ERROR nodes;
`missing_nodes` — missing nodes отдельно; `syntax_error_files` считает файлы с любым из этих видов.

Диагностика имеет typed severity/code, generic message, relative path, one-based line и **UTF-8 byte
column**, optional start byte и exclusive end byte. Missing node — zero-width range. Это parser
coordinates, не semantic SourceLocation и не Finding. Source snippets/node.text не логируются.

| Code | Outcome |
| --- | --- |
| PARSER_SYNTAX_ERROR / PARSER_MISSING_NODE | tree + diagnostics |
| PARSER_UNSUPPORTED_LANGUAGE | UNSUPPORTED; no source read |
| PARSER_SOURCE_READ_ERROR | FAILED; reader отказал / source changed |
| PARSER_DECODING_ERROR | FAILED; invalid UTF-8 |
| PARSER_SOURCE_INELIGIBLE | FAILED при нарушении adapter guard |
| PARSER_RESOURCE_LIMIT | SKIPPED при metadata limit; FAILED при oversized payload |
| PARSER_EXECUTION_ERROR | FAILED; isolated adapter/runtime failure |
| PARSER_DIAGNOSTICS_TRUNCATED | WARNING после cap; node metrics остаются полными |

При collect_error_nodes=false detailed locations не собираются, но metrics и один summary
diagnostic сохраняются. При cap сохраняются максимум N node diagnostics + один warning.

Tolerant default: ERROR/missing nodes дают PARSED с diagnostics; весь repository продолжается.
Strict: такой tree сохраняется в streaming output, outcome INVALID и aggregate is_valid=false;
остальные files также обрабатываются. Strict не бросает aggregate exception. Source read/decoding/
adapter failure дают FAILED в обоих режимах. Aggregate is_valid означает отсутствие FAILED/INVALID,
не семантическую корректность проекта; UNSUPPORTED не делает stage execution invalid.

parsed_files включает PARSED + INVALID; invalid_files — subset parsed_files. SKIPPED, UNSUPPORTED,
FAILED — отдельные категории: total_files = parsed_files + skipped_files + unsupported_files +
failed_files. total_candidates — existing eligible inventory; attempted_files = parsed_files +
failed_files. Unknown languages могут быть UNSUPPORTED вне candidate count. Diagnostics находятся
в file outcomes; aggregate .diagnostics возвращает их плоское представление.

Adapter invocation — локальная failure boundary: unexpected Exception превращается в видимый
FAILED outcome и diagnostic, не подавляется молча. Логируются только type/code, не exception args,
которые могут содержать source. KeyboardInterrupt/SystemExit не перехватываются. High-level logs:
snapshot, language/status, attempts/parsed/skipped/unsupported/failed/syntax files и duration.

## Developer CLI и verification

```bash
uv sync --locked --extra dev
.venv/bin/archguard parse inspect tests/fixtures/parsing --json
.venv/bin/archguard parse inspect tests/fixtures/repositories/mixed_java_ts
.venv/bin/archguard parse inspect /path/to/project --strict --json
```

Intake options --source local|zip|git, --ref, --exclude, --no-gitignore сохранены. Сами parsing
adapters никогда не обращаются в сеть; при --source git сеть используется только intake.
JSON metadata идёт в stdout, logs/errors — stderr. Exit 0 — accepted result; 3 — FAILED/strict INVALID;
2 — intake/config error. Raw tree/source не выводятся. API endpoints и DB schema не изменены.

Offline tests: valid/invalid/empty/comment-only для всех dialects, реальные syntax constructs,
missing nodes, strict/tolerant, deterministic metadata, malformed UTF-8/Unicode/BOM, guards, caps,
registry conflicts, mixed eligibility, runtime/read failures и temporary lifecycle. Regression на
60 files проверяет один read на candidate, один active stream и освобождение всех tree handles
при metadata aggregate; большого benchmark или platform-specific timing assertions нет.

Проверено 2026-10-03: `make check` — 343 passed, 0 failed/skipped, coverage 96%, Ruff/format и
strict mypy green. Ручной CLI на каждой из четырёх grammar fixture directories: два parsed files,
один с намеренной syntax error, без FAILED. Existing mixed Java/TSX fixture: два parsed files,
без syntax errors. Docker image собран с locked dependencies; full metadata parsing fixtures
(8 parsed, 4 с намеренными syntax errors) и mixed fixture совпали с macOS при Linux runtime.
Одноразовые контейнеры удалены, Compose остановлен, volume PostgreSQL сохранён.

Ограничения: syntax-only, без name/type/import resolution; grammar release ограничивает новейший
language syntax; parsing sequential, без incremental cache/parallelism и отдельного CPU timeout.
Byte guard ограничивает input, но не заменяет sandbox native parser или hard AST memory quota.
Следующий этап: **PROMPT 004 — Symbol & Dependency Extraction → IAM Builder**.
