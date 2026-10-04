# ADR 0007 — Typed UUID and versioned snapshots

Status: accepted · Stage: Foundation v1

## Context

IDs должны сериализоваться, быть тестируемыми и поддерживать сравнение версий без mutable counters.
Имена могут совпадать между modules/languages/overloads, а line offsets меняются при редактуре.

## Decision

UUID + NewType для static typing; nil UUID запрещён validation. Caller назначает ProjectId и
AnalysisId/FindingId (обычно UUIDv4), не domain constructor. NodeId/EdgeId могут строиться UUIDv5
в ProjectId namespace по canonical parser-owned identity с type discriminator. Schema envelopes
versioned independently from application version; lockfile фиксирует resolved dependencies.

## Consequences

IDs повторяемы при стабильной canonical identity, scoped по project/entity kind. NewType не
является runtime wrapper, поэтому aggregate checks защищают ссылки. Canonical identity policy
конкретного parser должна быть versioned; renames и semantic matching требуют future comparison.
Schema version изменения требуют совместимости/migration review. Docker image digests и runtime
patch versions будущих measured runs записываются в reproducibility artifacts.
