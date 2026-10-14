# Bounded Security interprocedural analysis V2

Protocol: `security-interprocedural-v2`. P029 adds engineering fidelity; it does not create a
Security benchmark, human ground truth or effectiveness metrics. P027 meanings/schemas and all
P028 source/fixture/JSON history stay frozen. V2 lives in separate modules and artifacts.

## Application service

`from archguard.security.analyzer_v2 import run_security_analysis` accepts the existing P027
`SecurityAnalysisContext`, classified V1 `SecuritySourceInput` bytes and optional `V2Limits`.
Callers do not build summaries, AST indexes or framework packs. `SecurityAnalyzerV2` also offers
a bounded in-memory summary cache across invocations. The V1 entry point remains unchanged.
Existing Java/TypeScript parser adapters and generic locations are reused; no parser/IAM,
Architecture rules/Hybrid, HTTP API, persistence, migration, provider or UI change is needed.

## Summaries and resolution

Typed summaries bind a deterministic declaration UUID, source reference, arity, protocol version,
parameter-to-return/sink/field effects, return/source/sanitizer effects, field operations,
call targets and explicit unknown effects. Fingerprints bind these semantic records. No bodies,
source excerpts, secret literals or internal cache source digests are serialized.

Symbolic parameter analysis builds summaries only for declarations with a parsed body. Actual
arguments and heap slots then specialize those bodies under the same bounds; summaries are not
guessed identity functions and no fixed-point or compiler-complete claim is made. Source within
a callee, returned values, argument-to-internal-sink flows and sanitizer returns are supported.
Call evidence records CALL_ARGUMENT, CALLEE_PARAMETER, CALLEE_RETURN and CALL_RETURN locations.
Parameter-to-field effects include constructor/setter writes where static slots are observable.

Resolution prefers lexical declared functions, same-class local methods, known local constructor
instances, explicit class static calls and explicit relative named/namespace exports. Java overloads
are filtered by arity; same-arity alternatives remain AMBIGUOUS. Renamed TS imports are resolved
against supplied module declarations. No filesystem/module fetching occurs. A declared instance
type without a known local instance remains PARTIAL and cannot apply a definite body summary.
Unrelated receiver methods never resolve merely by matching a function name.

EXACT/UNAMBIGUOUS_LOCAL may drive bounded specialization. PARTIAL/AMBIGUOUS/UNRESOLVED keep
UNKNOWN and diagnostics. Wildcards/re-exports/default module resolution, rest/default/destructured
parameters, inheritance/virtual dispatch, closures and framework callback lifecycle are unsupported.
Direct/mutual recursion returns UNKNOWN with a cycle diagnostic. No recursive fixed-point analysis.

Cache identity includes symbol identity, private whole-input graph source version, protocol,
configuration and remaining deterministic summary budget. Source digests stay private in memory,
never become secret-value fingerprints. Semantic node costs are charged identically for cache hits
and misses. Cache order/hits/timing are excluded from result fingerprints. Tests cover cold/hot output,
changed source/configuration, eviction and reversed input order.

## Fields, aliases and uncertainty

Local object/array literals allocate distinct deterministic bounded heap slots. Aliases share those
slots; static reads/writes, nested properties, constant indexes, safe/tainted overwrites and known
constructor initialization are supported. Same-named fields on different objects stay separate.
Dynamic indexes and unsupported writes remain UNKNOWN; known container sources may support only
a POTENTIAL downstream flow. Alias/field/object/node/candidate bounds produce partial diagnostics.
This is not a points-to analysis or unrestricted dynamic-container/heap model.

The four-state V1 lattice remains: UNTAINTED, TAINTED, SANITIZED, UNKNOWN. UNKNOWN never becomes
safe by default and cannot fabricate a source. Unresolved calls preserve known arguments/receiver
paths as incomplete; they invalidate sanitation. New taint invalidates sanitizer state. Immutable
alias transfers preserve valid proofs, while path/URL transformation or field mutation invalidates
the relevant safety proof. Known true/false branches are respected; unsupported control flow stays
partial. Zero findings never means secure; failed parsing/analysis/detectors are FAILED, not evaluated.

## Framework packs and rule status

17 genuine packs bind selected APIs, language, roles, rules, semantics, limitations and tests:
JAVA_SERVLET_V2, JAVA_SPRING_WEB_V2, JAVA_JDBC_V2, JAVA_HTTP_V2, JAVA_FILESYSTEM_V2,
JAVA_CRYPTO_V2, JAVA_PROCESS_V2, JAVA_SERIALIZATION_V2, JAVA_RENDER_SCRIPT_V2;
TS_EXPRESS_V2, TS_PG_V2, TS_NODE_HTTP_V2, TS_NODE_FS_V2, TS_DOM_V2,
TS_NODE_CRYPTO_V2, TS_PROCESS_SCRIPT_V2, TS_PRISMA_RAW_UNSAFE_V2.
Version-agnostic scope means the declared AST/API subset, not ecosystem/version completeness.

