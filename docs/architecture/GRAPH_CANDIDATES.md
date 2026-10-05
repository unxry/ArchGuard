# Graph candidates — ARCH101–105

`GraphCandidate` отдельный contract, не `Finding`. Default thresholds null: generation disabled.
Любой candidate имеет `confidence: null`, `not_calibrated: true`, observed metrics, explicit thresholds,
reason, graph subject, source locations и GRAPH_METRIC evidence. Нет severity/calibrated probability,
automatic violation или Hybrid decision. Explicit ARCH003 остаётся отдельным доказанным finding.

| ID | Predicate / required config |
| --- | --- |
| ARCH101 | total distinct neighbours ≥ excessive_coupling |
| ARCH102 | Ca ≥ hub_fan_in |
| ARCH103 | component member_count ≥ god_min_members AND total_neighbors ≥ god_min_coupling; optional method_count ≥ god_min_methods |
| ARCH104 | For A→B: I(B) − I(A) ≥ unstable_delta, оба I defined |
| ARCH105 | computed directed betweenness ≥ bottleneck_betweenness; optional total_neighbors ≥ bottleneck_min_neighbors |

ARCH103 поддерживает только component projection; иначе diagnostic и candidate отсутствует. Одна
большая size или coupling недостаточна. Methods относятся к actual METHOD descendants; size —
declaration members, не LOC. ARCH104 stable→less stable: например I(A)=0.2, I(B)=0.75, delta=0.4
даёт candidate. Более stable target или isolated/undefined I не дают signal. Skipped betweenness
не даёт ARCH105. Supporting metrics берутся из той же projection, а не смешанных granularities.

Integer thresholds positive, optional support counts nonnegative; floating thresholds finite в (0,1].
God Component требует одновременно size/coupling config. Floating `>=` допускает relative equality
`math.isclose(rel_tol=1e-12, abs_tol=0)` для platform rounding на границе; 0 не достигает positive
tiny threshold. Internal computation сохраняет precision, export округляет computed values до 12
decimal places. Это documented numeric tolerance, не empirical confidence calibration.

Candidate UUIDv5 включает project, rule ID, projection, node/edge subject и полный configuration
fingerprint; изменение thresholds/другого config меняет ID. Canonical rule/ID order deterministic.
Evidence содержит groundable incident graph edge/neighbor refs; graph edges сохраняют IAM proof.
Source contents не экспортируются. Result.statistics.candidate_count_by_rule отделён от findings.

[research-demo.json](../../examples/graph/research-demo.json) — только explicit research example:
coupling=4, Ca=3, God members/methods=3/3 и coupling=4, unstable delta=0.4,
betweenness=0.25 + neighbours=4. Hub fixture даёт ARCH101/102/103/104/105 = 2/1/1/1/2.
Этот набор не выбирается автоматически и не рекомендуется как production default. Threshold
calibration, false-positive evaluation и semantic validation остаются будущему эксперименту.
