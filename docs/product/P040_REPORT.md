# P040 — Cinematic application integration closure

Finalization date: 2026-10-18. Implementation and browser captures: 2026-10-17.

**P040_INTEGRATION_DELIVERED_WITH_BASELINE_QUALITY_BLOCKER**

The integrated local application is verified within the scope below. The repository-wide gate is **not PASS**. Its interrupted run has no final pytest/coverage summary; 25 observed problem cases reproduce on the unchanged baseline because six private prerequisites are absent. This is not a production-readiness certification.

## A. Git lineage

- Integration branch: `feature/archguard-cinematic-application`.
- Integration base and unchanged local/remote main: `5e384141a6f9dbafb6654886e83fcad57def564e`.
- `2fb15e6` — bounded local gateway and verified macOS sandbox.
- `4a91c92` — six cinematic workspaces connected to actual analyzer results.
- The commit containing this report closes public documentation and evidence. Its exact SHA and remote verification are supplied in the delivery message.

The integration starts from main; it is not a merge of the design branch. Only public frontend assets were transferred. The original checkout's unrelated thesis edits and deleted visual HTML were left untouched. No reset, rebase, amend, force push or merge was performed.

## B. P039.3 visual baseline

Preserved design branch: `design-lab/archguard-cinematic-polish-v4`, local and remote commit `c20f6a4ee4a9936e5bc628ee5e3048d85cc6a36d`, clean worktree. Its earlier baseline is P039.2 `1cba54e`.

The product retains polygonal volumetric platforms, materials, exact SVG light paths, Luminous Atlas Portal, camera transitions, module/layer selection, warning indicators, evidence inspector, onboarding, icons, settings/help, replay and reduced motion. Actual data determines layer names and row geometry; larger unclassified groups receive enough platform depth.

[Product source manifest](product-source-manifest.json) verifies all 28 packaged frontend files; 19 remain byte-identical to P039.3. [Design manifest](design-source-manifest.json) retains its original historical metadata. [Comparison](comparison.html) explicitly distinguishes the P039.3 screenshot, P040 demo and P040 actual result. Historical P039.3 tests are not counted as P040 tests.

## C. Gateway architecture

`archguard-ui` starts the separate `archguard.product.app:create_product_app` factory. It extends the existing foundation API with product routes and packaged static assets; the foundation API contract and scientific implementations are unchanged. No new dependency was added.

Session → launcher-approved project ID → typed job → bounded snapshot → sandboxed fixed worker → existing analyzers → source-bearing local result → strict browser adapter. Job status reflects actual stages, not a simulated progress percentage. Results persist locally and can be reopened.

See the [capability audit](CAPABILITY_AUDIT.md) for the exact seven product routes and backend → adapter → component → evidence mapping. A built wheel was checked against all 28 frontend source hashes.

## D. Sandbox and macOS runtime fixes

- Python startup requires literal directory reads of `/` and the package import parent. These are not recursive file-content permissions.
- Reads are restricted to the trusted interpreter/environment, ArchGuard package, job snapshot and required system resources. File metadata is globally readable. Writes are limited to the job directory and `/dev/null`.
- The default-deny OS policy denies network, forking and arbitrary executable launches. Only the trusted interpreter is an allowed executable. Project code, builds and install scripts are never executed.
- macOS rejects the attempted `RLIMIT_AS`; the parent instead polls worker RSS every 250 ms and terminates above 2 GiB. **This is sampled monitoring, not a hard OS memory limit.** Transient overshoot is possible; failure to obtain a numeric RSS sample does not enforce a quota for that interval.
- Process-group termination retries the brief `sandbox-exec` credential transition, waits for process exit and removes the temporary snapshot. Persistent termination failure is surfaced rather than treated as success.

Live execution is enabled only with macOS `/usr/bin/sandbox-exec`. Other environments fail closed with `OS_SANDBOX_UNAVAILABLE`; the UI exposes `P040_BLOCKED_SAFE_ANALYZER_EXECUTION` while import/demo remain available.

## E. Supported real project workflows

