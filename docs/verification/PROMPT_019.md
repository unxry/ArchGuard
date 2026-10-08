# PROMPT 019 — fresh component baselines and Hybrid evidence foundation

Fresh holdout and component outputs are frozen. Static and direct Graph achieved F1=1.0 on their separate applicable normative scopes. The Graph Structural Meta-Classifier V2 achieved F1=0.930233 on 80 fresh structural-signal cases. No cross-cohort winner or semantic/Hybrid effectiveness claim is made.

## A — Lineage / prospective plan

Lineage PASS. Initial HEAD `264e7cc237f96714fc1d066d04418944e397a6e2`, clean before P019 preparation. Required ancestry was resolved by Git and checked with merge-base; exact commits are recorded in the public plan. P010/P010.1/P011 and P015.F/P016/P017/P018, including intermediate freeze/recovery commits, are ancestors.

Old TEST was already consumed by V1/post-hoc work and cannot clear V2 fresh-holdout requirements. Historical dataset loading was restricted to integrity verification and ID/hash overlap auditing; no old cases, labels or predictions selected the new design. Old consumed TEST reused: **NO**.

Plan fingerprint: `e22642d1d37ff6522596bb0225757eb2914a7b3c2858eb3340a3c904380771b3`. Frozen before construction and predictions: **YES**. Recipes, source templates, oracle predicates, scope, default configurations, original engine hashes, ordering and missing/error/null policies were preregistered. A private seed is sealed; its fingerprint is public. Case/project/source-family IDs are opaque and deterministic from that seed.

Access audit is hash-chained and append-only. All timestamps below are UTC on 2026-10-08. Labels are separate from the execution manifest and unavailable to worker processes.

| Event | UTC |
|---|---|
| PLAN_FROZEN | 2026-10-08T07:56:14.765725+00:00 |
| HOLDOUT_FROZEN | 2026-10-08T07:56:45.231449+00:00 |
| LABELS_SEALED | 2026-10-08T07:56:45.231673+00:00 |
| STATIC_EXECUTION | 2026-10-08T07:57:46.415888+00:00 |
| STATIC_OUTPUT_FROZEN | 2026-10-08T07:57:47.406356+00:00 |
| GRAPH_EXECUTION | 2026-10-08T07:57:47.406714+00:00 |
| GRAPH_OUTPUT_FROZEN | 2026-10-08T07:57:49.503023+00:00 |
| V2_EXECUTION | 2026-10-08T07:57:49.503361+00:00 |
| V2_OUTPUT_FROZEN | 2026-10-08T07:57:50.531947+00:00 |
| SEMANTIC_EVIDENCE_EXECUTION | 2026-10-08T07:58:04.233524+00:00 |
| SEMANTIC_EVIDENCE_FROZEN | 2026-10-08T07:58:09.040110+00:00 |
| FIRST_TRUTH_JOIN | 2026-10-08T07:58:48.200451+00:00 |
| V2_FRESH_HOLDOUT_ACCESSED | 2026-10-08T07:58:48.201888+00:00 |
| METRICS | 2026-10-08T07:58:48.343565+00:00 |
| REGISTRY_FROZEN | 2026-10-08T07:58:48.748259+00:00 |

Audit chain head: `7c2c2e566fd1b4d03d9e110e231238433ac1d9bae9e8f42ea585691936e4bf19`. Chronology and artifact bindings mechanically verified. Component outputs and semantic evidence froze before the first result/truth join.

## B — Exact frozen V2 artifact

Artifact: `experiments/results/structural-v2/policy.json`; full fingerprint `2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185`. Original artifact status before P019: `AWAITING_FRESH_HOLDOUT`.

GRAPH_V2_FRESH_HOLDOUT_EVALUATION_ALLOWED = **YES**. Typed canonical artifact integrity and frozen dataset/selection/TRAIN/VALIDATION bindings verified. TRAIN: 42 cases, 20 P / 22 N. VALIDATION: 4, 2 P / 2 N. Weighted linear model alpha=10; threshold **0.398762395289**. TRAIN preprocessor fingerprint `9f9493e70cf7cf21f259fd020471db698834fc6b5be7601bead87eb980461ae7`.

