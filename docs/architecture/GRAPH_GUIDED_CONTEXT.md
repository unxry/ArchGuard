# Graph-guided context v1

`GraphGuidedContextBuilder` потребляет actual IAM, соответствующий `GraphAnalysisResult`,
safe `RepositoryWorkspace` через структурный `SourceReader` port и optional spec/discovery.
Контекст строится локально; vendor SDK, filesystem и network в intelligence domain отсутствуют.
IAM, Graph и Discovery сохраняют source-free contracts.

## Стратегии и выбор

- `LOCAL_ONLY`: декларация выбранного IAM node, bounded соседние строки и relevant metadata.
- `GRAPH_GUIDED`: k-hop IN/OUT/BOTH через существующий `graph.algorithms.neighbourhood`.
  Фильтруются individual dependency proofs, затем aggregate relation kinds; IMPORTS не
  становятся CALLS из-за объединения пары endpoints. Метод отображается в component owner,
  но его собственный source range сохраняется первым.
- `EXPANDED_BASELINE`: bounded набор component declarations из исходной projection без
  graph pruning, target первым, остальные по UUID. Это сравнение контекстов, не full-repo dump.

Приоритет GRAPH_GUIDED: target → direct outgoing → direct incoming → selected cycle members →
другие k-hop nodes; distance и UUID разрешают ties. Nodes вне выбранного radius не добавляются.
Cycles/metrics относятся к исходной полной projection; relation filtering меняет только selection
и dependency evidence. Это явно указано в `GRAPH_METRIC.metric_scope`.

Default: 1 hop BOTH, 20 nodes, 10 files, 20 fragments, 4000 chars/fragment, 20000 context chars,
120 lines/fragment, 2 before/after lines, 65536 bytes/line, 32 MiB scan/file. Hops ограничены 8,
nodes/files/fragments — 1000. Configuration typed; unsupported dependency relations запрещены.
Пример: [graph-guided.json](../../examples/ai/graph-guided.json).

## Фрагменты и бюджеты

Reader открывает только eligible repository-relative POSIX paths через существующий safe workspace.
Нет произвольного filesystem reader, исполнения проекта или повторного parsing. Каждый выбранный
файл открывается один раз за pack, streaming reader прекращает чтение после последнего необходимого
range либо scan/line/character limit. Для метода в середине файла reader проходит предшествующие
строки, но не загружает и не сохраняет весь файл. Line ranges inclusive, columns не обрезаются;
отсутствующий declaration end означает bounded point window.

Overlapping ranges одного файла объединяют subject references в приоритетном фрагменте,
не расширяя его за бюджет. Budget overflow сначала удаляет низкоприоритетные metadata evidence,
затем последние source fragments; последний target fragment сокращается, при необходимости
исключается. Даже JSON envelope и selected IDs входят в `max_total_chars`; source JSON escaping
учитывается. Если остаётся слишком много selected IDs, удаляются последние nodes.
Manifest сообщает truncation и dropped counts. EOF сам по себе не truncation.

`SourceFragment` существует transient: text + typed reference с path/range/language/purpose/node IDs,
SHA-256 выбранного UTF-8 текста и chars. Optional `ContextRedactor` меняет текст до fingerprint;
его versioned ID записывается. По умолчанию redactor отсутствует, secret detection не заявляется.
Line alignment redactor проверяется: изменение числа newline или ошибка redactor исключают
fragment с sanitized diagnostic вместо экспорта source или неверных координат.

## Traceability и fingerprint

Source-free `ContextManifest` содержит конфигурацию, выбранные nodes/distance/reason,
fragment references/hashes, bounded metadata evidence, counts/diagnostics и fingerprint.
Он никогда не содержит `SourceFragment.text`. Pack валидирует совпадение references, hashes,
chars и общего размера serialized untrusted data. Source inspection/export разрешён только
явным CLI `--show-source`; обычные JSON/result/request metadata не экспортируют source pack.

Evidence IDs локальны pack: `SRC001`, `DEP001`, `ARC001`, `DISC001`, `GRAPH001`.
Dependency evidence ссылается на реальные projected/IAM edge IDs, endpoints, relations,
locations и aggregated occurrence/provenance status. Оно не утверждает дополнительных resolution facts.
Normalized target constraints выбираются существующим classifier только для relevant scopes;
disabled/unrelated rules и raw YAML/descriptions исключаются. DSL по-прежнему допускает пять
уникальных builtin rules; тест с двадцатью duplicate rule IDs означал бы invalid spec.
Discovery передаётся как `HYPOTHESIS`, `normative=false`, с role/layer strengths и selected module
namespace/strength. Она не превращается в target architecture.

Fingerprint SHA-256 зависит от context schema, target, normalized selection configuration,
selected node descriptors, fragment references/hashes, реально включённой metadata и redactor ID.
Whole snapshot/IAM/Discovery fingerprints не входят в этот fingerprint. Изменение unselected
source без изменения включённой структуры/metadata не меняет fingerprint; изменение relevant
metrics/constraints/hypotheses меняет его даже при неизменном выбранном source.
Версии prompt/schema учитываются отдельно в logical semantic candidate identity.

`context_chars` — Unicode characters canonical serialized **untrusted data**, включая JSON metadata
и source escaping. Это не tokens и не bytes. System instructions, task и output schema учитываются
при optional exact request token counting, но не в этом context character budget.
Unknown token budget measurement отражается диагностикой; анализ с token cap требует exact
provider/tokenizer preflight count и пропускает вызов, если count unavailable. Приблизительные
tokens/4 не вычисляются.

Контекст детерминирован при одинаковых actual inputs/config. Ответ реальной модели таким свойством
не обладает. Проверки и фактические fixture measurements: [PROMPT 008 verification](../verification/PROMPT_008.md).
