# Bounded static/dataflow Security analysis V1

Protocol: `security-static-dataflow-v1`. P027 rule meanings, schemas and historical artifacts
remain unchanged. This is engineering detector coverage, not an effectiveness experiment.

## Application entry point

`archguard.security.analyzer_v1.run_security_analysis(context, sources, limits=None)` returns
the existing `SecurityAnalysisResult`. Each `SecuritySourceInput` contains a classified
`RepositoryFile`, caller-provided bytes (excluded from repr) and a bound source-file UUID.
The caller supplies repository/snapshot identity and selected SEC rules. Optional IAM input
must bind supplied file IDs and paths. Existing Java/TypeScript parser adapters and generic
source-location utilities are reused; the derived AST index stays entirely inside Security.
No filesystem/env discovery, credential configuration, HTTP endpoint, persistence or UI is added.
The old P027 foundation-only analyzer remains available with its intentionally empty registry;
the V1 service supplies the executable registry and handles failures explicitly.

## Flow semantics and bounds

Analysis is intraprocedural, ordered and deterministic. Assignments, aliases, concatenation,
templates, arguments, conditional merges, literal arrays and static object projections propagate
values. Local return expressions are visited; calls do not receive guessed return summaries.
Nested functions have fresh environments; closures/framework callbacks are not resolved.
Loops, try/switch and dynamic properties are unsupported and produce UNKNOWN/partial diagnostics.
An unsupported loop invalidates local values rather than being executed once.

States are UNTAINTED, TAINTED, SANITIZED and UNKNOWN. UNKNOWN dominates merges. Otherwise a
tainted contributor keeps a result tainted; rule-specific sanitizer sets are intersected across
tainted contributors. Thus sanitized plus new taint loses the relevant sanitation. Assignment of
a genuinely constant value replaces prior taint. Unresolved calls preserve known source paths as
incomplete UNKNOWN paths and invalidate sanitation. UNKNOWN without a known source never produces
a taint vulnerability. A known source through an unresolved transformation can produce POTENTIAL
with explicit uncertainty, never SUPPORTED. Aliased object writes invalidate other known aliases
to UNKNOWN; this is not a heap analysis.

Default limits: 32 flow steps (including sink), 512 tracked values per function, 10,000 visited
nodes per function, 32 branch states/paths, 60,000 indexed AST nodes per file, expression depth 64,
2 MiB source bytes. Exceeded flow/path limits preserve bounded incomplete evidence. Other exceeded
limits stop/invalidate the affected analysis and emit diagnostics. Invalid/oversized source inputs
fail evaluation; zero findings never means secure. No recursion/whole-program solver is claimed.

## Tested detector scope

| Rule | Status | Java | TypeScript | Boundary |
|---|---|---|---|---|
| SEC001 HardcodedSecret | IMPLEMENTED_V1 | Literal declarations | Literal declarations | Credential prefixes/private-key markers or credible credential-purpose literals; placeholders, ordinary strings, UUIDs/hashes excluded |
| SEC002 SQLInjectionRisk | PARTIAL_V1 | Typed java.sql.Statement SQL arguments | Typed imported pg Client/Pool string query | Constant SQL/bind parameters are not tainted SQL; prepared statements excluded; wrappers/options objects unsupported |
| SEC003 CommandInjectionRisk | PARTIAL_V1 | Runtime.exec; ProcessBuilder executable | Imported child_process exec/execSync/spawn/spawnSync | Fixed executable argv operands alone are not shell injection; spawn shell=true combines operands; unknown shell options and explicit Java shell argv are partial |
| SEC004 PathTraversalRisk | PARTIAL_V1 | Files read APIs and Paths/Path propagation | Imported fs read APIs and path propagation | Constant path excluded; normalize/resolve never prove confinement; fixed-root confinement is not modeled |
| SEC005 UnsafeDeserialization | PARTIAL_V1 | Locally constructed ObjectInputStream readObject/readUnshared | CONTRACT_ONLY | Observed filters become UNKNOWN; ordinary JSON/Jackson are not unsafe serialization sinks |
| SEC006 SSRF | PARTIAL_V1 | Locally constructed URL openConnection/openStream | Imported node:http/https get/request string URLs | Constants excluded; options objects, DNS, redirects and allowlists unsupported |
| SEC007 XSS | PARTIAL_V1 | Typed javax/jakarta JSP writer | DOM typed HTML assignment or document getter | textContent/logging excluded; default imported DOMPurify is SEC007-only sanitation; custom options unresolved |
| SEC008 WeakCrypto | PARTIAL_V1 | MessageDigest/Cipher literal algorithms | Imported crypto hash/cipher algorithms | MD5/SHA-1/DES/RC4 subsets; receiving security-purpose symbol required for CONFIRMED_PATTERN; unclear purpose POTENTIAL; explicit checksum context excluded |
| SEC009 InsecureRandomness | PARTIAL_V1 | Math.random / java.util.Random methods | Unshadowed Math.random | Receiving token/session/nonce/etc symbol evidence; game/simulation/parser/label purposes excluded; no filename heuristic |
| SEC010 UnsafeDynamicCodeExecution | PARTIAL_V1 | Typed ScriptEngine.eval | Unshadowed eval/Function, imported vm, string timers | Constant code/callback timers excluded; timers require locally proven string code; reflection is not code execution |

