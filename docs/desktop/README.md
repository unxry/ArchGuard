# ArchGuard for macOS · P041

> Current release: **0.1.1 / build 42**. See [workflow fixes and current verification](P042_FIXES.md).
> This document records the original P041 build. Its parent-folder selection,
> frontend hashes, checksums and test counts are historical; the current release
> opens the project folder itself through **File → Open Project** or the in-app button.

Native desktop integration of published P040 commit
`71e173482082162172b059729faf176f8bdfc82a`, on
`codex/archguard-native-desktop`. Verified on Apple Silicon, macOS 26.5.2,
October 18–20, 2026.

## Install

Build outputs (relative to the checkout):

- `dist/macos/ArchGuard-macos-arm64.dmg`
- `dist/macos/ArchGuard-macos-arm64.zip`
- `dist/macos/ArchGuard.app`

Open the DMG, drag **ArchGuard.app** to **Applications**, then open it.
The installed artifact was tested at `/Applications/ArchGuard.app`.
No terminal, browser, separately installed Python, Node, or development checkout
is required to use it. The bundle includes a public TypeScript example.
**File → Choose Projects Folder** selects a parent directory containing the
projects the user permits ArchGuard to analyze. **Use Included Example** restores
the bundled project; **Restart Local Engine** restarts the backend.

This release is **arm64 only**, with a macOS 13 deployment target. Older macOS
versions and Intel Macs were not tested. The artifact is **ad-hoc signed**,
verified with `codesign --verify --deep --strict`. It has **no Developer ID
signature and no Apple notarization**. A transferred/quarantined copy may require
the user's explicit approval in macOS Privacy & Security. This is a local review
build, not a notarized public distribution.

Checksums and sizes are in [artifacts.json](previews/artifacts.json). Generated
application binaries are ignored by Git; build source and verification evidence
are versioned.

## Native layer and lifecycle

The shell uses AppKit and the system WKWebView. It supplies its own window,
application identity, icon, menu, resize/fullscreen behavior, native folder/open/
save dialogs, loading state, retry state, and bounded diagnostic codes. It
embeds the existing cinematic interface; all **28 frontend file hashes match
P040**, both in source and in the installed application.

The bundle includes relocatable CPython **3.13.14**, dependencies from `uv.lock`,
and the ArchGuard wheel. The shell launches only that interpreter with fixed
arguments, isolated mode and bytecode writing disabled. The backend binds
`127.0.0.1:0` and retains the allocated socket through Uvicorn startup. The shell
waits for the readiness message and a successful health check before loading the
UI. Startup has a 30-second timeout.

A per-user process lock prevents duplicate instances. A lifetime pipe couples
the backend to the native owner; closing the window or quitting closes that pipe.
Shutdown waits for the process and escalates to termination if needed. A worker
parent watchdog also ends an analysis process if the backend is killed. Private
session directories are removed on normal exit; lock-aware startup recovery
removes abandoned sessions without deleting active or unrelated directories.

User state is under `~/Library/Application Support/ArchGuard/`: bounded saved
results, temporary `Runtime` sessions, a process lock, and a latest-event-only
startup log. Only five display preferences are transferred from localStorage to
native preferences so RU/EN and motion settings survive changing loopback ports.
The chosen projects root is stored separately by the native folder dialog.
Saved analysis results may contain source excerpts; they remain local and use
the existing P040 retention limit of 20 results.

## Security boundaries

- The HTTP listener is loopback-only. Existing Host/Origin checks, per-session
  API token, strict request schemas, project-root containment, input size limits,
  symlink/hardlink rejection, and result validation remain in place.
- Analysis uses the unchanged macOS `sandbox-exec` profile: bounded project
  snapshot, restricted filesystem writes, no network, no project-code execution,
  and existing time/memory limits. No sandbox was disabled for packaging.
- The AppKit parent and trusted HTTP coordinator are **not OS-sandboxed**.
  Project-root restrictions are enforced by application code; the analysis
  worker is the separate OS-sandboxed process. A native window alone is not a
  sandbox. A malicious process already running as the same user is outside this
  boundary.
- WKWebView navigation is limited to the exact active loopback origin. External
  HTTPS links require a link action and a native confirmation, then open outside
  application content. There are no privileged JavaScript message handlers.
  Native JSON import/export uses system file dialogs.
- Startup output contains readiness or fixed error codes, not source text,
  credentials, session tokens, or raw exceptions. No telemetry/provider calls
  or new network capability was added.

These claims cover the exercised gateway/worker tests and shell policy review;
they are not an independent security certification.

## Build again

On an Apple Silicon Mac with Xcode command-line tools and `uv`:

```sh
uv run --python 3.13.14 --locked --extra dev python scripts/build_macos.py
```

The recipe stages a copied managed Python, installs locked/hash-checked runtime
dependencies and the project wheel, compiles Swift, derives the icon from the
existing brand geometry, rejects external runtime symlinks, signs nested native
images and the application ad-hoc, verifies the seal, and produces ZIP and DMG.
The DMG contains the application, an Applications shortcut and installation
instructions. Initial dependency downloads require network access; application
use does not.

