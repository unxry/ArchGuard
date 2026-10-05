# PROMPT 010 — verification

Completed Benchmark, Ground Truth & Mutation Dataset Foundation. Changes remain uncommitted for
review. PROMPT 009 audit: clean diff-check, 912 passing tests and 94% coverage; committed/pushed as
`1a0db742dd6908831e08a8c4e8cff144598d9c91` (`feat: add hybrid evidence fusion foundation`).
HEAD and origin/main match. No force push or identity/credential configuration changes.

## Contracts and data

Benchmark schema `1.0`; `archguard-benchmark-v1` version `1.0.0`, ENGINEERING_SEED. Separate pure
benchmark models, resolver, identity/split/metrics, mutation protocol/registry and output adapters;
filesystem/limits/safe YAML and CLI reside outside the domain. Existing analyzers never import labels.

24 repositories, seven families, 62 cases: 30 POSITIVE/32 NEGATIVE, 31 per language, Java/TS only.
ARCH001–005 and ARCH201–205 each have two positive/two negative; ARCH101/102/104/105 also 2/2;
ARCH103 has 2/4. Five static families pair clean/mutants across Java/TS. One graph topology family
and one curated semantic family include both translations. TRAIN 5 families/16 repos/54 cases;
VALIDATION and TEST each 1 family/4 repos/4 cases. TEST is ARCH001, VALIDATION ARCH003; no
semantic/graph holdout. Hard checks enforce source duplicates, family and mutation lineage isolation.

Ground truth is independent and reviewed-status UNREVIEWED (no invented human reviewers). Stable
UUIDv5 and exact locators ignore lines/runtime IDs. Per-rule annotated subjects prevent cross-rule
scope inference. Missing/ambiguous truth is PARTIAL/UNRESOLVED_TRUTH; UNKNOWN is not negative.
A→B differs from B→A; callsites aggregate to file pair, cycles to SCC, semantic methods normalize to
component through IAM containment. Duplicates are diagnosed/deduplicated; contradictory states abstain.

## Manual verification

`benchmark validate`: VALID, no diagnostics. Logical dataset fingerprint:
`4e7a11770a42d68245e75bfde15101618579db4ff59bc12f27887478e796ba53`.
`benchmark split` equals the frozen split manifest. Formatting/comments preserve fingerprints.
Handcrafted prediction artifact through CLI: TP=8 FP=2 FN=2 TN=8; P=R=F1=0.8, FPR=FNR=0.2.

Actual pipeline smokes, **foundation only**:

| Task/channel | TP | FP | FN | TN | OOS | P | R | F1 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Confirmed conformance / Static | 8 | 0 | 2 | 10 | 0 | 1 | 0.8 | 0.888888888889 |
| Confirmed conformance / Graph | 2 | 0 | 8 | 10 | 0 | 1 | 0.2 | 0.333333333333 |
| Configured structural signals / Graph | 10 | 0 | 0 | 12 | 4 | 1 | 1 | 1 |

The Graph conformance run scores the same ARCH001–005 universe and detects only ARCH003, rather
than concealing unsupported rules. Structural results are candidate retrieval, not violation quality.
Zero denominators → null; no FPR without an explicit negative universe. Scoped extra FP outside
explicit controls disables FPR. Micro, macro rule/project, per-rule/language/project, abstention and
coverage are implemented. Recall/FNR are conditional when abstentions/AI coverage misses occur.

Manual mutations (strict parsing/IAM valid and complete, actual inserted dependency/cycle verified):

| Mutation | Identity | Base source fingerprint | Result source fingerprint |
| --- | --- | --- | --- |
| Java ARCH002 | f59c9b94-7207-523d-b7b1-9dfdd066bd8a | f6f0e43e1ca8f1a31adde9b13ed8ef36c67daaada92856a981a6b4fe57f0549e | f40d34a8faebc3c6caa87cbf1f7ffd9e8adbfee5bd4ec2b358ac5d9b4323dfac |
| Java ARCH003 | 2342d007-e0ef-560f-a365-a4b55c05dfe9 | 337e7c7f79f39acbe01ac372f7c0b9dd12e3bffbcb14ea3197431e71bf17182a | 1515749ea505de98d7607b74992ba3a398e463c4233deb55aef68c7adf15a120 |
| TS ARCH005 | 6839d533-d217-5207-8764-10ce6fd9c38b | 766b05cf75e454e7e39bde05818e777c83a54f2399b4d3586f871b54f9ecce23 | fd5b1f9164d971348cbc8e089088e796c8049a119ecf4831b3dbd7a1e29e9fd9 |

