# Hybrid Decision Engine

PROMPT 009 implements evidence composition and deterministic precedence. It does not implement
statistical fusion, calibrated rejection, fitted weights, a health score or a new Finding detector.

`HybridAnalyzer` accepts a prepared IAM and optional Static, Graph, Discovery and AI results, plus
the original specification when target conformance is supplied. IAM/spec/configuration/projection
fingerprints and actual directed proof references are checked. Candidate alignment currently uses
the actual component projection, preventing group metrics from being assigned to one arbitrary
class. Other actual projections are rejected explicitly; normative ARCH003 may still use any
supported explicit target projection. Graph conformance now records its
IAM fingerprint; a stale or unbound ARCH003 result cannot seed a confirmed case. The original
batch `ArchitectureEvidenceBundle` / `ArchitectureDecision` / `HybridDecisionEngine` contract is
preserved through `decide`. Typed case-level contracts are exported by the same contracts module.
Generic legacy evidence is preserved by that facade, without claiming new proof or semantic fusion.

`AnalyzeArchitectureHybrid.prepare` builds IAM once, Static once when a spec exists, actual Graph
once, and optional Discovery once. Actual Graph is independent of the target specification, so it
is valid input for Discovery and context selection. The existing graph conformance analyzer checks
the optional explicit ARCH003 rule separately: a layer/module/other rule projection may differ from
the actual component graph. This necessary target projection does not rebuild IAM or repeat the
Graph analysis/metrics pipeline. `execute_prepared` reuses all results. An explicitly injected
test-only offline provider runs the existing semantic analyzer once; Hybrid runs once. The CLI
never constructs a provider or reads provider credentials.

Each original deterministic Finding, structural candidate, semantic candidate or unanswered
requested semantic target anchors one case. Unanswered targets are explicit caller anchors,
not invented suspicious metrics. Deterministic, graph and semantic cases have stable order and
independent decisions. Shared evidence is referenced by its upstream identity. No speculative
composite cases or duplicate Findings are created. Node, target, containment and adjacency indexes
limit matching to relevant evidence. A 301-component test produces at least 302 anchored cases;
this verifies completion and ordering, not a performance advantage.

Default `deterministic-precedence` policy v1.0.0:

| Case evidence | State | Calibration | Severity / confidence |
| --- | --- | --- | --- |
| Valid STATIC rule proof or explicit GRAPH ARCH003 proof | CONFIRMED_DETERMINISTIC | DETERMINISTIC | Original rule severity / null |
| Structural anchor, with or without related AI | REVIEW_REQUIRED | UNCALIBRATED | null / null |
| Own semantic SUPPORTED or NOT_SUPPORTED | REVIEW_REQUIRED | UNCALIBRATED | null / null |
| Own INSUFFICIENT_CONTEXT or unanswered target | INSUFFICIENT_EVIDENCE | UNCALIBRATED | null / null |

Related signals cannot substitute for the unanswered target's own assessment. INSUFFICIENT_CONTEXT
is missing semantic evidence; NOT_SUPPORTED is an uncalibrated assessment. Neither proves the
global absence of a violation. Truncated supported assessments remain review candidates, with
an explicit quality flag. Known positive deterministic proof survives partial source input,
missing graph candidates and every AI response. Both analyzer and result validation enforce proof
retention, original Finding ID and severity, and actual feature/evidence fingerprints, even for
injected policies. A candidate cannot become CONFIRMED_DETERMINISTIC without proof.

`HybridDecisionPolicy` provides policy metadata and case/bundle/features → decision. The only
executable policy is deterministic precedence; therefore no registry or global mutable singleton
is introduced. `CalibratedPolicyArtifact` defines future weighted/logistic interchange metadata:
method, policy/schema versions, dataset and calibration run references, repository split and feature
schema fingerprints, intercept, coefficients and decision threshold. Missing calibration metadata
or incompatible feature schema is rejected. No artifact is shipped, no fitting/scoring/loading
execution is provided, and no learned/default weights are present. Future execution must require
an explicit validated external artifact and a frozen encoding for categorical/set/missing features.

CLI:

```bash
archguard hybrid analyze REPOSITORY --without-ai --spec architecture.yaml --json --output hybrid.json
archguard hybrid analyze REPOSITORY --config hybrid.json --ai-result ai-result.json --json
```

Standard local/ZIP/public HTTPS Git intake, namespace, exclusions, .gitignore and strict parser
options are reused. `--without-ai` and `--ai-result` are mutually exclusive; omitting both also
skips AI. Config is bounded to 128 KiB; saved source-free AI input to 8 MiB. Duplicate properties,
raw source/prompt/provider payload keys and invalid models are rejected with sanitized errors.
Saved manifests are reconstructed locally using the current IAM, graph, discovery, specification,
selection budgets and source windows. Context fingerprint mismatch fails before composition;
no provider call occurs. For direct prepared-model API calls the caller supplies upstream results;
Hybrid validates identities/proofs/references, but cannot re-read source without a workspace.

JSON embeds ordered features, provenance, availability, schema definition, feature fingerprint
and separate evidence fingerprint, without invented labels. No separate training export CLI is
needed. `max_candidate_cases` explicitly truncates only candidate/requested cases and reports
omitted counts/diagnostic; deterministic cases and all confirmed Finding references are uncapped.
Default cap is 1000. Intake, parser, graph and context budgets continue to apply independently.

Canonical JSON excludes source fragments, prose assessments, raw prompts/vendor payloads,
credentials, absolute paths, timestamps and invocation/request IDs. Floats are canonicalized to
12 decimal places, as in graph reproducibility. Reproducibility records IAM/snapshot/spec/graph/
discovery fingerprints, engine versions, AI provider/actual model/context strategy/hash/prompt/
schema/usage availability, feature schema and policy metadata. Fixed AI inputs yield deterministic
Hybrid output. Repeated live LLM responses from the same repository are not claimed deterministic.
