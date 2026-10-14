# PROMPT 028 verification

Status: **P028_SECURITY_STATIC_DATAFLOW_V1_COMPLETE** after engineering QA and immutable receipt freeze.
Publication must be confirmed by the final Git checks; no P029/UI work is started.

## A. Lineage

- Initial HEAD/P027 closure: `38778bb25e1fd993ce80fc50c207a76e958d4eaf`; initial tree: authorized unstaged deletion only.
- P027 implementation: `899cec534849a899e7d4ddf28a8cad5672e0fffc`.
- P026 closure source: `1fcb8e8f1f3eaf049c2de4f282910309088eed2f`.
- P025 evaluation source: `cecb6eb22036383b9b2f210cebc41c82ccee75c2`.
- P028 implementation: `d790da7e50e393ffe0225007182b64efd1db4979`.
- P025/P026 read-only acquisition, seals, model/truth/source/doc checks: PASS.
- P027 seals, source bindings and historical Git-bound docs: PASS. No P027 artifact regenerated.
- 151 protected Architecture/Hybrid/parser/IAM/API source files unchanged.

- P025_primary: `f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e`
- P025_hypothesis: `43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053`
- P025_receipt: `fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6`
- P026_scientific_registry: `53420d0aa167ebb99814adb498f3b84597b096f73fe1f77c5c467dc7882a8db1`
- P026_claim_registry: `e1efe0a9ab675b648cc303d1ec6a4b68148a6d467828d866511f390406440622`
- P026_closure: `69e17bfe8d573b580ff40099eece74f18dbc90d3be24e5e0077842d55fc97b26`

## B. Dataflow engine

`run_security_analysis` is the application entry point; existing Java/TypeScript parser adapters
and generic locations are reused. V1 performs bounded intraprocedural assignments/aliases,
concatenation/templates, argument evaluation, local return-expression traversal, branch joins and
static object/array projections. Calls remain interprocedural boundaries; function summaries are
not guessed. Dynamic fields, closures/framework binding, loops, try/switch and heap alias updates
remain partial/UNKNOWN. No whole-program/compiler-complete claim.

Lattice: UNKNOWN dominates, otherwise taint dominates; sanitation is rule-specific and intersected
across tainted contributors. New taint invalidates sanitation. Unsupported transformations preserve
known incomplete source paths and produce POTENTIAL; UNKNOWN alone never becomes a vulnerability.
Defaults: 32 flow steps, 512 tracked values, 10,000 visited nodes/function, 32 branch states/paths,
60,000 file nodes, depth 64, 2 MiB source bytes. Bounds produce diagnostics/partial or failed input,
never a false safe result. No added dependency.

## C. Detector matrix

| Rule | Detector status | Java | TypeScript | Java fixtures | TS fixtures |
|---|---|---|---|---:|---:|
| SEC001 | IMPLEMENTED_V1 | IMPLEMENTED_V1 | IMPLEMENTED_V1 | 5 | 5 |
| SEC002 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 3 | 3 |
| SEC003 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 4 | 15 |
| SEC004 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 3 | 3 |
| SEC005 | PARTIAL_V1 | PARTIAL_V1 | CONTRACT_ONLY | 3 | 1 |
| SEC006 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 2 | 2 |
| SEC007 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 2 | 6 |
| SEC008 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 4 | 3 |
| SEC009 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 4 | 3 |
| SEC010 | PARTIAL_V1 | PARTIAL_V1 | PARTIAL_V1 | 3 | 6 |

Counts: 10 executable registered detectors; IMPLEMENTED_V1=1; PARTIAL_V1=9; CONTRACT_ONLY=0 at
rule level. TypeScript SEC005 remains CONTRACT_ONLY. Exact API and per-rule limitations are in
[Security analysis V1](../security/SECURITY_ANALYSIS_V1.md) and the versioned capability matrix.
These statuses describe the declared tested scope, not ecosystem completeness.

