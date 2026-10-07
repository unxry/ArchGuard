# PROMPT 015.E.2 — structural correction handoff

Status: **WAITING_FOR_ADJUDICATOR_CORRECTION**.
Ground truth: **FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN**.

## Verification and mechanical diagnosis

| Check | Result |
| --- | --- |
| Approved original SHA before human JSON parsing | PASS |
| Original SHA-256 | `df749173ff5ea783d4bbf6a582d3394c3eee6361b5abbd55bba874c79bcc9d8f` |
| Recovered P015.D complete byte/inventory verification | PASS |
| Expected / submitted / unique submitted IDs | 4 / 4 / 4 |
| Missing / extra / duplicate IDs | 1 / 1 / 0 |
| Invalid own-case evidence references | 1 |
| Invalid ranges in resolvable own-case references | 0 |
| Schema / bundle binding | PASS / PASS |
| Root-cause classification | A: unknown `blinded_id`; typo or intended case NOT DETERMINED |
| Human clarification | **HUMAN_CLARIFICATION_REQUIRED** |
| Decision changed / rationale or note changed / evidence auto-remapped | NO / NO / NO |
| Original remains byte-identical | YES |
| A/B leakage / construction-intent leakage findings | 0 / 0 |
| Live AI calls | 0 |
| Adjudicator accepted / final human truth materialized | NO / NO |

The invalid structured evidence ID exists in the frozen bundle, but cannot bind
to the unknown submitted case ID. This lookup does not establish intended case
identity. Five literal evidence-ID mentions were found in rationale/note; one
refers to a different frozen ID. These findings are recorded privately and are
never used for assignment. A typo or copied response cannot be established from
source text, rationale, rule, similarity or order. No extra-to-missing mapping is
inferred.

The private diagnostic names all expected/submitted IDs, missing/extra IDs,
affected response positions, the invalid structured reference and its frozen
owner IDs, permitted evidence for valid affected cases, and literal text-reference
locations. Individual IDs and human answers are omitted from this public report.

## Append-only correction round

Private directory:

`experiments/semantic-holdout/private/adjudicator-submissions-v1/corrections-v1/round-1/`

Open first:

`handoff/index.html`

The same instructions are available in `handoff/README.txt`. The human uses
`handoff/response-template-corrected-v1.json` and saves a NEW file at:

`experiments/semantic-holdout/private/adjudicator-submissions-v1/completed-response-corrected-v1.json`

The corrected submission does not exist yet and was not validated. This stage
creates no acceptance snapshot, canonical validated-submission fingerprint or
acceptance receipt.

| Artifact | Fingerprint |
| --- | --- |
| Correction package | `559537a7892df24eb57e6edf8bdd8936e46eb627da40f2f76c8d09e5ecbfe207` |
| Correction template (SHA-256 of raw bytes) | `d652de3742d9592a463259876b027fb39481e0ad2ed2686ceff77cfb10f7a533` |
| Source-free public verification audit | `d350af5f8ecd5de414516832ab3b9921324e8c8291d354d5dcd534687722fff8` |
| Original frozen D package | `cec7af09c40b78e6afca5626f87b860a2e591fb6153eea0f0795fad83be488ac` |

Package fingerprint means the deterministic sealed correction-round manifest,
which binds the inventory and raw SHA of every package file. This is a handoff
freeze, not adjudicator acceptance.

The round preserves `original-submission-v1.json` as exact original bytes. Three
unaffected responses are copied field-for-field, including omitted optional fields
and literal Unicode/newlines. Private provenance marks them PREVIOUSLY_HUMAN_SUPPLIED
and locks them for this round. The fourth frozen ID has null decision, blank
rationale/note and empty evidence. The unknown-ID answer is not inserted there.
The new attestation is null until the same human personally confirms the correction.

Only the missing frozen packet, plus any valid structurally affected packet, is
included for source review. The source-only packet, guidance and response schema
retain their frozen content. The human must independently confirm the proper ID,
decision, rationale and evidence. No distribution or answer is suggested. Requests
to reconsider retained answers require a separate round; this workflow does not
silently rewrite them.

All history directories have mode 0700, files 0600, and are Git-ignored. Existing
rounds cannot be overwritten. The public audit contains counts, fingerprints and
workflow state only; private source, identity, responses, diagnosis IDs and mapping
are not committed. Primary A/B submissions are checked as opaque bytes, and private
conflict judgments remain undecoded. Construction provenance is checked only through
its original inventory hashes.

## Validation commands

Executed successfully:

- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_adjudication_correction.py`: 19 passed.
- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_adjudication_correction.py tests/benchmark/test_semantic_adjudication_acceptance.py tests/benchmark/test_semantic_adjudication.py`: 133 passed.
- `.venv/bin/python -m ruff check scripts/prompt015e2_correction.py src/archguard/infrastructure/semantic_adjudication_correction.py tests/benchmark/test_semantic_adjudication_correction.py`.
- `.venv/bin/python -m ruff format --check scripts/prompt015e2_correction.py src/archguard/infrastructure/semantic_adjudication_correction.py tests/benchmark/test_semantic_adjudication_correction.py`.
- `.venv/bin/python -m mypy --strict src/archguard/infrastructure/semantic_adjudication_correction.py`.
- `.venv/bin/python scripts/prompt015_holdout.py --verify`: original P015 inventories PASS.
- `.venv/bin/python scripts/prompt015e_acceptance.py --verify-prerequisites`: scoped C/D verification and opaque A/B integrity PASS.
- `.venv/bin/python scripts/prompt015e1_recover_handoff.py --verify-handoff`: original D full byte/inventory verification PASS.
- `.venv/bin/python scripts/prompt015e2_correction.py --prepare`: correction round prepared once.
- `.venv/bin/python scripts/prompt015e2_correction.py --verify`: deterministic correction inventory/bytes PASS.

Historical C/D preparation CLIs are not replayed: C decodes individual A/B outcomes
and D requires an empty human-return directory. The scoped commands above verify
their original freezes without replaying those preparation behaviors.

`make check`: PASS — Ruff PASS, 406 files formatted, strict mypy PASS for 212 source
files, 1461 tests passed, 92% coverage. `git diff --check`: PASS. All intended
untracked files passed whitespace and credential-pattern checks; public audits
passed recursive field checks, and no exact private adjudicator/evidence ID was
found in any public addition. Private permission and Git-ignore checks passed.
Tests cover raw-SHA guards, exact set differences, invalid evidence,
literal-reference diagnostics without inference, source-text independence, immutable
human preservation, no generated answers, source/privacy guards, append-only rounds,
HTML escaping, no corrected-file reads, no acceptance and no provider execution.

## Git state

The six previous E/E.1 public-safe untracked files were inspected and retained
unchanged. This stage adds a correction workflow module, CLI, synthetic tests,
source-free audit and this report. No unrelated change was found.

No commit or push is required by the existing correction-handoff protocol; none
was performed. HEAD remains `0665c0533e28f63b02a3c4e88ccabe9c0790da90`.
The public additions remain untracked for the eventual successful acceptance
closure: 11 intended public-safe untracked files, no tracked modification or staged
file. All private correction artifacts remain ignored.

No final truth, effectiveness evaluation, AI, Structural V2 or Hybrid experiment
was executed. PROMPT 015.F and PROMPT 016 were not started.