K=4 is established by mapping the exact artifact TRAIN-family fingerprints to the integrity-verified frozen dataset. These are repository/construction strata, not four rule IDs. Their supported annotation scope is:

| Artifact TRAIN family | Supported rules | Fresh cases / pairs | Java / TS | P / N |
|---|---|---:|---:|---:|
| graph-fan-in | ARCH101, ARCH102 | 20 / 10 | 10 / 10 | 10 / 10 |
| graph-fan-out | ARCH101, ARCH103 | 20 / 10 | 10 / 10 | 10 / 10 |
| graph-stable-core | ARCH104 | 20 / 10 | 10 / 10 | 10 / 10 |
| graph-topology-v1 | ARCH101, ARCH102, ARCH103, ARCH104, ARCH105 | 20 / 10 | 10 / 10 | 10 / 10 |

Validation family `graph-diamond` is separately fingerprint-bound and excluded from the primary supported TRAIN strata. Fresh projects use new source-family identities; historical family names above identify strata only. No old family project/case/source unit is reused.

P019 fitting: NO. Preprocessing refit: NO. Threshold/model/feature changes: NO. Candidate flags, detector decisions, rule/identity/label features are excluded. Inference uses the portable artifact transform/score directly, without executing a Hybrid policy or engine.

## C — Fresh holdout

| Quantity | Frozen value |
|---|---:|
| Cases / matched pairs | 180 / 90 |
| Java / TypeScript cases | 90 / 90 |
| Positive / negative | 90 / 90 |
| Track A cases / pairs | 100 / 50 |
| Track B cases / pairs | 80 / 40 |
| New source units | 2520 |
| P010/P011 exact case overlap | 0 |
| Exact source-unit overlap | 0 |
| Malformed pairs | 0 |
| IAM VALID / PARTIAL / INVALID | 180 / 0 / 0 |

Holdout fingerprint: `af4ba0736d2be86b0ef4db2c8a77c8aef76f8d27576ae8ec690f1b4e81551bd1`. Oracle fingerprint: `7fb82c1d9f2b4f5f2e83385c14f1458c38f29c48b31888387156630092c1c9e4`. Execution/context manifest: `541d1866bc0cccab7c19d7b55e8178df5382676239095c83e12249bb6dd45f81`. Source inventory: `04c0e0a4fee95e31f1a9df9eacfcc574b7b66e158797463820586f674eb6a3f0`. Sealed truth: `f53ab09564d0481025ffb00a8cbef868a8085b69dca7ceaf2a390d577aeb0e24`. Independence audit: `68cbcff7325f6ac7c308c91d20d76bee97f43062c486d0a08b44309b5e626cff`.

FRESH_COMPONENT_HOLDOUT_FROZEN = **YES**. New Java/TS projects contain explicit class/dependency interventions plus a varying auxiliary relay chain. Pair members retain language, topology cardinality, roles and stratum; only the defined intervention and opaque source identities differ. Private recipes/pair intent, normalized facts, specs, hashes, provenance, engineering receipts and labels freeze before execution.

Engineering validation passed intake, strict syntax parsing, extraction/resolution, IAM, exact normalized source/GraphBuilder adjacency, method facts, spec validation and deterministic IAM replay for all 180. Native Java launcher reports no compiler runtime; tsc is absent. javac/tsc compilation UNAVAILABLE and runtime NOT_RUN. VALID refers to parse/IAM/graph engineering validation, not an unperformed native compilation claim.

## D — Track A and independent oracles

| Rule | Cases | Pairs | P / N | Java / TS | Independent oracle |
|---|---:|---:|---:|---:|---|
| ARCH001 | 20 | 10 | 10 / 10 | 10 / 10 | PASS |
| ARCH002 | 20 | 10 | 10 / 10 | 10 / 10 | PASS |
| ARCH003 | 20 | 10 | 10 / 10 | 10 / 10 | PASS |
| ARCH004 | 20 | 10 | 10 / 10 | 10 / 10 | PASS |
| ARCH005 | 20 | 10 | 10 / 10 | 10 / 10 | PASS |

