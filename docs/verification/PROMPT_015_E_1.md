# PROMPT 015.E.1 recovery and acceptance verification

Recovery: **PASS**. Acceptance: **PROMPT_015_E_BLOCKED**.

The approved human file passes schema, attestation, identity-completeness and
bundle-binding checks. Its four unique responses do not cover exactly the four
frozen adjudicator IDs: one expected case is missing and one unexpected case is
present. One evidence reference consequently cannot resolve within its submitted
case. No human answer was edited, normalized, substituted or accepted.

## Recovery

| Check | Result |
| --- | --- |
| Canonical human submission SHA-256 | `df749173ff5ea783d4bbf6a582d3394c3eee6361b5abbd55bba874c79bcc9d8f` |
| Misplaced handoff submission SHA-256, before removal | `df749173ff5ea783d4bbf6a582d3394c3eee6361b5abbd55bba874c79bcc9d8f` |
| Human files byte-identical | YES |
| Recovery source | deterministic-regeneration |
| Recovered blank SHA-256 | `ba9d11aee3e19c00e255a45d9e4fe67306645928b905ef9db6edd5bd1ad125d1` |
| Blank exact expected hash | YES |
| Final D inventory and independent complete byte verification | PASS |
| Package cases / unique IDs | 4 / 4 |
| Other frozen files modified | NO |
| Prepopulated answers / leakage findings | 0 / 0 |

Filename searches found no preserved template in the holdout private tree,
workspace, `/private/tmp` or attachment directories. Unrelated archives were not
used. The unchanged D builder at
`0665c0533e28f63b02a3c4e88ccabe9c0790da90` reproduced the complete original
material using the verified source-only index, sample, guidance, four packets and
original private blinding key. The generation path does not read human submissions,
A/B decisions or construction provenance. Reproduced mapping, bundle, package and
all surviving handoff bytes matched before repair. Only the exact blank was written
and the proven duplicate was removed. The canonical human file remained unchanged.

| Original frozen artifact | Unchanged fingerprint |
| --- | --- |
| C conflict manifest | `47926ff2491a73194037a2f954b2ae01dfbcf972fb065ae3d2cf67b7a26d2189` |
| C safe index | `fb52bcde381fe4ba3357d18011bcca2c68b072ec5089edb55d8c989e793935db` |
| D package | `cec7af09c40b78e6afca5626f87b860a2e591fb6153eea0f0795fad83be488ac` |
| D private mapping | `fa0e5c568ca255129bd5e44435e69f48736072f0227b5cbf1e9cf62822e9d24f` |
| D public verification receipt | `b7b66eeb7905729fe0d0f76cf924974f03cda5852925f6694058bc85506406c5` |
| Adjudicator bundle | `83c9ebd641819381722797232ed1f22401e77a8f5adacc714a90cc65d78ccddd` |
| Recovery audit | `571e9aa9c0fa0cf34b1d5c37cb19147b9060b244ad9bba75da505288097d7889` |

## Acceptance result

| Check | Result |
| --- | --- |
| Approved raw SHA before parsing | PASS |
| Frozen schema / ADJUDICATOR slot | PASS |
| Nonblank self-declared identity / exact attestation | PASS |
| Exact bundle binding | PASS |
| Responses / unique submitted IDs | 4 / 4 |
| POSITIVE / NEGATIVE / UNCERTAIN / OUT_OF_SCOPE | 1 / 3 / 0 / 0 |
| Exact frozen case membership | FAIL |
| Missing / extra / duplicate cases | 1 / 1 / 0 |
| Invalid own-case evidence references | 1 |
| Invalid line ranges in resolvable references | 0 |
| Duplicate JSON keys | 0 |
| Human content modified | NO |
| Acceptance snapshot created / byte-identical snapshot | NO / NOT APPLICABLE |
| Canonical validated submission fingerprint | NOT ISSUED: validation failed |
| Acceptance receipt fingerprint | NOT ISSUED |
| Final human ground truth materialized | NO |
| Live AI calls | 0 |

The independent primary snapshots were checked as opaque bytes plus source-free
receipts. Private conflict judgments were verified through their original canonical
seal without decoding them. Original P015 inventories were verified by hashes;
construction intent was not decoded or compared. Semantic correctness was not
assessed. Reviewer A, Reviewer B and agreement/conflicts remain FROZEN.
Adjudicator remains NOT FROZEN; final human ground truth remains NOT FROZEN.

## Commands and checks

Executed successfully:

- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_adjudication_acceptance.py tests/benchmark/test_semantic_adjudication.py`: 114 passed.
- `.venv/bin/python -m ruff check scripts/prompt015e_acceptance.py scripts/prompt015e1_recover_handoff.py src/archguard/infrastructure/semantic_adjudication_acceptance.py tests/benchmark/test_semantic_adjudication_acceptance.py`.
- `.venv/bin/python -m ruff format --check scripts/prompt015e_acceptance.py scripts/prompt015e1_recover_handoff.py src/archguard/infrastructure/semantic_adjudication_acceptance.py tests/benchmark/test_semantic_adjudication_acceptance.py`.
- `.venv/bin/python -m mypy --strict src/archguard/infrastructure/semantic_adjudication_acceptance.py`.
- `.venv/bin/python scripts/prompt015_holdout.py --verify`: original public/private inventory PASS.
- `.venv/bin/python scripts/prompt015e1_recover_handoff.py --recover`: one-time recovery PASS.
- `.venv/bin/python scripts/prompt015e1_recover_handoff.py --verify-handoff`: original D full byte/inventory verification PASS.
- `.venv/bin/python scripts/prompt015e_acceptance.py --verify-prerequisites`: scoped C/D freezes and opaque A/B integrity PASS.

The historical C CLI is not replayed because it decodes individual A/B responses.
The historical D CLI also requires an empty return directory. The acceptance and
recovery commands above verify the approved freezes without those preparation-only
behaviors. No conflict set is rebuilt.

Executed with the required fail-closed result:

`.venv/bin/python scripts/prompt015e_acceptance.py --validate`

```text
PROMPT_015_E_BLOCKED: ADJUDICATOR_MEMBERSHIP_EVIDENCE_MISMATCH:
extra_cases=1, invalid_evidence_ids=1, invalid_line_ranges=0, missing_cases=1
```

`make check`: PASS, Ruff PASS, 402 files formatted, strict mypy PASS for 211 source
files, 1442 tests passed, 93% coverage. `git diff --check`: PASS. Intended untracked
files also passed independent trailing-whitespace and credential-pattern checks;
the recovery audit passed recursive public-data privacy checks. All private files
remain ignored. The regression suite covers this drift, exact-byte restoration, divergent
duplicates, scientific-byte preservation, formal schema/evidence validation,
append-only private acceptance, source-free receipts and isolated source generation.

## File classification and Git closure

Intended public-safe additions: acceptance implementation and CLI, recovery CLI,
synthetic regression tests, the source-free recovery audit, and this verification
report. The two previously untracked E implementation files were inspected and
retained with strict guards. No unrelated change was found.

Private: the restored source-bearing blank and all original handoff/mapping files;
the canonical human submission remains ignored by Git. The duplicate was removed
only after exact identity verification. No accepted snapshot or acceptance receipt
was created. No API credential or secret-bearing environment file was accessed.

No commit or push is permitted by the successful-acceptance condition while this
formal blocker remains. HEAD stays at
`0665c0533e28f63b02a3c4e88ccabe9c0790da90`; intended public additions remain
untracked. PROMPT 015.F and PROMPT 016 were not started.
