# Real-world OSS benchmark & annotation foundation — PROMPT 012

Dataset `archguard-oss-benchmark-v1`, schema oss-corpus-v1 / version 1.0.0,
status OSS_ANNOTATION_SEED. Synthetic dataset 1.1 remains separate and unchanged. Synthetic scenarios
provide controlled mutations and regression truth; OSS supplies realistic source/dependency structures,
ambiguous semantics and parser/resolver limitations. Neither alone establishes all thesis claims.

Eight independent public Java/TypeScript projects were selected under the preregistered
[protocol](OSS_SELECTION_PROTOCOL.md), pinned, frozen, fetched and characterized. Corpus fingerprint
`fe31539b44938fb1f87bcbc914d08af6cbdb2f7f25f23420fb92b09b0d6a9143`; receipt `61a87204f96a7c67981db2e6f3093ddc7708d3e05318f04b7a60b07b26c5e789`. Source is cached externally, never executed.
No V2 predictions, semantic AI or Hybrid decisions were used to select repositories or cases.
V2 remains AWAITING_FRESH_HOLDOUT; no evaluation/retraining/threshold tuning occurred. Full Hybrid NOT_READY.

## Reproduction

```bash
archguard benchmark oss validate
archguard benchmark oss fetch --dry-run --cache /tmp/oss-cache
archguard benchmark oss fetch --cache /tmp/oss-cache --output /tmp/fetch.json
archguard benchmark oss characterize --cache /tmp/oss-cache --output /tmp/characterization
archguard benchmark oss sample --cache /tmp/oss-cache \
  --frame /tmp/characterization/sampling-frame.json --output /tmp/sample
archguard benchmark oss annotation-export --cache /tmp/oss-cache \
  --sample /tmp/sample/sample.json --output /tmp/blinded
# After actual review, submit only completed rows. For second review use a separate form/directory.
archguard benchmark oss annotation-import --cache /tmp/oss-cache \
  --sample /tmp/sample/sample.json --annotations /tmp/completed-reviews.json --output /tmp/reviewed
# Append a distinct second reviewer or adjudicator without overwriting the first.
archguard benchmark oss annotation-import --cache /tmp/oss-cache \
  --sample /tmp/sample/sample.json --annotations /tmp/next-reviews.json \
  --previous /tmp/reviewed/annotations.json --output /tmp/next-reviewed
```

Defaults read the versioned protocol/corpus/freeze in experiments/oss. Export/import require the sample
freeze receipt beside sample.json or explicit --sample-freeze. Every output must be new. Network is
used only by explicit fetch; characterization, sampling, annotation and all tests are offline.

## Fetch safety/provenance

Git fetches exact commit objects with disabled hooks/credentials/system/global Git config, no recursive
submodules and no arbitrary protocols. Raw cat-file blobs are read without checkout, smudge filters,
attributes or LFS downloads. No npm/maven/gradle/node/java or repository scripts run. Submodule/symlink
entries are omitted without traversal and recorded in receipt.omitted_nonregular_paths; the raw Git
commit/tree remains pinned and materialized content identity is explicit. Symlinks inside caches are
rejected. Cache roots resolve outside Git working trees; normalized fingerprints ignore local root/time.
Limits reuse RepositoryScanPolicy (20000 files/40000 entries, 2 MiB source file, 64 MiB hash budget,
256 MiB materialization) plus 256 MiB corpus source budget. Git operations have a 120-second timeout.
Two clean real fetches produced identical content and snapshot fingerprints for all eight repositories.
Licenses are verified at the pinned commit by path and SHA256. Licensed source excerpts stay local.
Zod root README is an omitted symlink; human packets include the pinned upstream project documentation
link, and insufficient local context must lead to UNCERTAIN or a separately versioned context packet.

## Characterization after freeze

| Repository | Source files | Parsed | Syntax-error files | IAM nodes | IAM edges | Unresolved | Graph nodes | Graph edges | Cyclic SCCs | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| adonisjs-core | 195 | 195 | 2 | 1009 | 717 | 1304 | 230 | 284 | 3 | PARTIAL |
| alibaba-jetcache | 326 | 326 | 0 | 3777 | 4954 | 10063 | 507 | 1883 | 0 | PARTIAL |
| alibaba-sentinel | 1279 | 1279 | 0 | 12212 | 16915 | 29434 | 1464 | 5226 | 0 | PARTIAL |
| apache-commons-lang | 628 | 628 | 0 | 13687 | 13343 | 46745 | 1238 | 2166 | 0 | PARTIAL |
| colinhacks-zod | 513 | 513 | 4 | 3847 | 2271 | 8304 | 1755 | 1333 | 0 | PARTIAL |
| google-gson | 264 | 264 | 0 | 5107 | 8186 | 17899 | 803 | 2542 | 0 | PARTIAL |
| trpc-trpc | 1030 | 1030 | 3 | 7431 | 6034 | 11774 | 2498 | 2496 | 0 | PARTIAL |
| typestack-class-validator | 178 | 178 | 0 | 818 | 1064 | 957 | 433 | 886 | 1 | PARTIAL |

All remain PARTIAL, primarily due to resolver/external-reference coverage; syntax diagnostics also
exist in some TypeScript projects. Parsed counts include syntax-error files; parsed does not mean
resolved or complete. Component projection may skip betweenness above the unchanged 1000-node limit.
No source installation/build was attempted to increase resolution. No project was excluded after these
results. Raw graph distributions are saved without threshold changes. Private IAM/Graph/Discovery
context stays outside the annotator view; only the independent source-reference frame reaches sampling.
Characterization is not candidate accuracy, architectural quality or scalability evidence.

## Annotation readiness

40 frozen packets: 20 Java / 20 TypeScript; 5 per repository; 8 for each ARCH201–205. Raw IAM-degree
terciles LOW/MEDIUM/HIGH yield 16/16/8 controls/strata, never presumed positive/negative labels.
Sample `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`; sample-freeze `6631ab6acfac3dd82a888e06192b90ecf48c11665e82901e324d22810393cbd0`.
All 40 UNREVIEWED, 0 human reviewers, 0 known labels, positive rate unknown. Annotation export and empty
unreviewed import are verified; this does not claim completed human review. Cost=null, live AI=0.

Machine-readable selection/provenance/count reports and source-free packet/schema/receipt data are in
experiments/oss/corpus and experiments/oss/annotation. Local excerpts/private analysis are outside Git.
[Annotation protocol](ANNOTATION_PROTOCOL.md), [external-validity limitations](EXTERNAL_VALIDITY.md)
and [verification](../verification/PROMPT_012.md) describe the remaining work. No PROMPT 013 starts here.
