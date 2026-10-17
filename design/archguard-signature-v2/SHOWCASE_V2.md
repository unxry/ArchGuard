# ArchGuard Signature Experience V2 — review entry

Open **`index.html` in this directory** with its sibling `src/` and `style.css` files present. This offline showcase requires no install, backend, CDN or provider key. Russian is the default; EN is in the header. All demo data is authored and labelled. This is the completed local investigation experience, not a production project-analysis service.

For a development preview, run from this directory:

```sh
node dev-server.cjs --port 8779
```

Open `http://127.0.0.1:8779/`. Stop the server with Ctrl+C. The optional real system-only connection uses the existing project Python environment; from the repository root:

```sh
PYTHONPATH=src python design/archguard-signature-v2/tests/system_backend.py
```

Then start the preview with:

```sh
node dev-server.cjs --port 8779 --backend http://127.0.0.1:8780
```

That helper constructs `Settings(_env_file=None)` and calls the real FastAPI app. Only `/health` and `/api/v1/system/info` are bridged. It does not analyze projects or read a dotenv file.

## Suggested review route

1. Projects → current project → Atlas. Select CheckoutController, replay a direction and open a linked finding.
2. Choose 40 and 216 modules. Open a domain, move between pages, search a module, focus and fit. Pulses are finite static relationship explanations.
3. Security → SEC002, SEC006, SEC007, SEC008, SEC005. Compare supported proof, unknown flow, insufficient evidence, synthetic scoped certificate and unsupported state.
4. Models → rules, discovery, context/Hybrid, capabilities. These distinguish explicit rules, structural candidates and semantic hypotheses.
5. New project → Git/local/ZIP. Validate a source and inspect the CLI plan/gate. Cancel a demo run, then complete one.
6. Import `tests/fixtures/architecture-graph.json`, then `architecture-check.json`. Verify that demo data disappears; actual file relations/ARCH001 evidence replace it. Import context/Hybrid/discovery artifacts for their specialized detail.
7. Runs → original JSON export, provenance, compatible session comparison and optional system-only service handshake.
8. Repeat on mobile, switch EN, and enable reduced motion in browser settings.

## Evidence

- [Overview RU](previews/overview-ru-1440.png), [EN](previews/overview-en-1440.png), [1920 desktop](previews/overview-1920.png)
- [Atlas](previews/atlas-12.png), [directional pulse](previews/atlas-directional-pulse.png), [216 clusters](previews/atlas-216-clusters.png), [bounded drilldown](previews/atlas-216-drilldown.png)
- [Finding](previews/finding-investigation.png), [Security](previews/security-supported.png), [unknown boundary](previews/security-unknown.png)
- [Onboarding](previews/onboarding-source.png), [Git gate](previews/onboarding-git-gate.png), [loading](previews/loading-demo.png), [error](previews/invalid-import-error.png)
- [Real CLI graph](previews/real-cli-graph.png), [ARCH001](previews/real-cli-arch001.png), [Hybrid](previews/real-cli-hybrid.png), [context](previews/real-cli-context.png)
- [Mobile overview](previews/mobile-overview.png), [mobile Atlas](previews/mobile-atlas.png), [mobile Security](previews/mobile-security.png)
- [Actual browser motion video](previews/motion-showcase.webm)
- [Functional/performance receipt](previews/browser-report.json), [validation](VALIDATION.md), [visual review](VISUAL_REVIEW_V2.md)

## Technical review

[Full capability audit](FULL_PRODUCT_CAPABILITY_AUDIT.md) · [backend/UI matrix](CAPABILITY_TO_INTERFACE_MATRIX.md) · [coverage and remaining boundaries](UI_CAPABILITY_COVERAGE_REPORT.md) · [frontend architecture](FRONTEND_ARCHITECTURE.md) · [import contracts](REAL_CLI_IMPORT.md) · [Security UX](SECURITY_UX_SPEC.md) · [frontend security](FRONTEND_SECURITY_REVIEW.md) · [production roadmap](IMPLEMENTATION_ROADMAP.md).

Files are intentionally isolated under `design/archguard-signature-v2/`, based on P038 `49087a4`, in `design-lab/archguard-signature-v2`. No merge into main is part of this delivery. Review completion and publication receipt are recorded in `DELIVERY_STATUS.md`.
