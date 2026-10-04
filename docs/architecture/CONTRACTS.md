# IAM / Finding contracts v1.0

Application version — `archguard.__version__` (0.1.0); IAM envelope — `iam_schema_version="1.0"`;
Finding envelope — `finding_schema_version="1.0"`. Envelopes reject unknown versions and fields.
Enum/field changes требуют явного review совместимости, а breaking changes — новой schema version
и migration. JSON Schema доступна через Pydantic `model_json_schema()`; round trips проверены тестами.

## Общие правила

`DomainModel` — Pydantic frozen snapshot, extra fields forbidden, finite numbers only;
nested model instances revalidate. Collections — tuples. UUID NewType даёт статическое разделение
NodeId, EdgeId, FindingId, AnalysisId, ProjectId и IDs остальных сущностей; JSON хранит UUID strings.
Nil UUID запрещён. Runtime NewType не отличает UUID разных категорий: aggregate checks проверяют
referential integrity. Никаких global counters и implicit random IDs.

`attributes`, `properties`, `metadata` — `dict[str, JsonValue]`, не `Any`. Это расширяемые JSON
карты, не место для ORM objects, SDK responses или произвольных Python objects. Frozen относится
к полям модели; вложенные JSON карты не deeply immutable. Не мутировать их после валидации и не
использовать snapshots как hash keys. Перед передачей между execution boundaries сериализовать
и повторно валидировать. При изменении snapshot создавать новую модель через `model_validate`;
`model_construct` и `model_copy(update=...)` обходят валидацию и не предназначены для untrusted data.

Typed fields хранят обязательные семантические данные. JSON metadata не заменяет namespace,
severity, confidence, identifiers или source location. UI не получает raw settings/database URL.

## IAM

| Model | Семантика |
| --- | --- |
| Project | логическая система; ID сохраняется между снимками |
| Module | часть Project; module boundary не определяется здесь эвристически |
| Package | namespace внутри Module; пустое qualified_name разрешено для default package |
| SourceFile | repository-relative path, language, module и optional package |
| Symbol | declaration в SourceFile; signature различает перегрузки |
| ArchitectureNode | graph representation; optional links к module/package/file/symbol |
| ArchitectureEdge | relation между существующими NodeId, optional location, nonnegative weight |
| ArchitectureModel | versioned snapshot с uniqueness/referential consistency checks |

NodeKind и Language нейтральны относительно AST Java/TypeScript. Parser adapters будут приводить
языковые конструкции к IAM; отсутствие точного соответствия обозначается UNKNOWN и provenance.
External dependencies разрешены как nodes без source location. Self-loops и parallel edges
разрешены: edges имеют собственные IDs, а cycle analysis ещё отсутствует. Source/target IDs
обязательны; aggregate отвергает dangling endpoints. `weight=1.0` — вес relation, не confidence.

Node module/package/file/symbol links, если заданы, должны совпадать с entities snapshot.
Symbol location соответствует своему SourceFile. Неизвестный language node допускается;
известный language linked node должен соответствовать файлу. Source text и AST не хранятся здесь.

`stable_node_id(project_id, identity)` / `stable_edge_id(...)` — UUIDv5. Canonical identity
предоставляет будущий parser/extractor: language, module-relative path, qualified declaration,
signature; для edge — endpoints, relation и call-site discriminator. Line offsets сами по себе
не подходят для declaration identity. Переименования не гарантируют сохранение ID: version
comparison в будущем сопоставляет изменения отдельным механизмом.

## SourceLocation

Repository-relative canonical POSIX path; абсолютные, Windows-style, parent traversal,
пустые сегменты и `.` запрещены. Line/column — строгие integers ≥1, включая end. End coordinates
задаются парой и не предшествуют start в lexicographic order. End inclusive; без end это точка.
Колонки считаются по Unicode code points; future parsers конвертируют byte/UTF-16 offsets.
Location относительна repository snapshot, который задаётся analysis envelope/storage owner.

## Finding / Evidence / Trace

Finding содержит ID, namespace, rule/category, title/description, severity, optional confidence,
locations, хотя бы одно evidence, optional trace, versioned detector, recommendation и metadata.
`rule_id` — namespace + ровно три ASCII digits (`ARCH002`, `SEC001`); catalog membership сейчас
не enforced, чтобы schema не зависела от реализации будущих правил. Все evidence имеют namespace
finding и уникальные внутри finding IDs. DetectorSource обязан соответствовать namespace.

Evidence несёт ID, namespace, type, message, location и typed JSON properties. ARCH evidence
не принимает reserved security types. Generic GRAPH_PATH/SOURCE_CODE/LLM_RESULT могут использоваться
SEC pipeline, но сохраняют SEC namespace. Поэтому даже SEC LLM_RESULT не поступает в Hybrid.

Trace содержит ID и хотя бы один шаг. Sequence начинается с 1, строго упорядочена и непрерывна;
неверный порядок не исправляется молча. Relation шага описывает входящее ребро; NodeId/EdgeId и
location опциональны для ещё не сопоставленного внешнего source/sink. Label обязателен. Привязка
trace IDs к конкретному IAM в будущем проверяется analysis envelope, standalone trace не знает графа.

Severity INFO/LOW/MEDIUM/HIGH/CRITICAL — значимость. Confidence.score — конечное число [0,1];
`not_calibrated` по умолчанию означает detector score, не вероятность. `calibrated` требует
calibration_reference на зафиксированный calibration artifact; uncalibrated запрещает такую
ссылку. `Finding.confidence=None` означает отсутствие оценки; численная псевдоточность не вводится.

## Hybrid boundary

`ArchitectureEvidenceBundle`: AnalysisId, static/graph/semantic evidence и уже подтверждённые
deterministic findings. Static channel принимает STATIC_RULE/SOURCE_CODE/ARCHITECTURE_RULE;
graph — GRAPH_PATH/GRAPH_METRIC; semantic — LLM_RESULT. Все элементы ARCH. Подтверждённые
findings имеют STATIC source. `ArchitectureDecision` принимает только ARCH findings.
`HybridDecisionEngine` — Protocol, без implementation/scoring/fusion. Future implementation
обязана сохранять deterministic findings и соответствующий AnalysisId; LLM не может их отменить.
Это postcondition будущего engine, алгоритм сохранения результатов сейчас не имитируется.

Основные библиотеки: [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/),
[SQLAlchemy sessions](https://docs.sqlalchemy.org/en/20/orm/session_basics.html),
[Alembic tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html).