Two builds completed during implementation. “Reproducible” here means a repeatable
recipe with pinned Python and locked dependencies, **not byte-identical binaries**
across different SDKs, signing tools or disk-image timestamps. The tested compiler
was Apple Swift 6.3.3. Run manual interpreter probes with `-I -B` to avoid creating
bytecode inside the signed bundle.

## Verification

| Check | Result |
|---|---|
| Product gateway + desktop lifecycle pytest | 22 passed, 0 failed, 0 skipped |
| Existing JavaScript adapters | 16 passed, 0 failed, 0 skipped |
| Existing product browser regression against installed app's backend | 29 passed, 0 JS/console errors |
| Existing supplemental browser regression | 5 passed, 0 JS errors |
| Ruff / formatting / mypy | Passed; 609 formatted files, 291 typed source files |
| DMG integrity and installed bundle signature | Passed |
| Isolated bundled-runtime imports | Passed with empty inherited environment |
| Frontend preservation | 28/28 source and installed hashes match P040 |
| Scientific/analyzer/frozen-data diff from P040 | Zero |

Browser regressions exercise the installed backend with Chromium; they are
**not native-window evidence**. Their separate reports are
[browser-regression.json](previews/browser-regression.json) and
[browser-supplement.json](previews/browser-supplement.json). The supplement imports
the previously generated P040 200-file actual result; P041 does not claim a new
200-file analysis run.

Actual installed-window checks used AppKit/WKWebView through desktop automation:
launch from the installed bundle; automatic readiness; native folder selection;
real analysis of both the bundled public example and its external folder copy;
4 modules, 3 dependency edges, ARCH002 and SEC002; all six workspaces; source
evidence and return to the selected Atlas node; directional light, portal and
assembly/replay; RU/EN; native motion-off control; JSON export through NSSavePanel
and import through NSOpenPanel. The exported JSON was independently parsed and
its actual graph counts checked.

Normal quit removed native/backend processes, listening port and session
snapshots. Relaunch preserved language and selected root. A duplicate executable
launch left one native app and one backend. Killing the native owner also ended
the backend, released the port and removed snapshots; relaunch succeeded.
Terminating the backend produced the native error overlay; **Retry** recovered.
A deliberately incomplete test bundle produced **RUNTIME_MISSING**. Automated
tests separately cover invalid-root startup failure, concurrent dynamic ports,
SIGTERM, abandoned-session recovery and worker exit after backend SIGKILL.
See [native-verification.json](previews/native-verification.json).

The browser test verifies the `prefers-reduced-motion` path and animation
suppression; native verification additionally exercised motion-off. The macOS
system accessibility preference was not changed. No new native performance
benchmark, recording, or Intel/older-macOS certification is claimed.

Actual desktop screenshots:

- [Overview](previews/native-overview.png), [Atlas](previews/native-atlas.png)
- [Evidence](previews/native-evidence.png), [Security](previews/native-security.png)
- [Models](previews/native-models.png), [Runs](previews/native-runs.png)
- [Motion off](previews/native-motion-off.png), [Imported Atlas](previews/native-imported-atlas.png)
- [Missing runtime](previews/native-runtime-missing.png), [Backend error](previews/native-backend-error.png)

## Full repository gate and publication

**Full `make check`: NOT PASS; not rerun for P041.** The historical P040 run was
interrupted without a final pytest/coverage summary: 1,801 observed passes,
6 failures, 19 setup errors, and 1,555 unreported cases out of 3,381 collected.
Those are partial historical counts, not P041 results. P040 reproduced the same
25 affected cases on its baseline because six private prerequisites were absent.
All six remain absent in this checkout. See the unchanged
[P040 quality report](../product/previews/quality-report.json) for exact test IDs
and missing paths. The remainder remains unverified. No private prerequisites,
scientific assertions, metrics, fingerprints or benchmark truth were fabricated
or changed to obtain a passing gate.

P040's local/published commit remains `71e173482082162172b059729faf176f8bdfc82a`.
Main advanced independently between October 18 and 20; the closure reference is
`7582e62c0cb86fc90e5730c4284378eeaeb984d5`. This task did not update or merge into
main. Only the dedicated desktop branch is committed and pushed normally.
Final publication SHA is reported after the push, avoiding a self-referential
commit hash in this document.

Verified acceptance scope:

```text
NATIVE_MACOS_APP = VERIFIED
BROWSER_NOT_REQUIRED = YES
APP_BUNDLE_EXISTS = YES
BACKEND_AUTO_START = VERIFIED
REAL_ANALYSIS = VERIFIED
CINEMATIC_UI_PRESERVED = YES
SIX_WORKSPACES = VERIFIED
APP_QUIT_CLEANUP = VERIFIED
SECURITY_BOUNDARIES = VERIFIED
BUILD_REPRODUCIBLE = YES
SCIENTIFIC_FREEZE_DRIFT = 0
MAIN_UNCHANGED = YES
READY_FOR_DESKTOP_REVIEW = YES
```

`BUILD_REPRODUCIBLE` and `SECURITY_BOUNDARIES` use the bounded meanings above.
`MAIN_UNCHANGED` means unchanged by this task, not unchanged by other work.
`DESKTOP_BRANCH_PUSHED` is confirmed only after remote SHA verification in the
delivery message. Desktop review readiness does not imply a green full repository
gate, notarized distribution, or merge authorization.
