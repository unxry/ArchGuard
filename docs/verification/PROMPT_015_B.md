# PROMPT 015.B — Independent Reviewer B handoff

Status: **WAITING_FOR_REVIEWER_B**. No B review, acceptance, agreement,
adjudication or P016 execution was performed. Live AI calls: **0**.

## A workflow closure

All eight formerly untracked P015.A/A.2 files were inspected and classified as
intended public-safe workflow/tests/audits/reports. Unrelated files and secret
findings: 0. Human identity/rationales/notes, case/source evidence, private
submissions/packets/provenance and credentials were excluded from Git. Test
source strings are synthetic contract fixtures, not cohort evidence.

Closure commit: `091bbf1eade51d3c4915624d599c371f8df9df68`.
Message: `feat: freeze reviewer A acceptance workflow`.
Ordinary `git push origin main`: **SUCCESS**. Tracked and untracked working tree
was clean before B preparation. P014/P015 commits were not amended or rewritten.

The approved A source/snapshot SHA-256 and acceptance/canonical fingerprints
were verified during closure, before B preparation. A remains frozen, private
and **not final ground truth**. B preparation checks only the source-free A
acceptance receipt, never loads/parses A responses, and passes no A information
to the B builder. The coordinator report and repository must not be sent to B.

## Frozen B material and leakage audit

Original B bundle fingerprint:
`e8dd9955c0b3151fbe98d24024d74c09ec0e6d259ae7b49e80d75805629f682a`.

Separate private B handoff fingerprint:
`7df6cc9d55728b8abb2c3049886a407a86112c289ad7968df52cd68c08514059`.

The builder's sole input is the already frozen B bundle. Bundle bytes, 100
packets, frozen B order/IDs, source evidence, architecture contracts and general/
target rule guidance are preserved. No new context, hints or evidence selections
were added; there is no construction-intent lookup or regeneration of ordering.

| Verification | Result |
| --- | --- |
| Cases / unique blinded IDs | 100 / 100 |
| Matched pairs / Java / TypeScript | 50 / 50 / 50 |
| Cases per ARCH201–ARCH205 | 20 each |
| VALID / PARTIAL / INVALID | 100 / 0 / 0 |
| Missing / extra / duplicate cases | 0 / 0 / 0 |
| Pre-populated decisions / rationales / evidence | 0 / 0 / 0 |
| A→B leakage findings | 0 |
| Construction/pair/provenance leakage findings | 0 |
| AI/detector/V2/Hybrid output leakage findings | 0 |
| B labels collected / accepted B results | 0 / 0 |
| P013/P014/P015 fingerprints unchanged | YES |
| A accepted freeze still valid | YES |

The package contains no A decisions, rationale/note text, evidence selections,
identity, decision counts, uncertain/OOS case hints or submission fingerprints.
Generic independence instructions mentioning reviewer slots are procedural only.
HTML escapes source and forbids scripts/network resources. Typed bundle schemas,
recursive metadata/marker checks, fixed fingerprints and byte comparisons guard
against leakage and case alteration. Both original frozen inventories were
checked without decoding private construction provenance or pair maps.

Automated guards deny both pathlib and built-in reads of synthetic private A
source/snapshot files. Changing those canaries leaves every B package byte and
receipt unchanged. AST guards exclude provider/evaluation imports, A answer
inputs and ordering regeneration. The shared renderer/schema refactor preserves
the frozen A response-schema fingerprint.

## Human handoff and private return

Give **only this complete directory** privately to the different real human B:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-b-handoff-v1/`

Open first:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-b-handoff-v1/README.txt`

Then open `index.html` locally and fill a copy of `response-template.json`.
For every ID, the human must independently enter one category, a nonblank
rationale and their own nonempty evidence array with evidence_id/start_line/
end_line. Notes are optional. There are no default answers or reconstructed
evidence selections. Preserve the B slot, IDs and bundle fingerprint.

B self-declares their own reviewer_identity and
`REAL_HUMAN_INDEPENDENT_REVIEW` only after all 100 cases are reviewed. This also
declares that B is a different person from A, had no access to A answers, did not
communicate case answers before both submissions froze, and used no AI/model/
detector assistance or construction metadata. Identity/person distinction and
independence are not externally verified by this workflow.

Return the completed copy privately to the coordinator at:

`/Users/bendasroman/Downloads/ArchGuard/experiments/semantic-holdout/private/reviewer-b-submissions-v1/completed-response.json`

The submission directory is empty, mode 0700 and Git ignored. No completed or
accepted B record was initialized. Original handoff and bundle remain immutable;
future accepted submissions must be separately fingerprinted and stored without
overwrite. This stage provides no B acceptance execution path.

Source-free coordinator audit:
`experiments/semantic-holdout/reviewer-b-handoff-verification-v1.json`.

## Executed checks and Git

- Targeted review/holdout tests: **75 passed**.
- Targeted Ruff lint, formatting check and strict mypy: **PASS**.
- `make check`: **PASS**, Ruff lint/format, strict mypy, **1269 tests passed**,
  93% coverage.
- `scripts/prompt015b_handoff.py --prepare` and subsequent verification: **PASS**.
- Original-freeze, `git diff --check` and new-file whitespace checks: **PASS**.

Final working tree contains intended public-safe B workflow/test/audit/report
changes only: two shared modules modified and five new public-safe files.
Private handoff and empty submission directory remain ignored.
Only the A closure was committed/pushed. B changes are left reviewable.

**STOP: WAITING_FOR_REVIEWER_B.**
