# PROMPT 015.A.2 — Reviewer A submission validation and acceptance freeze

Validation **PASS**. Reviewer A is formally accepted and independently frozen.

## Input and formal validation

Private input:
`experiments/semantic-holdout/private/reviewer-a-submissions-v1/completed-response.json`.

SHA-256 was checked **before parsing or other processing**, and matched the
user-approved value:
`b6d231701aa727966481868c51cf43261dcd5c799d6b4c430cbdbf77eff3973e`.

Frozen A bundle:
`54069d685872195aafa91692d4184d4790655915da8ac4ef18d61620794c6151`.

The response schema version, A slot, exact bundle binding, nonblank self-declared
identity and `REAL_HUMAN_INDEPENDENT_REVIEW` attestation passed formal validation.
No human identity, rationale, note or individual decision is included in this
public report. Identity, authorship and independence are self-declared, not
externally verified.

| Check | Result |
| --- | --- |
| Responses / unique blinded IDs | 100 / 100 |
| POSITIVE | 52 |
| NEGATIVE | 43 |
| UNCERTAIN | 4 |
| OUT_OF_SCOPE | 1 |
| Missing / extra cases / duplicate IDs | 0 / 0 / 0 |
| Invalid evidence IDs / invalid line ranges | 0 / 0 |
| Frozen response schema / evidence validation | PASS / PASS |
| Construction metadata field/marker audit | PASS |

Counts were verified against the requested totals, never adjusted. Each response
has exactly one allowed category, a nonblank human rationale and a nonempty
structured evidence array. Evidence IDs belong to the corresponding frozen case;
inclusive integer line ranges fit the frozen source text. Duplicate JSON fields
are rejected rather than silently collapsed.

The working handoff directory contains `completed-response.json` and no longer
contains `response-template.json`. The original packet bundle, schema, HTML,
instructions and handoff receipt are unchanged. Acceptance validates the frozen
bundle and frozen submission schema separately from the empty delivery template.
No working handoff file or human answer was repaired, overwritten or deleted.
The handoff receipt remains
`7edd552a2fa288dd10936fd5e3a40f9302e25d59e3676349be6a1b379b1c428e`.

## Append-only acceptance

The acceptance snapshot is created once at:
`experiments/semantic-holdout/private/reviewer-a-submissions-v1/frozen-v1/`.

- `submission-v1.json`: exact submitted bytes, preserving all human content and
  formatting. The original `completed-response.json` also remains unchanged.
- `submission-freeze-v1.json`: source-free acceptance receipt containing input
  SHA-256, canonical validated submission fingerprint, bundle binding, reviewer
  slot, response/decision counts, validation results, zero invalid/missing/extra/
  duplicate counts, and lineage to P015's sample/corpus/freeze and handoff.

The tool refuses an existing freeze directory. Both the human input and snapshot
stay private/Git ignored, inside mode-0700 directories. The receipt contains no
reviewer identity, rationales, evidence texts or individual case outcomes.
No timestamp was added; existing holdout receipts use deterministic seals without
validation timestamps.

Acceptance receipt fingerprint:
`58488f51c3050266ecdc930e8c24814d7d4040ba1101765ed2180d8a1c0ffb08`.

Canonical validated submission fingerprint:
`5c9e97870a96b195eee3d2331f3003918cdf30ad30236922b56b93b16cf114d2`.
The original and accepted snapshot are byte-identical and have the approved
submitted-file SHA-256 stated above. Human answers modified: **NO**.

The source-free public audit is:
`experiments/semantic-holdout/reviewer-a-acceptance-verification-v1.json`.

## Scientific boundaries and old freezes

Reviewer A is one independently submitted human review stream. It is **not final
ground truth**, not adjudicated truth and not model labels. The review is not
compared against construction metadata. There is no accuracy, precision, recall,
F1, agreement, mutation success rate or semantic correctness assessment.

HEAD remains `e91e6c13e6cc7dff7b640f9a968e52dd07745f11`, descending from P014
`f69a544a9b80911a471040b478173bb8bf7f9486`. P013/P014 tracked experiment trees
and the complete P015 frozen public/private inventories remain unchanged.
Sample = 100; VALID = 100. The original A and B bundle hashes are unchanged;
B's bundle was checked as file bytes only, with no B ordering/answers loaded.
Private construction provenance and pair maps were hashed for integrity only,
never decoded or joined to responses.

Live AI calls during this stage = **0**. No secret env file was read, and no
credential was exposed or persisted. Reviewer B was not started; no adjudication
or P016 execution occurred.

## Commands and Git

Actually run:

- `python -m pytest -q tests/benchmark/test_semantic_review.py tests/benchmark/test_semantic_holdout.py`
  using `.venv/bin/python`: **48 passed**.
- Targeted Ruff and strict mypy for the review workflow: **PASS**.
- `make check`: **PASS**, Ruff lint/format, strict mypy, **1242 tests passed**,
  93% coverage.
- `python scripts/prompt015_holdout.py --verify` using `.venv/bin/python`: **PASS**.
- `git diff --check` and checks of new-file whitespace: **PASS**.
- `.venv/bin/python scripts/prompt015a_handoff.py --accept-completed`: **PASS**.

Git contains only the intended, untracked P015.A workflow/test/audit/report files
and this P015.A.2 report/audit. No existing tracked files were changed. No commit
or push was requested or performed. All human response files remain ignored.

Final status: **REVIEWER_A_FROZEN / READY_FOR_REVIEWER_B_HANDOFF**.
Stopped before Reviewer B handoff, adjudication or P016.