## D. Rule execution

Normal orchestration selects registered requested detectors, validates rule/language/context/
source/version bindings, executes them, deduplicates identical logical findings and reports coverage.
Source failures and detector errors are FAILED/not evaluated. Unsupported requests are separate;
all initial flow/API packs preserve PARTIAL coverage. Exceptions are published only as safe codes.
NOT_APPLICABLE is applicability metadata, not a fabricated finding.

Engineering inputs: 80 inert synthetic fixtures (33 Java, 47 TypeScript); 36 expect supported/static/
potential patterns and 44 expect no finding. These are expected engineering behaviors, not human
Security ground truth. Additional parametrized tests cover API variants, boundaries and limits.
No fixture source is executed as shell/network/deserialization code. No fake production result path.

## E. Java / TypeScript

Java: explicitly imported javax/jakarta Servlet request getters, java.sql.Statement, Runtime/
ProcessBuilder, Files/Paths, constructed URL/ObjectInputStream, typed JSP writer, crypto/random/
ScriptEngine subsets. TypeScript: imported express.Request fields, pg, child_process, fs/path,
node:http/https, typed DOM HTML writes, default DOMPurify, crypto and selected code evaluation APIs.
The registry contains 22 typed API entries bound to tests and semantics.
Spring binding, JavaScript/TSX Security contracts, wildcard/callable aliases and framework wrappers
are not claimed. Safe bind parameters/constant inputs/argv, textContent, JSON parsing, secure random,
strong crypto and non-security purpose examples are covered. normalize-only is not a sanitizer;
confinement/allowlist proof remains unsupported.

## F. Findings

Frozen P027 SEC schemas and UUID5 identity are used unchanged. Distinct source paths at one sink
produce separate findings; exact duplicates collapse. Every emitted fixture finding has valid
file identity/language/locations/evidence refs/version; flow findings bind source and sink and an
ordered path. Deterministic double runs and Pydantic JSON round trips: PASS. SEC001 candidates
retain no literal, preview or secret digest and serialize `[REDACTED]`. No raw private code,
credentials, authorization headers or exception messages are persisted. Input/flow value repr
hides raw bytes/literals. UNKNOWN/failed/unsupported coverage cannot appear as a clean evaluation.

## G. Isolation

AST import firewall (including new engine/service) and existing runtime Architecture rejection
checks: PASS. Security imports no Architecture/Hybrid/calibration/benchmark/provider implementation.
Architecture does not import Security; no SEC rule/evidence/finding enters a Hybrid evidence vector,
score or Architecture decision. The receipt adapter performs only read-only historical checks.
ARCH rule definitions, scientific models/metrics and source hashes unchanged. No generic parser/IAM
change was needed. API_CHANGE=NO; PERSISTENCE_CHANGE=NO; no migration or combined risk score.

## H. Provider / science

Live provider calls=0; connectivity calls=0; credential reads=0; paid execution=0.
`.env.ai.local` was not opened, hashed, serialized, logged or staged; existing Git ignore verified.
No Security benchmark, labels, truth, LLM classification, remediation/adjudication, training or
Architecture scientific re-evaluation. Security Precision/Recall/F1/FPR/FNR/accuracy=NOT_AVAILABLE.
CORE_THESIS_COMPLETE remains true; prior accepted claims unchanged.

## I. Quality

- All Security tests: **217 passed** (including 142 new P028 tests).
- Combined parser/IAM, Static/Graph, semantic offline, Hybrid, API/findings and P025/P026 regressions:
  **685 passed**.
- Full `make check` on implementation: **2532 passed**; Ruff PASS; format PASS (529 files); strict mypy PASS (255 files).
- Determinism, serialization, evidence locations, false-positive fixtures, bounded UNKNOWN,
  sanitizer invalidation, failure semantics, import/runtime firewall and privacy checks: PASS.
