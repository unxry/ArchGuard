# Structural feature leakage audit — PROMPT 011.1

The PROMPT 011 held-out score is retained as an engineering diagnostic and is not used as thesis evidence after the post-hoc feature-leakage review.

V1 predictor `selection.candidate_present` is the GraphCandidateEngine's decision, not raw
measurement. Labels in this seed can be generated from related metric thresholds, allowing
circular rule replay. The v1 F1=1 cannot establish held-out scientific validity or Hybrid added value.
V1 is DIAGNOSTIC, LEAKAGE_SENSITIVE, SUPERSEDED_FOR_RESEARCH. Its artifact and historical result
bytes remain unchanged; the separate research-status.json carries this review finding.

[Machine-readable audit](../../experiments/calibration/feature-leakage-audit.json).
Input inclusion refers to the explicit specification; missing-output inclusion refers to the frozen
TRAIN preprocessor. Constants may be dropped. All retained v2 fields can be calculated without truth,
annotation, candidate classification or rule labels. RAW counts are topology measurements; DERIVED
measurements apply graph algorithms/arithmetic to that topology, never configured detector thresholds.
Graph cyclicity is SCC membership, not an ARCH violation boolean. Quality is unresolved IAM references,
not annotation confidence/completeness. Missing means unavailable measurement, not absent candidate.

| Feature | Classification | V1 | V2 | Reason | Leakage risk |
| --- | --- | --- | --- | --- | --- |
| graph.Ca | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.Ce | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.coupling | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.I | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.scc_size | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.betweenness | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.pagerank | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.cyclic | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.source.Ca | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.source.Ce | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.source.I | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.target.Ca | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.target.Ce | RAW_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| graph.target.I | DERIVED_MEASUREMENT | True | True | pre-classification graph measurement; no configured threshold | no decision leakage; threshold-derived task remains limited |
| selection.candidate_present | DETECTOR_DECISION | True | False | existing candidate engine output; baseline metadata only | HIGH: can replay threshold-derived target |
| quality.unresolved | QUALITY | True | True | unresolved IAM references; analysis quality only | measurement availability/quality may proxy fixture scope |
| graph.Ca.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.Ce.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.coupling.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.I.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.scc_size.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.betweenness.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.pagerank.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.cyclic.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.source.Ca.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.source.Ce.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.source.I.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.target.Ca.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.target.Ce.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| graph.target.I.missing | MISSINGNESS | True | True | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| selection.candidate_present.missing | MISSINGNESS | True | False | candidate availability; removed with detector predictor | inherits detector dependence; excluded v2 |
| quality.unresolved.missing | MISSINGNESS | False | False | 1 iff raw measurement absent; TRAIN decides retention | scope can proxy task structure; no labels used |
| static.confirmed | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| static.rules | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| static.relations | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| graph.candidate_rules | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| graph.ARCH101 | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| graph.ARCH102 | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| discovery.roles | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| discovery.layers | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| discovery.strengths | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| discovery.ambiguous | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.ARCH201.decisions | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.ARCH202.decisions | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.ARCH203.decisions | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.ARCH204.decisions | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.ARCH205.decisions | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| context.strategies | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| context.truncated | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.iam_complete | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.parse_errors | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.ambiguous | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.graph_complete | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.discovery_complete | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.metrics_skipped | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.ai_requested | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.ai_completed | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.ai_insufficient | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| quality.ai_partial | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| selection.static_generated | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| selection.graph_generated | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| ai.target_selected | DETECTOR_DECISION | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| channel.static_available | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| channel.graph_available | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| channel.discovery_available | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| channel.ai_available | QUALITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| task.family | IDENTITY | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| graph.source.coupling | RAW_MEASUREMENT | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| graph.target.coupling | RAW_MEASUREMENT | False | False | outside fixed numeric whitelist; no automatic feature inclusion | never consumed as predictor |
| configured thresholds | DETECTOR_DECISION | False | False | prohibited predictor metadata | target/identity shortcut; excluded |
| ground-truth label/annotation/rationale | TARGET_DERIVED | False | False | prohibited predictor metadata | target/identity shortcut; excluded |
| split/repository/family/case/node ID/name/path/rule ID | IDENTITY | False | False | prohibited predictor metadata | target/identity shortcut; excluded |
| Finding label/severity/confidence | DETECTOR_DECISION | False | False | prohibited predictor metadata | target/identity shortcut; excluded |

## Raw IAM/static measurement feasibility

Existing ArchitectureModel.nodes/edges/symbols and EdgeKind expose IMPORTS, CALLS, CREATES, USES,
INHERITS and IMPLEMENTS. Endpoint relation counts/diversity and inheritance counts could be computed
without findings or annotations. Symbol kinds expose METHOD, CONSTRUCTOR, FIELD and PROPERTY;
file/package/module links expose partial containment/provenance. There is no uniform class-member
ownership field or CONTAINS edge: class member counts require a separately frozen attribution policy
and parser coverage validation. Names/IDs would be used only to resolve a subject, never as predictors.
Provenance IDs themselves must remain metadata; relation availability could supply analysis quality.

V2 deliberately uses graph measurements already present in the source-free frozen cohort. Adding IAM
predictors requires a new extraction/schema and independently specified single/pair subject scope,
coverage and missingness rules. This correction does not invent an analyzer or change the cohort.
Static precedence is execution behavior, not predictive Static evidence. The accurate experiment term
is GRAPH STRUCTURAL META-CLASSIFIER. Even after removing decisions, raw threshold-derived truth may
just ask ML to approximate known formulas; a Direct Graph Rule Baseline is therefore mandatory.
