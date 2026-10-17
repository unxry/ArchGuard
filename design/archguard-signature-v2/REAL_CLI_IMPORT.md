# Real CLI artifact import

Choose **Projects → Import result** or **New project → CLI result**. Select one JSON file up to 5 MiB. All reading occurs in tab memory; no upload or automatic command execution. Failed validation leaves the previous dataset intact. A successful import atomically replaces the demo and records a session entry. Export returns the original imported JSON, unchanged semantically.

## Supported viewing contracts

| Contract | Canonical discriminator | Display |
| --- | --- | --- |
| GraphAnalysisResult | result_schema_version 1.0 + graph.graph_schema_version 1.0 | Nodes, relation/proof geometry, metrics, cycles, findings, uncalibrated candidates and thresholds |
| ArchitectureModel / IAMBuildResult | iam_schema_version 1.0 / iam.iam_schema_version 1.0 | Static nodes/edges and source references; no invented classification |
| StaticConformanceResult | result_schema_version 1.0 + classification + reproducibility | Actual findings/evidence; no-graph state |
| ArchitectureCheckResult | analysis_kind architecture_check | Independently decoded GraphConformanceResult plus static findings; aggregate consistency |
| ArchitectureDiscoveryResult | analysis_kind architecture_discovery | Nested full graph and role/layer hypotheses, strengths/conflicts, evidence, module candidates and matrix details |
| ContextManifest | context_schema_version 1.0 | Target, selected nodes, budgets, source-free fragment references/hashes and diagnostics; no cross-graph join |
| HybridAnalysisResult | result_schema_version hybrid-analysis-v1 | Cases, decisions, policy/calibration state, missing references, evidence bundles/features; no fabricated LLM verdict |
| SecurityAnalysisResult / SecurityReportSection | namespace SEC / domain SECURITY | Version-aware coverage, separate SecurityFinding, proof/unknown flow, evidence and reported certificate details |

Not supported as direct product imports: arbitrary JSON, raw ContextPack with source, AIAnalysisResult standalone, parser/inventory reports, benchmark/calibration outputs. Their actual CLI/library availability is described in Models → Capabilities. The demo JSON export is a labelled showcase export, not a canonical backend interchange format.

Validation is deliberately bounded prototype validation, not authenticated provenance or complete backend-equivalent validation. Unknown fields retained in canonical metadata do not become verified proof. Claimed confidence is never synthesized. Security evidence strength and candidate thresholds are distinct from confidence/severity.

## Verified fixture lineage

`tests/fixtures/architecture-mini` is authored TypeScript, never executed. Initial graph/static CLI runs produced 3 graph nodes, 4 IMPORTS edges, one cycle observation and one separate ARCH001 finding. `tests/generate_cli_fixtures.py` subsequently ran IAM, discovery, source-free context, offline Hybrid, configured structural candidates and composite ARCH001/ARCH003 check using that same repository. Expected nonconformance exit is 1; successful analysis exits 0. No `.env` or paid provider invocation.

All eight architecture artifacts were imported through the real browser file input. Three Security V2 fixtures are authored model instances, not analyzer runs; each was accepted by the actual SecurityAnalysisResult Pydantic model and browser importer. See fixture README, adapter tests and browser report. Imported display text remains original backend text and is not translated as if authored UI copy.
