"""Prospective P019 recipes and independent predicates, without detector imports."""

import hashlib
from collections import Counter, deque
from typing import Any

from archguard.benchmark.oss.models import digest

DATASET = "component-baseline-holdout-v1"
STATIC_RULES = ("ARCH001", "ARCH002", "ARCH004", "ARCH005")
TRAIN_FAMILIES = {
    "graph-fan-in": ("ARCH101", "ARCH102"),
    "graph-fan-out": ("ARCH101", "ARCH103"),
    "graph-stable-core": ("ARCH104",),
    "graph-topology-v1": ("ARCH101", "ARCH102", "ARCH103", "ARCH104", "ARCH105"),
}
V2 = "2ae6c0293aa1f1bbf356e666c5fffc77afb346366ffd4a02b3c33418cc402185"


def identity(seed: str, *parts: object) -> str:
    return hashlib.sha256((seed + ":" + ":".join(map(str, parts))).encode()).hexdigest()[:32]


def recipes(families: tuple[str, ...]) -> list[dict[str, Any]]:
    rows = []
    for track, names in (("A", tuple(f"ARCH00{i}" for i in range(1, 6))), ("B", families)):
        for family in names:
            for language in ("JAVA", "TYPESCRIPT"):
                for index in range(5):
                    rules = (family,) if track == "A" else TRAIN_FAMILIES[family]
                    rule = rules[index % len(rules)]
                    for positive in (False, True):
                        rows.append(
                            dict(
                                track=track,
                                family=family,
                                language=language,
                                index=index,
                                rule=rule,
                                positive=positive,
                            )
                        )
    return rows


def topology(rule: str, index: int, positive: bool) -> dict[str, Any]:
    """Explicit matched interventions; numeric predicates are benchmark definitions."""
    n = 12 + index
    edges: list[tuple[int, int]] = [(i, i + 1) for i in range(8, n - 1)] + [(7, 8)]
    roles = ["service"] * n
    methods = [1] * n
    target = [0]
    if rule in {"ARCH001", "ARCH002", "ARCH005"}:
        roles[0], roles[1], roles[2] = (
            ("domain", "store", "service")
            if rule == "ARCH001"
            else ("ui", "store", "service")
            if rule == "ARCH002"
            else ("alpha", "beta", "shared")
        )
        edges.append((0, 1 if positive else 2))
    elif rule == "ARCH004":
        roles[0], roles[1] = "domain", "store"
        edges.append((1, 0) if positive else (0, 1))
    elif rule == "ARCH003":
        edges.extend([(0, 1), (1, 2), (2, 0 if positive else 3)])
    elif rule in {"ARCH101", "ARCH103"}:
        edges.extend((0, i) for i in range(1, 7 if positive else 2))
        if rule == "ARCH103":
            methods[0] = 6 if positive else 1
    elif rule == "ARCH102":
        edges.extend((i, 0) for i in range(1, 7 if positive else 2))
    elif rule == "ARCH104":
        target = [0, 1]
        edges.append((0, 1))
        edges.extend((i, 0 if positive else 1) for i in range(2, 5))
        edges.extend((1 if positive else 0, i) for i in range(5, 8))
    elif rule == "ARCH105":
        edges.extend([(i, 0) for i in range(1, 4)] + [(0, i) for i in range(4, 7)])
        if not positive:
            edges.extend((i, j) for i in range(1, 4) for j in range(4, 7))
    else:
        raise ValueError("unregistered oracle")
    return dict(
        nodes=list(range(n)), edges=sorted(set(edges)), roles=roles, methods=methods, target=target
    )


def adjacency(facts: dict[str, Any]) -> dict[int, set[int]]:
    result: dict[int, set[int]] = {i: set() for i in facts["nodes"]}
    for a, b in facts["edges"]:
        if a not in result or b not in result or a == b:
            raise ValueError("invalid normalized adjacency")
        result[a].add(b)
    return result


def reachable(adj: dict[int, set[int]], start: int, end: int, removed: int | None = None) -> bool:
    queue, seen = deque([start]), {start}
    while queue:
        node = queue.popleft()
        if node == removed:
            continue
        if node == end:
            return True
        for other in adj[node] - seen - {removed}:
            seen.add(other)
            queue.append(other)
    return False


