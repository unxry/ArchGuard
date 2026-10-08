# PROMPT 021.A — authoritative human handoff and formal intake

P021_A_HUMAN_HANDOFF_READY / WAITING_FOR_REVIEWER_A_B. No human response was supplied, read, accepted or interpreted during this stage. Only synthetic temporary answers were used to exercise formal validation. Scientific provider calls=0; connectivity calls=0; paid spend=$0; PAID_EXECUTION_APPROVED=NO.

## A — Lineage

A1 P020 final commit PASS; A2 final holdout seal PASS; A3 authoritative registry PASS; A4 initial scientific tree PASS; A5 preserved unrelated deletion untouched YES.

Initial HEAD: `1891fa553218200139f027ed9c3a82d100f61462`. Entry `git status --porcelain=v1 -z` contained exactly the approved unstaged deletion ` D index(визуал).html`. Its content was never opened, hashed, restored, modified, staged or committed. Only that exact path is excluded; other entry modifications=0. The filesystem helper rejects reading/hashing this path.

Ancestry resolved through `git merge-base --is-ancestor`, never from a textual claim:

| Stage | Ancestor | Result |
|---|---|---|
| P017 | `8a11b012dadde660318053f2cb6845703cae7547` | PASS |
| P018 | `264e7cc237f96714fc1d066d04418944e397a6e2` | PASS |
| P019 | `2f596fb57b00a1d8374cdcba50a98ab6ffbe4023` | PASS |
| P020_ALIGNMENT | `b16e91b99708cc84bfec88c63c9dcef62c67bc92` | PASS |
| P020_HOLDOUT | `8d561c9c33a35bb8ce8717ff7020d8e212ad0505` | PASS |
| P020_CORRECTION | `29e9c1782d3ec60b65d4e1f1bb1ad721f4d03758` | PASS |
| P020_CLOSURE | `1891fa553218200139f027ed9c3a82d100f61462` | PASS |

These P020 seals were verified without decoding the execution, prediction or request contents. All remained unchanged after handoff copying:

