# UI capability coverage — final V2

Public product audit completed across repository intake, parser/extraction, IAM, conformance/specifications, graph/discovery/context/semantic/Hybrid, Security, CLI, API and infrastructure boundaries. AST inventory is breadth evidence, not a claim of line-by-line review of every module. Detailed implementation/test references are in `audit/` and `FULL_PRODUCT_CAPABILITY_AUDIT.md`.

All 15 catalogue categories have a deliberate UI entry point or explicit integration boundary. This is **not 100% backend execution coverage**. Browser execution of analysis, durable project/job lifecycle, authentication and source access remain unavailable. Existing system API alone is integrated live.

| ID | Backend / invocation | UI / component | Contract and verified coverage | Remaining boundary |
| --- | --- | --- | --- | --- |
| C01 | DiscoverRepository; repo inspect, Local/ZIP/Git | Projects / onboarding.js | Source selection, validation, quoted CLI plan, explicit gate; browser tests | No browser clone, extraction, folder scan or inventory API |
| C02 | ParseRepository; parse inspect, strict/ignore options | Projects configuration / Models capabilities | Java/TS/JS/TSX capability explained; demo config retained | Parser execution/diagnostic report view needs adapter; Python unsupported |
| C03 | BuildIAM / IAMBuilder; iam build | Atlas / adapters.js, graph.js | ArchitectureModel and wrapper recognized; real IAM imported | Full symbol tree/resolution diagnostics not specialized UI; original result retained |
| C04 | static conformance + GraphConformanceResult; architecture validate/check | Models Rules + Findings + Atlas | Real static ARCH001 and composite ARCH001/003 artifacts, evidence/locations; adapter/browser tests | No spec editor/validator endpoint; classification retained but no dedicated editor |
| C05 | GraphAnalysisResult; graph analyze | Atlas / graph.js, artifacts.js | Real nodes/edges/proofs, metrics/cycle inspection, direction/filter/search/zoom, clustering | No browser re-projection or shortest-path engine; imported fingerprints unverified |
| C06 | GraphCandidate ARCH101–105; configured thresholds | Findings / adapters.js, evidenceView | Real threshold export → 3 candidates; no severity/confidence invented; metric/threshold details | Production threshold editing/rerun needs job adapter |
| C07 | ArchitectureDiscoveryResult; architecture discover | Models Discovery / artifacts.js | Real components, role/layer strength/conflicts, evidence and module/matrix details | Hypotheses are not accepted target architecture; matrix detail is JSON, not graphical editor |
| C08 | GraphGuidedContextBuilder; ai context | Models Context / artifacts.js | Real source-free manifest, budgets/fragments/selected nodes; browser import | Demo budget preview is a bounded list only; no graph-guided computation/source retrieval in browser |
| C09 | SemanticArchitectureAnalyzer; ai analyze opt-in/dry-run | Models rule catalogue and AI gate | ARCH201–205 descriptions and unavailable provider channel | Standalone AI result import absent; no provider integration/calls |
| C10 | HybridAnalyzer; hybrid analyze --without-ai | Models Hybrid / artifacts.js | Real offline case/decision/policy, evidence bundles/features/missing refs; browser import | Imported case review is read-only; no policy scoring/calibration UI or fake LLM verdict |
| C11 | SecurityAnalyzer V1/V2/V3 internal Python | Security / coverage + evidence inspector | 10 demo rules; requested imported rules; positives/potential/insufficient/partial/unsupported/failed, multi-finding selection, source/unknown flow | No public scan endpoint/CLI; three model-validated fixtures, not real analyzer run |
| C12 | bounded V3 completeness certificate | Security / certificate details | Synthetic scoped negative; imported certificate marked reported/unverified | Browser cannot reproduce AST scope proof; empty import stays partial |
| C13 | actual FastAPI health/system | Runs / app.js + dev-server.cjs | Real two-endpoint handshake, independent LIVE_SYSTEM_ONLY; bridge and browser tests | Does not enable analysis or imply project readiness |
| C14 | DB/settings/logging foundations; reports boundary | Runs/session export/preferences | Original JSON round-trip, compatible-ID comparison, explicit missing server history | No auth, persistence, report generation, jobs or collaboration backend |
| C15 | benchmark/calibration/OSS tooling | Models Capabilities | Research-only explanation | Intentionally no research execution, private labels, metrics or source exposure |

## Resolved review gaps

The first review found incorrect composite decoding, unrendered imported candidates/context/Hybrid, missing graph proof/metric inspection and stale catalogue paths. V2 now uses a separate composite decoder, renders candidates without severity, presents artifact-specific model details and edge proofs/metrics/cycles, and points to actual implementation paths. Earlier raw-only discovery presentation was replaced by expandable component hypotheses. Unit tests cover actual CLI formats and malformed counterparts.

## Verification boundaries

`tests/browser.cjs` covers source gates, cancelled/completed demo, real and authored contract imports, graph lifecycle, 12/40/216 density, evidence, errors, locales, session export/comparison, responsive widths and the real system handshake. `previews/browser-report.json` is the final executed receipt. No claim of production analysis lifecycle, complete Pydantic validation parity, manual screen-reader audit, 1000-node scalability or scientific effectiveness is made.
