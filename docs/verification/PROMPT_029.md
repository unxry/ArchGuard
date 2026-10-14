# PROMPT 029 verification

**P029_SECURITY_INTERPROCEDURAL_V2_COMPLETE** after engineering QA and immutable V2 freeze.
Git publication is confirmed by the final post-commit remote checks, recorded in the final response.
P030/UI are NOT_STARTED. [Scope and limitations](../security/SECURITY_ANALYSIS_V2.md).

## A. Lineage

Initial HEAD/P028 closure: `e93ada51108223e784d38df513183632a48b20ba`. Actual P026/P027/P028 ancestry checked.
P028 implementation: `d790da7e50e393ffe0225007182b64efd1db4979`. P027 implementation:
`899cec534849a899e7d4ddf28a8cad5672e0fffc`; P027 closure:
`38778bb25e1fd993ce80fc50c207a76e958d4eaf`.
Initial P028 verifier: PASS before edits. All P028 JSON bytes, source, fixture/test bindings and
historical Git-bound docs verified read-only. Authorized HTML deletion preserved unstaged throughout.

- P025_primary: `f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e`
- P025_hypothesis: `43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053`
- P025_receipt: `fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6`
- P026_scientific_registry: `53420d0aa167ebb99814adb498f3b84597b096f73fe1f77c5c467dc7882a8db1`
- P026_claim_registry: `e1efe0a9ab675b648cc303d1ec6a4b68148a6d467828d866511f390406440622`
- P026_closure: `69e17bfe8d573b580ff40099eece74f18dbc90d3be24e5e0077842d55fc97b26`

## B. Interprocedural core

Typed FunctionSummary/ParameterFlow/ReturnFlow/SinkEffect/SanitizerEffect/FieldEffect/UnknownEffect
contracts describe parameter-to-return/sink/field, field-to-return, callee source and sanitizer return
relationships. Symbolic effects are cached; actual bodies specialize against arguments and heap
under bounds. Only parsed body-backed declarations generate summaries. No speculative external
body, identity-return assumption or fixed-point claim.

Local/lexical functions, same-class methods, known constructor instances, explicit class static
calls and relative named/namespace TS imports are supported within declared scope. Renamed imports
and arity filtering are tested. Same-arity overloads/multiple targets stay AMBIGUOUS; unknown instance
dispatch stays PARTIAL and does not apply a definite summary. Unresolved transformations preserve
known input paths as incomplete. Direct/mutual recursion terminates UNKNOWN with diagnostics.

Defaults: call depth 4 including entry frame; expansion/declaration limit 256; recursion visits 1;
targets 4; nodes/summary frame 4096; cache entries 256; total flow steps 64; actual and symbolic total
node budgets 50,000 each. Cache keys bind symbol, private full input-source graph version,
protocol/configuration and deterministic remaining budget. No source digest/raw source is published.
Cached semantic node costs are charged identically; cold/hot cache, changed source/configuration,
eviction and reversed input order tests verify byte-identical canonical output where inputs agree.

## C. Object / field flow

SUPPORTED within bounded scope: local object/array slots, basic aliases, nested static properties,
constant indexes, field writes/reads, safe and tainted overwrites, observable constructor/setter
initialization. Distinct objects with identical field names remain distinct. Shared aliases observe
writes. Dynamic indexes/unsupported heap/dispatch/control flow remain UNKNOWN/PARTIAL, never safe.
Path/URL mutation and unknown transformations invalidate proofs. Defaults: aliases/object 32,
heap objects 256, fields/object 64, total heap fields 2048, candidates 512. Source files 64,
2 MiB/file and 8 MiB total; other V1 node/value/branch/depth guards remain active.
Stress tests cover deep/wide/recursive calls, alias/field/object/node/candidate/target limits without
timing assertions. This is not arbitrary heap points-to or whole-program container analysis.

## D. Framework packs

Counts are implemented semantic API groups, not ecosystem coverage. All packs are PARTIAL_V2;
exact imports/types/annotations and declared conditions/limitations bind their tests.