| Rule | V2 status | Java / TypeScript scope and remaining gaps |
|---|---|---|
| SEC001 | IMPLEMENTED_V2 (V1-equivalent) | Frozen literal credential patterns/redaction reused; no env/config acquisition or credential validation |
| SEC002 | PARTIAL_V2 | JDBC Statement/constant prepared bind, pg string/bind, explicit Prisma unsafe APIs through helpers; query objects/builders/tagged ORM proofs unsupported |
| SEC003 | PARTIAL_V2 | Helper shell strings, executable vs operands, spawn shell options and Java argv; tainted operands without shell remain POTENTIAL, not universally safe |
| SEC004 | PARTIAL_V2 | File-read/helper/field flows and narrow lexical confinement; no symlink/race/filesystem realpath proof |
| SEC005 | PARTIAL_V2 Java; CONTRACT_ONLY TS | Servlet InputStream to ObjectInputStream construction/read through helpers; unknown origin/filter stays partial; JSON is not an unsafe sink |
| SEC006 | PARTIAL_V2 | Java URL/node:http/https string/URL flows and exact host guards; options, DNS, redirects and broader scheme/port policy unmodeled |
| SEC007 | PARTIAL_V2 | JSP/typed DOM HTML sinks, helper/alias flow, default DOMPurify return proof; text sinks excluded; custom options/wrappers/context unknown |
| SEC008 | PARTIAL_V2 | MD5/SHA-1 helper facts and receiving security vs checksum context; DES/RC4/ECB explicit configuration; strong primitives excluded; unknown purpose POTENTIAL |
| SEC009 | PARTIAL_V2 | PRNG result facts through helpers/fields into token/session/reset purpose; simulation/game/parser uses and secure RNG excluded; arbitrary downstream use unknown |
| SEC010 | PARTIAL_V2 | Helper eval/Function/ScriptEngine/vm/string timers; constants/callbacks/reflection not fabricated sinks; unknown interpreters partial |

Sources require actual import/type/annotation evidence. Servlet Request getters/InputStream and
typed express.Request properties are supported; unrelated req-shaped objects are not sources.
Spring supports imported RequestParam/PathVariable/RequestHeader/RequestBody scalar annotation
bindings; DTO/model/lifecycle binding is not inferred. JavaScript/TSX Security contracts remain
undeclared. Framework identity never comes solely from words such as query/exec/eval/sanitize.

## Implemented proof subset

- SQL_PARAMETERIZATION: constant JDBC/pg query template plus separately transported bind values;
  no quote replacement or generic string sanitizer. Unknown templates/wrappers remain partial.
- PATH_CONFINEMENT: trusted absolute canonical root, canonical derived path, dominating rejecting
  boundary-aware containment guard, same path at file sink. Java Path segment containment and
  POSIX path.resolve plus root+path.sep are modeled. normalize/resolve alone is insufficient.
  Changing a path, checking another variable/root or an unknown transform invalidates the proof.
- SSRF_ALLOWLIST: parsed URL identity, exact static host equality/list membership, reject mismatch,
  same unmodified URL at outbound sink. Substring/suffix/regex/scheme-only tests are not proofs.
  This does not prove DNS/IP rebinding, redirects or comprehensive destination policy safety.
- XSS_SANITIZATION: default imported DOMPurify for a modeled HTML sink, including proven helper
  returns. New taint, unknown/custom options/transforms or different output context invalidates it.
- COMMAND_ARGUMENT_BOUNDARY: constant executable with separate argv and known shell=false/default
  proves absence of modeled shell interpolation only. Tainted operands remain POTENTIAL argument
  injection; tainted executable/shell text produce stronger source-backed evidence.

Proof records expose only kind/rule/scope and concrete evidence locations, not path/host/query values.
Safety remains rule-specific. The public proof registry lists actual implemented/tested conditions,
invalidators and limitations, not speculative future sanitizers.

## Bounds, evidence and reproducibility

Defaults: call depth 4 including the entry frame, expansions/declarations 256, recursive visits 1,
targets/call 4, nodes/summary frame 4096, cache entries 256, total path steps 64, aliases/object 32,
heap objects 256, fields/object 64, total heap fields 2048, source files 64, source bytes/file 2 MiB,
total source bytes 8 MiB, total actual nodes 50,000, total symbolic nodes 50,000, candidates 512.
V1 branch/value/file/expression bounds remain in `V2Limits`. Bounds are deterministic, reported
as partial/unknown/failed intake, never safe. Execution is serial; stress fixtures assert termination
and diagnostics without sleeps, timing thresholds or performance conclusions.

P027 finding schemas/namespace/UUID5 identity stay authoritative. Equivalent source/call-context
paths are coalesced deterministically to their longest informative representative; distinct sources
or call contexts remain distinct findings. Exact duplicates collapse. Evidence covers real positions,
call boundaries, propagation, sanitizer/proof and sink where modeled. Static crypto/random evidence
retains helper/use references. Exception text/stack traces, bodies, secret previews and value hashes
are not published. SEC001 remains `[REDACTED]` by construction.

`scripts/prompt029_security_analysis.py audit|freeze|verify` checks read-only P025/P026 scientific
seals, source/doc bindings and exact P027/P028 historical inventories. Historical JSON/source is
never rebuilt against V2. Eleven new public JSON files under
`experiments/security/security-interprocedural-v2/` freeze nine protocol/registry/manifest fingerprints,
quality and immutable source/test/fixture/doc inventory. Freeze requires completed QA and zero
provider/connectivity/credential activity. Architecture/Security import and runtime firewalls stay
permanent; no Security evidence/finding/rule enters an Architecture Hybrid vector/score/decision.

## P030 handoff

P030 may establish a prospective Security benchmark protocol, independent human truth strategy,
balanced Java/TS cases, mutation/control design, dev/final separation, per-rule applicability and
metric definitions. Labels must be independent of detector output. P029 creates only parsed inert
engineering fixtures: no TP/FP/TN/FN, Precision/Recall/F1/FPR/FNR/accuracy or detection-rate claims.
Security ground truth/effectiveness: NOT_AVAILABLE. Provider/connectivity/credential reads/spend: 0.
P030, semantic escalation and UI are not started.
