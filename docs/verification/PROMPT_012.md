# PROMPT 012 — Real-world OSS benchmark & independent annotation foundation

1. **Status:** implemented OSS_ANNOTATION_SEED engineering foundation. Corpus/sample frozen;
   independent human annotation remains pending. No PROMPT 013 started.
2. **Git:** audited clean main/origin/main at `df899b097bd07d240591c594baf1ff5ba77a831e` before changes;
   baseline make check: 1074 passed / 94% coverage. Prior commit/history unchanged. PROMPT 012 is a
   reviewable uncommitted working-tree diff; no commit/push was created for this stage.
3. **Changes:** isolated benchmark/oss DTO/sampling/review boundary; explicit infrastructure fetch,
   characterization and annotation adapters; CLI; offline tests; 16 source-free OSS JSON artifacts;
   four research docs, this verification, README/.gitignore and two ADRs. No third-party source in Git.
4. **Dataset:** archguard-oss-benchmark-v1, oss-corpus-v1 / 1.0.0, OSS_ANNOTATION_SEED;
   independent of immutable synthetic dataset 1.1.
5. **Selection protocol:** `2f52233c2f45a4f743547c73990f8285fad60c2f7feaa69a54f60f1b14b6cf87`;
   registered before metadata search. Selection uses only primary GitHub metadata/license/tree APIs.
6. **Considered:** 16 candidates, complete immutable metadata selection log; selected 8.
7. **Selected:** 4 Java + 4 TypeScript / 8 independent families. Exact revisions/license provenance:

