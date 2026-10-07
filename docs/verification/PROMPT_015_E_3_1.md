# PROMPT 015.E.3.1 — metadata recovery and corrected acceptance

## Explicit metadata recovery

| Check | Result |
| --- | --- |
| `.DS_Store` listed in the frozen manifest | NO |
| Intended frozen artifact count | 8, plus their sealed manifest |
| Every intended raw SHA valid before removal | YES |
| `.DS_Store` was the only unexpected entry; missing/other hidden entries | YES; 0 / 0 |
| Metadata removal performed | YES |
| Event | NON_SCIENTIFIC_FILESYSTEM_METADATA_REMOVAL |
| Any scientific/human file changed during recovery | NO |
| Round-1 regenerated / permissions normalized / timestamps intentionally changed | NO / NO / NO |
| Exact post-recovery inventory and hashes | PASS |

The explicit command checked the approved sealed manifest and all intended bytes
before unlinking exactly the root `.DS_Store`. It read no OS metadata contents.
Ordinary inventory verification remains strict. `.DS_Store` is identified as known
OS metadata, while arbitrary extra or hidden entries and changed/missing expected
files still block. `.gitignore` already contained `.DS_Store`, `.env.*` and the
private experiment rule; it was left unchanged.

| Frozen E.2 artifact | Unchanged fingerprint |
| --- | --- |
| Correction package | `559537a7892df24eb57e6edf8bdd8936e46eb627da40f2f76c8d09e5ecbfe207` |
| Correction template, raw SHA-256 | `d652de3742d9592a463259876b027fb39481e0ad2ed2686ceff77cfb10f7a533` |
| Correction public audit | `d350af5f8ecd5de414516832ab3b9921324e8c8291d354d5dcd534687722fff8` |
| Metadata recovery audit | `b9359b4cbefb197452c538bf1ed87c46c62ca7a2246798dce101f397bcc9fb79` |

## Complete resumed validation

| Check | Result |
| --- | --- |
| Corrected SHA verified before JSON parsing | PASS |
| Corrected input SHA-256 | `aa87b0b34a69ec660b0e83e0c91d5a379cf4f173ffb492c869b7d7de0157c66d` |
| Original rejected attempt preserved unchanged | YES |
| Original SHA-256 | `df749173ff5ea783d4bbf6a582d3394c3eee6361b5abbd55bba874c79bcc9d8f` |
| E.2 correction lineage, checked without regeneration | PASS |
| Recovered P015.D full byte/inventory verification | PASS |
| Schema / slot / attestation / bundle binding / membership / evidence | PASS |
| Responses / unique IDs | 4 / 4 |
| Missing / extra / duplicate / invalid evidence / invalid ranges | 0 / 0 / 0 / 0 / 0 |
| POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE | 1 / 3 / 0 / 0 |
| Locked unaffected responses / changed | 3 / 0 |
| Human-filled affected response / changed | 1 / 1 |
| Automatic remapping or generated answers | NO |
| Semantic correctness assessed | NO |
| Canonical validated corrected-submission fingerprint | `9ce7c7c38703ed0425a973de8fdee07812a4284ae85b64d916679fc198baa494` |

The approved corrected file is checked from scratch. Locked raw response
dictionaries are compared field-for-field, including optional fields and evidence
ordering. Affected-response changes use a multiset difference; no unknown original
ID is paired with a missing expected ID. The human may change the affected answer.
All four categories remain distinct; expected counts are measured, never imposed.

Only the third human's original/corrected inputs and permitted frozen case mapping
are used for correction scope. Primary A/B payloads and private conflict judgments
remain opaque; their approved hashes/seals are verified. Original construction
provenance is verified through inventory hashes without interpreting intent.
Identity matching is self-declared only, with no external identity claim.

## Acceptance and checks

| Acceptance check | Result |
| --- | --- |
| Accepted input | `completed-response-corrected-v1.json` |
| Private snapshot, byte-identical to approved corrected input | YES |
| Accepted snapshot raw SHA-256 | `aa87b0b34a69ec660b0e83e0c91d5a379cf4f173ffb492c869b7d7de0157c66d` |
| Canonical validated corrected-submission fingerprint | `9ce7c7c38703ed0425a973de8fdee07812a4284ae85b64d916679fc198baa494` |
| Adjudicator acceptance receipt fingerprint | `ba7397577483b344a5f94a0fc1adb4fbe51732d20d3234f61944fb2241b7e32e` |
| Public acceptance audit fingerprint | `6e3df8a75938b868f0685b1a0805235e52e7682fb7e61b470cc3ac002e82ec54` |
| Acceptance invocation count | 1 |
| Human content modified by acceptance | NO |
| Private snapshot inventory / modes / Git ignored | PASS / 0700 directory, 0600 files / YES |
| Original rejected input and correction history preserved | YES |
| Reviewer A / Reviewer B / agreement-conflict set / adjudicator | FROZEN / FROZEN / FROZEN / FROZEN |
| Status | ADJUDICATOR_FROZEN |
| Next state | READY_FOR_FINAL_HUMAN_GROUND_TRUTH_FREEZE |
| Ground truth status | FINAL_HUMAN_GROUND_TRUTH_NOT_FROZEN |
| Final 100-case truth materialized | NO |
| Construction intent accessed for semantic comparison | NO |
| Live AI calls | 0 |
| Effectiveness evaluation / Structural V2 / Hybrid experiments | NOT RUN / NOT RUN / NOT RUN |
| P015.F / P016 started | NO / NO |

The accepted snapshot contains the original corrected raw bytes, including their
formatting. Its source-free receipt binds all earlier freezes and correction
lineage. Creation is append-only and rejects an existing freeze. Verification
after creation passed without repeating acceptance or changing correction history.