Oracle code imports no detector, candidate or classifier implementation. It evaluates serialized normalized source roles/dependencies against explicit architecture constraints. ARCH001 tests forbidden scope pairs; ARCH002 tests layer allow sets; ARCH004 tests the declared dependency direction; ARCH005 tests module allow sets. ARCH003 uses an independent Kahn adjacency-elimination cycle predicate.

Track B predicates use fixed construction mathematics: six distinct outgoing branches; six incoming branches; six methods plus six outgoing branches; directed Ca/Ce instability ordering; and removal-sensitive paths through a central target. These are benchmark intervention definitions, not production candidate thresholds. Source-derived adjacency/method facts are checked against construction before freeze. No production threshold, candidate flag or V2 score supplies truth.

## E — Static-only baseline

Static ran on all 100 Track A cases. ARCH001/002/004/005 are primary binary scope (80 cases); ARCH003 is UNSUPPORTED by Static (20 records), excluded from binary confusion counts. Primary coverage is 100%; applicability over recorded Track A is 80%.

| Scope | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | Coverage | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Static micro, N=80 | 40 | 0 | 40 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.445425 |
| ARCH001 | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.142195 |
| ARCH002 | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.099073 |
| ARCH004 | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.105620 |
| ARCH005 | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.098537 |

Static recorded runtime for all 100: 0.545339s. Errors: 0. STATIC_BASELINE_EVALUATED = YES. Output fingerprint `b9b3c92d90689e28e7562e0733c675a0bf69d41f081e069a6c229226f215f796`.

## F — Direct Graph-only baseline

Graph ran once on all 180 cases, preserving raw metrics, SCC/cycle observations, candidates and conformance outputs. ARCH003 is the sole legitimate primary binary scope. ARCH101–105 capability is **CANDIDATE_ONLY**, not calibrated binary detection. All default candidate thresholds are None; no candidate flags were emitted and no thresholds were enabled. Other normative rule outputs are UNSUPPORTED by direct Graph. No candidate-derived confusion matrix is created.

| Scope | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | Coverage | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| ARCH003, N=20 | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.282672 |

Graph recorded runtime for all 180: 1.523590s. Errors: 0. Binary applicability over all records: 20/180; applicable ARCH003 coverage: 100%. GRAPH_BASELINE_EVALUATED = YES. Output fingerprint `d9438e8292aad2d015dd4762749aa7fc339a72ade4f89d36b7eaf9254bf87964`.

## G — First fresh-holdout Graph V2 evaluation

80 cases, 40 P / 40 N. All predictions froze before truth access. Frozen Graph outputs supply the existing P009 materializer and whitelist; no Graph predictions or model calls are repeated during joins/verification.

| Scope | TP | FP | TN | FN | Precision | Recall | F1 | Specificity | FPR | FNR | Coverage | Seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| V2 overall, N=80 | 40 | 6 | 34 | 0 | 0.869565 | 1.000000 | 0.930233 | 0.850000 | 0.150000 | 0.000000 | 1.000000 | 0.445327 |
| graph-fan-in | 10 | 1 | 9 | 0 | 0.909091 | 1.000000 | 0.952381 | 0.900000 | 0.100000 | 0.000000 | 1.000000 | 0.106160 |
| graph-fan-out | 10 | 2 | 8 | 0 | 0.833333 | 1.000000 | 0.909091 | 0.800000 | 0.200000 | 0.000000 | 1.000000 | 0.114470 |
| graph-stable-core | 10 | 0 | 10 | 0 | 1.000000 | 1.000000 | 1.000000 | 1.000000 | 0.000000 | 0.000000 | 1.000000 | 0.113137 |
| graph-topology-v1 | 10 | 3 | 7 | 0 | 0.769231 | 1.000000 | 0.869565 | 0.700000 | 0.300000 | 0.000000 | 1.000000 | 0.111560 |

Output fingerprint `8ffcde7035780cc6e3c968f64cc2266602898e40bf5f6298446511ec459aded9`. Lifecycle receipt `80d2bf43607994eb0ef9fe4673d9185fdede99ce06cbf9325471858b1b236f2b`. Current authoritative fresh-holdout status **ACCESSED**, appended immediately at the first truth join. Original artifact bytes/status remain immutable; its historical AWAITING status is not a claim that this new holdout remains unconsumed.

