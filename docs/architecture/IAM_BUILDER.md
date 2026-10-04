# IAM Builder — v1.0.0 / IAM schema 1.0

Builder переводит compact facts + explicit resolution outcomes в настоящий `ArchitectureModel`.
Core/IAM не зависит от extraction. Отдельный `iam_building` зависит от core/IAM/extraction и не
импортирует Tree-sitter, инфраструктуру, БД или frameworks. Schema 1.0 сохранена: additive NodeKind
PROPERTY/TYPE_ALIAS используют существующие Symbol/node contracts. Layer остаётся None.

## Structural semantics и validation

PROJECT → Java source-group MODULE → PACKAGE prefixes → FILE → declaration nodes.
Для Java package `com.example` создаются `com` и `com.example`, default package имеет name
`<default>` и empty qualified package name. Это grouping исходников, не вывод Maven/Gradle modules.
ES каждый FILE имеет собственный MODULE (`es:<path>`), без Java-like packages. Namespace declaration
также NodeKind.MODULE, но имеет Symbol и принадлежит FILE/namespace declaration.
EXTERNAL_DEPENDENCY принадлежит PROJECT и не имеет SourceFile/Symbol.

Единственная containment convention v1: `node.attributes.parent_node_id` с UUID string у каждого
non-root node; `symbol.attributes.container_symbol_id` — parent declaration SymbolId либо null для
file-level declaration. MODULE/PACKAGE/FILE nodes ссылаются на реальные core entities; declaration
node — на соответствующий Symbol/SourceFile/module/package. FILE хранит относительный path,
language/parser dialect, reused SHA256 и syntax-error flag. Container links независимы от edges:
структурная вложенность не выдаётся за dependency.

Builder проверяет принадлежность facts snapshot inventory, canonical declaration keys, unique
identities, exact coverage references resolutions и наличие resolved targets. Core model проверяет
UUIDs, linked entities, languages/locations и endpoints. `validate_built_iam()` дополнительно
проверяет единственный root, parents, cycles, container/file consistency, one node per entity,
call/create target kinds, uncertain-binding rejection и explicit provenance. `serialize_iam()` повторяет validation, в том числе
после изменения вложенных attributes. Невалидная структура даёт IAMValidationError.

## Dependency semantics

| EdgeKind | Source → target |
| --- | --- |
| IMPORTS | FILE → internal FILE или external namespace/package; named bindings сохраняются в compact resolution facts |
| INHERITS | type declaration → explicitly resolved base declaration |
| IMPLEMENTS | class/type declaration → explicitly resolved interface/type alias |
| CALLS | enclosing declaration (или FILE для top-level call) → resolved method/function |
| CREATES | enclosing declaration/FILE → resolved class; implicit constructor symbol не создаётся |
| USES | enclosing declaration/FILE → resolved type из явной type/annotation syntax |

USES не извлекается из каждого identifier, generic DEPENDS_ON edges не генерируются.
Uncertain/external receiver calls не создают edges. Java import может указывать на declaration
при resolution, но IMPORTS edge всегда имеет file-level granularity. Multiple bindings одного
import между теми же файлами агрегируются так же, как calls; self-imports не замалчиваются.

Edge identity v1 = project UUIDv5 + source NodeId + target NodeId + EdgeKind, без callsite/line.
Один edge на тройку endpoints/kind; `occurrences` хранит число reference facts, `provenance` —
отсортированные source locations, reference kind, resolution status/method, extractor id.
`weight=1.0` не имитирует confidence и не заменяет occurrences. Primary source_location — первая
provenance location. Лимит per edge сохраняет первые N locations, точный `provenance_truncated` и
IAM_PROVENANCE_LIMIT diagnostic. Потеря деталей всегда явная; IDs не меняются от новых callsites.
Полный IAMBuildResult содержит все compact references/resolutions независимо от edge cap.

## Serialization и developer CLI

```bash
.venv/bin/archguard iam build tests/fixtures/extraction/mixed --namespace example-project
.venv/bin/archguard iam build /path/to/project --namespace stable-project-id --output /tmp/iam.json
.venv/bin/archguard iam build /path/to/project --json --strict
.venv/bin/archguard iam build project.zip --source zip --exclude '*.generated.ts' --no-gitignore
```

Intake flags `--source local|zip|git`, `--ref`, `--exclude`, `--no-gitignore` сохранены. Local/ZIP builds
offline; явно выбранный public HTTPS Git intake использует существующий clone adapter, extraction
никогда не ходит в сеть. `--json` stdout — IAMBuildResult с IAM, facts, resolutions, diagnostics,
statistics, parsing metadata и extraction config; `--output` — только ArchitectureModel JSON.
Логи идут в stderr. Exit 0 — valid (включая unresolved/tolerant incomplete), 3 — invalid partial
build (strict syntax/extraction/parsing failures), 2 — intake/config/output/IAM validation error.
CLI не создаёт API endpoints и не пишет IAM в БД. Output directory должен существовать.

Canonical artifact: UTF-8, ensure_ascii=false, sorted keys, indent=2, trailing newline; collections
отсортированы по canonical UUID/identity. Metadata содержит schema, snapshot fingerprint/id,
project namespace, parser/extractor/resolver/builder versions, configs, statistics и completeness.
Нет timestamp, duration, absolute root/temp path, native AST, source bytes или source snippets.
Parser runtime metadata — версии packages/grammar ABI, не OS-specific details.
Snapshot fingerprint используется для reproducibility, не для persistent symbol IDs.

Repeated build неизменного fixture обязан дать byte-identical artifact; другой root и Linux/macOS
тоже. Изменение source hash/coordinates/config закономерно меняет artifact при сохранении IDs.
IAMBuildResult JSON проходит Pydantic round-trip, artifact — ArchitectureModel round-trip.
Исходный текст не сохраняется; type/default literal values редактируются в signatures. Paths,
identifier names и explicit module specifiers являются structural metadata и не анонимизируются.

## Validation evidence и пределы этапа

Tests: реальные Java/TS/JS/TSX/mixed fixtures, explicit imports/aliases, overload ambiguity,
shadowing/dynamic unknowns, package/nested hierarchy, heritage/type uses, source privacy,
UTF-8/CRLF, identity stability/rename, bounded provenance, invalid graph rejection и weakref
streaming на 48 файлах. Ручная CLI/Docker проверка описана в `docs/architecture/IAM_VERIFICATION.md`.

IAM — syntax-based intermediate model, не доказательство runtime зависимости. Нет architecture
rules/findings, graph metrics/NetworkX/projections, LLM/Hybrid implementation, Security Engine,
compiler/typechecker/LSP, frontend, persistence tables или analysis endpoints. Следующий этап:
**PROMPT 005 — Architecture Specification & Static Conformance Foundation**.
