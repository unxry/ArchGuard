# Frontend security review

Scope: V2 static application, importers, session state, local preview bridge. No penetration-test or production-security certification claim.

| Boundary | Implemented control | Verification / remaining boundary |
| --- | --- | --- |
| Imported HTML/source | All dynamic strings escaped before HTML/SVG rendering; source in escaped code text | Browser malicious `<img onerror>` artifact caused no element, execution or remote request |
| Script/network policy | CSP default none; local scripts/styles; same-origin connections; no plugins/iframes/forms | Offline workflow has zero HTTP(S) requests; no CDN or analytics |
| JSON intake | 5 MiB before parsing; object/type/version/ID/reference constraints; depth 25, 100000 visited values, 50000-char strings; graph ≤500 nodes/3000 edges | Adapter tests include hostile keys, path/range failures, wrong schema, count/proof mismatch; browser oversize/invalid state preserves previous dataset |
| Provenance | Retain original JSON, report PROTOTYPE_STRUCTURE_ONLY and fingerprints_verified=false | UUID/hash format checks do not authenticate artifact or recompute fingerprints; runtime validators are not full Pydantic parity |
| File paths | Relative normalized source locations; no traversal, absolute source paths or control characters | Paths rendered as text only; no arbitrary source-file read API |
| Git/local/ZIP | Syntax validation and quoted CLI plan only; no server request or execution | URL syntax does not establish public DNS destination; future clone service needs destination/DNS/redirect/resource policy |
| CLI plan | Source kind allowlist; shell single-quote escaping; no eval/exec invocation | Literal shell metacharacters tested. User must deliberately run the plan outside UI |
| System bridge | Fixed loopback backend configured by CLI, host/origin checks, GET-only exact route, two fixed upstream paths, 64 KiB response cap and total timeout, no redirects, schema validation | Native tests cover success and failures; actual FastAPI handshake verified separately |
| Static server | Artifact-root allowlist; hidden/traversal/encoded separator rejection; symlink/special-file checks and no-follow final open | Intended for a trusted local checkout, not hostile concurrent filesystem mutation or public deployment |
| Credentials/auth | No token input, browser token storage, Git credential collection or provider integration | Loopback preview is not an authenticated shared multi-user service; production auth absent |
| Data mode | Import replaces demo; system connection does not enable analysis; unbound result comparison rejected | Browser checks modes and imports; history is in-memory only |
| Private custody | Authored fixture repository only; public implementation inspected | No `.env`, private truth, human/adjudication datasets or scientific result files read by UI tooling |

Only the new design directory is committed. No backend semantics were changed. Unit tests and browser checks are referenced in `VALIDATION.md`; limitations remain documented rather than hidden behind a “safe” badge.
