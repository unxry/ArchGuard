# Symbol & Dependency Extraction — v1.0.0

```text
RepositorySnapshot + workspace → ParseRepository.iter_parse()
  → Java / TypeScript / JavaScript / TSX LanguageExtractor
  → immutable, language-neutral ExtractedFileFacts
  → SymbolIndex → SymbolResolver → IAMBuilder → ArchitectureModel 1.0
```

`BuildIAM` получает injected parser coordinator, extractor registry, resolver и builder.
Каждый extractor читает только tree текущего файла. Никаких filesystem/network/process/compiler
services внутри extraction/resolution/builder нет. Исходный код никогда не исполняется.
`ParseRepository.execute()` по-прежнему возвращает только metadata; `iter_parse()` сохраняет
streaming contract. Coordinator освобождает ParsedSourceFile после extraction и закрывает
iterator даже при исключении. Между фазами остаются compact facts и parser metadata, без
Tree/Node/bytes/source/snippets. SymbolIndex индексирует эти facts; IAM не мутируется экстракторами.

## Реальная поддержка

| Dialect | Declarations и syntax facts |
| --- | --- |
| Java | package; обычные/static/wildcard imports; class/record, interface/annotation type, enum, nested types; method/constructor/field; visibility/modifiers/annotation names; generic parameters; extends/implements; calls/new/type uses |
| TypeScript | class/interface/enum/type alias/namespace; method/constructor/property; function, named arrow/function expression; parameter types/modifiers; imports с aliases/default/namespace, exports/re-exports; extends/implements; calls/new/type uses |
| JavaScript | classes/methods/properties/functions/named arrows; ES imports/exports, basic static CommonJS require и exports; calls/new |
| TSX | TypeScript extraction, JSX не становится architectural symbol/node |

Anonymous ES functions/callbacks и Java anonymous class bodies пропускаются без synthetic symbols.
Local types/functions и computed method names дают `EXTRACT_UNSUPPORTED_CONSTRUCT`; локальные
bindings сохраняются для блокировки ложного resolution.
Dynamic calls/import/require остаются UNRESOLVED с metadata/diagnostics. Re-exports дают module
IMPORTS dependency, но цепочки re-export bindings не разрешаются. COMMONJS поддерживает top-level
named/destructured bindings и явные `exports.name = local` / `module.exports = {local}` / default
identifier export; нет исполнения require и анализа произвольных вычисляемых assignments.
Enum constants/record components/implicit constructors/accessor properties не синтезируются.

## Facts, identity и координаты

Frozen Pydantic models содержат RepositoryFile из исходного snapshot (hash не пересчитывается),
declarations, imports, exports, reference candidates, source locations, shadowed names,
diagnostics, syntax-error flag и versioned parser/extractor metadata. Типы не содержат native AST.
Контейнеры обязаны существовать в том же файле, containment acyclic; locations совпадают с file path.

Declaration identity v1 — canonical JSON tuple из relative POSIX path, neutral language, NodeKind,
qualified name и normalized parameter signature. Java top type: `package.Type`, nested type:
`package.Outer.Inner`, member: `container#name(signature)`; default package не получает фиктивный
префикс. ES top declaration: `path::name(signature)`, nested: `container#name(signature)`.
Signatures сохраняют типы параметров; значения default/annotation arguments/string literals
не сохраняются, literal types обозначаются `literal`. Это сознательная потеря distinctions:
несовместимые duplicate identities дают ошибку extraction, а не случайный UUID.

ProjectId — UUIDv5 фиксированной схемы и namespace; при наличии RepositoryId он имеет приоритет,
иначе используется `ExtractionConfig.repository_namespace` (CLI `--namespace`). Для разных реальных
репозиториев задавайте разные постоянные namespaces: общий default предназначен для локальных
experiments. SymbolId/NodeId зависят от project namespace и declaration identity, FileId — от path и
language. Абсолютный root, fingerprint, строки, timestamp не участвуют в IDs. Вставка строк и изменение
другого файла сохраняют identity; rename/signature/kind/container change меняют её. Новый snapshot
меняет reproducibility metadata, а координаты могут менять artifact bytes при сохранении IDs.