| Pack | Language | Framework/library | Sources | Sinks | Sanitizers | Boundaries | Rules |
|---|---|---|---:|---:|---:|---:|---|
| JAVA_CRYPTO_V2 | JAVA | java.security/javax.crypto | 0 | 0 | 0 | 0 | SEC008, SEC009 |
| JAVA_FILESYSTEM_V2 | JAVA | java.nio.file | 0 | 1 | 0 | 1 | SEC004 |
| JAVA_HTTP_V2 | JAVA | java.net.URL | 0 | 1 | 0 | 1 | SEC006 |
| JAVA_JDBC_V2 | JAVA | JDBC | 0 | 2 | 0 | 1 | SEC002 |
| JAVA_PROCESS_V2 | JAVA | java.lang process APIs | 0 | 1 | 0 | 1 | SEC003 |
| JAVA_RENDER_SCRIPT_V2 | JAVA | JSP/ScriptEngine | 0 | 2 | 0 | 0 | SEC007, SEC010 |
| JAVA_SERIALIZATION_V2 | JAVA | java.io.ObjectInputStream | 0 | 1 | 0 | 0 | SEC005 |
| JAVA_SERVLET_V2 | JAVA | javax/jakarta Servlet | 2 | 0 | 0 | 0 | SEC002, SEC003, SEC004, SEC005, SEC006, SEC007, SEC010 |
| JAVA_SPRING_WEB_V2 | JAVA | Spring Web scalar annotations | 1 | 0 | 0 | 0 | SEC002, SEC003, SEC004, SEC006, SEC007, SEC010 |
| TS_DOM_V2 | TYPESCRIPT | DOM/DOMPurify | 0 | 1 | 1 | 1 | SEC007 |
| TS_EXPRESS_V2 | TYPESCRIPT | express.Request | 1 | 0 | 0 | 0 | SEC002, SEC003, SEC004, SEC006, SEC007, SEC010 |
| TS_NODE_CRYPTO_V2 | TYPESCRIPT | node:crypto + Math | 0 | 0 | 0 | 0 | SEC008, SEC009 |
| TS_NODE_FS_V2 | TYPESCRIPT | node:fs/path (POSIX lexical scope) | 0 | 1 | 0 | 1 | SEC004 |
| TS_NODE_HTTP_V2 | TYPESCRIPT | node:http/https + WHATWG URL | 0 | 1 | 0 | 1 | SEC006 |
| TS_PG_V2 | TYPESCRIPT | pg | 0 | 1 | 0 | 1 | SEC002 |
| TS_PRISMA_RAW_UNSAFE_V2 | TYPESCRIPT | PrismaClient explicit unsafe APIs | 0 | 1 | 0 | 0 | SEC002 |
| TS_PROCESS_SCRIPT_V2 | TYPESCRIPT | node:child_process/vm + built-in code evaluation | 0 | 2 | 0 | 1 | SEC003, SEC010 |

Servlet getters/InputStream and express.Request fields are supported; unrelated req/body shapes
are not sources. Spring scalar imported annotations are supported, DTO/model/lifecycle binding is
not inferred. HTTP/query options objects, ORM tagged templates/query builders, wildcard/re-exports,
unknown callback/closure dispatch and JavaScript/TSX Security contracts remain unsupported.
API group count does not imply every framework overload/version is modeled.

## E. Proof semantics

SQL_PARAMETERIZATION: known constant JDBC/pg template plus separate bind transport; dynamic query
recontamination invalidates it. No generic manual escaping/string sanitization.
PATH_CONFINEMENT: canonical trusted root, canonical derived path, rejecting boundary-aware guard,
same path at sink. Java Path and POSIX path.resolve/root+sep subsets only. normalize/resolve alone,
wrong variable/root, suffix/prefix changes and unknown transforms do not prove confinement.
SSRF_ALLOWLIST: parsed URL identity, exact static host equality/membership, reject mismatches, same
unmodified URL at outbound sink. Substring/suffix/regex/scheme-only tests are not proofs. No DNS/IP
rebinding, redirects or comprehensive destination policy guarantee.
XSS_SANITIZATION: default imported DOMPurify and proven helper return for HTML sinks only. New
taint, custom options/unknown transforms or different rendering context invalidate it.
COMMAND_ARGUMENT_BOUNDARY: known constant executable/separate argv/shell=false proves no modeled
shell interpolation only. Tainted operands remain POTENTIAL argument injection, not universally
safe. Shell text/tainted executable have stronger source-backed evidence.
All proof records bind concrete locations and rule scope, with no private host/path/query literals.
Proof registry fingerprint: `71c878c72406a3856e6a4f9e6e3a0c7ac2bee45f79c503b1186f7abe4335332a`.

