# Architecture Specification v1

Stage: PROMPT 005. Target architecture — explicit проверяемые ограничения автора проекта.
Actual architecture — существующий language-neutral IAM, построенный из синтаксиса и conservative
resolution. Target spec не дописывает layers, modules или guessed dependencies в actual IAM.

## DSL

```yaml
version: "1.0"
architecture:
  layers:
    - name: presentation
      include: ["**/controller/**"]
      exclude: ["**/controller/generated/**"]
    - name: application
      include: ["**/service/**"]
    - name: persistence
      include: ["**/repository/**"]
rules:
  - id: ARCH002
    type: layer_dependency
    from: presentation
    allow: [application]
    allow_same_layer: true
    severity: high
    enabled: true
```

`version` должен быть строкой `"1.0"`. `architecture` обязателен; `layers`, `modules` и `rules`
по умолчанию пусты. Scope задаёт `name`, непустой список `include`, optional `exclude` и `description`.
Names: ASCII letter, затем letters/digits/`_`/`.`/`-`, максимум 128 символов. Names уникальны отдельно
в layers и modules; одинаковое имя в разных dimensions допустимо. Неизвестные fields запрещены.
YAML использует только aliases `from`/`to`; Python models имеют attributes `source`/`target`.

Каждый rule принимает `severity` (info/low/medium/high/critical, без учёта регистра; default medium),
`enabled` (boolean, default true), optional description, непустой `relations` (default six IAM
dependency kinds). v1 разрешает один экземпляр каждого builtin ID: ARCH001/002/004/005, максимум
четыре rules. ID должен соответствовать type; произвольные rule IDs и SEC IDs не принимаются.
Повторные IDs, unknown references, empty allow/deny, одновременные allow и deny запрещены.
Disabled rules тоже проходят schema/reference validation.

## Classification и globs

Matching выполняется на repository-relative POSIX `SourceFile.file_path`, case-sensitive на всех
OS, независимо от absolute checkout path. `*`, `?`, `[abc]`, `[!abc]` действуют внутри одного segment;
целый segment `**` поглощает ноль или больше segments. Например `**/controller/**` включает
`controller/A.java` и `src/shop/controller/A.ts`; `controller/*.java` не включает nested file.
Patterns без implicit anchoring: весь path должен совпасть. Hidden segments не имеют особой семантики.
Absolute paths, drive prefixes, backslashes, NUL, пустые/`.`/`..` segments и `a**` запрещены;
максимальная длина pattern 512 символов.

Файл matches scope при любом include и отсутствии любого exclude. Нет priorities/first-match wins.
Два matches в одной dimension дают `AMBIGUOUS_LAYER_MATCH` или `AMBIGUOUS_MODULE_MATCH` и invalid
classification. Любые findings такого analysis подавляются. Возможный overlap без actual matching
file не ищется заранее: DSL validation проверяет структуру, classification — фактические paths.

FILE и declarations, включая nested members и file-linked namespaces, наследуют file classification.
Java package/source-group MODULE и ES structural MODULE без file link, PROJECT, PACKAGE и EXTERNAL
исключены. IAM core module identity не подменяется target module name. Layer и module независимы;
файл может иметь оба. Unmatched node остаётся UNCLASSIFIED, accepted и учитывается в статистике.
Rule не проверяет endpoint, у которого отсутствует нужная dimension. Status node вычисляется из
candidate lists; JSON хранит candidates и unique layer/module assignment.

## Четыре правила

| ID / type | Constraint | Violation |
| --- | --- | --- |
| ARCH001 / forbidden_dependency | `from: {layer: domain}`, `to: {layer: infrastructure}` | Actual edge from exact source scope to exact target scope |
| ARCH002 / layer_dependency | `from: presentation`, `allow: [application]` либо `deny: [persistence]` | Source layer matches; classified target violates allow/deny |
| ARCH004 / reverse_dependency | `expected: {from: application, to: domain}` | Exact reverse edge domain → application |
| ARCH005 / module_boundary | `from: orders`, `deny: [payments]` либо `allow: [shared]` | Source target-module matches; different classified target-module violates constraint |

ARCH001 selector содержит ровно один из layer/module; dimensions endpoints могут различаться.
ARCH002 same-layer edges разрешены по default `allow_same_layer: true`; false запрещает их.
Эта явная same-layer policy имеет приоритет над allow/deny. ARCH005 same-module edges всегда allowed.
ARCH004 требует разные declared layers; YAML order/имена/вес edges не определяют направление.
Rules ограничивают только указанный source; неуказанные directions allowed. Например layered-clean
проверяет presentation → application, но не вводит отдельный запрет service → repository.
ARCH003 требует cycle/path analysis и отклоняется как unsupported до будущего Graph Engine.

Default relations: IMPORTS, INHERITS, IMPLEMENTS, CALLS, CREATES, USES. Future IAM relation kinds
не принимаются DSL v1. Каждый rule может сузить этот set; duplicates/order нормализуются.
External dependencies исключаются. Это explicit scope foundation, без package security policy.

## Safe loading и reproducibility

Runtime PyYAML 6.0.3 используется для bounded events и representation nodes, без object construction.
Loader запрещает aliases и anchors (включая alias bombs), custom/Python tags, merge keys, duplicate
mapping keys, non-string keys, timestamps и non-finite floats. JSON-like scalar/seq/map tags допустимы
только на соответствующих node kinds; числовые scalars — decimal. Source — valid UTF-8.
Default limits: 128 KiB, depth 32 collections, 10,000 scalar/collection nodes. File adapter читает
не более byte limit + 1. Limits проверяются перед representation composition. Не читаются env,
другие files, network; expressions/scripts не исполняются. Parser errors sanitised, без YAML/source
fragments, с optional one-based line/column. Errors typed: invalid specification, unsupported
version/rule, resource limit. Schema errors не экспортируют pydantic input values.

Нормализуются scope/rule order, include/exclude/allow/deny/relations sets и severity. Canonical
normalized model (JSON, aliases, sorted keys, UTF-8) → SHA-256. Comments/formatting/order irrelevant;
description и semantic constraints входят в fingerprint. Loader pure, file access только в
`infrastructure.architecture_specification`; модели/spec validation/classification не импортируют
repository adapters, parsers, extraction, database или transport.

Примеры: [layered-clean](../../examples/architecture/layered-clean.yaml),
[layered-strict](../../examples/architecture/layered-strict.yaml),
[modular](../../examples/architecture/modular.yaml).
Primary API reference: [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation).