| Recovered P015.D check | Unchanged fingerprint |
| --- | --- |
| Package | `cec7af09c40b78e6afca5626f87b860a2e591fb6153eea0f0795fad83be488ac` |
| Blank template SHA-256 | `ba9d11aee3e19c00e255a45d9e4fe67306645928b905ef9db6edd5bd1ad125d1` |
| Private mapping | `fa0e5c568ca255129bd5e44435e69f48736072f0227b5cbf1e9cf62822e9d24f` |
| Public receipt | `b7b66eeb7905729fe0d0f76cf924974f03cda5852925f6694058bc85506406c5` |
| Conflict count / full byte-inventory check | 4 / PASS |

Commands actually executed:

- `.venv/bin/python scripts/prompt015e31_recover_metadata.py --recover-os-metadata`: explicit one-time recovery PASS.
- `.venv/bin/python scripts/prompt015e3_corrected_acceptance.py --verify-correction-round`: strict E.2 inventory/bytes/lineage PASS, no regeneration.
- `.venv/bin/python scripts/prompt015e3_corrected_acceptance.py --validate`: complete corrected validation PASS, no snapshot at validation.
- `.venv/bin/python scripts/prompt015e31_recover_metadata.py --verify-recovery`: trusted recovery audit and unchanged lineage PASS, including after acceptance.
- `.venv/bin/python scripts/prompt015e3_corrected_acceptance.py --accept-corrected`: one-time acceptance PASS.
- `.venv/bin/python scripts/prompt015e3_corrected_acceptance.py --verify-accepted`: approved raw bytes, correction scope, lineage, private/public seals and all status guards PASS.
- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_adjudication.py tests/benchmark/test_semantic_adjudication_acceptance.py tests/benchmark/test_semantic_adjudication_correction.py tests/benchmark/test_semantic_adjudication_corrected_acceptance.py tests/benchmark/test_semantic_adjudication_metadata_recovery.py`: 198 passed in the final targeted run.
- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_adjudication_metadata_recovery.py`: 16 passed after recovery hardening.
- `.venv/bin/ruff check scripts/prompt015e31_recover_metadata.py tests/benchmark/test_semantic_adjudication_metadata_recovery.py`: PASS.
- `.venv/bin/ruff format scripts/prompt015e31_recover_metadata.py tests/benchmark/test_semantic_adjudication_metadata_recovery.py`: two files unchanged.
- `.venv/bin/python -m mypy --strict src/archguard/infrastructure/semantic_adjudication_corrected_acceptance.py`: PASS.
- `make check`: PASS; Ruff passed, formatting check passed for 414 files, mypy passed for 213 source files, 1526 tests passed, coverage 92%.
- `.venv/bin/python scripts/prompt015_holdout.py --verify`: original P015 inventories PASS.
- `.venv/bin/python scripts/prompt015e_acceptance.py --verify-prerequisites`: scoped C/D freeze verification and opaque A/B integrity PASS.
- `.venv/bin/python scripts/prompt015e1_recover_handoff.py --verify-handoff`: recovered D complete byte/inventory verification PASS.
- `git diff --check`: PASS.

The historical C CLI decodes individual A/B responses, and the historical D/E.2
preparation CLIs impose pre-acceptance state checks. Scoped integrity commands above
verify their approved freezes without repeating those preparation behaviors.

Regression coverage includes sole extraneous OS metadata, frozen metadata,
unknown/nested/hidden extras, changed/missing expected files, unchanged round
fingerprints and human bytes, dangling acceptance symlinks, trusted audit seals,
corrected SHA before parsing, strict schema/IDs/evidence/ranges/duplicate JSON keys,
locked raw dictionaries, all four categories, byte-identical append-only snapshots,
privacy, and absence of final truth/AI paths.

## Git scope and privacy

Every changed/untracked Git-visible file was inspected. Classification:
20 A public-safe files, 0 B private files and 0 C unrelated files. No tracked file
was modified. The following individual files are all category A:

- `docs/verification/PROMPT_015_E_1.md`
- `docs/verification/PROMPT_015_E_2.md`
- `docs/verification/PROMPT_015_E_3.md`
- `docs/verification/PROMPT_015_E_3_1.md`
- `experiments/semantic-holdout/adjudicator-correction-verification-v1.json`
- `experiments/semantic-holdout/adjudicator-handoff-recovery-verification-v1.json`
- `experiments/semantic-holdout/adjudicator-os-metadata-recovery-verification-v1.json`
- `experiments/semantic-holdout/adjudicator-acceptance-verification-v1.json`
- `scripts/prompt015e1_recover_handoff.py`
- `scripts/prompt015e2_correction.py`
- `scripts/prompt015e31_recover_metadata.py`
- `scripts/prompt015e3_corrected_acceptance.py`
- `scripts/prompt015e_acceptance.py`
- `src/archguard/infrastructure/semantic_adjudication_acceptance.py`
- `src/archguard/infrastructure/semantic_adjudication_corrected_acceptance.py`
- `src/archguard/infrastructure/semantic_adjudication_correction.py`
- `tests/benchmark/test_semantic_adjudication_acceptance.py`
- `tests/benchmark/test_semantic_adjudication_corrected_acceptance.py`
- `tests/benchmark/test_semantic_adjudication_correction.py`
- `tests/benchmark/test_semantic_adjudication_metadata_recovery.py`

The historical E.1/E.2 reports and the E.3 blocked report are retained. Private
human inputs, correction artifacts, accepted snapshot, source evidence, identities
and mappings remain Git-ignored and excluded from this classification of visible
files. Public workflow code, synthetic tests, source-free audits and reports were
checked for credential patterns and actual human identities, IDs, rationales and
notes; none were found. No secret-bearing environment file was read or fingerprinted.
Only category A is eligible for the normal commit/push closure.
