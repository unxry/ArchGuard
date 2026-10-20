# Desktop workflow corrections · 0.1.1 / build 42

The native app now opens the **project folder itself**, from the Projects screen,
the Local Project control, File → Open Project, or Cmd+O. The previous requirement
to choose a parent containing projects made ordinary repository selection list
its internal subdirectories instead. Explicit single-project intake now reads
only the selected root, never enumerating or granting access to sibling projects.
Legacy parent-folder configuration and the included example remain supported.

Projects without `architecture.yaml` default to dependency/security analysis;
layer checking is disabled with an explanation. Projects with a specification
retain the existing checks. Selected project and analysis options survive UI
rerenders and reopening the configuration dialog. Missing/unsupported sources,
size limits and filesystem errors have actionable RU/EN messages. Supported
analysis scope remains bounded Java / TypeScript, 200 files and 4 MiB.

Repeated activation of Run creates one request. Cancellation/new runs invalidate
earlier polling responses, so a delayed response cannot reopen or overwrite a newer
analysis. Gateway polling retries are bounded, and the interface offers reconnect
without a page reload. Saved results can be deleted after confirmation, including
damaged records that previously disappeared from the list while occupying storage.
The 20-result storage cap remains in place. Deletion is protected by the existing
session token, same-origin checks and a strict result identifier; project source
files are unaffected. A damaged JSON result returns a controlled error.

Native restart is serialized. Preference collection has a deadline so an
unresponsive web process cannot indefinitely block shutdown/restart. Quitting
during restart prevents a subsequent backend launch. Atlas element fullscreen is
enabled in WebKit, with Escape returning to the application. Cancelled navigation
does not become a false startup error. Export failures now produce a native error
instead of silently disappearing.

## Verification

- **25 pytest cases passed**, zero failures/skips: product gateway/intake and
  native lifecycle. New coverage includes selecting a project whose path contains
  spaces, actual analysis without a specification, excluding sibling projects,
  and authenticated result deletion/corruption handling.
- **7 workflow browser cases passed**, zero JavaScript errors: options persistence,
  double Run, real analysis without a specification, cancellation with a held stale
  response, deletion/confirmation cancellation, storage-limit recovery messaging,
  and reconnect after an offline startup.
- Existing adapters: **16 passed**. Existing product browser regression:
  **29 passed**, no JavaScript/console errors. Existing supplement: **5 passed**.
  Browser checks exercise the installed app's backend; they are separate from
  native window verification. The supplement uses the historical actual P040
  200-file result, rather than claiming a new density analysis.
- Ruff, formatting, targeted mypy and Swift type checking passed.
- Actual installed AppKit/WKWebView window: the in-app folder button opened a
  native picker; a project path containing spaces was selected directly; its
  analysis produced 4 modules, 3 edges and the actual security finding, with an
  honest unclassified platform. Project selection survived quit/relaunch.
  Native result-deletion confirmation and Cancel were checked without deleting
  existing saved results. Native Atlas fullscreen and Escape were exercised.
- Rapid restart left exactly one backend/session. Normal quit and quit during
  restart released processes, port and temporary sessions. The final installed
  bundle matches the packaged sources and passes strict deep signature verification.
- Final DMG was integrity-checked, mounted read-only, installed, and launched.
  It is arm64, locally ad-hoc signed, **not Developer ID signed or notarized**.

Reports: [workflow](previews/p042-workflow.json),
[browser regression](previews/p042-browser.json),
[supplement](previews/p042-supplement.json),
[artifact checksums](previews/p042-artifacts.json),
[verification receipt](previews/p042-verification.json).

Actual native screenshots: [project selection](previews/p042-native-open-project.png),
[unclassified actual graph](previews/p042-native-no-spec-atlas.png),
[fullscreen](previews/p042-native-fullscreen.png).

## Delivery and limits

Current artifacts: `dist/macos/ArchGuard.app`, `ArchGuard-macos-arm64.dmg` and
`ArchGuard-macos-arm64.zip` in the same directory. The DMG is also copied to the
user's Downloads folder, and the installed application is updated. Build with
`uv run --python 3.13.14 --locked --extra dev python scripts/build_macos.py`.

The two changed frontend files are workflow logic and scoped product CSS; the
cinematic graph/motion implementation and analyzers are unchanged. No frozen
science, benchmarks, private prerequisites or metrics were edited. Full
`make check` is **not verified**: the six historical private prerequisites remain
absent; see the [original gate report](../product/previews/quality-report.json).
Targeted and UI passes are not a claim of a green repository-wide gate or universal
correctness for every project. Intel Macs and older macOS releases were not tested.

Changes remain on `codex/archguard-native-desktop`, published normally without a
merge into main. The final commit is recorded in the delivery message.
