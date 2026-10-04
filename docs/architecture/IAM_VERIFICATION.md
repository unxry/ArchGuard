# PROMPT 004 — verification report

Проверено 2026-10-04. Этап Symbol & Dependency Extraction / IAM Builder завершён.

1. Реализованы syntax extraction, compact facts, SymbolIndex, conservative resolution, IAM builder,
   structural validation, canonical serialization и developer CLI `archguard iam build`.
2. Pipeline: streaming Parser → Extractor → compact facts → release current tree → global Index →
   Resolver → Builder. Ни facts, ни IAM не содержат native AST/source bytes.
3. IAM schema 1.0 сохранена; extractor/resolver/builder versions 1.0.0. Additive kinds PROPERTY/TYPE_ALIAS.
4. Languages: Java, TypeScript, JavaScript, TSX; JSX tags не создают architectural declarations/nodes.
5. Declarations: class/interface/enum, nested types, function/method/constructor, field/property,
   type alias и namespace. Java package/imports и ES imports/exports сохраняются как facts.
6. Relations: IMPORTS, INHERITS, IMPLEMENTS, CALLS, CREATES, USES. Generic DEPENDS_ON не генерируется.
7. Resolution требует scope/import/container evidence и unique target; same-arity overloads,
   неоднозначные relative modules, unknown receivers, dynamic expressions и shadowed bindings
   не дают guessed edges. Java и ES не соединяются по совпадению имени.
8. Mixed reference statistics: resolved **9**, ambiguous **0**, unresolved **1**, external **3**.
   Отдельные ambiguity fixtures реально дают AMBIGUOUS (см. таблицу), без guessed CALLS.
9. NodeId/SymbolId: UUIDv5 project namespace + relative path/language/kind/qualified name/signature.
   Namespace берётся из RepositoryId либо explicit config. Строки, root, fingerprint, timestamp и
   uuid4 не входят в persistent identity. Class rename меняет ID; сдвиг строк/другой файл — нет.
10. EdgeId: UUIDv5 project namespace + source/target NodeId + EdgeKind; новые callsites ID не меняют.
11. Canonical edge сохраняет occurrence count и ordered provenance locations/methods/extractor id.
    Три callsites реально сохраняются в одном edge с тремя locations. Cap имеет explicit truncation.
12. Полный `make check`: **424 passed, 0 failed, 0 skipped** = 343 прежних + 81 новых тестов.
    Meaningful coverage включает identity, extraction, aliases/static calls, ambiguity, shadowing,
    reassignment, external packages, new-arrow rejection, structural validation, serialization,
    provenance, offline/no-source-execution и streaming weakrefs на 48 ParsedSourceFile.
    Regression tests воспроизвели и закрыли serialization Java generic/type annotation arguments.
13. Coverage существующего workflow (statements + branches): **92.67%** total;
    extraction **89.53%**, iam_building **86.17%**, BuildIAM **96.91%**. Настройки не ослаблены.
14. `uv sync --locked --extra dev`, Ruff, format (160 files), strict mypy (98 source files) — green.
    `git diff --check` — green. Git index пуст: весь проект пока untracked, поэтому обычный diff
    пустой. Дополнительно проверены реальные stage files через `git diff --no-index --check`.
15. Реальные CLI builds всех пяти language/mixed fixtures выполнены, результаты ниже. Все valid;
    tolerant/incomplete и strict-invalid outcomes отдельно покрыты тестами.
16. Image `archguard:extraction-004` пересобран из `docker/Dockerfile` с `uv sync --locked`.
    Linux ARM64 run: read-only filesystem/fixture, network none, отдельный tmpfs output; не
    использует user source как исполняемый код. macOS/Linux NodeIds, EdgeIds и весь IAM JSON совпали.
17. `cmp iam-a.json iam-b.json` и `cmp iam-a.json iam-linux.json` завершились с exit 0.
    SHA256 всех трёх artifacts:
    `0e72c2515e82fa1e7fcce65d698370accb0ed490d56534f1f830c0fc69143c57`.
    Temporary IAM artifacts удалены. Проверены отсутствие /Users paths, Docker /fixture paths,
    raw source/tree fields и случайных backup/conflict/debug markers. UI reference byte-identical.
18. Не реализованы architecture specification/rules/findings, graph engine/metrics, LLM/Hybrid,
    Security Engine, IAM persistence, analysis endpoints и production frontend. API health
    contracts/DB volumes не изменялись. Нет commits/reset/checkout/clean.
19. Основные изменения: `extraction/`, `iam_building/`, `application/build_iam.py`, streaming config
    accessor/type в ParseRepository, CLI, additive NodeKind values; tests/fixtures и boundary test;
    README, EXTRACTION/IAM_BUILDER/PARSING docs и ADR 0011. Ограничения: нет compiler/type inference,
    tsconfig aliases, re-export chain resolution, runtime dispatch, function-constructor semantics;
    conservative shadow scope может снижать recall. Результат — syntax IAM, без semantic completeness claim.
20. Следующий этап: **PROMPT 005 — Architecture Specification & Static Conformance Foundation**.
    В рамках PROMPT 004 он не реализован.

## Manual CLI results

Команда для каждого fixture: `.venv/bin/archguard iam build tests/fixtures/extraction/<fixture> --json`.
Files = успешно извлечённые файлы; references включают imports и type-use candidates.

| Fixture | Files | Declarations | Imports | References | Resolved | Ambiguous | Unresolved | External | Nodes | Edges |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Java | 11 | 35 | 3 | 21 | 13 | 2 | 5 | 1 | 56 | 12 |
| TypeScript (+ module ambiguity JS file) | 8 | 27 | 6 | 19 | 13 | 2 | 3 | 1 | 45 | 10 |
| JavaScript | 5 | 7 | 5 | 12 | 8 | 0 | 3 | 1 | 19 | 7 |
| TSX | 1 | 3 | 1 | 2 | 1 | 0 | 0 | 1 | 7 | 2 |
| Mixed Java + TS + TSX | 5 | 8 | 5 | 13 | 9 | 0 | 1 | 3 | 22 | 9 |

Имена/kinds/types/relative paths являются structural metadata и не анонимизируются. External Java
namespace — syntactic import prefix, без Maven artifact coordinates; npm namespace — package root,
node builtins отдельны. CALLS/CREATES для external functions/classes не выдумываются.
