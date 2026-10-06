# PROMPT 013 — Human Annotation Execution & Adjudication Foundation

1. **Engineering status:** workflow implemented and verified. Research annotation is
   **WAITING_FOR_HUMAN_REVIEW**, not completed. No real human submissions were supplied.
2. **Git:** starting HEAD `df899b097bd07d240591c594baf1ff5ba77a831e`; PROMPT 012 committed as
   `ee84a6d0c3766ea12f4125d75bb91ddb68df7b85`
   (`feat: add real-world OSS benchmark and annotation foundation`) and safely pushed to
   `origin/main`, without force/history rewrites/global Git changes. PROMPT 013 is an uncommitted
   separate diff. Baseline make check passed before edits: 1080 tests.
3. **Files:** `benchmark/oss/review.py` adds source-free versioned review/history/report/freeze
   contracts; `infrastructure/oss_review.py` adds verified contexts, independent bundles and
   immutable atomic snapshots; `oss_review_cli.py` adds explicit commands; `oss_cli.py` routes them.
   New synthetic tests, three research guides, this verification, five source-free preparation
   artifacts and README workflow are included. Original PROMPT 012 corpus/sample/contracts remain
   unchanged. No dependencies or frontend changes.
4. **Frozen identities unchanged:**
   - corpus: `fe31539b44938fb1f87bcbc914d08af6cbdb2f7f25f23420fb92b09b0d6a9143`
   - corpus freeze: `61a87204f96a7c67981db2e6f3093ddc7708d3e05318f04b7a60b07b26c5e789`
   - sample: `3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9`
   - sample freeze: `6631ab6acfac3dd82a888e06192b90ecf48c11665e82901e324d22810393cbd0`
   All 8 repositories, commits, licenses, families, 40 subjects and ARCH201–205 assignments unchanged.
5. **Reviewer A bundle:**
   `/Users/bendasroman/Downloads/ArchGuard/experiments/oss/blinded/prompt013-final-v1/reviewer-a/`.
   Fingerprint `d467981fecb75603ff92bd9280a346a77b859a6881320cd2b2b0834deb3fc689`.
6. **Reviewer B bundle:**
   `/Users/bendasroman/Downloads/ArchGuard/experiments/oss/blinded/prompt013-final-v1/reviewer-b/`.
   Fingerprint `0cb837f7c3bab43922b01cf6bbef22d5582227130f938c61d186a4e13d0cc427`.
   Their content fingerprints match; only slot metadata differs. Earlier draft exports remain local
   and immutable; the final-v1 paths above are the handoff versions.
7. **Prefilled labels:** 0. Labels/uncertainty/attestations null, rationales empty, evidence selections
   empty. Packet evidence is separately available as technical context, not human-selected evidence.
8. **Fake reviewers:** 0. Reviewer IDs null; no completed human attestations, human rationales,
   adjudications or labels are fabricated. A/B directory names identify independent slots only.
9. **Questions:** neutral ARCH201–205 questions establish intended role, substantive controller
   business behavior, concrete infrastructure leakage, documented/manually justified placement
   and substantial distinct responsibilities. Validation/delegation, abstract interfaces and import
   counts alone do not establish positive labels. Insufficient context → human UNCERTAIN; an
   inapplicable question → human OUT_OF_SCOPE. No labels are assigned from these rules by code.
10. **Context:** request-extra-context verifies pinned repository/commit, relative path, full-file
    hash and inclusive line bounds. It appends a supplemental packet revision with the same case ID,
    predecessor fingerprint and actual question/guide identity. Review inputs name revision and
    fingerprint. Evidence may narrow registered ranges. Original packet stays frozen. All 40 final
    packets have existing source, correct hashes/ranges, visible declaration identifiers/questions
    and no silent truncation. Missing/empty/over-budget context is rejected, not turned into a label.
11. **Transitions:** UNREVIEWED → SINGLE_REVIEW (provisional, final NOT_ANNOTATED) → DOUBLE_REVIEW
    on agreement or ADJUDICATION_REQUIRED on conflict → ADJUDICATED by a distinct third human.
    Only resolved POSITIVE/NEGATIVE labels are binary-eligible. UNCERTAIN/OOS never count as NEG/TN.
12. **Amendments:** explicit supersedes_review_id links the active same-person/case event. History is
    retained and replay-validated; duplicate/stale/silent updates rejected. Changing a pair invalidates
    its old adjudication. Imports validate the entire batch before atomic new-directory publication;
    invalid batches/dry-runs do not modify the preceding snapshot. Outputs cannot be overwritten.