## F. Rule status V2

| Rule | V1 | V2 | Java | TypeScript | Interprocedural | Proof subset |
|---|---|---|---|---|---|---|
| SEC001 | IMPLEMENTED_V1 | IMPLEMENTED_V2 | IMPLEMENTED_V2 | IMPLEMENTED_V2 | NO | NONE |
| SEC002 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | SQL_PARAMETERIZATION |
| SEC003 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | COMMAND_ARGUMENT_BOUNDARY |
| SEC004 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | PATH_CONFINEMENT |
| SEC005 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | CONTRACT_ONLY | YES | NONE |
| SEC006 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | SSRF_ALLOWLIST |
| SEC007 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | XSS_SANITIZATION |
| SEC008 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | NONE |
| SEC009 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | NONE |
| SEC010 | PARTIAL_V1 | PARTIAL_V2 | PARTIAL_V2 | PARTIAL_V2 | YES | NONE |

10 executable registered detectors; IMPLEMENTED_V2=1 (SEC001 V1-equivalent), PARTIAL_V2=9,
CONTRACT_ONLY=0 at rule level. TypeScript SEC005 explicitly remains CONTRACT_ONLY.
SEC005 Java now separates stream origin, construction and read; trusted inert byte resources/JSON
are negative cases, unresolved origin/filter stays partial. Crypto facts propagate through helpers
and distinguish credential purpose from checksum/simulation; DES/RC4/ECB configuration stays an
explicit weak pattern, strong AES/GCM is negative. PRNG result facts reach token/session/reset
assignments and fields; secure RNG/simulation paths are negative. Remaining gaps are documented in
V2 matrix and scope guide. No full ecosystem completeness claim.

## G. Analysis honesty / findings

Fake/demo production output paths: 0. UNKNOWN becomes safe: NO. Unresolved call sanitizes: NO.
No finding means secure: NO. Framework matching solely by method/property words: NO.
Known source/sink evidence required for taint findings: YES. Bounds reported partial: YES.
P027 SEC finding schemas/namespace/UUID5 identity remain unchanged. V2 paths retain source, argument,
parameter, callee return/call return, propagation, optional sanitation/proof and sink references.
Equivalent source/call-context paths coalesce deterministically; distinct source/context/sink stays
distinct. Exact duplicates collapse. Qualitative evidence strength is not a probability.
SEC001 remains source-safe `[REDACTED]`; no secret literal/value hash/whole source/stack trace is
serialized. Static crypto/random effects retain helper and sensitive-use locations.
Failures are FAILED/not evaluated; partial and unsupported scope are separate. JSON round trips,
source locations, summaries, paths, findings, diagnostics and result fingerprints are deterministic.

## H. Metrics / provider

Security ground truth, Precision, Recall, F1, FPR, FNR, accuracy and detection rate: NOT_AVAILABLE.
97 parsed inert engineering fixtures: 29 Java, 68 TypeScript.
They are not a benchmark, dataset, empirical effectiveness measurement or authoritative truth.
No TP/FP/TN/FN computation. Provider calls=0; connectivity=0; credential reads=0; Security LLM=NO;
paid spend=0. Credential files are not opened/hashed/logged/staged; ignore rules unchanged.

## I. Science / isolation

P025 drift=0; P026 drift=0; P027 meanings/domain drift=0; P028 history rewritten=NO.
Architecture/Hybrid/ARCH rules/API/persistence/migrations changed=NO; SEC enters Hybrid=NO.
151 protected Architecture/parser/IAM/API implementation files unchanged.
Static import firewall scans new V2 modules; existing runtime rejection checks enforce SEC evidence/
findings/rule IDs at Architecture boundaries. Historical verification checks immutable byte/seal/model/
truth/source/doc bindings read-only; no training, prediction, truth join or scientific re-evaluation.
CORE_THESIS_COMPLETE stays true; scientific freeze=PASS.

## J. Quality

- P029 tests: **126 passed**; all Security: **343 passed**.
- Summaries, local/import/static/ambiguous resolution, aliases/fields, framework identity, proof
  invalidation, SEC002–SEC010 behavior, false-positive packs, bounds/stress, determinism,
  serialization/redaction/locations and import/runtime firewall: PASS.
