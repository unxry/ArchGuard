# ADR 0018: Freeze OSS corpus before analysis

Status: accepted for PROMPT 012 foundation, 2026-10-05.

Decision: preregister metadata-only selection, retain the complete candidate log, pin Git commits,
verify SPDX/license hashes, and freeze an independent OSS corpus/receipt before source acquisition
and saved characterization. Keep post-fetch source/snapshot identities in immutable linked receipts.
Fetch raw blobs without executing source; cache outside Git. Keep post-freeze failures in reports.

Consequences: no performance-driven inclusion or silent replacement; new inclusion needs a new
corpus version. The eight-family seed improves realism but is not a representative/final benchmark.
Synthetic dataset and frozen V2 remain untouched; no V2 or AI evaluation occurs in this stage.