| Frozen input | Fingerprint | Result |
|---|---|---|
| `experiments/unified-hybrid/p020-final-holdout-freeze-v1.json` | `fad0026e938a04a626fcf3b4ce73a8c78d05f6f1835ad42f4db1e03fc5d5be06` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/inputs/manifest.json` | `44f397e9ea9660dc270744338a175ccfc78b742a9cc014a455492c50b46b31a7` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/evidence/evidence.json` | `bcefd040216b64a1d636a155ec2b62b6aeb9d089be92405d9899874c86971633` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/requests/contexts.json` | `852f827060673d7189aecf72b1d4f81d19617d7c9e171868dd3230ac568d8c22` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/requests/manifest.json` | `efa1dec52b7694122e6b13779ed1b9683b771c0fc6cd4031f5c16b8671d2e507` | PASS |
| `experiments/unified-hybrid/p020-hybrid-protocol-v1.json` | `331ffb2bc8d9c9d8b99c2bd4d12fd5e929ba50b584b02eb49360b2e9eba2b77a` | PASS |
| `experiments/unified-hybrid/p020-ablation-protocol-v1.json` | `b0f57d269f7c945afa10d9ecd604700d1c1892eb95a98dac2e197fed0dc4b959` | PASS |
| `experiments/unified-hybrid/p020-registry-v2.json` | `2bec29bb5d19419d90e8a5627a49044c82c33f7f13528116d587ade70d0a4116` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/review-v2/packet-inventory.json` | `0fe24c499e544e24343c0bceb5fa0367e0a6af946b3878954ce053fa3ad60843` | PASS |
| `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/review-v2/assignment-manifest.json` | `dd51cb05ff374f07ac21cc9b2906351c5d18c90a596150b08b4719745a2eedbc` | PASS |
| `experiments/unified-hybrid/p020-blinded-review-handoff-v2.json` | `dcc25eb58fcb25055de10c17ea94c5796edf7ae81f30e4c575f417c8d041f3aa` | PASS |

## B — Authoritative review-v2

B1 ONLY authorized source: `experiments/unified-hybrid/private/unified-hybrid-experiment-v1/final/review-v2/`.

B2 packet inventory: `0fe24c499e544e24343c0bceb5fa0367e0a6af946b3878954ce053fa3ad60843`.

B3 assignment: `dd51cb05ff374f07ac21cc9b2906351c5d18c90a596150b08b4719745a2eedbc`.

B4 P020 authoritative handoff receipt: `dcc25eb58fcb25055de10c17ea94c5796edf7ae81f30e4c575f417c8d041f3aa`.

Historical generation packet `86e037ed607c4b0d273e51215d0c174f61dcc926b8c16457bf349ef75f7a5130` is lineage ONLY, never a human handoff authority.

B5 Reviewer A packets=100; B6 Reviewer B packets=100; B7 same scientific case set=YES (opaque packet IDs and sealed packet fingerprints match exactly); B8 independently blinded order=YES. Each existing sequence matches P020 SHA256 ranking of version, reviewer slot and opaque ID. P021 does not regenerate order or access the construction map. No guarantee of nonadjacent pairs is asserted: incidental adjacency cannot be diagnosed without decoding private construction data. The order does not depend on pair or construction position; P020 permutation regressions verify this independently.

B9 construction leakage findings=0; B10 component/model leakage findings=0. Checks are schema, inventory, hash and prohibited-metadata checks only. Bundle source is never used to decide categories. Protocol/guidance schemas and source packet seals are unchanged; templates contain no category, rationale, evidence or attestation.

## C — Legacy package safety

C1 legacy `final/review/` exists=YES, retained as historical data. C2 authorized for humans=NO; C3 copied into handoff=NO; C4 rejecting legacy/alternative handoff paths=PASS. P021 does not read the legacy order or copy legacy files. The authoritative source path is checked before handoff preparation and verification.

## D — Private human handoff

| Reviewer | State | Cases | Instructions SHA256 | Handoff receipt fingerprint | Archive |
|---|---|---:|---|---|---|
| Reviewer A | READY | 100 | `92a31f4535460ae7f6326be73662937a3fc7511901958e2a79bb4a22604d512e` | `e746165e96b4badab275323cdbd17da4dd3791f1c3e4349022154b2cf49c67f9` | null |
| Reviewer B | READY | 100 | `6a033b1f35b2d87ba4f1a7bf3cef8810bd253aa9b0713ad9183a89d8b63b8dec` | `58a3d4b668f6d6050d255534bec337f837d630133ea226636f10ae8a93583d58` | null |

D1/D2 both READY. D3 instructions fingerprints and D4/D5 receipt fingerprints are above. D6 archive fingerprints=null; directory handoffs suffice. D7 source packet bytes changed=NO.

Give A ONLY `/Users/bendasroman/Downloads/ArchGuard/experiments/unified-hybrid/private/unified-hybrid-experiment-v1/human-handoff/reviewer-a/`.

Give B ONLY `/Users/bendasroman/Downloads/ArchGuard/experiments/unified-hybrid/private/unified-hybrid-experiment-v1/human-handoff/reviewer-b/`.

Each contains six manifest-bound files plus one receipt: byte-identical `bundle.json`, `submission-schema.json`, `submission-template.json`, `guidance.json`, `protocol.json`; new role-specific `README.txt`; and `handoff-receipt.json`. No assignment map, packet inventory, coordinator map or other reviewer package is copied. Full file composition, bytes, receipts and blankness verify deterministically. Directories are mode700; files mode600; all delivery material is Git-ignored. Receipts contain roles, counts, seals and byte inventory only. No archive or hidden metadata file was added.

Read README first. Copy the blank template to `completed-response.json`, complete all 100 rows, keep IDs/role/bundle fingerprint fixed, and return privately. Evidence lines are inclusive, start at 1 inside decoded source evidence text, and must belong to that case's supplied evidence_id. The immutable blank template stays blank.

Independent human judgments and human-written rationales are mandatory. ChatGPT, Claude, Gemini, Copilot, all other LLMs and automatic architecture classifiers are prohibited. Ordinary editors/viewers are allowed. Use only supplied packet material, no internet or repository browsing. No answer exchange before BOTH accepted independent submissions freeze.

The four definitions retain the P015-compatible rubric: POSITIVE requires an applicable question with sufficient concrete violation evidence; NEGATIVE requires applicable sufficient evidence justifying absence; UNCERTAIN denotes insufficient context or unresolved role/boundary/interpretation; OUT_OF_SCOPE denotes an inapplicable question. No uncertain or out-of-scope answer becomes negative.

## E — Formal intake foundation

E1 expected responses/reviewer=100; E2 unique expected IDs/reviewer=100. E3 enum=POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE. E4 rationale required=YES; E5 evidence validation=YES; E6 semantic auto-correction=NO; E7 append-only freeze=YES; E8 explicit correction workflow=YES.

The existing frozen P015 submission schemas are reused byte-for-byte. Strict formal validation checks reviewer slot and exact v2 bundle, exact 100 assigned IDs, missing/extra/duplicate IDs, duplicate JSON object keys, enum, nonblank rationale, required attestation, nonempty references, known evidence within that case, positive integer existing source lines and ordered inclusive ranges. Unknown fields are forbidden at submission/response/evidence levels. No category is inferred from prose, normalized, corrected or scored. Raw accepted human bytes are preserved, including their original formatting.

Reviewer identity must be an opaque `human-` plus 32 lowercase hexadecimal characters; names/emails/account IDs are rejected. The coordinator must privately establish two distinct humans. Distinct pseudonyms and self-attestations alone cannot prove identity, authorship or independence. Public receipts expose no reviewer identity or personally identifying provenance.

Future coordinator intake must snapshot returned `completed-response.json` into a private round and seal its exact hash, role and authoritative bundle in `intake-manifest.json` BEFORE formal parsing. The caller pins that manifest fingerprint; a submitter's own inventory is not trusted. `validate_intake_directory` requires the exact two-entry snapshot inventory and full hashes, then validates the unchanged submission. No real round or completed form was created in P021.A.

The narrow metadata rule is retained: an explicitly requested root `.DS_Store` removal is allowed only when it was not frozen, is the sole extra filesystem entry, every expected file exists with its frozen hash, and no expected artifact changed. The expected inventory is rechecked after removal. Any other hidden/unexpected file, extra directory, nested `.DS_Store`, changed/missing file, symlink or traversal blocks. There is no generic hidden-file exemption.

Future independent acceptance uses A/v0001 and B/v0001 stores. An existing accepted version cannot be overwritten. A correction requires the latest previous receipt, a nonempty human reason, explicit human correction attestation and a new numbered immutable version. It preserves the original response and all earlier receipts. Same-role bundle/pseudonym must remain bound; A/B pseudonyms must differ. No real acceptance/correction occurs in this stage; synthetic fixtures reside only in temporary test directories.

## F — Prospective agreement and adjudication

F1 categorical agreement protocol frozen=YES; F2 kappa protocol frozen=YES; F3 conflict=A category != B category; F4 adjudicator protocol frozen=YES; F5 exact agreements sent to adjudicator=NO; F6 AI adjudicator=NO.

Protocol fingerprint: `ad36f4d71ccedb76a38bd44abcc3fda626d148f996b8b504436474bca21811c1`. Readiness freeze: `6b1a9af74955442402acc4920c5ca2bc71474af346df15bd25a0ab62c2755804`.

Agreement may run only after both distinct humans' accepted submissions freeze. Align the same 100 opaque IDs, never response order. Exact agreement count uses all four categories; agreement rate=count/100. Cohen's kappa=(observed agreement-expected agreement)/(1-expected agreement), expected agreement=sum over four marginal-category products; null when undefined. Binary eligibility requires BOTH human-selected categories in POSITIVE/NEGATIVE; report eligible coverage and exact binary agreement/eligible count, null if eligible count=0. Retain four-category counts separately. Nothing is calculated on empty or synthetic answers.

Freeze categorical conflicts only; rationale wording never creates conflict. A third distinct real human receives only original source, target question/rule and contract, following the P015-compatible source-only independent design. A/B categories/rationales are withheld. Exact-agreement cases never go to adjudication. Require a human-selected one-of-four category, own rationale, supplied evidence lines and attestation. No construction metadata, components, model results or automated vote is admissible. No conflict manifest, adjudicator packet or answer was created here.

## G — Scientific boundaries

| Item | Actual |
|---|---|
| G1 Reviewer A scientific answers created | NO |
| G2 Reviewer B scientific answers created | NO |
| G3 Adjudication answers created | NO |
| G4 Final semantic human truth created | NO / NOT_CREATED |
| G5 Construction intent decoded for review | NO |
| G6 AI-generated scientific labels | NO |
| G7 Provider calls | 0 |
| Connectivity calls | 0 |
| G8 Paid spend | $0 |
| Paid execution approved | NO |
| G9 Hybrid trained | NO |
| G10 Final evaluation | NO |

No 180 development or 300 final provider requests, connectivity validation, Hybrid fitting, ablations or correctness join were started. The CLI exposes ONLY prepare/verify; it has no human-answer import, inference or evaluation command. Its audit hook blocks network and credential opens and restricts private file reads to pinned artifacts and review-v2. Coordinator construction/truth and component output capabilities are denied. P020 fingerprints and packet bytes remain immutable. Private case source is processed solely for hash/schema/evidence-bound/privacy integrity, never to decide or suggest a category.

## H — Quality

H1 targeted P021 + P020 order + P015 A/B/schema/adjudication/metadata/agreement + architecture-boundary regression: **245 passed**, including **54 P021.A tests**. These include synthetic valid/invalid intake, append-only originals and corrections, exact inventory, strict privacy, offline capabilities and exact worktree exception tests. No test calls a real provider or creates real scientific answers.

H2 full make check=PASS; H3 total tests=**2007 passed** in 1008.58s; H4 coverage=**87%**; H5 Ruff=PASS; H6 formatting=PASS (464 files); H7 strict mypy=PASS (232 source files).

H8 authoritative review-v2 deterministic verification=PASS; H9 synthetic intake verification=PASS. H10 privacy audit=PASS; H11 secret audit=PASS; H12 git diff check=PASS. A fresh subprocess also verified the handoff with a minimal environment containing no credential configuration.

The public surface is protocols, counts, synthetic tests, coordination code, hashes and status only. No scientific source excerpt, human answer/rationale/evidence, reviewer identity or private assignment map is published. The secret env file is never opened, read, hashed, logged, serialized, diffed or committed.

## I — Git closure

I1 the closure commit is resolved by `git log -1 --format=%H -- docs/verification/PROMPT_021_A.md` after committing this report; its full SHA and normal push result are returned in the final response. An artifact cannot contain its own Git commit hash before commit. I2 normal push to origin/main only, verified by remote HEAD equality after commit. I3 scientific tree clean after closure; I4 the sole original ` D index(визуал).html` exception remains unstaged. No amend/rebase/reset/squash/force push. No private handoff, assignment, source, answer or secret is staged.

## Next manual action

1. Give Reviewer A ONLY the Reviewer A authoritative handoff directory.
2. Give Reviewer B ONLY the Reviewer B authoritative handoff directory.
3. They work independently, without AI assistance.
4. Do not exchange answers before BOTH independent submissions freeze.
5. Return the two completed human submission bundles privately to the coordinator.
6. Do not start adjudication manually before A/B submissions freeze and the categorical conflict manifest is generated.

## Final status

P021_A_HUMAN_HANDOFF_READY
AUTHORITATIVE_REVIEW_V2_VERIFIED
REVIEWER_A_PACKAGE_READY
REVIEWER_B_PACKAGE_READY
HUMAN_SUBMISSION_VALIDATOR_READY
WAITING_FOR_REVIEWER_A_B

STOP. Do not review cases, create human answers/final truth, call a provider or train Hybrid.
