# Frontend architecture

V2 is a local, modular, dependency-free investigation application. `index.html` works from `file://` with sibling assets; `node dev-server.cjs` supplies the optional development preview. A buildless delivery avoids a package install or network dependency and preserves the same code for both paths. It is a prototype, not a project/job backend.

## Modules and contracts

| Module | Responsibility |
| --- | --- |
| `core.js` | Session state, escaped rendering helper, locale/motion preferences, notifications and downloads |
| `i18n.js`, `catalog.js`, `artifacts.js` resources | Central RU/EN strings, typed rule/capability catalogue, canonical labels |
| `fixtures.js` | Authored synthetic demo; never merged into imports |
| `adapters.js` | Bounded JSON validation and conversion to a shared viewing DTO; format-specific semantics retained |
| `graph.js` | SVG geometry, clustering/paging, camera, selection, finite path pulses and cleanup |
| `artifacts.js` | Imported graph proof/metrics/cycles, discovery hypotheses, context fragments and Hybrid cases |
| `views.js` | Six workspaces and evidence/coverage inspectors; common visual primitives |
| `onboarding.js` | Source → demo configuration → cancellable finite stages; real intake gates and CLI plans |
| `app.js` | Navigation, events, imports/exports, locale switching, independent system handshake |
| `contracts.d.ts` | DTO documentation; runtime checks in adapters are authoritative. No `tsc` claim |
| `dev-server.cjs` | Local static preview and exactly two fixed backend system reads |

Scripts load in explicit dependency order. There is one application namespace and one current dataset. Renderer-generated strings are escaped; imported source and paths never become executable HTML, URLs or shell commands. Repository-supplied text retains its original language. Native `dialog`, buttons, selects and details provide browser keyboard behavior.

`A.render` disposes the current graph before remount. Each graph owns an AbortController and its camera/pulse animation IDs. View teardown aborts listeners and cancels frames; no background analysis jobs exist. The large renderer is divided by workspace; imported artifact presentations are separate from authored demo presentation.

## State boundaries

- `LOCAL_DEMO`: explicitly authored synthetic records, finite demonstration stages, session-only configuration/history.
- `LOCAL_RESULT`: exactly one selected artifact, retained original JSON and provenance. No auto-join to earlier files; no demo residue.
- `LIVE_SYSTEM_ONLY`: an independent service state. `/health` and `/api/v1/system/info` do not change dataset mode or enable analysis.
- `REQUIRES_BACKEND_ADAPTER` / `UNAVAILABLE`: product gates, not simulated successful jobs.

Only locale and motion preference are persisted. Source, artifacts, results, service credentials and session runs are not put in localStorage. File reload intentionally starts a new demo session. Session comparison uses project IDs and data mode; unbound manifests/results cannot be equated.

## Integration debt

Server-side auth, validated ingestion/jobs, cancellation, source authorization, persisted history, result schema/version negotiation, provenance verification, canonical policy editing and report generation remain backend work. The browser preview does not execute uploaded code or invoke providers. See the capability matrix and security review for per-subsystem boundaries.
