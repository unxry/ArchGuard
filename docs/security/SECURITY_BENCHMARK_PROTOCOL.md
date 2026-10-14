# Prospective Security benchmark v1 — P030

This post-thesis controlled benchmark asks how ArchGuard detects SEC001–SEC010 within the declared Java/TypeScript scope, controls false positives and preserves applicability/coverage. P030 constructs evidence and protocols only. No detector is run on the cohort, no authoritative human label exists, and no Security effectiveness is estimated. P025–P029 remain immutable.

## Prospective design

Exactly 300 inert cases, one case per mini-project: DEV 100 and FINAL 200. Each rule has DEV 10 (5 Java/5 TypeScript) and FINAL 20 (10/10). Intent is exactly half mutation and half control per rule/split, 150/150 overall. DEV's odd language counts alternate the 3/2 allocation between Java and TypeScript; FINAL has 5/5 per language/rule.

`security-controlled-generator-v1` enumerates fixed rule/language/variant dimensions, uses SHA256 for opaque design identities and sorts by opaque case ID. It uses no PRNG, environment values, external snippets, detector output, ranking or prediction-dependent filtering. All syntactically valid constructed cases are retained. Each template specifies target rule, language, framework, flow shape, capability for either construction intent, parameterization dimensions and generator path in the private inventory. The chosen intent is a design attempt, never truth or an expected detector decision.

Fifteen flow families per language/rule cover direct local use, return helper, local record, conditional source and an opaque wrapper in DEV, with constructor field, two-return helpers, separate source module, alias, constant-index container, caller-to-sink helper, branch merge, nested field, callback and parameter-copy boundaries in FINAL. These deliberately include unknown/custom wrapper evidence and unsupported flow constructs; they do not promise successful V2 modeling. Rule-specific APIs distinguish binding, shell/argv, normalization/confinement, object streams/JSON, allowlist/pseudo-allowlist, HTML/text/sanitizer, crypto purpose/checksum, randomness purpose and dynamic evaluation/reflection.

TypeScript SEC005 has 15 private `UNSUPPORTED_BY_CURRENT_DETECTOR` expectations. This is a detector limitation and does not force a human OOS label. Canonical P027 rule definitions govern review. A reviewer independently chooses POSITIVE, NEGATIVE, UNCERTAIN or OUT_OF_SCOPE from supplied source evidence.

## Separation and construction validity

DEV/FINAL have zero project, exact source-file, source-bundle, case and template fingerprint overlap. Template fingerprints are computed before case identifiers are inserted. Normalized source overlap removes long generated identifiers and string literals; it must also be zero. A separate token 5-gram Jaccard diagnostic reports cross-split similarity within language/rule. Shared API concepts and small boilerplate are intentional and disclosed; lexical resemblance does not establish independence. No case is selected or discarded using detector correctness.

Every case passes normal discovery → ParseRepository (strict syntax) → BuildIAM → normal IAM structural validation with source-location mapping. No benchmark parser bypass, compiler validation claim, dependency installation or source execution occurs. Declared framework APIs and supplied ambient/custom wrappers bound what human review can establish. No SQL, shell, network, deserialization, filesystem sink or dynamic code fixture is executed. SEC001 credential-shaped literals are deterministically fabricated; no secret-bearing environment file is read.

## Human review and custody

Private evidence is under `experiments/security/security-benchmark-v1/private/`, Git ignored. The coordinator owns the inventory, construction ledger and split manifests. Each reviewer receives ONLY their `packets/A/` or `packets/B/` directory plus SECURITY_REVIEWER_GUIDE.md and the public schemas. Packets contain the same source evidence, frozen rule definition, declared framework, review scope, four label choices, evidence fingerprint and distinct response destination. They contain no split, project/template identity, intent, support expectation, prediction, confidence, truth or other reviewer response. No response files or adjudications are created by P030.

Do not hand reviewers the generator, coordinator directory, opposite reviewer packet set or prediction roots. Reviewers work independently without discussion or exchanging labels/rationales until both initial submissions lock. Use only real human responses. LLM/Astra/OpenAI must not fill or adjudicate responses. Slots A/B are sufficient; no names or other PII are required.

A submission must cover the exact frozen case set once, match its slot and mark every row completed with one allowed label. Rationale/evidence note are optional. Equal locked labels become final truth, preserving UNCERTAIN/OOS. Conflicts require a separate human coordinator/adjudicator who receives case evidence and both locked rationales, preserving A, B, conflict and adjudicated label. Intent or detector output is never a tie-break. Future agreement reports raw agreement, Cohen's kappa when defined, conflicts, reviewer label distributions and adjudication counts, with an artificial-class-construction caveat. None is computed for the benchmark in P030.

