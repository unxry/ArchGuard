# ADR 0014: Discovery hypotheses separate from target conformance

Status: accepted. Stage: PROMPT 007.

## Context

Actual IAM/Graph отражают syntax/resolved dependencies, но не expected architecture. Naming,
framework hints и directories могут помогать reconstruction без calibrated semantic certainty.
Смешение inferred labels с target scopes превращало бы hypotheses в неподтверждённые violations.

## Decision

Создать отдельные DiscoveredArchitecture/RoleHypothesis/LayerHypothesis/ModuleCandidate/Evidence
contracts. Не выдавать Finding, target ArchitectureSpecification или architecture.yaml. Strength —
explainable precedence: specific framework hint, independent name/path agreement, single structural
hint, secondary graph evidence. Equal role conflicts и disagreeing layer hints остаются ambiguous;
UNKNOWN валиден. Generic Component/Injectable не получают specific role без других signals.

BuildIAM/GraphAnalyzer по одному разу. Graph остаётся independent boundary; discovery reuses
public graph proofs/metrics/cycles и не импортирует NetworkX. Layer direction pass добавляет только
supporting observations, без feedback assignments. Modules — configurable actual Java namespace /
ES directory seeds с explicit size/strength policy и documented cohesion, без community detection.

Normalized profile/version fingerprints и UUIDv5 identities, canonical computed precision 12,
config precision preserved. Coverage измеряет unambiguous assignment, не accuracy/probability.

## Consequences

Discovery работает без target spec и не утверждает violations. Framework names/path conventions
ограничивают достоверность; ambiguous/unknown/unassigned output может быть правильным результатом.
Более глубокие roots требуют config; future semantic/calibration work не подменяется heuristics.
LLM/Hybrid/Security, context construction, persistence/API/frontend остаются отдельным этапам.
