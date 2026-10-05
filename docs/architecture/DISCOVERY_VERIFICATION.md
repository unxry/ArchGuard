# PROMPT 007 verification

Run: 2026-10-05. PROMPT 006 audited at HEAD 1ccebf0: 626 tests passed, coverage 94%, diff-check
green, only stage 006 changes. Local commit **280f26c**:
`feat: add graph engine and structural architecture analysis`. No push/remote/global identity changes.
PROMPT 007 remains a separate uncommitted reviewable diff.

## Quality gate

`uv sync --locked --extra dev`, `make check` passed: **704 passed, 0 failed, 0 skipped**, 9.35 s,
overall branch-aware coverage **94%**. Ruff check/format: 227 formatted files; strict mypy: 141
source files, no issues. `git diff --check` includes new files through intent-to-add; staged content empty.
Existing 626 tests remain green; added 78 discovery tests. One existing IAM CLI assertion explicitly
updated from ECMAScript extractor 1.0.0 to 1.1.0 for additive decorator-name metadata. Privacy,
determinism, exact-version and old static/graph invariants remain tested.

Discovery coverage: signals/config/summary 100%, classification 97%, analyzer/modules 96%, models
88%. Some invalid-contract/unsupported-input branches remain uncovered; no universal accuracy claim.
Tests verify actual Local/ZIP Java/TS/TSX pipeline, annotation/decorator arguments excluded, generic
Component/Injectable UNKNOWN, inheritance/import provenance, bounded suffix/path signals, unknown
graph cycle, role/layer conflicts, minimum strengths/size, explicit/ambiguous roots, shared seeds,
exact cohesion/matrices, exact 7/10 assignment coverage, input contracts and canonical round-trip.
Application spies prove one IAM build and one GraphAnalyzer call per discovery. Root/order copies
give identical artifacts; line changes preserve hypothesis IDs and change source/snapshot metadata.

## Manual CLI scenarios

`.venv/bin/archguard architecture discover tests/fixtures/discovery/<fixture> --namespace
prompt007-verification --config examples/discovery/structural-baseline.json --json`.
No target spec; every scenario COMPLETE, exit 0, no ARCH findings.

| Fixture | Components | Strong / moderate / weak role hypotheses | Unknown roles | Ambiguous roles/layers | Modules | Assigned/unassigned | Role coverage | Layer coverage | Cyclic SCC |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| java-layered | 6 | 6/0/0 | 0 | 0/0 | 2 | 6/0 | 1 | 1 | 0 |
| typescript-layered | 6 | 5/0/1 | 1 | 0/0 | 3 | 5/1 | 0.833333333333 | 0.833333333333 | 0 |
| mixed Java/TS/TSX | 12 | 11/0/1 | 1 | 0/0 | 5 | 11/1 | 0.916666666667 | 0.916666666667 | 0 |
| conflict | 1 | 1/0/0 | 0 | 0/1 | 1 | 0/1 | 1 | 0 | 0 |
| unknown | 3 | 0/0/3 | 3 | 0/0 | 0 | 0/3 | 0 | 0 | 1 |
| features | 8 | 5/1/2 | 2 | 0/0 | 4 | 7/1 | 0.75 | 0.625 | 0 |

WEAK counts include UNKNOWN placeholder hypotheses; coverage excludes UNKNOWN and ambiguous.
Mixed layers: PRESENTATION=2, APPLICATION=2, DOMAIN=1, PERSISTENCE=2, INFRASTRUCTURE=4,
UNKNOWN=1, AMBIGUOUS=0. Roles: CONTROLLER/SERVICE/REPOSITORY/ADAPTER/CLIENT each 2,
DOMAIN_MODEL=1, UNKNOWN=1. Java and TS feature namespaces remain distinct: two orders, two payments,
one weak ui candidate. Widget TSX remains UNKNOWN/unassigned.

Mixed layer matrix: PRESENTATION→APPLICATION=2, APPLICATION→PERSISTENCE=2,
INFRASTRUCTURE→INFRASTRUCTURE=2. Six unique projected edges, not twelve supporting import/call
proof records. All four accepted feature modules have only internal dependencies (orders 2 each,
payments 1 each); no cross-module cells. Weak ui has no accepted assignment/dependencies.

Conflict: strong Controller role + domain path → AMBIGUOUS layer with DOMAIN/PRESENTATION evidence.
Unknown fixture has Foo/Bar/Baz directed cycle; all roles/layers UNKNOWN, no ARCH003. Feature fixture:
orders internal/incoming/outgoing=2/0/1, cohesion=2/3; shared=1/1/0, cohesion=1/2. ui size 1 remains
weak/unassigned under minimum size 2. Controller→Repository-like observation never becomes ARCH002.

## Determinism and Linux

Two actual mixed CLI subprocess exports A/B: `cmp` exit 0. Docker image built after green local gate:
`docker build -f docker/Dockerfile -t archguard:prompt007 .`. Read-only fixture/config mounts,
`--rm --network none --read-only --tmpfs /tmp`, existing nonroot image user.

Local Darwin arm64 Python 3.13.14 versus Linux aarch64 Python 3.13.16: full canonical discovery JSON
**byte-identical**, `cmp` exit 0. **168,197 bytes**, SHA-256:
`0375c0a98782007ce21db2a29e3242f11073be0762cbc2d397a68a05b62921e3`.
Additional assertions compare entire discovered model, hypothesis IDs/strengths/evidence, modules,
matrices, statistics, graph metrics and reproducibility. Config precision retained; computed ratios/
graph floats canonicalized to 12 decimal places. Temporary results/config/logs removed.
This is a representative runtime comparison, not a guarantee across all future versions/platforms.

## Self-review and limits

Discovery source/use case contain no Finding construction, target specification/classification use,
NetworkX imports, numeric confidence, normative violation wording or architecture.yaml generation.
Graph position does not assign semantic roles; candidates remain uncalibrated observations. Registry
uses small data-driven hints, does not verify framework imports/runtime behavior. Source arguments
and private JSX marker are absent from output. Profile/version metadata are explicit and deterministic.

Package/directory module seeds are hypotheses, not Maven/npm ownership. Root conventions may need
configuration; unknown/ambiguous/unassigned valid. Exact unweighted graph metrics and conservative
resolution/provenance/processing budgets limit coverage. Cohesion is not modularity/architecture quality.
Coverage is assignment coverage, not precision/recall/accuracy; strengths are not probabilities.

LLM/embeddings, graph-guided source context, Hybrid/calibration/scoring, Security/taint/routing,
health score, automatic target conversion, DB/analysis API/frontend remain unimplemented.
Next only after review: PROMPT 008 Graph-Guided Context Construction & AI Architecture Analysis
Foundation, or corrections to this stage. See [Discovery](ARCHITECTURE_DISCOVERY.md),
[Classification](STRUCTURAL_CLASSIFICATION.md), [Modules](MODULE_DISCOVERY.md).