## Frozen metrics

Only POSITIVE/NEGATIVE truth is binary eligible. UNCERTAIN and OUT_OF_SCOPE are reported separately, never coerced negative. Actual P027 finding enums are CONFIRMED_PATTERN, SUPPORTED, POTENTIAL, INSUFFICIENT_EVIDENCE and NOT_APPLICABLE. The first two map to definitive positive; POTENTIAL is a candidate nondefinitive. No finding becomes definitive negative only for successful COMPLETE, applicable execution. FAILED/UNSUPPORTED are nondefinitive; PARTIAL with no definitive finding remains nondefinitive. A supported finding can remain a definitive positive despite partial traversal. V2's implementation capability `PARTIAL_V2` alone is not an execution outcome or negative evidence. The actual P029 receipt status `SUPPORTED_PARTIAL_V2_SCOPE` maps to PARTIAL, `CONTRACT_ONLY` with no evaluation maps to UNSUPPORTED, and FAILED takes precedence. Its `applicable_rules` is derived from findings, so an absent rule there cannot establish semantic nonapplicability. P029 currently emits no COMPLETE no-finding applicability certificate: no-finding V2 rows stay PARTIAL. A later version could emit COMPLETE only under a prospectively frozen receipt contract, before FINAL predictions/truth opening.

Strict TP/FP/TN/FN use definitive outcomes and binary truth. Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1=2TP/(2TP+FP+FN), Specificity=TN/(TN+FP), FPR=FP/(TN+FP), FNR=FN/(TP+FN). Nondefinitive outcomes are not invented TN/FN. Thus strict recall is conditional on definitive decisions and must appear beside effective positive recovery TP/N_human_positive, effective negative correctness TN/N_human_negative and nondefinitive counts.

Primary unified reporting retains **all cases**, including unsupported TypeScript SEC005, with (TP+TN)/N_all and definitive/analysis/applicability/truth coverage. Binary effective correctness=(TP+TN)/N_binary penalizes abstentions. Report each nondefinitive category separately. Attempted analysis coverage includes PARTIAL and excludes FAILED/UNSUPPORTED; applicability coverage is a descriptive attempted non-NOT_APPLICABLE fraction, not a proof of scope. A supported-scope supplement may exclude unsupported language-rule cases; it cannot replace the unified view. A predeclared candidate-inclusive supplement maps POTENTIAL to positive and recomputes the same formulas; it cannot replace strict primary results. Every zero denominator is null.

Report rule, language and rule-language strata within each split; micro pool cases, macro average only defined strata and report included stratum count. Do not pool DEV into FINAL effectiveness claims. No post-truth mapping/denominator changes are allowed.

## Future FINAL chronology

1. Collect human responses in restricted coordinator custody during P031.
2. DEV may inform a new detector version; keep P029 immutable and never tune on FINAL truth/intent.
3. Freeze the future detector, configuration, protocol and implementation before FINAL prediction.
4. Mount only `prediction/FINAL/sources/` plus its sanitized roster for the worker. No coordinator, responses, truth, intent or DEV roots.
5. Freeze complete FINAL predictions before opening FINAL truth.
6. Require explicit later `SECURITY_FINAL_POST_PREDICTION_TRUTH_JOIN` authorization and prediction-freeze guard.
7. Evaluate under this frozen mapping, preserving all coverage outcomes.

`PredictionInputs` enforces an application path allowlist, rejects metadata fields, traversal and symlinks. It is not an OS sandbox. The future executor must separately enforce restricted identity/container mounts; P030 neither provisions a live executor nor authorizes prediction/truth joining. Frozen P030 private material is append-only; later human responses/truth belong in a new stage root.

## Reproduction and limitations

Run `.venv/bin/python scripts/prompt030_security_benchmark.py validate` for source generation, normal intake, historical freeze and leakage/dependency validation. `freeze --quality ... --implementation ...` accepts only matching-source PASS quality and committed implementation, creates a new private/public freeze once and rejects overwrites. `verify` rechecks inventories, private reproduction, schemas/packets, science and detector freezes without evaluating cases. All public source, tests, docs, schemas and aggregate receipts are committed; ignored private contents are reproduced from the committed generator and bound by public opaque fingerprints.

This is a finite controlled synthetic benchmark, not natural vulnerability prevalence, application risk distribution, exploitability probability, all-framework/all-language coverage or universal SAST accuracy. N=300 with DEV=100/FINAL=200, ten rules and small strata limits generalization. Construction artifacts, shared semantic patterns, selected P029 framework semantics and unsupported TS SEC005 are limitations. Human truth and real OSS effectiveness remain unavailable. P031 requires independent real humans; it is not started here. Provider, connectivity and credential reads remain zero; no UI is built.
