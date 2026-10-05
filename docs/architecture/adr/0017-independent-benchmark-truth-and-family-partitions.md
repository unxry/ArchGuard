# ADR 0017: Independent truth, scoped evaluation and family partitions

Status: accepted for PROMPT 010 foundation.

Architecture analyzers remain unaware of labels. Benchmark contracts, exact resolver, evaluator,
adapters, mutations and split planner consume typed analyzer results in a separate boundary.
Filesystem/safe YAML and CLI orchestration remain in infrastructure/CLI. No new analyzer or classifier
is introduced. Dependency tests prevent a reverse import into core/IAM/architecture/application.

Truth comes from source scenarios and a priori mutations, with separate provenance/review metadata.
Rule families have separate evaluation tasks; graph candidates are structural signals. Explicit negative
controls define the FPR universe; unknown/partial annotations and abstention are separate counters.
Exact IAM resolution, containment normalization and SCC/file-pair granularity avoid fuzzy matching.

Splits group mutation ancestry and language translations. A versioned cryptographic planner and frozen
split manifest must agree. Exact source duplicates crossing splits fail. Canonical fingerprints include
sources, truth, split, specs and mutation metadata, excluding operational paths/timestamps.

The seed is small and lacks semantic/graph holdouts. Hybrid default feature export contains only
proposed positive cases; no missing negative evidence is manufactured. These are disclosed constraints,
not sufficient calibration data. Expansion, external review and cohort coverage precede fitting.
PROMPT 011 requires review; no weights, training, threshold selection or final research claims here.
