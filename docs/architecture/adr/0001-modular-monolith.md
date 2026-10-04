# ADR 0001 — Modular monolith + analysis worker boundary

Status: accepted · Stage: Foundation v1

## Context

Исследовательская система развивается многими этапами. Микросервисы сейчас потребовали бы
transport contracts, orchestration и эксплуатацию до появления реального pipeline.

## Decision

Один Python package с явными API/application/domain/infrastructure boundaries. Domain зависит
только от stdlib/Pydantic и внутренних domain modules. Future worker — отдельный entrypoint
того же modular monolith, с AnalysisId/revision/versioned config на job boundary.
Очередь, Redis и Celery не добавляются. API code находится в `src/archguard/api`; `apps/api`
фиксирует deployable boundary без дублирования package.

## Consequences

Модульные contracts можно проверять локально и reuse в worker. Composition root связывает
adapters, domain не знает HTTP/ORM. Долгие анализы нельзя будет выполнять в API request thread;
job lifecycle/delivery решаются при реализации orchestration, не имитируются сейчас.
