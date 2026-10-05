# Hybrid evidence, identity and missing data

Case UUIDv5 material contains project identity, case type, canonical primary IAM subject IDs,
origin, originating rule/candidate/Finding/requested-target identity and scope. It excludes free
text, timestamp, invocation/request ID and random run ID. Bundle ID derives from case ID. Decision
ID also includes policy/version and separate evidence/features fingerprints. Related subjects can
change with selected context without changing the anchored case identity. Separate rules/findings
retain separate cases, even for the same subject pair and different severities.

Typed channels:

| Channel | Contents |
| --- | --- |
| static (deterministic conformance) | Original Finding ID, ARCH001–005 code, proper STATIC/GRAPH detector/version, actual IAM pairs/edges/relations, locations, provenance counts/truncation, spec fingerprint, original severity, deterministic=true |
| graph | Candidate IDs/codes, mapped IAM subjects/pairs, projection, numeric observations and explicit thresholds, graph engine/config fingerprint; separate per-subject Ca/Ce/I, centrality/PageRank, SCC identity/members and cycle edges |
| ai | Candidate/rule/decision/subjects/reference IDs, context hash/strategy, provider and actual model, prompt/schema versions, nullable reported usage and availability, not_calibrated=true |
| discovery | Role/layer/module hypotheses, strengths, alternatives/conflicts and IDs, normative=false |
| context | Source-free normalized manifest: selected IDs, fragment references/path/lines/hash, metadata reference kinds, truncation and dropped counts; no source or metadata free payload |
| completeness | Nullable channel/source quality and explicit known counts, never substitute unknown with zero |

IAM completeness, parse error presence, unresolved/ambiguous references, graph completeness,
skipped algorithms, discovery completeness/unknown/ambiguous counts, local AI requests/completed
responses/partial/insufficient counts and context truncation are separate fields. Known zero
unresolved references is distinct from missing metadata. Missing AI is null request/completion
information; an unanswered requested target has known request count and zero completed responses.
An insufficient response counts as completed while `ai_insufficient` records missing semantic
support. Discovery unknown/ambiguity counts describe the upstream discovery coverage, not targets
reclassified by a normative rule. Graph observations are never architecture specifications.

Alignment uses stable IDs and records source refs, target case, method, agreement/reason and
`hybrid-concerns-v1` mapping version:

- EXACT_SUBJECT: identical actual IAM ID; names and filenames do not participate.
- EXACT_SUBJECT_PAIR: same directed actual pair. A→B does not match A→C or B→A.
- CONTAINMENT_OWNER: known IAM parent links, including method→class; traversal stops at file scope.
- DIRECT_GRAPH_RELATION: actual IAM dependency, or its explicitly mapped component graph relation;
  this is related context and carries no automatic concern agreement.
- EXPLICIT_CANDIDATE_LINK: the original anchor identity.

Identity alignment is separate from SUPPORTING / CONTRADICTING / NEUTRAL / MISSING /
NOT_APPLICABLE. Common subject, high PageRank or proximity alone is not semantic support.
The small mapping permits ARCH101/102→ARCH205, ARCH103→ARCH201/202/205 and
ARCH105→ARCH203/205, with exact subject/pair or verified containment. ARCH104 has no automatic
semantic mapping. SUPPORTED yields supporting concern evidence; NOT_SUPPORTED yields a visible
conflict; INSUFFICIENT_CONTEXT yields missing support. All remain uncalibrated review signals.

ARCH202 uses controller/presentation/structural context; ARCH203 domain/application versus
infrastructure dependency context; ARCH205 mixed role/layer/coupling context. Discovery hypotheses
are visible neutral contextual prerequisites, never normative proof. For static ARCH001/002/004/005
versus ARCH205, contextual agreement/conflict additionally requires an exact directed proof pair
and an explicitly referenced matching TARGET_CONSTRAINT. Other aligned AI remains neutral.
No ARCH201–205 rule is equated with ARCH003's normative cycle prohibition. A contradiction cannot
remove a deterministic proof or alter severity.

`hybrid-evidence-v1` features are ordered typed BOOLEAN / INTEGER / FLOAT / CATEGORICAL / SET /
MISSING observations, with availability and provenance refs. Scalar graph features describe a
single primary subject; multi-subject cases retain per-subject measurements without inventing an
average. Absent candidate evidence is missing, not `false` or a negative vote. Skipped betweenness/
PageRank and undefined isolated-node instability remain null. Sets preserve the actual observed
rules/roles/decisions. Ordinal discovery strengths remain categorical values, not probability.

Evidence fingerprint hashes the selected typed bundle; feature fingerprint hashes schema version
and ordered feature values/availability/provenance. Neither uses unrelated unselected upstream
evidence, random operational IDs or a training label. Overall IAM/snapshot fingerprints may change
when unrelated source changes; a case's selected bundle remains independent of such global result
metadata unless its relevant observations or source quality actually change.