Artifact changed: NO. Training/tuning: NO. Fresh truth before prediction: NO. Errors: 0. GRAPH_V2_FRESH_HOLDOUT_EVALUATED = YES.

Runtime is measured per frozen-IAM record and excludes source construction, parser validation, subprocess startup and final file writes. V2 reuses frozen Graph measurements; Graph computation is reported in the Graph stage. These durations are not comparable end-to-end production benchmarks.

## H — Graph feature diagnostic (DESCRIPTIVE)

Only the 15 existing frozen V2 input features are summarized. No diagnostic threshold or replacement feature is created. Scalar graph fields deliberately remain missing for directed two-subject cases; source/target fields carry their individual measurements.

Existing P009 ownership alignment also selects PROPERTY rather than CLASS in **14 single-subject TypeScript cases** when no Discovery representative is supplied. Their scalar features are missing despite a valid complete raw Graph. Frozen TRAIN median imputation and missing indicators handle these inputs. This limitation is retained and disclosed; no input repair or prediction rerun occurs after truth access. Reported V2 metrics apply to this preregistered extraction path. A future alignment correction requires a separate prospective assessment.

| Stratum | Scalar Ca available N / P | Missing N / P | Mean coupling N / P (available only) |
|---|---:|---:|---:|
| graph-fan-in | 9 / 7 | 1 / 3 | 1.000000 / 6.000000 |
| graph-fan-out | 8 / 5 | 2 / 5 | 1.000000 / 6.000000 |
| graph-stable-core | 0 / 0 | 10 / 10 | null / null |
| graph-topology-v1 | 7 / 6 | 3 / 4 | 2.428571 / 6.000000 |

Full per-family/per-class availability, means and medians: `p019-graph-feature-diagnostic-v1.json`, fingerprint `e39c64ec464c10fc18572f8b74827141b7e957ccd6ac6a851c9cb4d1b59c12b3`. Its statistics describe frozen inputs only.

## I — P015 semantic-cohort Static/Graph evidence

P015 cases=100; evidence records=100; missing=0; duplicates=0. A separate fresh worker could read only the neutral sample, original source directories and blinded source packets. Audit capabilities deny final human truth, reviewer submissions, P017 correctness, P018 construction intent, P019 pair maps and credentials. Human truth accessed during generation: NO; P017 correctness: NO; P018 intent: NO.

Each record contains existing P009 evidence/features, dependencies and Static classification/findings metadata, Graph metrics/neighborhoods/SCC/cycles/candidates, and existing Discovery roles/layer/module relationships. No machine-executable Static normative spec was supplied for this semantic cohort, so Static uses an empty rule set; empty findings do not establish semantic conformance. Existing Discovery hypotheses remain evidence only. Default Graph candidate thresholds remain disabled.

New ARCH201–205 heuristic: NO. Semantic binary decisions: NO. Hybrid decision/training: NO. Evidence freezes before any future truth-aware Hybrid use. Source/IAM evidence is private; public artifacts contain count/hash receipts only.

Evidence fingerprint `be079bfa094459379cf09e2a7226c539d84946374da5caabcc519da488b1287b`. Receipt `ea4be88ebb5ec96ea5448ed4dca7c85a0f3e982b39a1a6e8b2ffaf013d851fbb`. SEMANTIC_COHORT_STATIC_GRAPH_EVIDENCE_FROZEN = YES.

## J — Frozen component registry

| Reference | Full fingerprint / status |
|---|---|
| GRAPH | `d9438e8292aad2d015dd4762749aa7fc339a72ade4f89d36b7eaf9254bf87964` |
| STATIC | `b9b3c92d90689e28e7562e0733c675a0bf69d41f081e069a6c229226f215f796` |
| V2 | `8ffcde7035780cc6e3c968f64cc2266602898e40bf5f6298446511ec459aded9` |
| V2 artifact / lifecycle | `2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185` / ACCESSED |
| P016 normalized LLM assessments | `a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273` |
| P017 evaluation aggregate | `992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091` |
| Registry | `7a8a4fde188effe7b70cc50401b410f6a69b968a9eff0d944540f05b594703ac` |
| Baseline aggregate | `df63bc91ddf0a167dab98380a969f3513a71d5ddb0036f74646fbb164a48a5f4` |