- Combined parser/IAM, Static/Graph, semantic offline, Hybrid, API/findings and P025/P026 regression
  suite: **811 passed**.
- Full `make check`: **2658 passed**; aggregate code coverage **85%**.
- Ruff PASS; format PASS (540 files); strict mypy PASS (261 files).
- P028 initial verification plus P029 historical P025/P026/P027/P028 audit: PASS.
- Privacy/secret audit/diff check: PASS. Only actually executed commands are in quality receipt.
Coverage is software test coverage; it is not Security detection effectiveness or fixture accuracy.

## K. Freezes

Nine deterministic, timestamp-free V2 fingerprints:

- `summary-protocol.json`: `d7df5af8fa93344b62c2fc54927a15a2b5b49aef0ffb358643556422f24d0388`
- `call-resolution-protocol.json`: `a9441b152dd0f1dd618b6e3deb3ef5c62818ebc33c3a09dd507870ed58259560`
- `framework-pack-registry.json`: `8af448d672af6cb8ce9462bf8032bcc1ec4d6b2fae0f10d09d52c658f3302283`
- `security-proof-registry.json`: `71c878c72406a3856e6a4f9e6e3a0c7ac2bee45f79c503b1186f7abe4335332a`
- `detector-registry-v2.json`: `822701f320cc0e604053c3d70556de0e43867de66695a329db201982a70897ab`
- `security-capability-matrix-v2.json`: `863c33fe50134ef653c6f3b5bad261e0f68668c8a805acc4eb16d8b56e874a24`
- `fixture-inventory.json`: `1c25575be16bfe4b22ea0733264707e8c7eb0b73697872cd774e14d39db8f79c`
- `analysis-boundary-v2.json`: `a89d108f8a2ca144da959adcb707a611fd6c8648c04ef34400bbea8aa000130c`
- `security-analysis-v2.json`: `c74ab979768cd597ffaa91567a7e6424a1ec4e28938a32889f8fd4572c35e2c7`

Eleven public JSON files freeze protocols, framework/proof/detector/capability registries, synthetic
fixture inventory, boundary, manifest, quality and source/test/fixture/doc byte inventory.
Public artifact contents are source-safe metadata; no private project snippets or runtime cache keys.
P027 canonical/domain and all P028 JSON/source/fixture pins remain exact. The standalone verifier
reconstructs metadata and checks immutable seals/inventory without executing provider/scientific work.

## L. Git publication / stop gate

Implementation: `ae99aa94c818f89a4d988bca99c73eb18b6a74cf` (`feat: add security interprocedural analysis v2`).
The subsequent `chore: freeze security analysis v2 verification` commit includes this final report
and all eleven V2 receipts. Its exact SHA and final local/remote HEAD equality are recorded in the
final response because a report cannot contain its own commit hash. Publication uses only ordinary
`git push origin main`; no force/reset/rebase/amend/squash. Remote starts at `e93ada51108223e784d38df513183632a48b20ba`.
All 14 public implementation files and the final receipts/report are committed/pushed. No new
private P029 artifact is created; existing ignored credentials/private historical experiments stay
ignored. Final required status: only authorized unstaged ` D index(визуал).html`; no P029 M/A/??.
The HTML is not restored, staged, read as evidence or fingerprinted.

SECURITY_CALL_SUMMARIES_V2_FROZEN; SECURITY_CALL_RESOLUTION_V2_FROZEN;
SECURITY_FRAMEWORK_PACKS_V2_FROZEN; SECURITY_SANITIZER_PROOFS_V2_FROZEN;
JAVA_SECURITY_V2_READY; TYPESCRIPT_SECURITY_V2_READY; SEC002_SEC010_FIDELITY_IMPROVED;
ARCHITECTURE_HYBRID_UNCHANGED; THESIS_SCIENCE_UNCHANGED;
SECURITY_EFFECTIVENESS_NOT_YET_EVALUATED; PROVIDER_CALLS=0; UI_NOT_STARTED.

P030 handoff: prospective benchmark protocol, independent human truth, balanced Java/TS cases,
mutation/control design, dev/final split, per-rule applicability and metric definitions. No labels
from detector output. READY_FOR_P030_SECURITY_BENCHMARK_FOUNDATION; P030 is NOT_STARTED. STOP.
