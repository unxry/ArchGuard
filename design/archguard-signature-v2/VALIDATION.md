# Final validation receipt

Executed 17 October 2026 against the isolated V2 directory. Browser: Chromium 151.0.7922.34, headless Playwright. No mocked page screenshots; captures and WebM came from the actual rendered application.

## Results

- Native Node tests: **43 passed, 0 failed, 0 skipped**. This includes the original **23 bridge cases**, 16 importer cases and 4 localization cases.
- Browser scenarios: **58 passed, 0 failed**, **0 JavaScript errors**, **0 console errors** in the final receipt.
- All runtime JavaScript passed `node --check`. DTO declarations are documentation; TypeScript compilation is not claimed.
- Eight actual CLI architecture artifact files imported through the browser; three authored Security V2 artifacts passed real Pydantic validation and browser import. Generic graph/static originals were generated twice byte-identically; extra artifacts are reproducible with the committed generator.
- Actual FastAPI system handshake returned ArchGuard AI 0.1.0 / foundation / schema 1.0. Only fixed `/health` and `/api/v1/system/info` were queried upstream. `LOCAL_DEMO` remained independent from `LIVE_SYSTEM_ONLY`.
- Offline workflows issued **zero HTTP(S) requests**. After explicit service preview, requests were only local app assets and `/__bridge/system`.
- Tested viewport sizes: 1920×1080, 1440×900, 1024×768, 768×1024, 390×844 and 320×720. All six workspace pages fit horizontally in the final regression.
- 37 actual PNG captures (including intermediate review states), plus actual `motion-showcase.webm` recording.

## Measured behavior and limits

| Measurement | Final observation | Interpretation |
| --- | --- | --- |
| DOM interactive | 126.5 ms | Navigation Timing observation for local file; **not a measured TTI** |
| 40-node overview action | 31 ms | Playwright click-to-assert interval, includes automation overhead |
| 216-node overview action | 35 ms | Six clusters; drilldown bounded to 18/page |
| Pulse frame intervals, 4× CPU throttle | P95 17.4 ms; 242 measured frames; 0 intervals >50 ms | Controlled desktop emulation, not a physical weak-device benchmark |
| Full stress-session long tasks | 1; max 307 ms | Includes file-limit/error/import/stress operations; not claimed jank-free |
| Layout shift total | 0.00251 | Observed in this automated run; not field Core Web Vitals |
| Heap before / after 20 mount-unmount cycles + GC | 10927556 / 3107700 bytes | No retained-graph accumulation observed; not an exhaustive leak proof |
| Runtime HTML + CSS + 10 JS modules | 215316 bytes, uncompressed | No downloaded fonts/images or runtime framework dependency |

Pulses follow real SVG path length/points, cap at four and stop after four seconds. Reduced motion yields zero pulses. A synthetic `visibilitychange`/hidden-state lifecycle test verified frame pause/resume; this is explicitly **not an OS background-tab scheduling test**. Navigation aborts listeners and cancels pulse/camera frames. Stress claims stop at 216 visible-data nodes; the 500-node import ceiling is a validation bound, not a benchmark promise. No 1000-node claim.

## Accessibility and localization

Native keyboard controls, Enter/Space and arrow graph navigation, edge keyboard activation, slash search, Escape/native dialog focus behavior, live announcements, reduced motion and mobile list assistance were exercised. Russian is default; EN persisted correctly. Every literal translation key and matching locale resource was checked; authored fixture prose has both locales. Imported backend strings and identifiers retain their original language.

Representative computed WCAG contrast ratios: primary dark-workspace text **13.39:1**, muted dark-workspace text **7.69:1**, primary dossier text **11.03:1**, dossier body **4.66:1**. This is not full WCAG certification; manual screen-reader testing and exhaustive component-state contrast review remain future work. Map overview text is small at mobile scale; the open module list and full inspector are the readable investigation path.

## Failures found and resolved

1. First harness run stopped on an ambiguous close-button locator; selected the intended first dialog close control.
2. Initial comparison assertion wrongly assumed two artifacts from the same mini-project were unrelated; now separately tests compatible and incompatible IDs.
3. Populated Runs overflowed at 768 px because of intrinsic grid minimum width; bounded workspace/columns fixed it and regression passed.
4. Visual pass found crowded dense domains, insufficient imported artifact inspection and small labels; these were corrected and verified. See VISUAL_REVIEW_V2.md.

No failed/skipped scenario is hidden in the final receipt. Intermediate runs were not counted as successful. Full backend/research test suites were not run: no backend source was changed, and private/research artifacts remained outside scope.

## Reproduction

From the V2 directory:

```sh
node --test tests/*.test.cjs
```

With Playwright available in Node's module resolution and the two local preview services running as documented in SHOWCASE_V2.md:

```sh
node tests/browser.cjs
```

The report JSON names every scenario and retains raw measurements. Shell syntax checks, privacy scan, staged diff checks and branch publication are recorded in DELIVERY_STATUS.md.
