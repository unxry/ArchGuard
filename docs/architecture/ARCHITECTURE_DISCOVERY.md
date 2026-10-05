# Architecture Discovery — PROMPT 007

Discovery описывает предполагаемую actual architecture по implementation evidence. Conformance
проверяет expected `architecture.yaml` против actual IAM. Discovered roles/layers/modules не являются
target scopes и не передаются автоматически в ArchitectureSpecification/ArchitectureClassification.
Discovery не создаёт ARCH001–005 Findings, не генерирует architecture.yaml, не объявляет нарушения.

## Pipeline и contracts

`DiscoverArchitecture`: BuildIAM once → GraphAnalyzer once (без spec) → StructuralRoleClassifier →
LayerInferenceEngine → ModuleDiscovery → matrices/topology → ArchitectureDiscoveryResult.
Graph Engine переиспользуется; discovery не импортирует NetworkX и не реализует второй graph engine.
Analyzer принимает same-IAM/same-config component GraphAnalysisResult; чужой IAM fingerprint,
target-spec/conformance context и incompatible projection отклоняются.

ArchitectureDiscoveryResult включает отдельный DiscoveredArchitecture: eligible components,
RoleHypothesis/LayerHypothesis, LayerGroup, ModuleCandidate, unclassified/ambiguous/module-unassigned
IDs, sparse layer/module dependency matrices и topology observations. GraphAnalysisResult сохранён
как groundable public context: IAM proofs, metrics, SCC/cycles, explicit GraphCandidate refs.
Циклы остаются observations; ARCH101–105 не превращаются в semantic role truth. Candidates могут
быть отключены, как в default graph config. Unified Finding не используется для discovery hypotheses.

Eligible components — file-linked CLASS/INTERFACE/ENUM/FUNCTION/MODULE nodes component projection.
Residual FILE endpoints остаются в graph, но не получают component-role hypotheses. Matrix field
excluded_noncomponent_edges отдельно считает исключённые зависимости; topology dependency_count
относится ко всему graph. TSX functions eligible, но UI/JSX presence не означает CONTROLLER.
Same names в Java/TS не создают cross-language dependencies или merged feature modules.

## Profile и CLI

Default profile `structural-baseline-v1`, engine 1.0.0, NOT CALIBRATED. Role patterns version
`suffix-tokens-v1`; registry data-driven. Typed config включает enabled_signal_types, framework_signals,
graph_refinement, minimum role/layer/module strengths, module roots/minimum size/package settings,
topology rank limit и nested existing GraphAnalysisConfig. Default minimum strengths MODERATE;
AMBIGUOUS не допустим как minimum. Discovery требует internal COMPONENT graph без self-edges.

```bash
.venv/bin/archguard architecture discover tests/fixtures/discovery/mixed
.venv/bin/archguard architecture discover tests/fixtures/discovery/mixed \
  --config examples/discovery/structural-baseline.json --namespace my-project \
  --json --output /tmp/discovered-architecture.json
```

Поддерживаются existing --source local/zip/git, --ref, --exclude, --no-gitignore, --strict и --namespace.
`--spec` не принимается; найденный architecture.yaml не используется как target. Config — UTF-8 JSON
≤128 KiB, unknown fields/invalid thresholds/paths rejected, errors sanitized. No source execution.
Exit 0 COMPLETE, 2 invalid input/processing, 3 INCOMPLETE; exit 1 conformance violations отсутствует.
UNKNOWN/ambiguous hypotheses допустимы и сами по себе не processing errors. Human output явно
говорит: “Discovery results are hypotheses, not architecture conformance findings.”

## Evidence, matrices и coverage

DiscoveryEvidence содержит stable ID, kind, actual subject node, observed name/path/metric,
matched signal, strength, optional role/layer hint, SourceLocation и bounded metadata refs.
Нет snippets или annotation/decorator arguments. Strength — interpretable precedence, не probability.
[Classification](STRUCTURAL_CLASSIFICATION.md) и [Modules](MODULE_DISCOVERY.md) фиксируют правила.

Layer matrix axes — discovered labels; module axes — candidate UUIDs плюс UNASSIGNED. Sparse cells
содержат unique projected directed edges и graph_edge_ids, а не callsite/provenance count. Diagonal
`internal: true` отделён от cross-group cells. UNKNOWN/AMBIGUOUS/UNASSIGNED diagonals описывают
группы неопределённых компонентов, не доказывают существование logical layer/module.
Topology reuse: cycles, highest Ca/Ce/betweenness и GraphCandidate IDs. Никаких violations из direction.

role_coverage = unambiguous non-UNKNOWN selected roles / eligible components;
layer_coverage = non-UNKNOWN/non-AMBIGUOUS selected labels / eligible components. Empty scope → null.
Это discovery assignment coverage, НЕ accuracy/precision/recall. Role strength counts включают все
hypotheses: UNKNOWN имеет placeholder WEAK; ambiguous roles отдельно от role_counts и UNKNOWN.
Layer UNKNOWN и AMBIGUOUS — разные buckets. Evidence counts deduplicate stable evidence IDs,
даже когда role/layer ссылаются на одно evidence.

## Reproducibility и limits

UUIDv5 identities используют actual project/node, versioned hypothesis kind, normalized profile hash;
modules также namespace/member IDs. Line shifts меняют locations/snapshot hash, сохраняя hypothesis
identity. Result содержит IAM schema/hash/snapshot fingerprint, whitelisted extractor/resolver/builder/
parser versions, graph/discovery versions, full config и fingerprint. Set-like config fields нормализуются.
Canonical JSON sorted, без timestamps/absolute roots/native trees/source content. Computed graph metrics,
coverage/cohesion/topology betweenness экспортируются с 12 decimal places; config не округляется.

Completeness наследуется от Graph/IAM processing; ambiguity module roots — descriptive diagnostic,
не code violation. Source/graph/provenance budgets и conservative resolution ограничивают охват.
Framework names — hints, actual framework binding/type semantics не проверяются. Profiles/strengths
не calibrated; нет labeled benchmark и universal accuracy claim. Shared ownership, arbitrary project
conventions, monorepo roots и unsupported constructs могут остаться unknown/unassigned.

Не реализованы LLM, embeddings, semantic review, graph-guided source context, Hybrid/scoring,
entry-point routing/security classification, architecture health score, target conversion, DB/API/UI.
Следующий этап только после review: PROMPT 008 Graph-Guided Context Construction & AI Architecture
Analysis Foundation. [Verification](DISCOVERY_VERIFICATION.md),
[ADR 0014](adr/0014-discovery-hypotheses-and-structural-precedence.md).
