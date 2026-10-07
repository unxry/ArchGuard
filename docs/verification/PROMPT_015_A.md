# PROMPT 015.A — Reviewer A handoff validation

Status: **WAITING_FOR_REVIEWER_A**. No case was reviewed by this workflow.

## Baseline and unchanged cohort

HEAD remains P015 `e91e6c13e6cc7dff7b640f9a968e52dd07745f11`, descending from
P014 `f69a544a9b80911a471040b478173bb8bf7f9486`.
P013/P014 tracked experiment trees and the P015 public/private frozen inventories
are unchanged. Every declared file hash, both inventory seals, packet seals and
the embedded protocol/guidance seals were verified. Private provenance and pair
mapping were hashed for integrity only, never decoded or used to render cases.

- 100 cases, 100 unique blinded IDs, 50 frozen matched pairs.
- 50 Java / 50 TypeScript; 20 cases for each ARCH201–ARCH205.
- 100 VALID; 0 PARTIAL; 0 INVALID.
- Pre-populated decisions/rationales: **0**; human labels collected: **0**.
- Live AI calls during P015.A: **0**. P014's historical usage is unchanged.
- No holdout AI, detector-assisted labeling, V2, Hybrid, agreement, adjudication
  or P016 execution. Reviewer B was not started.

| Artifact | Unchanged fingerprint |
| --- | --- |
| Reviewer A bundle | `54069d685872195aafa91692d4184d4790655915da8ac4ef18d61620794c6151` |
| Corpus | `15273b2f42c2d15e79d9632b25942f8e2c4e589af93dd6eed9663fa080eca2b3` |
| Sample | `926cf3014e3c46f9c3a62df6421ce89886373559335411209f25780130e1f5fa` |
| Sample freeze | `b291e47d6b5ed7ffcbbac967b221b5dee7366fa2d559031b19bc5b3d751b3dfb` |

New, separate handoff freeze:
`7edd552a2fa288dd10936fd5e3a40f9302e25d59e3676349be6a1b379b1c428e`.
The source-free audit is
`experiments/semantic-holdout/reviewer-a-handoff-verification-v1.json`.

## Leakage audit — PASS

The handoff is generated solely from the already frozen A bundle, preserving its
100-packet order and copying its bytes unchanged. Its HTML shows blinded IDs,
target rules/components/paths, languages, architecture contracts, frozen general
and target guidance, and the existing source evidence with display line numbers.
No new dependency analysis or semantic hints were added.

Closed packet DTOs, recursive forbidden-metadata/marker checks, the fixed A
fingerprint and reproducible render comparisons reject leakage. There are no
visible pair identities, construction classes, operators/effects, provenance,
transformation records, predictions, B ordering/answers or adjudication data.
The copied frozen protocol includes independence/adjudication policy only.
The HTML escapes source and permits no scripts, network resources or forms.

The response template contains exactly 100 IDs, null decisions, empty rationales,
empty references and empty notes. It is deliberately rejected as a submission.
No categorical default is provided. No secret env file is loaded or included.

## Give this package to the real human Reviewer A

Give **only this entire directory**, through a private channel:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-a-handoff-v1/`

It contains `index.html`, `README.txt`, the unchanged `bundle-v1.json`,
`response-template.json`, `submission-schema.json` and `handoff-freeze.json`.
Do not send the repository, other private directories, B material or this
coordinator verification report. The handoff remains Git ignored and mode 0700.

The human opens `index.html` locally, reads `README.txt` and reviews all 100 cases
independently. They fill a copy of `response-template.json` with exactly one of
POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE for every case, their own concise
rationale, at least one same-case evidence ID and inclusive source line range,
and an optional note. They preserve IDs and the bundle fingerprint.

They enter their self-declared real identity and set
`attestation: REAL_HUMAN_INDEPENDENT_REVIEW` only after completing the review.
No model/detector may decide, suggest answers or write rationales. They must not
receive B answers or share their answers with B before both submissions freeze.
Identity, authorship and independence are not externally verified by this tool;
no reviewer identity or attestation has been assigned during P015.A.

## Return and later independent submission freeze

Template:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-a-handoff-v1/response-template.json`

Return the human's completed copy privately to the coordinator at:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-a-submissions-v1/completed-response.json`

The prepared submission directory is empty, mode 0700 and Git ignored. No
response record or human label has been initialized. After actual human return,
the coordinator can validate and independently freeze the submission from the
repository root:

```sh
.venv/bin/python scripts/prompt015a_handoff.py --submit \
  experiments/semantic-holdout/private/reviewer-a-submissions-v1/completed-response.json
```

This command was **not run on the real cohort during P015.A**. It requires exactly
100 unique frozen IDs, exactly one allowed category, nonblank rationale/identity,
human attestation and valid same-case source references. It rejects missing,
multiple, duplicate JSON fields, invalid categories, foreign evidence and extra
metadata. It does not verify or generate semantic decisions/rationales.

Accepted records are created once at:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-a-submissions-v1/frozen-v1/submission-v1.json`

Its independent canonical fingerprint and self-declaration limitation are
recorded in sibling `submission-freeze-v1.json`. An existing freeze cannot be
overwritten or reimported by the tool. The frozen A bundle remains unchanged.
The intake copy is separate from this accepted snapshot. There is no construction
intent join, access to B answers, agreement calculation or adjudication.

## Validation and Git

- 43 targeted tests passed: existing P015 leakage/freeze tests plus new synthetic
  response contract, source scope, duplicate decision, HTML escaping and immutable
  submission tests. Synthetic fixture IDs are never real cohort judgments.
- Strict mypy for both new modules: PASS; targeted Ruff: PASS.
- Final `make check`: PASS — Ruff lint/format, strict mypy, 1237 tests; 93% coverage.
- `git diff --check` and new-file whitespace checks: PASS.
- Git: expected new P015.A workflow, tests, audit and this report only; no existing
  file changes, commit or push performed. Source-bearing handoff/submissions stay
  ignored outside the original immutable P015 private inventory.

**STOP: WAITING_FOR_REVIEWER_A.**
