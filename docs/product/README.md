# ArchGuard Cinematic · local application

Production source: `src/archguard/product/web/index.html`. The frontend is packaged in the Python wheel. It uses the existing P039.3 graph and motion engines, native browser modules, and a small FastAPI local gateway. No frontend dependency installation or hosted service is needed.

## Launch

From this integration checkout on macOS:

```sh
uv sync --locked --extra dev
uv run archguard-ui --projects-root examples/product --state-dir /tmp/archguard-local-results --port 8790
```

Open **http://127.0.0.1:8790/**. Stop with **Ctrl+C**; shutdown cancels active work and removes its temporary snapshot. Each immediate child directory of `--projects-root` is a selectable project. For your own code, supply a dedicated directory containing only projects you intend to analyze. The root is chosen by the person launching the server; browser requests only accept an opaque project ID.

Select `observatory-ts`, leave Architecture and Security enabled, and run analysis. The real synthetic source project produces 4 file nodes, 3 edges, an ARCH002 layer violation and a SEC002 finding. The project is a product integration test, not research ground truth. These results are computed by existing analyzers; they are not the Northstar demo fixtures.

Architecture checking requires `architecture.yaml` at the project root. Disable that option to build a file graph without a specification. Layer names come from actual classification; without a specification the visual platform is explicitly unclassified. Security V2 has bounded coverage: no findings never means secure. Pipeline `READY` means the result was written, not that all security properties were proved. Overall results with Security V2 are marked `PARTIAL`; graph completeness is recorded separately.

Results persist in the selected state directory (up to 20; no UI deletion). Reopen them in Runs. Imports of supported CLI JSON remain memory-only. Demo is an explicit synthetic mode and works without the gateway. It does not get merged with a real result. Browser reload starts empty and offers saved results.

## Execution boundary

Live analysis currently requires **macOS `/usr/bin/sandbox-exec`**. Other platforms fail closed with `OS_SANDBOX_UNAVAILABLE`; CLI JSON import and demo remain usable. A separate platform sandbox implementation is required before enabling live execution elsewhere.

The gateway binds only to `127.0.0.1`, checks Host/Origin/Fetch-Site, requires a per-process session token for product data and mutations, limits request bodies, and accepts a fixed typed operation. It never accepts shell commands. No project code, build scripts, package installs, provider calls, Git clone, or ZIP extraction are executed.

Intake copies only UTF-8 Java/TypeScript/TSX files and root `architecture.yaml`: 200 files including the specification, 256 KiB per file, 4 MiB total, 5,000 entries, depth 20. Hidden paths, dependencies, build products and scientific stores named `experiments`/`benchmarks` are excluded. Symlinks and hard-linked source files are rejected using no-follow descriptors. `.env`, `.ssh` and JSON credential files are not copied. This is **not** a general secret scanner: ordinary source files can contain sensitive data. The local result contains source lines; detected SEC001 lines are redacted. Select only intended project roots and treat exported JSON as source-bearing data.

The worker has an OS default-deny sandbox. Read access is restricted to the trusted interpreter, its environment, the ArchGuard package, necessary system libraries and the per-job snapshot. A literal directory read of `/` and the package import parent enables Python startup; it does not authorize file-content reads beneath those directories. Global file metadata is readable. Network and arbitrary executable launches are denied. Writes are restricted to the job directory and `/dev/null`.

Limits: one job, 45-second parent timeout, 20-second CPU limit, 32 MiB output/file limit, 96 descriptors, no core dumps. macOS rejects `RLIMIT_AS`; the parent samples worker RSS every 250 ms and terminates above 2 GiB. This sampled threshold permits transient overshoot and is not a hard virtual-memory quota. The worker cannot fork arbitrary subprocesses. Cancellation retries the brief `sandbox-exec` credential-transition window and waits for actual process exit. Runtime errors expose bounded error codes, not source-bearing exception traces.

This is a local application integration, **not a production-readiness certification**. Sandbox-exec availability is platform-dependent. Multi-user auth, service deployment, encrypted result storage, retention controls, external source intake and independent operational/security review remain outside this delivery.

## Verification

```sh
uv run pytest tests/product -q
make check
node --test tests/product/adapters.test.cjs
uv run python tests/product/density.py /tmp/p040-density-result.json
NODE_PATH=/absolute/path/to/existing/node_modules node tests/product/browser.cjs
```

The browser check expects Playwright/Chromium available in the caller's environment and a running gateway at port 8790; override with `ARCHGUARD_URL`. It performs a real analysis and writes PNG/WebM evidence into `docs/product/previews`. Start with an empty test state directory to stay below the 20-result cap. The product browser tests never read private benchmark stores. Run `tests/product/supplement.cjs` with the same Node environment for the generated 200-file result and offline-demo checks; `tests/product/media.cjs` records a concise real workflow. The repository-wide scientific tests can require private artifacts excluded from this checkout; see the report for the full-gate outcome.

See [capability audit](CAPABILITY_AUDIT.md), [completion report](P040_REPORT.md), [actual browser report](previews/browser-report.json), and [visual comparison](comparison.html).
