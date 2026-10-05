# Frozen experiment partitions — PROMPT 010.1

Expanded manifest: `benchmarks/v1/dataset-1.1.json`, schema `1.0`, dataset version `1.1.0`.
The original `dataset.json` / `splits.json` remain the reproducible PROMPT 010 baseline.
Expanded source and truth reuse that root; changing partitions is an explicit dataset version change.

The existing `sha256-ranked-families-v1` planner ranks SHA-256(seed + ':' + family), reserves
floor(families/5) families for TEST and VALIDATION, and assigns the remainder to TRAIN.
Seed `archguard-expanded-composition-v1:5986` is the first deterministic seed satisfying the declared
composition constraints: each holdout has one new multi-rule static family, one graph family and
one paired semantic family. Selection used family metadata only, before detector evaluation.
No predictions, scores, prompts, weights or thresholds selected this seed.
`benchmarks/expand_seed.py` reproduces `splits-1.1.json` and the complete expanded manifest.

Family is the unit of independence. Base sources, all descendants/mutations, translations and
renamings remain in one family and one split. Literal content hashes and mutation lineage are
validated in addition to family IDs. Different labels or file paths cannot legitimize cross-split
copies. Near-clone detection and real OSS provenance remain future work.

## Composition

| Split | Families | Repositories | Cases | Positive | Negative |
| --- | ---: | ---: | ---: | ---: | ---: |
| TRAIN | 12 | 32 | 90 | 44 | 46 |
| VALIDATION | 3 | 12 | 24 | 12 | 12 |
| TEST | 3 | 12 | 24 | 12 | 12 |
| TOTAL | 18 | 56 | 138 | 68 | 70 |

Cases are annotation units, not independent statistical samples; language variants and mutations
are correlated. Three holdout families per split do not establish statistical sufficiency.

## Task coverage

Eligible counts use only the complete STRUCTURAL extraction variant, without duplicated missing
channel or bounded-metric variants. These counts differ from all-record export counts below.

| Split | Task | Families | Positive | Negative | Eligible families | Eligible P/N |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| TRAIN | Static | 5 | 10 | 10 | 5 | 10/10 |
| TRAIN | Semantic | 3 | 14 | 14 | 0 | 0/0 |
| TRAIN | Graph | 4 | 20 | 22 | 4 | 20/22 |
| VALIDATION | Static | 1 | 6 | 6 | 1 | 6/6 |
| VALIDATION | Semantic | 1 | 4 | 4 | 0 | 0/0 |
| VALIDATION | Graph | 1 | 2 | 2 | 1 | 2/2 |
| TEST | Static | 1 | 6 | 6 | 1 | 6/6 |
| TEST | Semantic | 1 | 4 | 4 | 0 | 0/0 |
| TEST | Graph | 1 | 2 | 2 | 1 | 2/2 |

## Rule distribution

Visible zeros mark unsupported per-rule holdouts. Graph holdouts exercise ARCH105; they do not
support a per-rule generalization claim for ARCH101–104. Semantic ARCH201/204 have no holdout here.

| Rule | TRAIN P/N | VALIDATION P/N | TEST P/N |
| --- | ---: | ---: | ---: |
| ARCH001 | 2/2 | 0/0 | 2/2 |
| ARCH002 | 2/2 | 2/2 | 2/2 |
| ARCH003 | 2/2 | 2/2 | 0/0 |
| ARCH004 | 2/2 | 2/2 | 0/0 |
| ARCH005 | 2/2 | 0/0 | 2/2 |
| ARCH101 | 6/6 | 0/0 | 0/0 |
| ARCH102 | 4/4 | 0/0 | 0/0 |
| ARCH103 | 4/6 | 0/0 | 0/0 |
| ARCH104 | 4/4 | 0/0 | 0/0 |
| ARCH105 | 2/2 | 2/2 | 2/2 |
| ARCH201 | 3/3 | 0/0 | 0/0 |
| ARCH202 | 3/3 | 0/0 | 2/2 |
| ARCH203 | 2/2 | 2/2 | 0/0 |
| ARCH204 | 4/4 | 0/0 | 0/0 |
| ARCH205 | 2/2 | 2/2 | 2/2 |

## Family membership

| Family | Split | Repositories | Cases | Languages |
| --- | --- | ---: | ---: | --- |
| graph-cluster-bridge | TEST | 2 | 4 | JAVA, TYPESCRIPT |
| graph-diamond | VALIDATION | 2 | 4 | JAVA, TYPESCRIPT |
| graph-fan-in | TRAIN | 2 | 8 | JAVA, TYPESCRIPT |
| graph-fan-out | TRAIN | 2 | 8 | JAVA, TYPESCRIPT |
| graph-stable-core | TRAIN | 2 | 4 | JAVA, TYPESCRIPT |
| graph-topology-v1 | TRAIN | 2 | 22 | JAVA, TYPESCRIPT |
| semantic-ledger | VALIDATION | 2 | 8 | JAVA, TYPESCRIPT |
| semantic-reporting | TRAIN | 1 | 4 | JAVA |
| semantic-responsibilities-v1 | TRAIN | 2 | 20 | JAVA, TYPESCRIPT |
| semantic-shipping | TEST | 2 | 8 | JAVA, TYPESCRIPT |
| semantic-ui-orders | TRAIN | 1 | 4 | TYPESCRIPT |
| static-1 | TRAIN | 4 | 4 | JAVA, TYPESCRIPT |
| static-2 | TRAIN | 4 | 4 | JAVA, TYPESCRIPT |
| static-3 | TRAIN | 4 | 4 | JAVA, TYPESCRIPT |
| static-4 | TRAIN | 4 | 4 | JAVA, TYPESCRIPT |
| static-5 | TRAIN | 4 | 4 | JAVA, TYPESCRIPT |
| static-batch-workflow | VALIDATION | 8 | 12 | JAVA, TYPESCRIPT |
| static-webshop | TEST | 8 | 12 | JAVA, TYPESCRIPT |

TRAIN alone may fit future structural weights. VALIDATION may select them under a preregistered
protocol. TEST stays frozen. Composition checks and offline pipeline smokes establish mechanics;
no parameter selection, fitting or scientific inference occurred in this stage. Source/context
content must never include annotation labels, rationales, split outcomes or reviewer decisions.
