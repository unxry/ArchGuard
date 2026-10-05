# Graph Engine — PROMPT 006

`AnalyzeGraph` переиспользует intake → streaming AST → extraction → conservative resolution → IAM.
`GraphAnalyzer` принимает только IAM, typed config и optional validated spec. NetworkX находится
только внутри `architecture/graph`; public Pydantic models не содержат NetworkX/AST/raw source.
IAM не изменяется. `architecture check` строит IAM один раз и объединяет четыре static rules с
explicit graph ARCH003; graph analyze не запускает static rules.

## Dependency projections

Directed `A → B`: A depends on B. Default relations: IMPORTS, INHERITS, IMPLEMENTS, CALLS, CREATES,
USES; explicit empty projection relation set допустим. Future IAM kinds отклоняются.
External nodes и projected self-edges по default исключены; config может включить их для discovery.
Graph conformance всегда internal, без self-edges. Singleton self-loop не считается cyclic SCC.

| Projection | Mapping |
| --- | --- |
| component | CLASS/INTERFACE/ENUM/FUNCTION и file-linked namespace MODULE; members → nearest owning component |
| file | File-linked nodes → actual IAM FILE |
| package | Actual Java `SourceFile.package_id`; TypeScript/TSX не получают guessed packages |
| layer | Independent explicit target layer classification |
| module | Independent explicit target module classification; не IAM core module identity |

File IMPORTS могут перейти к component только при ровно одном component в файле; иначе остаётся
residual FILE node. Unowned top-level dependencies также сохраняют FILE endpoint. Ambiguous
target classification инвалидирует result; unmatched endpoints исключены с отдельным счётчиком.
PACKAGE_LANGUAGE_UNSUPPORTED делает смешанный/TS package result incomplete, сохраняя Java часть.

Aggregation — одна directed graph edge на endpoint pair. Сохраняются actual IAM edge IDs,
relation kinds, endpoints, occurrences, known locations, bounded provenance и truncation counts.
Допускаются только confirmed RESOLVED proofs с known resolution method и repository-relative
location соответствующего source file; external proofs требуют EXTERNAL_PACKAGE. Unknown/ambiguous
proof исключается с diagnostic. Усечённый proof сохраняет известную часть и помечает incomplete.
Projection не выполняет resolution и не создаёт transitive/semantic edges.

## SCC и explicit ARCH003

NetworkX SCC partition канонически сортируется. Cyclic SCC имеет минимум два узла. На SCC
выдаётся одна deterministic representative cycle: canonical start по label/ID, reverse BFS внутри
SCC, shortest closing route с canonical tie order. `simple_cycles` не используется. Trace содержит
повторный start; при превышении trace budget observation помечается truncated без partial proof,
ARCH003 не создаётся. Это dependency cycle, не execution trace.

Без spec/enabled `circular_dependency` output содержит observations, metrics и optional candidates,
без findings. Explicit rule использует собственные projection/relations независимо от discovery
config. Valid rule + valid IAM/classification + closed proof → один GRAPH ARCH003 Finding на SCC.
Severity берётся из spec, confidence отсутствует. ARCHITECTURE_RULE и GRAPH_PATH evidence содержат
rule hash, SCC members, representative edges и IAM provenance. Trace node/edge refs относятся к
projected conformance graph; metadata содержит underlying IAM IDs. Этот graph экспортируется
в nested conformance context, даже если discovery projection отличается.

Finding UUIDv5 зависит от project, normalized rule scope и sorted SCC membership, не line numbers,
severity или количества occurrences. Graph/component IDs опираются на actual IAM IDs; aggregate
scope/edge/SCC IDs versioned UUIDv5. Changed topology/selection может изменить identity.

## Paths и neighbourhood

`shortest_path(graph, source, target)` — directed BFS, canonical UUID tie order, None для disconnected,
typed error для unknown node. `neighbourhood(graph, origin, hops, direction, max_nodes)` — bounded
IN/OUT/BOTH traversal, origin включён, induced edges и IAM references экспортируются. При budget
truncation указан flag. Caller передаёт `config.max_neighbourhood_nodes`; default utility cap 1,000.
Это domain query API, без новых transport endpoints/CLI subcommands/LLM consumers.

## Typed configuration и canonical output

`graph analyze ... --config config.json`: bounded UTF-8 JSON ≤128 KiB, unknown fields запрещены.
`--projection`/`--relations` override config. Candidate thresholds описаны отдельно.

| Field | Default |
| --- | --- |
| max_graph_nodes / max_graph_edges | 10,000 / 100,000 |
| calculate_betweenness / betweenness_node_limit | true / 1,000 |
| calculate_pagerank | true |
| pagerank_alpha / pagerank_tolerance / pagerank_max_iterations | 0.85 / 1e-10 / 200 |
| max_cycle_trace_length | 256 nodes, включая повторный start |
| max_neighbourhood_nodes | 1,000 |

Node/edge budget overflow возвращает typed resource diagnostic и empty invalid graph, без partial
complete claim. Skipped centrality, convergence failure, truncated trace/provenance и incomplete IAM
отражаются diagnostics и completeness. Подтверждённые findings сохраняются при incomplete coverage;
invalid conformance не выдаёт findings. Root COMPLETE — processing status, не architectural quality.

Reproducibility содержит project/snapshot/IAM fingerprints, spec hash, engine/NX versions, полный
config и projection/config hashes. Canonical JSON sorted, без clocks/absolute roots/source fragments.
Только computed metrics и candidate metric evidence округляются до 12 decimal places при export;
config и thresholds сохраняются точно, internal computations не округляются. SHA/IDs используют
normalized configuration, relation order/duplicates не влияют. Operational logs идут отдельно.

## Boundaries и limitations

Runtime NetworkX locked 3.7, dev stubs types-networkx 3.6.1.20260911; Python 3.13.
[NetworkX installation](https://networkx.org/documentation/stable/install.html),
[package metadata](https://pypi.org/project/networkx/).
Нет SciPy/Pandas; PageRank реализован uniform power iteration для dependency graph.
Betweenness exact, unweighted; большие graphs пропускают его по node budget. Выбранные budgets
не являются wall-clock guarantee. Dense SCC output bounded одной cycle, но graph/provenance export
остаётся O(nodes + edges + retained proofs). Intake и resolver limits действуют раньше graph budgets.

Conservative resolution ограничивает semantic recall; missing edges не восстанавливаются.
Component ownership отражает syntax containment, не business responsibility. Package — только Java.
Target scopes path-based; unclassified endpoints уменьшают охват. Raw source, LLM/Hybrid scoring,
embeddings, inferred target architecture, health score, Security, persistence, analysis API и frontend
не реализованы. Следующий этап после review — PROMPT 007 либо исправления PROMPT 006.1.

См. [Metrics](GRAPH_METRICS.md), [Candidates](GRAPH_CANDIDATES.md),
[Verification](GRAPH_VERIFICATION.md), [ADR 0013](adr/0013-graph-projections-and-bounded-evidence.md).
