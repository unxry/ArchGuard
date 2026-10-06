# Frozen human ground truth — PROMPT 013.F

Status: **ANNOTATION_FROZEN**. All 40 cases are terminal: 39 DOUBLE_REVIEW, 1 ADJUDICATED.
Two initial reviewers contributed 80 reviews; distinct human `reviewer-c` contributed one
adjudication. Source-free final truth is P=0 / N=32 / U=0 / OOS=8; 32 binary-eligible, 8 excluded.

Engineering baseline/head at freeze: `e822fa4d71b934bf5b4b4ba1389a2bf79c30f07e`.
Sample: `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`.
Final catalog: `9d5e3aad6ce60a5d65ed0b1b34976066301be539c220bd8379325884985c0443`.
Adjudicated store: `684577a73716e15792e04cee77c8220bd4bd5e6c4363cbd1880b886f50eb957b`.
Adjudicated snapshot report: `d77b39c7a05899460ec2c7c5b86da428e3ea66ba29a01ae09803bc7daa9868f6`.
Ground truth: `14e8de64c7b0d1ccaa11dc6d0fed247ea723abc6bca2a1445f8f8298895ca0e4`.
Full experiment freeze: `6ed86e0806de70b797fff5d28a0d9a6417f65ba9cbcb85c131621aba73653a5f`.
Native protocol freeze: `7bc1dd4f4e48f6a32e9b29071e460effe8c5f8eb79e38ea33bcf13e5f504f2a3`.

`ground-truth.json` follows original sample order and includes only human labels, terminal states,
pinned packet identity and pseudonymous/event provenance. It contains no rationales or source text.
`annotation-freeze.json` is the experiment lineage receipt: it binds the existing native CLI
freeze plus corpus/sample/context/baseline, all three submissions, A+B/adjudicated stores,
source snapshot report, frozen-status report, ground truth and protocol/schema versions.
The native contract remains unchanged in `protocol-freeze/annotation-freeze.json`.

Verify the native protocol using the actual existing CLI, from the repository root:

```sh
.venv/bin/archguard benchmark oss review status \
  --catalog experiments/oss/annotation/review-packet-revisions-final-v1.json \
  --store experiments/oss/blinded/prompt013-e/import-adjudicated/reviews.json \
  --freeze-receipt experiments/oss/annotation-results/prompt013-f/protocol-freeze/annotation-freeze.json
```

The full experiment receipt is not passed to `--freeze-receipt`: that flag expects the native
oss-reviewed-annotation-freeze-v1 contract. Full bindings and artifact hashes are recorded here.
Any later human correction requires a new explicit version, lineage and freeze. These files
must remain immutable for the planned experiment; no silent truth edits or retroactive resampling.

## Agreement before adjudication

Original A/B categorical agreement is **39/40 = 97.5%**, including one ARCH202 OOS/NEGATIVE
conflict. Binary agreement is **32/32 = 100%**, nonbinary **7/8 = 87.5%**. Cohen's kappa is null:
both binary marginals contain only NEGATIVE, so the chance-agreement denominator is zero.
The adjudicator is not a third paired rater. Native agreement_rate=1.0 describes only 32 binary
pairs and must never be described as original A/B agreement on all 40 cases.

## Scientific readiness

ANNOTATION_VALID=YES; POSITIVE_CLASS_PRESENT=NO; REAL_AI_EXECUTION_READY=YES.
PRIMARY_SEMANTIC_EFFECTIVENESS_READY=NO; PRIMARY_BINARY_SEMANTIC_METRICS_READY=NO.
Zero human positives does not invalidate annotation, but this cohort alone cannot establish
meaningful positive-class Recall/F1/false-negative rate for semantic violation detection.
A separately authorized future experiment may assess specificity, negative correctness,
abstention/OOS handling, context comparisons, tokens, latency, cost and false positives.
A positive-bearing cohort must be a new prospectively defined dataset with its own freeze.
No new cohort or real AI/V2/Hybrid evaluation was performed by this freeze.

Human independence and the unseen annotation process rely on supplied procedural attestations;
real-world identity and external execution were not independently instrumented. The freeze
verified exact submitted fields and append-only imported history, with no automated truth changes.

## Final breakdown

| Rule | N | OOS | Binary eligible | Adjudicated |
| --- | ---: | ---: | ---: | ---: |
| ARCH201 | 8 | 0 | 8 | 0 |
| ARCH202 | 0 | 8 | 0 | 1 |
| ARCH203 | 8 | 0 | 8 | 0 |
| ARCH204 | 8 | 0 | 8 | 0 |
| ARCH205 | 8 | 0 | 8 | 0 |

Java and TypeScript each have 20 cases: N=16 / OOS=4 / binary-eligible=16.
Each of eight repositories has five cases: N=4 / OOS=1 / binary-eligible=4.
The adjudicated case is TypeScript in colinhacks-zod. P and U are zero in every group.
Private submissions/stores remain local; only source-free experimental artifacts are versioned.
STOP: do not start PROMPT 014 or real AI automatically.
