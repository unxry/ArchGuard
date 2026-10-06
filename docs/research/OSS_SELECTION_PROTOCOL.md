# OSS selection protocol v1

Preregistered before metadata search. Fingerprint `2f52233c2f45a4f743547c73990f8285fad60c2f7feaa69a54f60f1b14b6cf87`;
registration `2026-10-05T19:05:29.370807+00:00`, base HEAD df899b0, baseline 1074 passed.
Metadata collection uses primary GitHub repository/language/license/commit/tree APIs. README high-level
purpose, license and file inventory are admissible; no ArchGuard, GraphCandidate, V2, AI or Hybrid
output participates. All 16 considered repositories remain in the candidate log.

Criteria: public Git, exact pinned SHA, explicit detected OSS SPDX plus exact pinned license blob/hash,
primarily Java or TypeScript (>=50% GitHub language bytes), >=30 source files in >=2 directories,
metadata Git size <=300000 KiB, multi-component source readable without execution. At most one demo.
Target 8 independent repositories, 4 per language. Official forks/mirrors/translations share a family;
only one representative is selected. Generated/vendor-dominant, tiny, unsupported, unavailable,
unpinnable or unclear-license projects are excluded. The metadata license check is deliberately
conservative: NOASSERTION is excluded even if later manual legal clarification might be possible.

No parser-performance exclusion or detector-quality exclusion is permitted. After freeze retain
PARTIAL/ANALYSIS_UNSUPPORTED with quantitative limitations. Replacing a repository requires a new
corpus version, not an edit to the frozen one. GitHub language/size estimates differ from actual
ArchGuard inventory; no repository was replaced after analysis. This is a convenience/purposive sample,
not a random population sample. Several application candidates failed the frozen metadata criteria;
selected projects are predominantly libraries/frameworks, not eight representative deployed systems.

## Selected repositories

| ID | Project/revision source | Language | Immutable commit | License | Family |
| --- | --- | --- | --- | --- | --- |
| adonisjs-core | [adonisjs/core](https://github.com/adonisjs/core/commit/e3534b9d1b8a10cd7dea1b9847d781bf952143b8) | TYPESCRIPT | `e3534b9d1b8a10cd7dea1b9847d781bf952143b8` | MIT | adonisjs/core |
| alibaba-jetcache | [alibaba/jetcache](https://github.com/alibaba/jetcache/commit/15a89c8981b8bdbc1f6e7edad8f0148188a32398) | JAVA | `15a89c8981b8bdbc1f6e7edad8f0148188a32398` | Apache-2.0 | alibaba/jetcache |
| alibaba-sentinel | [alibaba/sentinel](https://github.com/alibaba/sentinel/commit/a3f40ba8e900c8489bd520274739f17235a7721c) | JAVA | `a3f40ba8e900c8489bd520274739f17235a7721c` | Apache-2.0 | alibaba/sentinel |
| apache-commons-lang | [apache/commons-lang](https://github.com/apache/commons-lang/commit/682a8ff5cddfeedecb98f62ac7c8d94b5ff65f33) | JAVA | `682a8ff5cddfeedecb98f62ac7c8d94b5ff65f33` | Apache-2.0 | apache/commons-lang |
| colinhacks-zod | [colinhacks/zod](https://github.com/colinhacks/zod/commit/0b216ef674e297ebe41d8bf902262e56f8755822) | TYPESCRIPT | `0b216ef674e297ebe41d8bf902262e56f8755822` | MIT | colinhacks/zod |
| google-gson | [google/gson](https://github.com/google/gson/commit/216c41b6e70dc04e6856418dd76bb00c854eb6b4) | JAVA | `216c41b6e70dc04e6856418dd76bb00c854eb6b4` | Apache-2.0 | google/gson |
| trpc-trpc | [trpc/trpc](https://github.com/trpc/trpc/commit/d756e591a5e37ef20b8d75ecd4d736c195497289) | TYPESCRIPT | `d756e591a5e37ef20b8d75ecd4d736c195497289` | MIT | trpc/trpc |
| typestack-class-validator | [typestack/class-validator](https://github.com/typestack/class-validator/commit/2e1a5c27dbd65b80e27fe96b49bd6e6641fa3603) | TYPESCRIPT | `2e1a5c27dbd65b80e27fe96b49bd6e6641fa3603` | MIT | typestack/class-validator |

## Excluded candidates

| Project | Typed reason | SPDX observed, if unclear |
| --- | --- | --- |
| mybatis/mybatis-3 | LICENSE_UNCLEAR |  |
| jknack/handlebars.java | LICENSE_UNCLEAR | NOASSERTION |
| spring-projects/spring-petclinic | LANGUAGE_UNSUPPORTED |  |
| nestjs/nest | TOO_LARGE |  |
| outline/outline | LICENSE_UNCLEAR | NOASSERTION |
| n8n-io/n8n | LICENSE_UNCLEAR | NOASSERTION |
| resilience4j/resilience4j | LICENSE_UNCLEAR |  |
| caprover/caprover | LICENSE_UNCLEAR | NOASSERTION |

The machine-readable candidate log retains description, metadata size, language proportion, estimates,
reason and primary metadata URL. License path/SHA256, Git tree SHA, commit date and method remain in
oss-corpus-v1.json. Acquired date, normalized content fingerprint and ArchGuard snapshot fingerprint
are in separate immutable acquisition receipts bound to the frozen corpus. Upstream code is not vendored.

Corpus `fe31539b44938fb1f87bcbc914d08af6cbdb2f7f25f23420fb92b09b0d6a9143`; freeze receipt `61a87204f96a7c67981db2e6f3093ddc7708d3e05318f04b7a60b07b26c5e789` at `2026-10-05T19:10:29.912984+00:00`,
BEFORE_FETCH_AND_ANALYSIS. The selected list remains immutable; post-fetch identities are receipts,
not changes to corpus inclusion. All characterization uses this exact corpus/protocol/freeze triple.