13. **Adjudication:** export requires actual conflicts, shows actual source and both human rationales
    only to the adjudicator. Third ID must differ from initial reviewers and address the current pair.
    Corrections link supersedes_adjudication_id; old events persist. No current adjudication export
    or completed annotation freeze exists. Freeze is blocked until every case is independently
    reviewed and every conflict resolved; terminal nonbinary cases remain ineligible for scoring.
14. **Agreement:** actual binary paired reviews only; disagreements included. Nonbinary pairs are
    counted separately. Overall/per-rule/per-language/per-repository counts and agreement provided.
    Kappa null for no binary pairs, degenerate marginals or heterogeneous rater pairs. Current rate
    and kappa are null; no fake agreement statistic is computed. No prediction is used as truth.
15. **Actual counts:** total 40; UNREVIEWED 40; SINGLE 0; DOUBLE 0; conflicts 0; adjudicated 0;
    P 0; N 0; UNCERTAIN 0; OOS 0; binary-eligible 0; human reviewers 0; review events 0.
    Canonical source-free state/report: `experiments/oss/annotation/reviews-unreviewed-v1.json`,
    `review-report-unreviewed-v1.json`. `review-pending-v1.json` is explicitly not a completed freeze.
16. **Readiness:** WAITING_FOR_HUMAN_REVIEW. Full Hybrid NOT_READY. The actual empty cohort's
    freeze command returned exit 2 and created no output directory.
17. **V2 evaluation:** NO; V2 remains AWAITING_FRESH_HOLDOUT. No resampling, tuning or evaluation.
18. **Live AI calls:** 0. No model/AI rationales or labels for any real OSS case.
19. **Tests:** 33 new offline synthetic review tests pass; complete suite **1113 passed, 0 failed,
    0 skipped**. Covered empty/nonbinary states, independent agreements, conflicts/third adjudication,
    amendments and stale resolutions, same-ID/duplicate rejection, evidence/rationale/attestation,
    sample/packet/history tampering, blinding, extra context, mixed-batch atomic rejection, dry-run,
    immutable output and full synthetic freeze. Real OSS tests inspect empty lineage only.
20. **Coverage:** overall branch-enabled coverage **94%** (11268 statements, 3452 branches).
    New domain **99%**, infrastructure **98%**, CLI **98%**, combined new modules **99%**.
    No target scores/labels were used to increase scientific coverage.
21. **Gates:** locked dev sync, Ruff, formatting (343 files), mypy (193 sources), make check and
    git diff --check green. Native gate log `/tmp/archguard-013-check.log`; targeted synthetic
    coverage `/tmp/archguard-013-target.log`. No new dependencies. Human packets/cache stay local.
22. **Determinism:** final bundle trees generated twice on macOS and twice in Linux Docker
    (`archguard:prompt0111`, mounted current source, `--network none`, verified materialized cache).
    All file hashes/bundle identities and empty status reports match across OS and repeat runs.
    No fetch/sampling/model outputs needed. Linux generation/status verified; that runtime image
    lacks pytest, so the full test gate above is native macOS. Canonical preparation proof:
    `experiments/oss/annotation/review-preparation-v1.json`. Identity contains no wall-clock time.
23. **Required next action:** give A and B their separate final-v1 directories; two actual distinct
    humans independently inspect all cases and submit their own completed forms. Keep responses
    private until both finish. This human action is the remaining research prerequisite.
24. **A completes:**
    `/Users/bendasroman/Downloads/ArchGuard/experiments/oss/blinded/prompt013-final-v1/reviewer-a/review-form.json`.
    Start with that directory's README.md/index.md; inspect all referenced pinned source/docs.
25. **B independently completes:**
    `/Users/bendasroman/Downloads/ArchGuard/experiments/oss/blinded/prompt013-final-v1/reviewer-b/review-form.json`.
    Never copy A's decisions or see A's completed responses before independent review.
26. **Import:** exact validate/dry-run/A-import/B-append/status commands are in
    [Human annotation execution](../research/HUMAN_ANNOTATION_EXECUTION.md). Every continuation passes
    --store; supplemental contexts also pass the updated --catalog. Export actual conflicts for a
    distinct human, then freeze explicitly only after sufficient independent decisions.
27. **Limitations:** identities/actual inspection rely on honest human attestation; technical checks
    establish provenance/shape, not semantic truth. Bounded source, unresolved external dependencies,
    library-heavy sample, PARTIAL repositories and absence of universal documented layers remain.
    Omitted nonregular files cannot become verified packet evidence. No real human reliability,
    binary OSS performance, completed freeze or Full Hybrid quality is claimed. Models need separate
    future receipts. Bundles and cache are local, ignored/outside Git.
28. **Next stage:** only after actual independent reviews, necessary human adjudication and explicit
    annotation freeze may the user authorize fresh V2 evaluation/real AI assessment work. PROMPT 014
    is not started automatically.
