# ADR 0002 — Language-neutral IAM

Status: accepted · Stage: Foundation v1

## Context

Java и TypeScript имеют разные AST, offsets и declaration semantics. Аналитика и evidence
не должны зависеть от конкретного parser toolkit.

## Decision

Versioned IAM envelope с typed entities, nodes/edges и общими SourceLocation/UUID contracts.
Graph projections логически независимы: dependency/call/data-flow/security. Parser adapters
отвечают за canonical identity, overloads, source offset conversion и provenance.
Default package допускает пустое qualified_name. External nodes могут не иметь location.

## Consequences

Добавление parser не требует менять Finding. Snapshot integrity проверяется при создании.
Нейтральная модель не сохраняет весь language-specific AST; действительно дополнительные
сведения допускаются в JSON attributes. Parsing, extraction и projection algorithms отсутствуют.
