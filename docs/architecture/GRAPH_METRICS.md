# Directed graph metrics

Все значения вычисляются на выбранной simple directed projection, без weight IAM edge и без
дублирования aggregated occurrences. `A → B` означает A depends on B.

| Metric | Definition |
| --- | --- |
| fan-in / in_degree_edges; fan-out / out_degree_edges | Количество projected incoming/outgoing edges |
| unique_in_neighbors / unique_out_neighbors | Distinct predecessor/successor nodes, кроме self |
| Ca / afferent_coupling | unique_in_neighbors: сколько других узлов зависит от этого |
| Ce / efferent_coupling | unique_out_neighbors: от скольких других узлов зависит этот |
| total_unique_neighbors | Union incoming/outgoing neighbours; bidirectional neighbour считается один раз |
| instability | Ce / (Ca + Ce); isolated node → null |
| in/out degree centrality | NetworkX standard directed degree centrality, denominator N−1 |
| betweenness | Exact unweighted normalized directed shortest-path betweenness, endpoints excluded |
| PageRank | Uniform teleport/dangling distribution, power iteration, alpha из config |
| scc_size / is_cyclic | SCC size / size ≥2; singleton self-loop не cycle |

Chain A→B→C: (Ca,Ce,I) = (0,1,1), (1,1,0.5), (1,0,0); directed betweenness B=0.5.
Cycle A→B→C→A: Ca=Ce=1, I=0.5, uniform PageRank=1/3. Isolated node имеет I=null.
Для N=1 NetworkX degree centralities равны 1; эти standard values не подменяются coupling.
При explicitly retained self-edge raw edge/degree counts включают self, Ca/Ce/total_neighbors исключают.

PageRank stable node/predecessor order и `math.fsum`; initial distribution 1/N. Convergence при
L1 difference < N × tolerance. Если max iterations исчерпан, весь PageRank column = null,
PAGERANK_CONVERGENCE diagnostic, без fabricated uniform fallback. Empty graph → empty metrics.
Это стандартная unweighted PageRank recurrence, без optional SciPy runtime dependency.
[NetworkX PageRank reference](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.link_analysis.pagerank_alg.pagerank.html).

Betweenness пропускается при N > betweenness_node_limit или disabled config: values null,
metric recorded as skipped. Degree/coupling/SCC продолжают вычисляться. Diagnostic budget skip
делает result incomplete. Все числа finite; no NaN/Infinity. Computed float export precision 12
decimal places применяется один раз, config precision не меняется. Metrics — structural signals,
не probabilities/confidence/quality scores. Thresholds проверяются на internal values, с relative
boundary tolerance 1e-12 для floating equality; integer comparisons exact.
