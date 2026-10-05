# ADR 0013: Directed projections, bounded cycle evidence and separate candidates

Status: accepted. Stage: PROMPT 006.

## Context

IAM смешивает file imports и declaration dependencies, сохраняя bounded resolver provenance.
Graph analysis требует явной granularity/direction, доказуемых traces и ограниченного output.
Structural anomalies без calibrated interpretation не доказывают architectural violation.

## Decision

NetworkX locked 3.7 ограничен graph package. Public models — typed serializable contracts. Dependency
direction A→B = A depends on B. Five explicit projections aggregate only resolved actual IAM edges,
без IAM mutation/semantic inference. True Java packages отделены от path-based target scopes.

SCC вместо exhaustive cycle enumeration; одна canonical shortest representative closed cycle на
cyclic SCC. Node/edge/trace/centrality/neighbourhood budgets typed and reproducible. ARCH003
в unified Finding/Evidence/Trace создаётся только по enabled explicit rule, severity from spec,
confidence absent. Без rule cycles — observations. Invalid classification подавляет conformance.

ARCH101–105 — отдельные uncalibrated candidates с explicit thresholds, disabled by default.
Directed coupling/centralities относятся к одной projection. Uniform PageRank power iteration
не требует SciPy; convergence failure — diagnostic/null, exact betweenness ограничен budget.
Canonical float export 12 decimal places; config не округляется; internal values полные. Relative
threshold equality tolerance 1e-12 предотвращает floating boundary drift без fabricated confidence.

Application orchestration строит IAM один раз, объединяет independent static/graph conformance;
static registry не импортирует NetworkX. Normalized config/spec hashes и stable UUIDv5 identity
позволяют сравнивать macOS/Linux canonical artifacts.

## Consequences

Dense SCC не порождает exponential output; representative proof не перечисляет все cycles.
Incomplete resolution/provenance/unsupported languages и skipped metrics ограничивают coverage.
Source-level dependency cycle не означает runtime execution cycle. Candidate thresholds требуют
будущей empirical calibration. Без LLM/Hybrid, inferred architecture, Security, persistence или UI.
