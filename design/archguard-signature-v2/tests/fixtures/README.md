# Safe offline architecture import fixtures

Авторский fixture создан для P039; реальные пользовательские репозитории и private/research fixtures не использованы. В `architecture-mini` три TypeScript-модуля и четыре статических import:

- `src/ui/controller.ts` → `src/domain/service.ts`, `src/data/repository.ts`;
- `src/domain/service.ts` → `src/data/repository.ts`;
- `src/data/repository.ts` → `src/ui/controller.ts`.

Классы намеренно пустые: source не исполняется, `IMPORTS` — единственный тип рёбер. Spec запрещает presentation → persistence по ARCH001/HIGH. В ней нет ARCH003: цикл остаётся observation, а не cycle finding.

## Реальные CLI exports

Созданы штатным backend CLI в текущем worktree, Python 3.13 из существующего project venv, с `PYTHONPATH` на `src` этого worktree. `.env` не читался; Settings и provider не создавались; сетевых/provider вызовов нет. Команды для воспроизведения из корня репозитория (`ARCHGUARD_PYTHON` — путь к установленному project Python):

```sh
PYTHONPATH=src "$ARCHGUARD_PYTHON" -m archguard.cli graph analyze design/archguard-signature-v2/tests/fixtures/architecture-mini --projection file --relations IMPORTS --namespace archguard:signature-v2-fixture --output design/archguard-signature-v2/tests/fixtures/architecture-graph.json
PYTHONPATH=src "$ARCHGUARD_PYTHON" -m archguard.cli architecture check design/archguard-signature-v2/tests/fixtures/architecture-mini --spec design/archguard-signature-v2/tests/fixtures/architecture-mini/architecture.yaml --namespace archguard:signature-v2-fixture --output design/archguard-signature-v2/tests/fixtures/architecture-check.json
```

| File | Реальный результат | Exit | SHA-256 |
| --- | --- | --- | --- |
| `architecture-graph.json` | COMPLETE, file projection, 3 nodes, 4 edges, 4 import proofs, 1 SCC/cycle observation, 3 metric records, 0 findings/candidates | 0 | `fa5a3a6740758673345bf0c49f475ee967170760bde5f01c74ceff25f3a1341b` |
| `architecture-check.json` | NON_CONFORMANT, valid/complete, 1 ARCH001 HIGH finding, confidence null | 1 (ожидаемое нарушение) | `72f481536d67ead4763f539c46820c0e538cb4160aca488007a2e2364220d9db` |

Проверено 17 октября 2026 (Europe/Moscow): `GraphAnalysisResult.model_validate_json`, `StaticConformanceResult.model_validate_json`; точные counts/relations/proofs; общий project ID и IAM fingerprint; relative source locations; отсутствие `/Users/`, `/home/`, `file://`. Повторные реальные CLI runs с `--json` дали stdout побайтно равный сохранённым `--output` файлам. Эти проверки подтверждают engine → artifact; browser importer проверяется отдельно.

## Точные field routes для browser importer

**Graph artifact** — `GraphAnalysisResult`, не непосредственный graph:

- discriminator: `result_schema_version === "1.0"` и `graph.graph_schema_version === "1.0"`; одного top-level version недостаточно;
- status: `status`, `is_valid`, `is_complete`; projection: `graph.projection.projection`;
- nodes: `graph.nodes[]` → `id`, `label`, `kind`, `iam_node_ids[]`, `locations[]`;
- edges: `graph.edges[]` → `id`, `source_id`, `target_id`, `relation_kinds[]`, `proofs[]`;
- evidence: `graph.edges[].proofs[]` → `iam_edge_id`, `source_node_id`, `target_node_id`, `relation`, `locations[]`, `provenance[]`, `occurrences`, `provenance_truncated`;
- file/line: `locations[].file_path`, `.start_line`, `.start_column`, `.end_line`, `.end_column` (one-based, optional ends null);
- metrics: `metrics[]` join by `node_id`; cycles: `cycles[].node_ids`, `.edge_ids`, `.truncated`; SCC: `sccs[]`;
- confirmed findings: `findings[]`; structural candidates: `candidates[]`; neither contains the cycle observation in this fixture;
- identity: `graph.project_id`, `reproducibility.iam_fingerprint`, `.snapshot_fingerprint`, `.configuration_fingerprint`, `.projection_fingerprint`;
- warnings/coverage: `diagnostics[]`, `projection_statistics`, `statistics.metrics_skipped`.

**Static check artifact** — `StaticConformanceResult`: no `analysis_kind`, no nested full graph. Root `findings[0]` carries `id`, `rule_id`, `severity`, `confidence:null`, `primary_location`, `related_locations`, `evidence[]`, `trace`, `detector`, `metadata`. Rule scope comes from `specification_summary`; per-node target assignment from `classification.nodes[]`; `status` is NON_CONFORMANT. Match to the graph using `reproducibility.project_id` and `reproducibility.iam_fingerprint`, not filename or array index.

For a future discovery import, graph nodes are at **`graph.graph.nodes`** because `ArchitectureDiscoveryResult.graph` is itself a GraphAnalysisResult. Do not apply that nesting to this standalone graph fixture.

## Additional final verification

`tests/generate_cli_fixtures.py` reproducibly generates IAM, discovery, source-free context, offline Hybrid, structural candidates and composite check artifacts from the same authored mini-project. Candidate threshold=1 is explicit synthetic test configuration, not a recommended production threshold. The composite fixture adds explicit ARCH003 and therefore has two findings; the original graph-only cycle stays an observation. All eight architecture JSON artifacts passed browser file-input import. The three `security-*.json` artifacts are authored V2 model instances (supported / potential-incomplete / empty-partial), accepted by the real SecurityAnalysisResult model; they are not analyzer execution receipts.
