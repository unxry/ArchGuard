# Capability → adapter → product surface → validation

Audit baseline: `origin/main` at `5e384141a6f9dbafb6654886e83fcad57def564e`. The existing application factory in `src/archguard/api/app.py` exposes `/health` and `/api/v1/system/info` only. Its API contract is unchanged. The product entry point is a separate factory, `src/archguard/product/app.py:create_product_app`, adding only the documented local routes. There was no supported product frontend framework to extend; the packaged browser frontend preserves the existing Graphite implementation without new third-party dependencies.

| Existing capability / source | Adapter | Frontend | Test / evidence | Integration status |
|---|---|---|---|---|
| Repository discovery; `application/discover_repository.py`, repository policy | No-follow bounded snapshot → existing discovery | Projects selection and configuration | `test_intake_*`, `test_real_analysis_result_and_reopen`, browser actual job | Local Java/TS/TSX; Git/ZIP gated |
| Parsing; `application/parse_repository.py` and parser registry | Fixed worker `ParseRepository` | Actual analysis stages; result diagnostics | Real pipeline test | Live subset selected by intake; no code execution |
| IAM; `application/build_iam.py` | Worker `BuildIAM`; strict existing JSON adapter | Models counts, Atlas file projection | 4 real file nodes; IAM counts; wheel packaging | Live; standalone IAM JSON import also supported |
| Normative ARCH001–005; `application/check_architecture.py` | Worker `CheckArchitecture` with optional explicit spec | Findings, evidence, Atlas classification | Actual ARCH002 and source navigation | Live configured rules; no inferred target architecture |
| Graph / metrics / SCC / cycles; `architecture/graph/analyzer.py` | Worker `GraphAnalyzer`, file projection | Spatial Atlas, edge proofs, direction, node inspector | Actual 3 edges, portal and light-path checks | Live file graph; static dependencies, not runtime traffic |
| ARCH101–105 candidate thresholds | Existing strict graph JSON importer | Findings candidate metrics / thresholds | Existing imported-model renderer; graph import smoke | Import-only opt-in CLI output; no live configuration UI |
| Architecture discovery; `architecture/discovery` | Existing discovery JSON importer | Models Discovery, graph | Existing strict adapter carried forward | Import-only; hypotheses retain their original status |
| Deterministic context; `architecture/intelligence` | Existing context manifest importer | Models Context/Hybrid | Existing bounded schema adapter carried forward | Import-only; manifests do not acquire invented code fragments |
| ARCH201–205 / Responses | No live provider adapter | Honest unavailable state / imported models | Session capabilities provider_calls=false; result provider_calls=0 | Live provider calls gated |
| Hybrid; `architecture/hybrid` | Existing strict hybrid result importer | Models decisions/evidence/features | Existing strict bindings adapter carried forward | Import-only; scores not probabilities |
| Security V2; `security/analyzer_v2.py` | Worker `SecurityAnalyzerV2` by Java/TS language; result importer | Security coverage, findings, dataflow/source | Real SEC002, bounded outcomes, zero-result semantics | Live V2 partial scope; not V3 promotion |
| Security V1/V3 and scope certificates | Existing strict Security JSON importer | Security reported certificates and scope | Existing schema validation retained | Import-only; no synthetic certificates in real mode |
| Result persistence / local session | Product runtime and per-process token | Runs: actual job states, cancellation, reopen, provenance | Authorization, origin, body limits, reopen, timeout, cancellation, shutdown tests | Local filesystem only; max 20 saved results |
| Existing foundation health/system | Original unchanged factory | Gateway session startup | Foundation API tests in full suite | Existing API preserved |
| Research/benchmark/calibration tooling | None | Not exposed | Git diff scope audit | No private scientific artifacts copied or surfaced |

## Product HTTP contract

- `GET /api/product/session`: token, OS sandbox availability, honest capability flags and limits.
- `GET /api/product/projects`: IDs and names under the launcher-selected root.
- `POST /api/product/jobs`: exact JSON `{project_id, architecture, security}`; no extra fields.
- `GET /api/product/jobs/{id}`: actual stages and terminal error code.
- `POST /api/product/jobs/{id}/cancel`: terminate actual child work.
- `GET /api/product/results`: saved result metadata.
- `GET /api/product/results/{id}`: validated identifier, bounded local result.

All product data routes except session require the token. Mutations require the exact loopback Origin. Unsupported methods, arbitrary paths, source URLs and command strings have no execution route. The gateway does not pretend that the foundation API supports analysis.

## Six workspace states

Projects begins empty with actual source selection, configuration, loading/error/gated states and explicit demo. Atlas is empty until a graph exists. Findings and Security show only the current dataset; absent Security analysis has an explicit empty state. Models shows actual IAM and classification for gateway results, or existing appropriate import surfaces. Runs shows real stages, failures, cancellation and saved results. All six navigation entries, product controls and motion settings have RU/EN labels; original analyzer descriptions and technical identifiers are preserved verbatim.
