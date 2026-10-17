# Возможность → интерфейс → интеграционная граница

Дата: 17 октября 2026. Backend evidence: [full audit](FULL_PRODUCT_CAPABILITY_AUDIT.md). UI evidence: `src/catalog.js`, `src/views.js`, `src/adapters.js`, `src/graph.js`, `src/core.js`, `src/contracts.d.ts`. «Есть» ниже означает существующий код поверхности/адаптера, не пройденный end-to-end browser test.

## Матрица C01–C15

| ID / возможность | Entry point и journey | Есть в текущем UI | Контракт / adapter | Что требует отдельной реализации |
| --- | --- | --- | --- | --- |
| C01 Local/ZIP/Git | Projects → new project → source → CLI plan | Source validation helpers/quoted command; demo/result entry surfaces | `adapters.validateGit`, `validatePath`, `command`; backend RepositoryInput→RepositorySnapshot | Actual browser upload/clone/native path access, intake execution, resolved revision |
| C02 Parsing | Projects → pipeline → parser policy | Pipeline stages, strict/respect-ignore configuration surface | Backend `ParseRepositoryResult`; no parser-specific result view | Inventory/exclusion diagnostics and parsed/failed/unsupported counts from real run |
| C03 IAM | Import → Atlas → select node/relation | IAM and IAMBuildResult branch; graph DTO | `importArtifact` → WorkspaceDTO nodes/edges; backend `ArchitectureModel` | Resolution coverage drilldown, complete entity tree, provenance-rich IAM edge inspector |
| C04 Rules/validation | Models → Rules → ARCH rule → Findings | Four catalog families, rule-to-finding action surface, generic Finding evidence | Static import root `findings[]`; `FindingDTO` and `evidenceView` | YAML editing/validation/check run; scope classification UI; robust composite import |
| C05 Projections/graph | Atlas → relation/direction → node/edge → inspector | Graph renderer, zoom/fit/focus, cluster controls, node list, demo scale 12/40/216, inspector | GraphAnalysisResult→NodeDTO/EdgeDTO; `Graph` class; imported graph max 500 nodes | Reprojection from IAM, server queries, metric/SCC inspector and shortest-path picker |
| C05 Proof/path | Select relationship → source evidence | Directed relation selection/highlight; proofs retained on EdgeDTO | `graph.edges[].proofs[]`, relative locations | Full retained proof/occurrence/truncation presentation; no runtime playback assertion |
| C06 Structural signals | Models catalog / Findings | Demo candidate semantics and ARCH101–105 descriptions | Backend root `candidates[]`, not Finding[] | Dedicated candidate adapter/list/threshold & metrics inspector for imported graph |
| C07 Discovery | Import discovery → Atlas / Models → Discovery | Nested graph imported; `raw.discovered` escaped JSON view; synthetic assignment view | ArchitectureDiscoveryResult `graph.graph`, `discovered` | Structured roles/strength/conflicts, module membership, matrices and edge-linked cells |
| C08 Context | Models → Context/Hybrid → budget preview | Budget inputs/preview surface; manifest shape recognized | ContextManifest selected nodes/evidence/fragments refs; no project/IAM identity | Actual manifest inspector, target selection/context rebuild, SourceReader integration |
| C09 Semantic AI | Models → semantic rules / AI channel | AI unavailable explanation and rule catalog | Backend AIAnalysisResult exists; no complete result UI established | Read-only candidate assessment adapter, valid evidence refs, explicit provider integration; no browser secret handling |
| C10 Hybrid | Import → Models → Context/Hybrid | Case/result structural validation branch and channel description | HybridAnalysisResult, ordered case/bundle/feature/decision arrays | Detailed imported case review, supporting/contradicting/missing refs, feature & policy explanations |
| C11 Security catalog | Models Rules / Security → SEC001–010 | Version-aware result import, rule coverage rows, finding evidence/proof rail | SecurityAnalysisResult or SecurityReportSection → WorkspaceDTO | General scan CLI/API, source intake bridge, full framework/summaries/call-resolution inspector |
| C11 Security investigation | Select rule → outcome/scope → finding → evidence | Separate result scope and evidence, known/unknown proof steps; unavailable source state | SecurityFinding evidence_ids/flow_path; safe text rendering | Evidence strength and execution coverage must stay separately visible; no unsupported safe promotion |
| C12 Narrow certificate | Security → SEC008 scope → certificate disclosure | Synthetic certificate explanation; imported zero findings conservatively partial | Backend CompletenessCertificate/map_v3_outcome; import does not authenticate certificate | Provenance-bound reported certificate view, exact grammar/invalidators; no repo-wide negative |
| C13 System connection | Runs → connect system | Connection surface and fixed loopback bridge | `dev-server.cjs` → `/health` + `/api/v1/system/info` → LIVE_SYSTEM_ONLY | No capability escalation to analysis; real API acceptance tested separately |
| C14 Runs/config | Projects demo → Runs → session activity | Session state/newRun record; demo config/history/compare surface | `core.js:A.newRun`, `A.state.runs`; no server persistence | Immutable persisted runs, cancel/retry/status service, cross-run compatibility |
| C14 Export/report | Atlas/Findings/Security/Runs → export JSON | Local Blob JSON download helper | `core.js:A.download`; current local result/view model | Canonical engine report/HTML/PDF service, storage/share/auth; local export not a backend report |
| C15 Research | Models → Capabilities | Explicit research-only boundary | Public CLI inventory only | No operational research UI intended; no benchmark data import/efficacy metrics |

