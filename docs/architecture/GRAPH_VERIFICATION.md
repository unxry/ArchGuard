# PROMPT 006 verification

Run: 2026-10-05. Local Darwin arm64, Python 3.13.14. Docker Linux aarch64, Python 3.13.16.
NetworkX 3.7 на обоих runtimes; dev types-networkx 3.6.1.20260911. PROMPT 005 baseline/HEAD
`1ccebf0` (предыдущий foundation `53956fc`). PROMPT 006 оставлен uncommitted working-tree diff.

## Quality gate

`uv sync --locked --extra dev`, затем `make check`:

- Ruff check passed; format check: 208 files already formatted.
- Strict mypy: 130 source files, no issues.
- `git diff --check` passed, включая новые files через intent-to-add; staged content отсутствует.
- Pytest: **626 passed, 0 failed, 0 skipped**, 7.26 s; overall branch-aware coverage **94%**.
- PROMPT 005 имел 559 passing tests; добавлено 67 graph tests. Три прежних tests обновлены для
  ARCH003 extension: unknown `future_cycle` по-прежнему rejected, static registry по-прежнему
  не исполняет circular rule. Core/domain import-direction guard дополнен NetworkX boundary check.
- Graph algorithms coverage 99%, analyzer 98%, builder 96%, candidates 100%, metrics 94%,
  conformance 97%. Provenance 76%, result contracts 82%, graph models 90%: часть invalid-input
  guard branches остаётся uncovered. Coverage не является semantic recall measurement.

Регрессии проверяют runtime import (NetworkX DiGraph не generic в runtime) и serialization config
с tolerance 1e-14: float export округляет computed values, сохраняя точный config и его hash.
Функциональные tests используют настоящий Java/TypeScript/TSX pipeline. Synthetic graphs нужны
только для точных metric/path assertions, dense SCC и bounded large-chain regressions.

## Manual CLI

Namespace `prompt006-verification`, component projection, six default relations, internal nodes,
self-edges removed. Запуск `.venv/bin/archguard graph analyze <fixture> --namespace
prompt006-verification --json` из `tests/fixtures/graph`; optional flags указаны в таблице.

| Fixture / flags | Nodes | Edges | SCC | Cyclic SCC | ARCH003 | Metric nodes | Exit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| acyclic/java | 3 | 2 | 3 | 0 | 0 | 3 | 0 |
| cyclic/java, no spec | 3 | 3 | 1 | 1 | 0 | 3 | 0 |
| cyclic/java, circular spec | 3 | 3 | 1 | 1 | 1 | 3 | 1 |
| cyclic/typescript, circular spec | 3 | 3 | 1 | 1 | 1 | 3 | 1 |
| mixed Java/TypeScript/TSX, circular spec | 7 | 6 | 3 | 2 | 2 | 7 | 1 |
| hub, research-demo config | 9 | 8 | 9 | 0 | 0 | 9 | 0 |

Все results COMPLETE. Все шесть metric groups computed, none skipped. Candidates default 0.
Circular spec: `--spec examples/architecture/circular-component.yaml`; representative Java trace:
`sample.a.A → sample.b.B → sample.c.C → sample.a.A`. GRAPH source, HIGH severity из spec,
confidence null; один finding на SCC, две cycles в mixed дают два findings.

Hub: `--config examples/graph/research-demo.json`. Counts ARCH101/102/103/104/105 **2/1/1/1/2**.
Explicit thresholds: total coupling 4, Ca 3, God members 3 AND methods 3 AND coupling 4,
instability delta 0.4, betweenness 0.25 + distinct-neighbour support 4. Это research values,
без calibration/default enablement. Stable: Ca=4, Ce=1, I=0.2, betweenness=0.285714285714;
Unstable: Ca=1, Ce=3, I=0.75, betweenness=0.267857142857. Stable→Unstable delta=0.55.

## Canonical A/B и macOS/Linux

Representative comparison repository: копия `mixed` плюс `hub` в подпапке `hub`. Config — demo
с единственным изменением `bottleneck_betweenness: 0.05` для normalized betweenness при N=16.
Spec circular-component, тот же namespace. Temporary fixture/config/results после проверки удалены.

На каждом runtime: 16 nodes, 14 edges, 12 SCC, 2 cyclic SCC, 2 ARCH003, 16 metric nodes,
ARCH101–105 counts 2/1/1/1/2. Все candidate types представлены, PageRank distribution nonuniform.
Два local subprocess exports сравнивались `cmp`: exit 0. Docker build выполнялся после успешного
local gate: `docker build -f docker/Dockerfile -t archguard:prompt006 .`.
Container `--rm --network none --read-only --tmpfs /tmp`, read-only fixture mount, existing nonroot
image user. Graph CLI exit 1 ожидаем из-за двух confirmed findings. Дополнительный runtime check
подтвердил отсутствие SciPy/Pandas.

`cmp macos-a.json linux.json`: **exit 0**, весь canonical JSON byte-identical, **245,784 bytes**.
SHA-256: `8c1399e8824b5d37213cf538fdfa601e4b0817371de156e8c39940c01f071826`.
Дополнительно equality assertions для graph nodes/edges, SCCs, representative cycles, findings,
candidates, metrics и reproducibility. Это одна representative cross-platform проверка,
а не гарантия равенства любых будущих runtimes/dependency versions.

## Resource и correctness regressions

Dense directed SCC: 35 nodes, 1,190 edges, один bounded representative closed cycle. Monkeypatch
`nx.simple_cycles` throws: analysis его не вызывает. Chain 350 nodes завершает SCC/coupling/PageRank;
betweenness budget 100 → skipped/null + diagnostic. Node/edge overflow → invalid empty result;
trace budget 3 не выдаёт partial cycle proof/ARCH003. PageRank iteration failure → null + diagnostic.
Это regression cases, не performance benchmark.

Проверены IN/OUT/BOTH k-hop budgets, deterministic directed shortest-path ties, disconnected/unknown
nodes, all five projections и ARCH003 traces, multiple components per file, external/self defaults,
relation filters (включая IMPORTS A→B + CALLS B→A), ambiguous/unclassified targets, mixed package
limitations, truncated/unproven provenance и incomplete/invalid IAM. Совместный ARCH002+ARCH003
check подтверждает single IAM build. Paths/metrics/proofs экспортируют graph и actual IAM refs.
Ordering/root copies дают одинаковый output; line changes сохраняют finding ID при изменении
locations/fingerprint. Raw-source marker/absolute root не попадают в canonical results.

## Limits и follow-up

Conservative IAM resolution не равен compiler analysis; missing dependencies не изобретаются.
Packages только Java, target scopes path-based; metrics exact/unweighted на selected projection.
Budgets ограничивают workload/output, не wall time. Candidate thresholds не calibrated.
Representative cycle не перечисляет все SCC cycles; dependency proof не runtime execution proof.

LLM/embeddings/Hybrid scoring, architecture discovery/inference, health score, Security, analysis
API, persistence и frontend не реализованы. После review — PROMPT 007 Architecture Discovery &
Structural Classification Foundation либо корректирующий PROMPT 006.1.