COMPONENT_RESULT_REGISTRY_FROZEN = YES. Scores combined: NO. Static normative violation detection, Graph cycle detection, graph structural-signal retrieval and semantic LLM assessment have distinct cohorts/tasks. No combined Hybrid F1, ranking or P017-vs-P019 effectiveness comparison is calculated.

## K — Scientific boundaries / public-private split

Provider calls=0; paid execution=NO; human labels modified=NO; P017/P018 modified=NO; V2 retrained=NO; Hybrid executed=NO; ablation=NO; Security=NO. No later PROMPT or experiment starts. Worker audit hooks deny network and credential files, and worker environments omit provider credentials. Git network activity is limited to the separately authorized normal push.

All sources, source/IAM contexts, labels, pair/provenance maps, detector/evidence records and truth joins remain under the ignored P019 private root with 600 file / 700 directory permissions. Public manifests, aggregate metrics, fingerprints, methods and chronology contain no human identity, rationale, per-case construction membership or source text. `.gitignore` adds only the new private-root rule; existing `.env.*` protection is unchanged. Secret env files are never read, hashed, serialized or staged. Credential-pattern/public-schema audit PASS.

P015 original sample/source, final truth, P016 execution/ledger, and P017/P018 freezes are byte-guarded against the pre-plan inventory. Original P018 deterministic verification and P015/P017/P018 regression guards passed. P016 normalized-assessment reference matches the frozen P017 binding.

## L — Quality / deterministic verification

Targeted regression selection: **334 passed** (P019, Graph Engine, Static conformance, P011 calibration, P015 source freeze, P017 evaluation/offline, P018 diagnostic). P019 alone has 79 tests; the local completed-freeze and exact-real-V2 checks run with the required local artifacts and skip in a clean checkout lacking them.

Ruff PASS; formatting PASS (449 files); mypy PASS (226 source files). `make check`: **PASS**, 1802 tests passed in 1005.03s; coverage **90%**. Final `git diff --check`: **PASS**.

Fresh holdout/source/IAM/oracle/independence verification PASS; Static/Graph/V2 output seals PASS; exact identity joins and confusion-count replay PASS; V2 immutable artifact and ACCESSED lifecycle PASS; exact-100 semantic evidence inventory PASS; old input bytes PASS; audit ordering/hash chain PASS; privacy/secret audit PASS. Verification reads frozen outputs and recomputes aggregate arithmetic, never detector/model predictions.

## M — Git closure

Additional protocol commits preceded construction: `cf2c0961ea3e080d9b14c892dbdfc2d86ed1888d` and `ac59c77f07163d095f511362e7a4f9be650d1371`.

M1 holdout commit: `d492b07d00427f76e674ccb420ff28ab89eb1f7f`, before all detector execution.

M2 baseline evaluation commit: `a7baef3632ed2e477a18ead76f34b8a8033dd333`. M3 scientific evidence/report commit: `813634df9f7f9e8a09a0decabe1b71b2a4bc148a`. M4 normal origin/main push: PASS, remote head independently verified at that scientific commit; the subsequent documentation-only closure is also pushed normally and its final SHA is reported in the final response. No force push, amend, squash, rebase or reset.

M5 working tree: no pending P019 changes. An unrelated local deletion of `index(визуал).html` appeared during closure; the user explicitly requested that it be preserved. It remains an expected uncommitted deletion and is excluded from every P019 commit. The working tree is therefore not globally clean; this does not change frozen scientific inputs or results.

## Final status

FRESH_COMPONENT_HOLDOUT_FROZEN = YES

STATIC_BASELINE_EVALUATED = YES

GRAPH_BASELINE_EVALUATED = YES

GRAPH_V2_FRESH_HOLDOUT_EVALUATED = YES

SEMANTIC_COHORT_STATIC_GRAPH_EVIDENCE_FROZEN = YES

COMPONENT_RESULT_REGISTRY_FROZEN = YES

READY_FOR_HYBRID_EXPERIMENT_FOUNDATION = YES

STOP. Hybrid execution remains unstarted.