## Общие UI возможности и ограничения

| Surface | Implementation | Meaning / check |
| --- | --- | --- |
| RU/EN | `src/i18n.js`, `catalog.js` localized text; locale preference in `core.js` | Product prose translated; identifiers/paths/rule IDs remain technical values |
| Local/demo provenance | WorkspaceDTO project mode LOCAL_DEMO/LOCAL_RESULT; service LIVE_SYSTEM_ONLY separate | Import must replace demo data; service connection must not silently reclassify dataset as live analysis |
| Findings search/filter | `views.js:A.filterFindings`, filters, reset surface | Namespace/status/severity/query; null severity remains unrated; empty filtered list distinct from whole-project clean |
| Evidence rendering | `views.js:evidenceView`, `core.js:A.escape` | No imported HTML; source unavailable unless actually supplied; demo snippets explicitly synthetic |
| Atlas scaling | `graph.js:A.syntheticGraph`, `A.Graph`; 12/40/216 controls in `views.js:atlas` | Stress UI geometry, not measured engine capacity; imported model size is independent |
| Accessibility primitives | Graph node list, aria labels, live region, reduced-motion preference | Browser keyboard/focus/contrast acceptance remains separate; attributes alone do not prove accessibility |
| Safe import | `adapters.js:importArtifact`, bounded structure/reference validation | Prototype validation, not cryptographic authenticity or exhaustive backend parity; file-size gate must be verified at file-reading handler |
| Preferences | `core.js:A.pref` | Locale/motion only local preference storage, not source/result persistence |

## Integration gates by action

1. **Open imported result:** local JSON validation and DTO transformation. No backend required; prove with the real CLI fixture.
2. **Explore existing graph:** browser-local search/filter/layout. Backend recomputation is a separate action; keep original projection/provenance.
3. **Validate spec / discover / build context:** existing Python callables, but no HTTP route. Show CLI plan or explicit unavailable state until an adapter exists.
4. **Run Security:** internal bytes/context API only. A generic graph CLI plan is not a Security scan command.
5. **Run AI/Hybrid:** live AI opt-in and offline Hybrid have different contracts. No implicit provider request from UI preview/import.
6. **Fetch source:** relative location is evidence, not source contents or read authorization. Source endpoint/revision binding missing.
7. **Save/share/assign/suppress:** no product contracts. Local session activity and download cannot stand in for collaboration or persistence.

## Required browser acceptance (planned here)

- Import `tests/fixtures/architecture-graph.json`: 3 nodes/4 directed IMPORTS edges, one cycle observation, no confirmed cycle finding, correct projection and source locations; demo replaced.
- Import `architecture-check.json`: one ARCH001 HIGH finding with null confidence, no fabricated full graph; source unavailable state and exact evidence locations.
- Reject stale/unsupported shape, invalid endpoint/UUID/proof, contradictory counts, unsafe path/source pack; preserve current dataset on failure.
- Distinguish discovery nested graph, GraphConformanceResult composite, and context/Hybrid standalone artifacts. Do not join context by UUID alone.
- Verify keyboard/selection, RU/EN, graph filter/direction, zero-findings partial Security, motion reduction, narrow viewport and local export. These checks must be recorded after execution; this matrix does not assert they passed.

## Final implementation reconciliation

The final coverage report supersedes intermediate gap notes: composite GraphConformanceResult, structural candidates, actual edge proof/metrics/cycles and imported context/Hybrid/discovery now have dedicated read-only presentations and fixture tests. C09 standalone AI result import remains unsupported; source execution, spec editing, lifecycle/auth/persistence and research workflows remain gated. Browser/bridge receipts are in VALIDATION.md. Catalogue source paths were corrected to actual application/architecture/iam_building modules.