| Repository ID | Project source | Language | Commit | SPDX | Family |
| --- | --- | --- | --- | --- | --- |
| adonisjs-core | [adonisjs/core](https://github.com/adonisjs/core/commit/e3534b9d1b8a10cd7dea1b9847d781bf952143b8) | TYPESCRIPT | `e3534b9d1b8a10cd7dea1b9847d781bf952143b8` | MIT | adonisjs/core |
| alibaba-jetcache | [alibaba/jetcache](https://github.com/alibaba/jetcache/commit/15a89c8981b8bdbc1f6e7edad8f0148188a32398) | JAVA | `15a89c8981b8bdbc1f6e7edad8f0148188a32398` | Apache-2.0 | alibaba/jetcache |
| alibaba-sentinel | [alibaba/sentinel](https://github.com/alibaba/sentinel/commit/a3f40ba8e900c8489bd520274739f17235a7721c) | JAVA | `a3f40ba8e900c8489bd520274739f17235a7721c` | Apache-2.0 | alibaba/sentinel |
| apache-commons-lang | [apache/commons-lang](https://github.com/apache/commons-lang/commit/682a8ff5cddfeedecb98f62ac7c8d94b5ff65f33) | JAVA | `682a8ff5cddfeedecb98f62ac7c8d94b5ff65f33` | Apache-2.0 | apache/commons-lang |
| colinhacks-zod | [colinhacks/zod](https://github.com/colinhacks/zod/commit/0b216ef674e297ebe41d8bf902262e56f8755822) | TYPESCRIPT | `0b216ef674e297ebe41d8bf902262e56f8755822` | MIT | colinhacks/zod |
| google-gson | [google/gson](https://github.com/google/gson/commit/216c41b6e70dc04e6856418dd76bb00c854eb6b4) | JAVA | `216c41b6e70dc04e6856418dd76bb00c854eb6b4` | Apache-2.0 | google/gson |
| trpc-trpc | [trpc/trpc](https://github.com/trpc/trpc/commit/d756e591a5e37ef20b8d75ecd4d736c195497289) | TYPESCRIPT | `d756e591a5e37ef20b8d75ecd4d736c195497289` | MIT | trpc/trpc |
| typestack-class-validator | [typestack/class-validator](https://github.com/typestack/class-validator/commit/2e1a5c27dbd65b80e27fe96b49bd6e6641fa3603) | TYPESCRIPT | `2e1a5c27dbd65b80e27fe96b49bd6e6641fa3603` | MIT | typestack/class-validator |

8. **Excluded:** mybatis/mybatis-3: LICENSE_UNCLEAR; jknack/handlebars.java: LICENSE_UNCLEAR; spring-projects/spring-petclinic: LANGUAGE_UNSUPPORTED; nestjs/nest: TOO_LARGE; outline/outline: LICENSE_UNCLEAR; n8n-io/n8n: LICENSE_UNCLEAR; resilience4j/resilience4j: LICENSE_UNCLEAR; caprover/caprover: LICENSE_UNCLEAR. No analyzer/model-performance criterion or post-analysis replacement.
9. **Corpus:** `fe31539b44938fb1f87bcbc914d08af6cbdb2f7f25f23420fb92b09b0d6a9143`; freeze receipt `61a87204f96a7c67981db2e6f3093ddc7708d3e05318f04b7a60b07b26c5e789`.
   Exact commits, family/repository counts and selection-protocol fingerprint are recorded.
10. **Freeze chronology:** corpus-freeze phase BEFORE_FETCH_AND_ANALYSIS, timestamp `2026-10-05T19:10:29.912984+00:00`.
    CLI validates corpus/protocol/freeze before fetching or constructing analyzers. Fingerprint receipt
    existed before the first saved characterization. No corpus inclusion changed after freeze.
11. **Fetch:** explicit command, raw pinned Git objects, verified commit/tree/license, external cache,
    content and ArchGuard snapshot identities, acquisition timestamps. Two clean real fetches match
    all eight source/snapshot fingerprints; acquisition timestamps/receipt hashes need not match.
12. **Safety:** no source execution/install/build; disabled hooks, global/system Git config and
    credentials; no checkout/filter scripts/submodule initialization/LFS downloads. Path/budget bounds,
    cache outside Git, special entries omitted and recorded. Zod has four omitted symlinks including
    root README; source identity refers to materialized regular files plus separately pinned Git tree.
    Pinned upstream documentation links remain in human packets. No Git/network actions occur in CI
    except local fake fixture Git operations.
13. **Characterization:** all 8 retained PARTIAL, no candidate accuracy metrics:

| Repository | Source files | Parsed | Syntax errors | IAM nodes | IAM edges | Unresolved | Graph nodes | Graph edges | Cyclic SCCs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| adonisjs-core | 195 | 195 | 2 | 1009 | 717 | 1304 | 230 | 284 | 3 |
| alibaba-jetcache | 326 | 326 | 0 | 3777 | 4954 | 10063 | 507 | 1883 | 0 |
| alibaba-sentinel | 1279 | 1279 | 0 | 12212 | 16915 | 29434 | 1464 | 5226 | 0 |
| apache-commons-lang | 628 | 628 | 0 | 13687 | 13343 | 46745 | 1238 | 2166 | 0 |
| colinhacks-zod | 513 | 513 | 4 | 3847 | 2271 | 8304 | 1755 | 1333 | 0 |
| google-gson | 264 | 264 | 0 | 5107 | 8186 | 17899 | 803 | 2542 | 0 |
| trpc-trpc | 1030 | 1030 | 3 | 7431 | 6034 | 11774 | 2498 | 2496 | 0 |
| typestack-class-validator | 178 | 178 | 0 | 818 | 1064 | 957 | 433 | 886 | 1 |

14. **Sampling:** preregistered seed 12012, five unique eligible IAM locators/repository, raw dependency
    degree terciles plus SHA256 ranking/round-robin. Discovery output is never annotation truth;
    candidate presence/V2/AI/Hybrid results are not accepted as sampler inputs. Raw graph distributions
    are recorded after freeze; default graph configuration/thresholds were not changed.
15. **Packets:** 40; sample fingerprint `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`;
    sample-freeze `6631ab6acfac3dd82a888e06192b90ecf48c11665e82901e324d22810393cbd0`. Exported local Markdown + editable JSON forms, source-free
    canonical packet metadata and packet/result schemas. Case IDs/scope unchanged by bounded-context
    line-range repair; invalid preliminary exports were rejected before any human labels or AI.
16. **Languages:** Java=20 / TypeScript=20; five packets for each selected repository.
17. **Rules:** ARCH201=8, ARCH202=8, ARCH203=8, ARCH204=8, ARCH205=8.
18. **Controls:** LOW=16 / MEDIUM=16 / HIGH=8 raw-degree count strata, including non-suspicious/unknown
    subjects. Equal degree ties do not imply distinct thresholds. Positive rate is unknown; no labels
    are inferred from degree or missing annotation. Exact repository/locator/question defines scope.
19. **Blinding:** no model_score, candidate_present, SemanticCandidate, HybridDecision or V2 artifact
    fingerprint in exported canonical/local packets. Annotation export accepts only sample + source
    cache, never private evaluation context. Hash-verified source/docs/dependency references and pinned
    upstream links are admissible. Private IAM/Graph/Discovery remain outside the annotator directory.
20. **Actual review:** 40 UNREVIEWED / NOT_ANNOTATED; reviews=[], adjudications=[], 0 human reviewers,
    0 binary labels, no real agreement calculation. Unit fixture human vectors are explicitly fake
    test inputs and are never included in the OSS dataset.
21. **Import/export:** actual 40-packet export and empty unreviewed import succeed; known sample/packet
    scope, source hashes/line bounds, fake subjects, binary evidence/rationale and no-overwrite checks.
    Blank forms are not imported as labels. Previous review history is replay-validated; CLI uses
    sample-freeze receipt to reject post-freeze sample modification.
22. **Agreement/adjudication:** preserved separate actual reviewer rows; SINGLE_REVIEW provisional,
    DOUBLE_REVIEW agreement, conflicts ADJUDICATION_REQUIRED, independent third adjudicator needed
    for ADJUDICATED. Raw categorical agreement/Cohen kappa only for paired reviews, undefined=null.
23. **Target provenance:** DOCUMENTED/MANUALLY_DERIVED/NONE with evidence/rationale/review status.
    Current target specs NONE; no Discovery-derived architecture.yaml or generic layered truth.
    Static conformance requires constraints; graph cycle fact differs from forbidden-cycle violation.
    STRUCTURAL_SIGNAL differs from ARCHITECTURAL_QUALITY_JUDGMENT; semantic packets have separate task.
24. **V2 model access during selection/sampling:** NO. No artifact load/import in corpus/sampling code;
    frozen V2 policy/calibration files unchanged. Existing regression tests exercise their old synthetic
    fixtures independently and do not score OSS or influence OSS selection.
25. **V2 evaluation:** NO. AWAITING_FRESH_HOLDOUT unchanged. Separate corpus/sample/annotation freezes
    prepare future lineage proof; a later model-linked evaluation protocol is still required.
26. **Live AI:** 0 calls, cost=null. No semantic AI cohort or Hybrid decisions run on OSS.
27. **Tests:** 1080 passed / 0 failed / 0 skipped in 94.95s; all existing 1074 remain green.
    Six aggregate offline OSS tests cover pins, licenses, source fingerprints, safety, sampling,
    blinding, source/scope validation, review/adjudication/agreements and annotation CLI.
28. **Coverage:** 93% overall with branch coverage enabled (10725 statements / 3272 branches).
    New domain annotation 88%, DTOs 91%, fetch/characterization adapter 86%; bounded source/export
    adapter 73%, OSS CLI 68%. Real manual characterization/fetch evidence is separate from pytest coverage.
29. **Gates:** locked dev sync, Ruff, format (329 files), strict mypy (190 source files),
    full pytest/coverage and git diff --check green. No dependencies added. Two clean real fetches
    have identical source/snapshot fingerprints; all acquisition timestamps are after corpus freeze.
30. **Technical limitations:** unresolved/external references, three TypeScript syntax-error cohorts,
    betweenness skipped above unchanged 1000-node limit, omitted Zod links/docs and bounded context.
    Parsed files are not proof of complete resolution. No third-party dependencies were installed;
    retained PARTIAL counts expose the limitation. Cache pin/receipt checks do not authenticate human
    review; reviewer attestation and independent workflow remain human responsibilities.
31. **External validity:** convenience/purposive public OSS sample, library/framework-heavy, few
    deployed applications, only two languages and conservative license/budget filtering. Forty scope
    pairs may include test/helper code. Realistic source is not automatically correct/representative
    ground truth. No superiority, probability calibration, significance or scalability claim.
32. **Full Hybrid:** NOT_READY unchanged; completed independent semantic review and real provider
    assessments remain absent. Reviewed annotation freeze does not automatically activate calibration.
33. **Next:** after review only, Independent Semantic Annotation Execution & Adjudication or a
    separately authorized real AI cohort on the frozen cases. Do not start PROMPT 013 automatically.

Evidence: protocols/manifests/receipts and reports under experiments/oss; `make check`, locked dev sync,
real explicit fetch A/B, post-freeze characterization and annotation CLI. Transient logs, full source,
private analysis and Markdown excerpts remain under /tmp, outside Git.