The launcher selects a root containing immediate child projects. Browser requests use opaque IDs, never arbitrary host paths. Intake accepts UTF-8 Java/TypeScript/TSX and optional root `architecture.yaml`: at most 200 files including the spec, 256 KiB/file, 4 MiB total, 5,000 entries and depth 20. Symlinks, hard-linked source files, non-regular/binary files and path escapes are rejected. Hidden paths, dependency/build directories and scientific stores are excluded.

Existing discovery, parser, IAM builder and file graph analyzer run on the snapshot. Architecture checking/classification uses the explicit YAML specification when enabled. Without it the graph has an honest unclassified platform. Security V2 is optional and retains its bounded `PARTIAL` semantics. Graph completeness is separate from security coverage; `READY` does not mean secure.

The public `examples/product/observatory-ts` source project produces **4 file nodes, 3 imports, ARCH002 and SEC002** through actual analyzer execution. It is an authored integration example, not private research truth or a substituted demo result. A separately generated 200-file TypeScript source project was actually analyzed: 200 nodes, 199 edges; the UI presents six groups and at most 18 visible nodes per page.

## F. Six workspaces

| Space | Verified behavior |
|---|---|
| Projects | Empty start, permitted catalog, configuration, actual job, explicit demo, CLI JSON import, honest Git/ZIP gates |
| Atlas | Actual dependency graph, volumetric layers, selection, directional light, portal context, camera, pagination, inspector and fullscreen |
| Findings | Actual rule records, evidence and source lines; return preserves selected module |
| Security | Actual V2 findings and SQL evidence, bounded coverage, no zero-findings security guarantee |
| Models | Actual IAM/classification; retained Rules, Discovery, Context/Hybrid and Capabilities surfaces with honest import/unavailable states |
| Runs | Real stages, cancellation/failure, persistence, reopen and provenance |

RU/EN, motion preferences, replay, settings/help and reduced motion remain available.

## G. Real data adapters

The worker emits `archguard-product-v1` with graph, IAM, optional architecture/classification/security, source lines and provenance. The UI validates the envelope and uses actual IDs, edges, counts and paths. Gateway-loaded data is marked `LOCAL_GATEWAY_RESULT`; user-imported envelopes are `PRODUCT_STRUCTURE_ONLY`, not authenticated gateway output. This is a provenance distinction, not a cryptographic attestation.

Existing strict CLI adapters remain available for IAM, graph/candidates, discovery, context, hybrid and Security artifacts. Provider calls, live hybrid inference and V3 promotion are not implemented by this gateway. Imported scores, hypotheses and scope certificates retain their original meaning.

## H. Demo/live separation

Startup contains no demo metrics. Northstar demo is explicitly selected, uses independent synthetic data and works with all gateway requests blocked. Returning to a saved actual result restores its data without synthetic counts. Actual-mode graph controls do not expose demo size selectors. Browser reload starts empty and offers saved results.

## I. Security boundaries and residual risks

| Boundary | Evidence |
|---|---|
| Loopback | Launcher binds `127.0.0.1`; exact Host and Origin/Fetch-Site checks |
| Request authorization | Per-process token, mutation Origin, typed operation and extra-field rejection, 2,048-byte declared body cap |
| Intake | Traversal, symlink, hardlink, oversize and binary rejection; excluded credential/dependency canaries |
| Filesystem/network/execution | Actual OS sandbox probe denies outside read, socket connection and shell execution; permitted job write succeeds |
| Credentials/command | Actual worker launch verified with fixed argv and only PATH/LANG/HOME/TMPDIR; injected parent credential canary not inherited |
| Time/resources | 45-second parent timeout, 20-second CPU limit, 32 MiB output/file limit, 96 descriptors, no core dumps |
| Cancellation/cleanup | Timeout, explicit cancel and shutdown terminate the child; actual process return code and snapshot removal checked |
| Concurrency | Second job rejected with `ANALYSIS_BUSY` |
| Memory | Injected high RSS sample triggers `MEMORY_LIMIT`, terminates the actual worker/process group, removes snapshot and publishes no result |

[Final security probes](previews/finalize-security-report.json) document the last two checks. The RSS probe injects `/bin/ps` output; it is not a real 2 GiB allocation stress test or proof of a hard quota. These probes supplement the 17 gateway tests; they are not additional pytest cases.

