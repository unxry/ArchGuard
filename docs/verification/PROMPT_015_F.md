# PROMPT 015.F — final human ground truth

Status: FINAL_HUMAN_GROUND_TRUTH_FROZEN. POSITIVE_CLASS_PRESENT and PRIMARY_SEMANTIC_EFFECTIVENESS_REFERENCE_READY are YES.

Metadata recovery was explicitly authorized. The sole root `.DS_Store` was absent from the sealed manifest; all eight raw hashes matched before removal. Only that metadata file was removed. No scientific/human bytes changed; strict post-recovery E.2 inventory and A/B/C/D/adjudicator verification passed. Recovery audit fingerprint: `7452145c5609b454d75c0ae78aab4f27bcd4708f761cf5bf6ff5061bb4318ddb`.

All approved A/B raw SHA, canonical submission and acceptance receipt fingerprints match. C analysis/conflicts/safe index and accepted adjudicator SHA/canonical/receipt match. Original P015 corpus, source, IAM and graph inventory passed opaque verification; construction provenance was never decoded.

Merge: EXACT_A_B_AGREEMENT_ELSE_ACCEPTED_THIRD_HUMAN_V1. Join uses explicit frozen IDs, never array position. Exactly 100 unique scientific IDs: 96 agreement cases and four adjudicated conflicts, each used once. No adjudicator response maps to an agreement case. Frozen cohort: 50 Java, 50 TypeScript; 20 per ARCH201–ARCH205; IAM VALID 100, PARTIAL/INVALID 0.

| Stratum | N | POSITIVE | NEGATIVE | UNCERTAIN | OUT_OF_SCOPE | Eligible | Excluded |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| TOTAL | 100 | 50 | 46 | 3 | 1 | 96 | 4 |
| ARCH201 | 20 | 10 | 10 | 0 | 0 | 20 | 0 |
| ARCH202 | 20 | 10 | 10 | 0 | 0 | 20 | 0 |
| ARCH203 | 20 | 10 | 9 | 0 | 1 | 19 | 1 |
| ARCH204 | 20 | 10 | 10 | 0 | 0 | 20 | 0 |
| ARCH205 | 20 | 10 | 7 | 3 | 0 | 17 | 3 |
| JAVA | 50 | 25 | 22 | 2 | 1 | 47 | 3 |
| TYPESCRIPT | 50 | 25 | 24 | 1 | 0 | 49 | 1 |

P015 is a CONTROLLED PROSPECTIVE SEMANTIC HOLDOUT created using mutation-based matched-pair construction. Its final human category distribution is NOT natural real-world prevalence. P013/P014 remains a separate OSS/natural cohort; prevalence statistics must not be merged.

Primary binary reference: POSITIVE and NEGATIVE are eligible (50 + 46 = 96); UNCERTAIN and OUT_OF_SCOPE are excluded (3 + 1 = 4). These are reference statistics; no detector effectiveness was calculated.

| Artifact | Fingerprint / SHA-256 |
| --- | --- |
| Raw private truth SHA | `db4872615247e856d416e76653d0396a3aee1c430b5fdd8de33bc5e39afabfd1` |
| Canonical truth | `1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276` |
| Lineage | `5060d5144a84da8dc03d2175b6d661259769afc050051aed30188deb147b75b3` |
| Private freeze receipt | `3e8596e27f968df9ed6ca3a74d9592d53409da1f1bfa624852077c63ed0da62d` |
| Public verification | `8d2af0804bbc208662818f58618f246c200976f74b8a98ebbe47e57938cfa46d` |

Private final truth contains only scientific_case_id, target_rule, language, final_category and resolution_provenance per case. It is Git-ignored, append-only, 0700 directory / 0600 files. No identity, rationale, note, source or human evidence selections were copied. Public receipt contains aggregates and lineage hashes only.

Commands executed at the Stage A checkpoint:

- `.venv/bin/python -m pytest -q tests/benchmark/test_semantic_final_truth.py`: 33 passed.
- `.venv/bin/ruff check --fix tests/benchmark/test_semantic_final_truth.py src/archguard/infrastructure/semantic_final_truth.py scripts/prompt015f_ground_truth.py`: PASS.
- `.venv/bin/ruff format tests/benchmark/test_semantic_final_truth.py src/archguard/infrastructure/semantic_final_truth.py scripts/prompt015f_ground_truth.py`: PASS.
- `.venv/bin/python -m mypy --strict src/archguard/infrastructure/semantic_final_truth.py`: PASS.
- `.venv/bin/python scripts/prompt015f_ground_truth.py --freeze`: one-time final truth freeze PASS.
- `.venv/bin/python scripts/prompt015f_ground_truth.py --verify`: deterministic recomputation and exact private/public freeze verification PASS.

A separate P016 offline commit follows this checkpoint. No live AI/provider/connectivity call, credential read, V2/Hybrid/Security run, mutation-success analysis or P017 execution occurred. API spend: $0.