def oracle(rule: str, facts: dict[str, Any], specification: dict[str, Any]) -> bool:
    """No production classifier, candidate threshold, SCC or model call supplies truth."""
    adj = adjacency(facts)
    roles, edges = facts["roles"], facts["edges"]
    constraint = specification["oracle_constraint"]
    if rule in {"ARCH001", "ARCH004"}:
        return any((roles[a], roles[b]) == tuple(constraint["forbidden"]) for a, b in edges)
    if rule in {"ARCH002", "ARCH005"}:
        return any(
            roles[a] == constraint["source"] and roles[b] not in constraint["allow"]
            for a, b in edges
        )
    if rule == "ARCH003":
        indegree = Counter(b for _, b in edges)
        queue = deque(i for i in adj if indegree[i] == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for other in adj[node]:
                indegree[other] -= 1
                if indegree[other] == 0:
                    queue.append(other)
        return visited != len(adj)
    target = facts["target"][0]
    incoming = {a for a, b in edges if b == target}
    if rule == "ARCH101":
        return len(adj[target]) >= 6
    if rule == "ARCH102":
        return len(incoming) >= 6
    if rule == "ARCH103":
        return facts["methods"][target] >= 6 and len(adj[target]) >= 6
    if rule == "ARCH104":

        def instability(node: int) -> float:
            ca = sum(node in neighbors for neighbors in adj.values())
            ce = len(adj[node])
            return ce / (ca + ce) if ca + ce else 0.0

        other = facts["target"][1]
        return other in adj[target] and instability(target) < instability(other)
    if rule == "ARCH105":
        return all(
            reachable(adj, a, b) and not reachable(adj, a, b, target)
            for a in range(1, 4)
            for b in range(4, 7)
        )
    raise ValueError("unregistered oracle")


def specification(rule: str) -> dict[str, Any]:
    roles = (
        ("alpha", "beta", "shared") if rule == "ARCH005" else ("ui", "domain", "store", "service")
    )
    scope = "modules" if rule == "ARCH005" else "layers"
    architecture = {scope: [{"name": r, "include": [f"**/{r}/**"]} for r in roles]}
    rules: list[dict[str, Any]] = []
    constraint: dict[str, Any] = {}
    if rule == "ARCH001":
        rules = [
            dict(
                id=rule,
                type="forbidden_dependency",
                **{"from": {"layer": "domain"}, "to": {"layer": "store"}},
            )
        ]
        constraint = {"forbidden": ["domain", "store"]}
    elif rule == "ARCH002":
        rules = [
            dict(
                id=rule,
                type="layer_dependency",
                **{"from": "ui", "allow": ["service"], "allow_same_layer": True},
            )
        ]
        constraint = {"source": "ui", "allow": ["ui", "service"]}
    elif rule == "ARCH004":
        rules = [
            dict(id=rule, type="reverse_dependency", expected={"from": "domain", "to": "store"})
        ]
        constraint = {"forbidden": ["store", "domain"]}
    elif rule == "ARCH005":
        rules = [dict(id=rule, type="module_boundary", **{"from": "alpha", "allow": ["shared"]})]
        constraint = {"source": "alpha", "allow": ["alpha", "shared"]}
    elif rule == "ARCH003":
        rules = [dict(id=rule, type="circular_dependency", projection="component")]
    return {
        "spec": dict(version="1.0", architecture=architecture, rules=rules),
        "oracle_constraint": constraint,
    }


def sources(case_id: str, language: str, facts: dict[str, Any]) -> dict[str, str]:
    adj = adjacency(facts)
    names = {i: f"Unit{case_id[:12]}N{i}" for i in adj}
    paths = {
        i: f"src/{facts['roles'][i]}/{names[i]}." + ("java" if language == "JAVA" else "ts")
        for i in adj
    }
    result = {}
    for i, name in names.items():
        if language == "JAVA":
            imports = "".join(
                f"import fresh.{facts['roles'][j]}.{names[j]};\n"
                for j in sorted(adj[i])
                if facts["roles"][j] != facts["roles"][i]
            )
            fields = "".join(f"  {names[j]} link{j};\n" for j in sorted(adj[i]))
            methods = "".join(
                f"  public int slot{k}() {{ return {i + k}; }}\n"
                for k in range(facts["methods"][i])
            )
            result[paths[i]] = (
                f"package fresh.{facts['roles'][i]};\n"
                + imports
                + f"public class {name} {{\n{fields}{methods}}}\n"
            )
        else:
            imports = "".join(
                f"import {{ {names[j]} }} from '../{facts['roles'][j]}/{names[j]}';\n"
                for j in sorted(adj[i])
            )
            fields = "".join(f"  link{j}: {names[j]} | null = null;\n" for j in sorted(adj[i]))
            methods = "".join(
                f"  slot{k}(): number {{ return {i + k}; }}\n" for k in range(facts["methods"][i])
            )
            result[paths[i]] = imports + f"export class {name} {{\n{fields}{methods}}}\n"
    return result


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    eligible = [r for r in rows if r["scope"] == "BINARY"]
    counts = Counter((r["truth"], r["prediction"]) for r in eligible if r["error"] is None)
    tp, fp = counts[True, True], counts[False, True]
    tn, fn = counts[False, False], counts[True, False]

    def ratio(a: int, b: int) -> float | None:
        return a / b if b else None

    return dict(
        cases=len(rows),
        eligible=len(eligible),
        evaluated=tp + fp + tn + fn,
        TP=tp,
        FP=fp,
        TN=tn,
        FN=fn,
        Precision=ratio(tp, tp + fp),
        Recall=ratio(tp, tp + fn),
        F1=ratio(2 * tp, 2 * tp + fp + fn),
        Specificity=ratio(tn, tn + fp),
        FPR=ratio(fp, tn + fp),
        FNR=ratio(fn, tp + fn),
        coverage=ratio(tp + fp + tn + fn, len(eligible)),
        applicability_coverage=ratio(len(eligible), len(rows)),
        errors=sum(r["error"] is not None for r in eligible),
        runtime_seconds=sum(r["seconds"] for r in rows),
    )


def validate_design(rows: list[dict[str, Any]], families: tuple[str, ...]) -> None:
    expected = 100 + 20 * len(families)
    if len(rows) != expected or len({r["case_id"] for r in rows}) != expected:
        raise ValueError("holdout case identity/count mismatch")
    pairs: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        pairs.setdefault(r["pair_id"], []).append(r)
    for members in pairs.values():
        if len(members) != 2 or {r["truth"] for r in members} != {True, False}:
            raise ValueError("malformed pair")
        if len({(r["family"], r["language"], r["rule"]) for r in members}) != 1:
            raise ValueError("unmatched pair")
    for track, names in (("A", tuple(f"ARCH00{i}" for i in range(1, 6))), ("B", families)):
        for family in names:
            subset = [r for r in rows if r["track"] == track and r["family"] == family]
            if Counter((r["language"], r["truth"]) for r in subset) != Counter(
                {(lang, label): 5 for lang in ("JAVA", "TYPESCRIPT") for label in (False, True)}
            ):
                raise ValueError("holdout balance mismatch")


def plan(seed_fingerprint: str, capability: dict[str, Any]) -> dict[str, Any]:
    families = tuple(capability["train_families"]) if capability["v2_allowed"] else ()
    value = dict(
        schema="p019-prospective-plan-v1",
        dataset=DATASET,
        seed_fingerprint=seed_fingerprint,
        capability=capability,
        track_a=dict(cases=100, pairs=50, rules=[f"ARCH00{i}" for i in range(1, 6)]),
        track_b=dict(
            K=len(families),
            cases=20 * len(families),
            pairs=10 * len(families),
            families=list(families),
        ),
        construction="5 Java + 5 TypeScript matched pairs per family; opaque seeded IDs",
        independence="new source units; old metadata/hash audit only; no old TEST selection",
        oracle_predicates={
            "ARCH001": "normalized dependency contradicts frozen forbidden scope pair",
            "ARCH002": "ui dependency outside service/ui allow set",
            "ARCH003": "independent Kahn adjacency elimination leaves nodes",
            "ARCH004": "store->domain contradicts declared domain->store direction",
            "ARCH005": "alpha dependency outside alpha/shared module allow set",
            "ARCH101": "constructed target has at least 6 distinct outgoing branches",
            "ARCH102": "constructed target has at least 6 distinct incoming branches",
            "ARCH103": "6 distinct target methods and 6 outgoing service branches",
            "ARCH104": "direct target pair: Ce/(Ca+Ce) source < target",
            "ARCH105": "every 1..3 to 4..6 path requires removal-sensitive target 0",
        },
        intervention="fixed recipes; independent auxiliary relay chain 7..11+index",
        selection="frozen design only; no coefficient/score/observed result selection",
        static_scope=list(STATIC_RULES),
        direct_graph_binary=["ARCH003"],
        graph_candidate_policy="all production default thresholds remain None",
        v2_policy="exact portable transform/score/threshold; no Hybrid policy or fit",
        metric_scope="micro + per-rule Static; ARCH003 Graph; overall/per TRAIN-family V2",
        zero_denominator=None,
        errors="excluded from confusion counts, reduce coverage",
        evidence="100 P015 source/packet-only P009 contracts/features; no semantic decisions",
        access_order=[
            "PLAN_FROZEN",
            "HOLDOUT_FROZEN",
            "LABELS_SEALED",
            "STATIC_EXECUTION",
            "STATIC_OUTPUT_FROZEN",
            "GRAPH_EXECUTION",
            "GRAPH_OUTPUT_FROZEN",
            "V2_EXECUTION",
            "V2_OUTPUT_FROZEN",
            "FIRST_TRUTH_JOIN",
            "METRICS",
        ],
        forbidden=[
            "provider",
            "network",
            "truth-aware evidence",
            "tuning",
            "retraining",
            "Hybrid decisions",
            "ablation",
            "Security",
            "old scientific edits",
        ],
    )
    return value | {"fingerprint": digest(value)}