Servlet sources require explicitly imported javax/jakarta HttpServletRequest parameter types;
getParameter, getHeader, getQueryString and getPathInfo return taint. TypeScript sources require an
explicit imported express.Request parameter/type and static query/params/body/headers projections.
An arbitrary object named req is not a source. Imports/types/built-in AST identities are matched;
shadowed functions/imports do not become platform APIs. Callable aliases, wildcard imports, Spring
binding, JavaScript/TSX Security language contracts and framework dispatch remain unsupported.
These are conservative syntactic bindings, not full compiler symbol resolution.

## Findings, uncertainty and isolation

Findings use frozen P027 SEC identity/schema contracts. Each distinct source path reaching a sink
has a separate deterministic UUID5 finding; identical duplicates collapse. Multiple sources at
one sink therefore may produce multiple findings. Static patterns use concrete locations.
Evidence summaries expose only rule/API classification and location, with source/propagation/
sanitizer/sink refs for flow findings. SEC001 candidates never retain literal values; the message
is `[REDACTED]`, with no value-derived digest, source preview or variable name. Internal flow literals
exist only during processing, have repr disabled and are never report/model fields.

All rule requests report supported/evaluated and PARTIAL/UNSUPPORTED/FAILED coverage. Partial pack
coverage is never a security guarantee. Failed source parsing or detector execution is not successful
zero-finding evaluation. Exception text/tracebacks are omitted; DETECTOR_ERROR is source-safe.
CONFIRMED_PATTERN describes an explicit pattern, SUPPORTED a bounded source-to-sink risk, POTENTIAL
an incomplete flow/context. Evidence strength is qualitative, not a probability.

Security cannot import Architecture decisions, Hybrid, calibration, benchmark or provider code.
Architecture registries/scorers cannot import Security. Existing runtime rejection tests cover
SEC findings/evidence/rule IDs at Architecture boundaries; V1 extends the import firewall scan.
The receipt adapter lives in infrastructure and performs read-only historical integrity checks.
No fitting, prediction, truth joining or scientific re-evaluation is performed.

Provider/connectivity/credential reads: 0. Security ground truth, Precision, Recall, F1 and accuracy:
NOT_AVAILABLE. Synthetic fixtures are parser inputs only, never executed shell/network/deserialization
programs and never a Security benchmark. No private project source appears in public receipts.

## Reproducibility and P029 handoff

`scripts/prompt028_security_analysis.py audit|freeze|verify` checks read-only P025/P026/P027 science
and historical source/doc bindings. Frozen P027 artifacts are never rebuilt against the new engine.
New protocol, detector/API registries, capability matrix, fixture inventory, boundary and manifest
are sealed separately under `experiments/security/security-static-dataflow-v1/`. The freeze index
binds implementation, tests, fixtures and docs. Frozen receipts reject mutation, incomplete quality
and provider activity; verification rebuilds deterministic engineering metadata only.

P029 may develop source-safe interprocedural summaries, framework packs, heap/object alias tracking,
confinement/allowlist/sanitizer proofs, call graph resolution and higher-fidelity flow rules.
Semantic escalation needs a separate authorized design. P029 and UI are not started by P028.
