# P039.1 validation

Chromium 151.0.7922.34; 1440×1000 desktop; 390, 768, 1280 responsive checks.

69 browser checks passed, 0 failed, 0 JS errors, 0 console errors, 0 external requests. Gallery additionally verifies loaded WebM metadata and mobile page width.

216 source nodes, 18 visible nodes, 4× CPU throttle: 240 frames, p95 interval 17.5 ms, 0 frames above 50 ms, 0 long tasks during the finite pulse interval. Observed CLS for the exercised session: 0.01268. Heap after GC: 3,007,688 → 3,002,284 bytes across 20 graph mounts/unmounts. These are local measurements, not universal FPS guarantees.

Both file:// and localhost entry points tested. Import covers ten supported public P039 fixtures; graph-thresholds is configuration and correctly rejected as a result artifact. Hidden visibility lifecycle is simulated with the document event, explicitly labelled in the report.

Changed scope: design/graphite-studio only. Original P039 remains at 4a73d9d56205ab040e0cc6e324959b3b2add0402. Local main remains at 5e384141a6f9dbafb6654886e83fcad57def564e. Scientific core/backend untouched; no merge.