- P027 verifier executed before edits: PASS. P028 read-only P026/P027 historical freeze audit: PASS.
- New public source/docs/fixtures/receipts secret audit and `git diff --check`: PASS.
- Only commands actually executed are recorded in `quality-verification.json`.

The final test-path portability correction was rechecked with all 217 Security tests and
full Ruff/format checks. Production implementation did not change after `make check` started.
No fixture pass rate is presented as empirical Security effectiveness.

## J. Freezes

Seven deterministic, timestamp-free P028 engineering fingerprints:

- `analysis-protocol.json`: `8515ef759a9cd890fff18aab20b68f80b6d61a254d7fede0404cae22927d23d2`
- `detector-registry.json`: `3a7a31f8515de16f44de1e98416e3e89151e05db226bb4a6b465ff3b19100ab0`
- `security-api-registry.json`: `ebffa8579e93b3502d8bc686beb50940dd694617063fa33d6532bd44fe7c4741`
- `security-capability-matrix.json`: `69431d3646e67596010c09f9d24e791b8fefa575f88231809c44d91585a6d8da`
- `fixture-inventory.json`: `1c7dad3b267644cf7ce501e4931787567253d22c0c6ed72d283881cb7e970b9a`
- `analysis-boundary.json`: `92c24315c03f78b5f21941d112c16edf3778b7396bb810f03ce3708aa09ea6f9`
- `security-analysis-v1.json`: `79a0274183d276f9c32b8c5a1f76f8ecc776ee12f61dd008987b4cb50683f708`

P027 unchanged fingerprints:

- `sec-rule-registry.json`: `9389a584676333887efb1d0e259078ecf8837dfe3f0492bf6c6907640e1c5320`
- `security-domain-model.json`: `4330b32e557a4f8e6670f4deecb442d0bcb04763ddf750e6cb00c78409efe9ac`
- `security-analysis-boundary.json`: `ccd79bd21f87eaa4e868cfc93379dd97182d8e3b39fa2af3a5b5c522d1df27b0`
- `security-boundary-receipt.json`: `4de191d80be96c2fbd46d4486e6a5b093a3285cc0ba11136817338ff0f94ef43`
- `security-capability-matrix.json`: `76c634aa9abde653784ad3d6f0e49805fb1f55b8c6288b8af370645803c264bb`
- `security-foundation.json`: `0b83e2ff509249829c9c61a2b32cb800805ed186fb8b7b67d2ae8f3d75e0fc5f`

The separate freeze index binds all nine public JSON artifacts, implementation/tests/fixtures and
documents. Public registries contain API/evidence metadata and synthetic fixture IDs/expectations;
no private project snippets or per-case private evidence. Quality is bound independently. The
verifier checks immutable byte inventory, seals and deterministic metadata reconstruction.

## K. Git publication

Implementation commit: `d790da7e50e393ffe0225007182b64efd1db4979` (`feat: implement security static dataflow analysis v1`).
The subsequent `chore: freeze security analysis v1 verification` commit publishes this report and
all nine engineering receipts. Its exact SHA and remote equality are recorded in the final response
because a document cannot include its own Git commit hash. Required publication is ordinary
`git push origin main`; no force push, rebase, reset, amend or squash. Origin starts at the P027
closure `38778bb25e1fd993ce80fc50c207a76e958d4eaf`. After push, local HEAD must equal origin/main.
All 13 implementation public files plus final nine receipts/report are included in those commits.
No new private P028 file is created. Existing ignored credentials/private historical experiments
remain ignored. The only permitted final working-tree change is the authorized unstaged deletion
`index(визуал).html`; it is not read, restored, modified, staged, committed or fingerprinted.

P029 handoff: source-safe summaries, framework packs, better alias/object fields, sanitizer/
confinement/allowlist proofs, call graph resolution and higher-fidelity flow rules. Optional semantic
escalation requires a separate design/authorization. P029 and UI remain NOT_STARTED.
