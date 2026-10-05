# ADR 0015: bounded context and semantic candidates

Status: accepted for PROMPT 008 foundation, 2026-10-05.

Context: IAM/Graph/Discovery показывают факты и structural hypotheses; semantic interpretation
требует source evidence, но внешний LLM не является authority. Full-repository upload мешает
privacy, reproducibility и controlled context comparisons.

Decision: source-free deterministic manifest и отдельный transient source pack; reuse graph queries
и safe workspace reader; typed node/file/fragment/character/token/call budgets; canonical hashes
только selected material. TARGET constraints и DISCOVERED hypotheses разделены. Все input context
считаются untrusted DATA, system/task/schema versioned. Remote source requires explicit opt-in.
Provider port отделён от infrastructure; production unavailable состояние не заменяется fake.
Test-only scripted provider и transport stubs обеспечивают offline verification.

LLM assessment ссылается только на provided subject/evidence IDs и requested ARCH201–205.
ArchGuard валидирует schema/catalog/references/lengths; SUPPORTED требует evidence. Все decisions
сохраняются как uncalibrated semantic candidate records, не Findings. Logical IDs отделены от
invocation/request IDs и stochastic output. Usage/cost неизвестны, пока не измерены.

Consequences: snapshots context reproducible, failures isolated; default remote path denied.
Character counts не заменяют token counts, validation не доказывает semantic correctness или
injection resistance. Source windows могут терять relevant bodies; strict caps дают явную truncation.
Custom provider обязан соблюдать timeout; generic synchronous port не обеспечивает forced cancellation.
Hybrid/calibration/benchmarks остаются отдельными этапами после review.
