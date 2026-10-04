# ADR 0003 — Unified Finding / Evidence / Trace

Status: accepted · Stage: Foundation v1

## Context

Разные модели ArchitectureViolation/SecurityIssue/AIProblem ломают совместимость UI/reporting
и затрудняют audit смешанного архитектурного метода.

## Decision

Одна versioned Finding schema с namespace, typed detector provenance, evidence collection и trace.
Evidence также имеет namespace: generic LLM/graph evidence сохраняет принадлежность pipeline.
Severity — значимость; optional Confidence — detector score с явным calibration status/reference.
Trace — ordered contiguous path steps. Pydantic frozen snapshots с tuple collections и JsonValue maps.

## Consequences

Общие storage/report/UI contracts работают для ARCH и SEC, но не смешивают decisions/metrics.
Каждый finding требует evidence, namespace/rule/detector agreement. Не появляются выдуманные
confidence probabilities. JSON metadata shallow mutable; ownership и repeated validation на
execution boundaries обязательны. Это осознанный предел frozen Pydantic, описанный в CONTRACTS.