Tree-sitter использует byte columns и exclusive end. Общий converter выдаёт one-based UTF-8 byte
columns и inclusive end, совместимые с SourceLocation; CRLF/Unicode покрыты tests. Не интерпретировать
column как Unicode character index. Zero-width missing nodes пропускаются.

## Conservative resolution

| Status | Значение / effect |
| --- | --- |
| RESOLVED | Один явно доказуемый internal target; разрешён соответствующий IAM edge |
| AMBIGUOUS | Несколько candidates; target не выбирается, edge отсутствует |
| UNRESOLVED | Недостаточно информации/unsupported/dynamic/shadowed; edge отсутствует |
| EXTERNAL | Явно известный namespace/package вне snapshot; только definite imports создают external node/edge |

Методы: EXACT_QUALIFIED, EXACT_IMPORT, SAME_FILE, SAME_PACKAGE, EXPLICIT_RELATIVE_MODULE,
UNIQUE_CONTAINER, STATIC_QUALIFIED, EXTERNAL_PACKAGE; NONE означает отсутствие доказательства.
Числовой confidence отсутствует. Same-file уникальные functions, current-container methods,
Java exact imports/same package/qualified types/static methods, ES relative exported bindings и
namespace functions разрешаются через index. Arity отсекает несовместимые overloads, но не выводит
типы аргументов: два overloads одинаковой arity остаются AMBIGUOUS. Static class-qualified calls
требуют `static`. Java/ES между собой не связываются.

`service.execute()` не разрешается по имени execute, даже если во всём проекте такой method один.
Parameter/local/field/property/reassigned bindings затеняют имена и блокируют guesses; блокировка локальных
bindings применяется ко всему enclosing declaration, поэтому возможны false negatives до binding
или вне вложенного блока. Не выводятся runtime receiver types, inheritance dispatch, polymorphism,
control flow, function-constructor semantics, decorators/DI, JSX components, Maven/Gradle source sets или tsconfig aliases.
Wildcard imports не выбирают unique global candidate. Relative module resolution лексическая:
explicit path либо `.ts/.tsx/.js/.jsx` и index files. Несколько существующих candidates дают AMBIGUOUS;
никакого tsconfig/Node extension priority, filesystem reads или package downloads на этой фазе.

Java external identity — syntactic import namespace prefix (например `java.util`), без выдуманных Maven coordinates.
ES bare specifier даёт npm package root (`@scope/pkg/subpath` → `@scope/pkg`); `node:path` — отдельный
node ecosystem. Missing relative file остаётся UNRESOLVED. External function/class nodes не создаются.
EXTERNAL не считается ошибкой и не превращается в fictional CALLS/CREATES.

## Errors и bounds

Tolerant parsing позволяет извлечь корректные части дерева вне ERROR/missing subtrees, ставит
`source_had_syntax_errors=true`, `is_complete=false`. Strict parser status INVALID по умолчанию
пропускается (`skip_invalid_files=true`); configurable retention не отменяет parser invalid result.
Failure одного extractor даёт sanitized diagnostic без exception args/source и не мешает другим
файлам. Missing registry entry и fact count limit дают typed diagnostics и `is_valid=false`.
Обычный UNRESOLVED/AMBIGUOUS не fatal и не architecture finding.

ExtractionConfig ограничивает declarations/imports/references на файл и provenance на edge.
ParseRepository ограничивает bytes на файл. Нет глобального лимита IAM размера: память первой фазы
ограничена AST одного файла плюс O(all compact facts), второй — O(index + facts + IAM + provenance).
Resource-limit extraction failure отбрасывает facts целого файла, не выдаёт их за полный результат.

`is_complete` отражает полноту syntax extraction: false для syntax errors, diagnosed omissions,
unavailable supported sources и unsupported source languages. Это не обещание semantic completeness
или 100% resolution. Statistics `resolution_rate` = internal RESOLVED / all reference candidates,
включая imports и EXTERNAL; по умолчанию CLI выводит raw status counts вместо смешанного процента.