The local user, interpreter/environment and installed ArchGuard package are trusted. Session auth is not multi-user/service authentication. Source can contain sensitive literals even when hidden credential files are excluded; only detected SEC001 lines are redacted. Results are source-bearing plaintext, with state directory mode 0700 and result files 0600, capped at 20 saved results. There is no UI deletion, encryption or general secret-scanning guarantee. Sandbox portability and independent security review remain open.

## J. End-to-end results

The browser ran: startup → real permitted project → gateway analysis → actual results → portal/Atlas → selected module → actual finding → evidence/source → same module → Security → Models → Runs/reopen. RU/EN, animation settings/replay, reduced motion, fullscreen/help, CLI import, arbitrary classification names and offline demo were also checked.

[Browser report](previews/browser-report.json): 29 passed; [supplement](previews/supplement-report.json): 5 passed. Zero failures, browser exceptions or console errors. These are assertion checks, not a claim of comprehensive browser compatibility.

## K. Screenshots and WebM

All files are under `docs/product/previews/`. `p0393-before.png` is explicitly the historical comparison image. All other screenshots and the video were captured from the running P040 integration.

- Desktop pairs `overview-{1280,1440,1920,2560}.png` and `atlas-{1280,1440,1920,2560}.png`; tested viewport sizes 1280×800, 1440×900, 1920×1080, 2560×1440. Some screenshots use full-page height.
- Startup, project selection, analysis, actual results, finding evidence, Security, Models, Runs, settings and reduced motion captures.
- `demo-baseline.png` / `large-graph.png` show explicit demo; `real-large-graph.png` shows the actual 200-file result.
- [Real workflow WebM](previews/real-workflow.webm): **1920×1080, 25.72 seconds**. Chromium decoded it and distinct frame checksums at 2/8/14/20 seconds confirmed changing content; see [video verification](previews/video-verification.json).

## L. Performance measurements

Chromium 151, 4× CPU throttling: 325 sampled frames, p95 frame interval **17.5 ms**, zero recorded long tasks in that measurement. The scene reaches resting/inactive state; its one idle graph scope is released on navigation. Desktop checks found no horizontal overflow. Narrow viewports show the desktop recommendation rather than a separate mobile UI.

These are bounded local measurements, not a universal FPS or zero-leak guarantee. Historical P039.3 portal p95 was 18.6 ms with one 122 ms construction task; workloads differ, so no speedup claim is made.

## M. Targeted validation

| Check | Passed | Failed | Skipped |
|---|---:|---:|---:|
| Gateway pytest, finalization rerun | 17 | 0 | 0 |
| Native JS adapters | 16 | 0 | 0 |
| Browser main + supplement assertions | 34 | 0 | 0 |
| Additional finalization security probes | 2 | 0 | 0 |

The four OS-guarded gateway test functions (parameterized into eight cases) ran on this macOS host; none were skipped. Final ruff check passed; formatting checked 605 files; mypy passed 290 source files. Wheel assets matched source. No product source was changed during finalization.

## N. Full gate and baseline reproduction

**`FULL_CHECK = BLOCKED_BY_MISSING_PRIVATE_BASELINE_ARTIFACTS`**

The previous `make check` was interrupted during `tests/intelligence/test_semantic_positive_recovery.py`; finalization found no surviving test process. Its log collected 3,381 cases and records **1,801 passing, 6 failing, 19 setup-error, 0 skipped progress markers**. Another **1,555 cases have no recorded terminal outcome**. These are partial observed counts, not a completed test summary. No exit code or final coverage report was recovered. The full count predates two later product cases; final product coverage is the 17-case targeted rerun. Overall guarded-skip totals are unknown.

Earlier notes mentioned only four failures. Final log accounting found two more failures and 19 setup errors; none are omitted here. All 25 problem cases were reproduced with source exported from `5e38414`, an isolated `PYTHONPATH` verified to import that source, the same unchanged historical tests and the same missing checkout-relative prerequisites. A matching integration rerun gave exactly the same test IDs and missing paths: **6 passed, 6 failed, 19 setup errors, 0 skipped; exit 1** in each reproduction.

The six failing tests are:

