# ADR 0011: Compact extraction facts, stable identity, conservative resolution

Status: accepted. Stage: PROMPT 004.

## Context

Parsing streaming contract выдаёт native AST одного файла; IAM должен быть language-neutral,
reproducible и пригоден для будущего Static Conformance без guessed dependencies. SnapshotId
меняется при любом content edit и поэтому непригоден как namespace persistent symbol identity.

## Decision

Language-specific syntax extractors создают immutable compact facts, освобождая дерево до следующего
файла. Общий index/resolver работает без AST, source reads, compiler services и исполнения кода.
Mapping в IAM выполняет отдельный builder; core/IAM не импортирует extraction.

IDs — UUIDv5 от постоянного repository/project namespace и canonical relative-path/kind/qualified
name/signature identity. Строки и fingerprint входят только в locations/reproducibility metadata.
Java имеет source-group module и packages, ES — file modules; hierarchy хранится в одной проверяемой
attributes convention. Additive PROPERTY/TYPE_ALIAS сохраняют IAM schema 1.0 contracts.

Resolution categoric: RESOLVED / AMBIGUOUS / UNRESOLVED / EXTERNAL, с explicit method. Только unique
проверяемые bindings дают symbol edges. Unknown receiver types, wildcard guesses и overload type
inference не используются. External nodes обозначают namespace/package, не придуманные classes.
IMPORTS file-level; other relations declaration-level. Aggregate edge identity — endpoints/kind,
все occurrences сохраняются в bounded provenance с явным count/truncation diagnostic.

## Consequences

Меньше recall, зато отсутствуют edges из unique-name guesses. Local binding scope блокируется
консервативно; tsconfig/re-export chains/inheritance dispatch/compiler semantics остаются за рамками.
Для разных repositories caller обязан выбирать разные стабильные namespaces. Сдвиг строк сохраняет
IDs, но меняет locations/JSON; same fixture при одинаковом config даёт одинаковый artifact на macOS/Linux.
RAM — AST одного файла плюс compact facts/index/IAM, а не все source trees одновременно.
