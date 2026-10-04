# ADR 0006 — Defer application persistence tables

Status: accepted · Stage: Foundation v1

## Context

Project и AnalysisRun storage lifecycle ещё не определены реальным intake/analysis use case.
Создание многочисленных tables сейчас закрепило бы неподтверждённую схему и domain/ORM coupling.

## Decision

SQLAlchemy 2.x Base с naming conventions, lazy engine, transaction-scoped sessions,
PostgreSQL/psycopg configuration и Alembic online/offline environment. Application tables,
ORM records и initial revisions отложены. Future table families описаны в DATA_MODEL.md.
SQL parameters скрыты engine configuration; credential URL не логируется и не возвращается API.

## Consequences

Health/system endpoints работают без БД. Domain не зависит от ORM. Alembic работает с пустой
metadata и может создавать только свою bookkeeping table. Первые project/repository/run records
и migrations появляются в соответствующем use case; no-op application migration не создаётся.
PostgreSQL connection/integration нужно проверять в среде с работающим сервером.