```text
tests/benchmark/test_component_holdout.py::test_completed_local_freezes_and_exact100_evidence
tests/benchmark/test_unified_human_review.py::test_real_v2_exact_pins_case_sets_blind_order_and_blankness
tests/intelligence/test_development_llm_executor.py::test_real_frozen_p020_requests_are_exact_unique_and_blind
tests/intelligence/test_development_llm_executor.py::test_future_adapter_reconstructs_identical_frozen_wire_without_call
tests/intelligence/test_final_llm.py::test_p023_frozen_models_and_protocol_still_locked
tests/intelligence/test_final_llm.py::test_actual_p020_final_300_exact_freeze_and_cost
```

Nineteen cases in `tests/benchmark/test_thesis_closure.py` fail fixture setup on the missing P025 receipt. [Quality report](previews/quality-report.json) lists every exact parameterized ID, all six missing relative paths, matching reproduction counts and local-log SHA-256 values. The missing prerequisites are component-holdout execution manifest, final review material freeze, P020 development requests manifest, final static-output evidence, P023 selected-model registry and P025 truth-blind receipt.

`BASELINE_PRIVATE_ARTIFACT_BLOCKERS = 25` counts affected test cases; **6** is the distinct missing-artifact count. These are baseline custody/environment blockers, not demonstrated P040 regressions or guarded skips. No frozen assertion, artifact, fingerprint or test was changed to make them pass. The unreported remainder is still unverified; baseline reproduction does not prove the full suite has no other failures. A duplicate full run was not started merely to repeat the interrupted work without its prerequisites.

## O. Scientific freeze and privacy

Changed paths are limited to `pyproject.toml` (one CLI entry point), `src/archguard/product/`, `examples/product/`, `tests/product/` and `docs/product/`. Existing Architecture/Security analyzers, science, benchmark truth, fingerprints, private custody and historical tests have zero Git changes. P039.3 remains a separate clean, published baseline. `SCIENTIFIC_FREEZE_DRIFT = 0` refers to this verified diff scope.

Only public authored product fixtures/source and their actual outputs are included. Logs containing local absolute paths are not published; the quality report contains only sanitized test IDs, relative prerequisite paths and digests. No private artifact contents, benchmark cases, reviewer/adjudication data, credentials, temporary snapshots or user-specific absolute paths are part of this delivery. `PRIVATE_DATA_EXPOSURE = 0` denotes the audited publication set, not a universal guarantee about future user exports.

## P. Exact startup

From this integration checkout on macOS:

```sh
uv sync --locked --extra dev
uv run archguard-ui --projects-root examples/product --state-dir /tmp/archguard-local-results --port 8790
```

Open `http://127.0.0.1:8790/`. Frontend source: `src/archguard/product/web/index.html`; it must be served through the gateway for live operations. Select `observatory-ts`, enable Architecture/Security, then analyze. Stop with Ctrl+C. Supply your own dedicated parent directory via `--projects-root` for other intended projects. See [README](README.md) for limits and verification commands. Owned preview servers were no longer running at finalization; no user server was stopped.

## Q. Known limitations and merge prerequisites

Live execution is macOS-only and bounded to Java/TypeScript/TSX, one job and 200 files. Git clone, ZIP extraction and live provider calls remain gated. Imported advanced CLI artifacts are supported without pretending their live workflows exist. Security V2 is partial; source-bearing results require local custody. Desktop only, with no mobile redesign. Memory monitoring has the sampled-control limitations above.

Before merge: an authorized custodian must provide the genuine missing private prerequisites in the appropriate environment, complete `make check` including the unreported remainder/coverage, and resolve any additional failures without changing frozen science. Coordinator review must also accept the platform scope and residual security risks. No production-readiness or merge authorization is inferred from this delivery.

## R. Git publication

Publication target: `origin/feature/archguard-cinematic-application`. The closure commit is made after public-path, secret/path and whitespace audits, then pushed normally. Its local SHA must equal `git ls-remote origin refs/heads/feature/archguard-cinematic-application`; remote main must remain `5e384141a6f9dbafb6654886e83fcad57def564e`. Exact publication outcome and closure SHA are recorded in the final delivery message after this report is committed, avoiding a self-referential commit hash.

No merge, main update, history rewrite or new development follows publication. The deliverable is ready for coordinator review with the explicit baseline quality blocker above; it is not unconditional `P040_COMPLETE`.
