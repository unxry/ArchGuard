# ADR 0008 — Physical repository contract and managed workspace lifecycle

Status: accepted · Stage: Repository Intake & Source Discovery

## Context

Parsing требует metadata и ленивого доступа к source files. IAM описывает extracted entities,
а не физические файлы. Хранение всех contents в snapshot растёт с размером проекта.

## Decision

RepositorySnapshot schema 1.0 отдельно от IAM, POSIX relative paths и no serialized absolute root.
Application зависит от RepositorySource/RepositoryWorkspace ports. Local source — read-only view;
ZIP/Git — controlled temporary copies. execute() возвращает durable inventory, open() сохраняет
lazy readers в context; cleanup закрывает descriptor handles и только owned temporary copies.
POSIX no-follow access и skip-all-symlinks policy защищают source reads. Content fingerprint
назначает SnapshotId; persistent RepositoryId принадлежит будущему owner.

## Consequences

Нет eager source-content RAM и premature database tables. Local sources не копируют гигабайты,
но не дают atomic filesystem snapshot; concurrent changes обнаруживаются per-file stat checks,
caller обеспечивает спокойное состояние repository. ZIP/Git bytes доступны только до context exit.
В дальнейшем parser use case должен держать workspace lifetime открытым. Windows adapter требует
отдельного решения: реализация использует POSIX descriptor semantics macOS/Linux.