Changed-file byte hashes:

| File | Before SHA-256 | After SHA-256 |
| --- | --- | --- |
| Controller.java | 24ef219e4e518a2cc40bebca7b5d837e14d8f7e56cde288ecf37ccae94757624 | 8521a797b7d27156d2ec54f20c5707a32f354c9e12e7cf97632019a0dc9fd472 |
| C.java | 9288f5a912016bfa42df0b3356d66db5392b0d5f11ad23d4f02620ddbf39f042 | 02dcedb55b3878c28dbd000121a12efb2e2695359fd0002494df0d4c0580aff6 |
| OrderService.ts | 0622daec6466b4919982db18fceae85f6975cfe3bc482dbbe8c07618a41a3946 | 643a967bff7aa60e6c578d102550b792210a1bd95459f605311e9f9c2614a510 |

All five operators are tested in both Java and TypeScript; clean negatives fail positive structural
verification, mutants pass. Originals stay unchanged. Test/scripted LLM is used only for artifact
contract mapping: SUPPORTED→CANDIDATE, NOT_SUPPORTED→NEGATIVE, INSUFFICIENT_CONTEXT→ABSTAIN.
Three saved artifacts replay identically on macOS/Linux; no AI quality metrics/live calls.

Hybrid source-free export: TRAIN 16 / VALIDATION 2 / TEST 2, schema `hybrid-evidence-v1`; labels
stored separately. SCC joins use all SCC members. Twenty records are positive and four unannotated
proposals are omitted. Missing negative/semantic vectors are not fabricated. Independent-label-change
test preserves features/fingerprints; saved negative AI assessment joins a curated negative case in
contract tests. This feature export cannot train a useful classifier yet.

## Reproducibility and quality

Two independent local runs produced identical dataset/split/mutation/results/JSONL bytes.
Docker `archguard:prompt010`, image
`sha256:41ecdbd758e742880452c78e599ac156b3d4717cae9cd89b98bfc9c3ec8ef3cd`, nonroot
`archguard`, network disabled, read-only root/dataset, writable output mount and temporary filesystem.
24 macOS/Linux artifacts (including mutant source/manifest bytes) plus saved AI adapter predictions
were byte-identical. Operational logs with timestamps were excluded.

| Canonical artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| validate.json | 20624 | 029beafe052c5fb442e2b7c6b649622775323662c091112232a2cd4fded60f80 |
| static.json | 15294 | 1fd49f5dc325a59c5fcfb28491bbd8575af3e886857f5d15d79c270f47c3684e |
| graph.json | 10610 | e29ab3a8456357e5973771748f7f2644d900b8a730c54165a9c7efd051f69893 |
| handcrafted.json | 16303 | 4d73c642534f6e678101f7811dd2bbdf1e6d29b9b2404b621466421a4c0833cd |
| train.jsonl | 108815 | 42e436af76a00b737d4310ef5a04286fe27e88b7f799239f251bd11a3763e629 |

`uv sync --locked --extra dev`: green, no dependency changes. Final `make check`: Ruff green;
format 299 files; strict mypy 173 source files; **1025 passed / 0 failed / 0 skipped**, including all
previous 912 tests. Branch coverage **94%**; evaluator 99%, identity/splits 100%, models/resolver 97%,
adapters 96%, mutations/CLI 92%, infrastructure 94%. `git diff --check`: green.

Local raw evidence: `/tmp/archguard-010-final/` (manual scripts, mac/repeat/Linux artifacts and logs),
`/tmp/archguard-010-final-check.log`, `/tmp/archguard-010-sync.log`. These temporary artifacts are not
versioned research results. Reproduce with the documented CLI; source/ground truth/splits/operators
and expected formulas are checked in.

## Deferred and limits

No fitting, logistic/weighted policies, calibrated confidence, threshold selection, significance tests,
real-world benchmark, externally reviewed semantic truth, live LLM quality experiment, persistent jobs,
Security Engine, frontend or additional APIs. Single-class component normalization and controlled
marked templates are v1 restrictions; approximate clone detection is deferred. Small synthetic
partitions lack semantic/graph holdouts and negative training vectors. Expand/review the dataset and
assessment cohort before calibration. PROMPT 011 remains unstarted and requires PROMPT 010 review.
