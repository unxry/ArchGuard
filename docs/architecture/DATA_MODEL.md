# Future database contract

Foundation предоставляет PostgreSQL-compatible SQLAlchemy 2.x Base, явный lazy engine/session
factory и Alembic environment. Application tables, ORM records и initial revisions отсутствуют.
Нет persisted demo data. См. [ADR 0006](adr/0006-deferred-persistence.md).

Будущие таблицы появляются по реально реализованным сценариям:

| Таблицы | Ownership / назначение |
| --- | --- |
| projects | логические ProjectId и конфигурация проекта |
| repositories | source origin, ProjectId, repository identity, approved intake configuration |
| analysis_runs | AnalysisId, ProjectId/repository revision, status, timestamps, schema/config/software versions |
| architecture_nodes | AnalysisId + stable NodeId, kind, names, typed attributes и location references |
| architecture_edges | AnalysisId + EdgeId, endpoints в том же snapshot, kind, projection provenance |
| architecture_specs | versioned target architecture, layer/module definitions |
| architecture_rules | versioned constraints и references на specs; не каталог fake rule outputs |
| findings | AnalysisId + FindingId, schema version, namespace, rule, detector, severity/confidence |
| finding_evidence | evidence provenance/properties с сохранением namespace и позиции |
| finding_locations | primary/related roles, path, validated source coordinates |
| finding_traces | TraceId/step order/node/edge/location links в пределах snapshot |
| graph_metrics | projection/config version, metric definitions, measured values |
| llm_requests | provider/model/parameters, context provenance/hash, token/cost/runtime audit |
| llm_results | schema-validated outputs, status/errors и source request |
| experiment_runs | immutable reproducibility manifests, split/method/config identities |
| experiment_cases | stable evaluation units, dataset/repository identity и case matching keys |
| ground_truth | reviewed ARCH labels, taxonomy, provenance, adjudication/version |
| reports | artifact metadata, source run IDs и generation/version information |

Foreign keys для nodes/edges/trace используют AnalysisId совместно с entity ID: stable NodeId
может повторяться в разных снимках. Проект/repository/run owns пути и версии, finding namespace
indexed/filterable; нельзя агрегировать ARCH и SEC в одну Architecture F1. JSON/JSONB используются
для действительно расширяемых attributes/properties, не вместо обязательных ключей и constraints.

Domain models не являются ORM classes. Future adapters явно map records ↔ versioned envelopes.
Unit-of-work boundaries принадлежат application use cases; transactions не проходят через domain.
Version comparison, artifact retention, idempotency и jobs требуют отдельных lifecycle решений
при их реализации. LLM audit не должен сохранять credentials; source-context storage требует
явных retention/redaction правил. Схема security-specific storage добавляется только при
реализации Security после CORE THESIS COMPLETE. Neo4j не нужен для foundation.
