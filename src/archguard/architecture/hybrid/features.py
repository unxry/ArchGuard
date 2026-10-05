from archguard.architecture.hybrid.models import (
    FeatureAvailability,
    FeatureValueType,
    HybridCase,
    HybridEvidenceBundle,
    HybridFeature,
    HybridFeatureDefinition,
    HybridFeatureSchema,
    HybridFeatureVector,
)
from archguard.architecture.hybrid.serialization import fingerprint

VERSION = "hybrid-evidence-v1"


def feature_schema() -> HybridFeatureSchema:
    definitions: list[HybridFeatureDefinition] = []
    for names, kind in (
        (("static.confirmed",), FeatureValueType.BOOLEAN),
        (("static.rules", "static.relations"), FeatureValueType.SET),
        (("graph.Ca", "graph.Ce", "graph.coupling", "graph.scc_size"), FeatureValueType.INTEGER),
        (("graph.I", "graph.betweenness", "graph.pagerank"), FeatureValueType.FLOAT),
        (("graph.cyclic",), FeatureValueType.BOOLEAN),
        (("graph.candidate_rules",), FeatureValueType.SET),
        (("graph.ARCH101", "graph.ARCH102"), FeatureValueType.BOOLEAN),
        (("discovery.roles", "discovery.layers", "discovery.strengths"), FeatureValueType.SET),
        (("discovery.ambiguous",), FeatureValueType.BOOLEAN),
        (tuple(f"ai.ARCH{rule}.decisions" for rule in range(201, 206)), FeatureValueType.SET),
        (("context.strategies",), FeatureValueType.SET),
        (
            ("context.truncated", "quality.iam_complete", "quality.parse_errors"),
            FeatureValueType.BOOLEAN,
        ),
        (("quality.unresolved", "quality.ambiguous"), FeatureValueType.INTEGER),
        (("quality.graph_complete", "quality.discovery_complete"), FeatureValueType.BOOLEAN),
        (("quality.metrics_skipped",), FeatureValueType.SET),
        (
            ("quality.ai_requested", "quality.ai_completed", "quality.ai_insufficient"),
            FeatureValueType.INTEGER,
        ),
        (("quality.ai_partial",), FeatureValueType.BOOLEAN),
    ):
        definitions.extend(HybridFeatureDefinition(name=name, value_type=kind) for name in names)
    return HybridFeatureSchema(version=VERSION, definitions=tuple(definitions))


def extract_features(case: HybridCase, bundle: HybridEvidenceBundle) -> HybridFeatureVector:
    values: dict[str, bool | int | float | str | tuple[str, ...] | None] = {}
    refs: dict[str, tuple[str, ...]] = {}

    def put(
        name: str,
        value: bool | int | float | str | tuple[str, ...] | None,
        provenance: tuple[str, ...],
    ) -> None:
        values[name], refs[name] = value, provenance

    static_refs = tuple(f"finding:{p.finding_id}" for p in bundle.static)
    put("static.confirmed", True if bundle.static else None, static_refs)
    put("static.rules", tuple(sorted({p.rule_id for p in bundle.static})) or None, static_refs)
    put(
        "static.relations",
        tuple(sorted({r for p in bundle.static for r in p.relation_kinds})) or None,
        static_refs,
    )
    # Scalar graph features describe the primary subject only; never average unrelated nodes.
    primary = case.primary_subject_ids[0] if len(case.primary_subject_ids) == 1 else None
    measurement = next((m for m in bundle.graph_measurements if m.subject_id == primary), None)
    for name, attribute in (
        ("Ca", "afferent_coupling"),
        ("Ce", "efferent_coupling"),
        ("coupling", "total_unique_neighbors"),
        ("scc_size", "scc_size"),
        ("I", "instability"),
        ("betweenness", "betweenness_centrality"),
        ("pagerank", "pagerank"),
        ("cyclic", "is_cyclic"),
    ):
        put(
            f"graph.{name}",
            getattr(measurement.metrics, attribute) if measurement else None,
            (measurement.provenance_ref,) if measurement else (),
        )
    graph_refs = tuple(f"graph:{s.candidate_id}" for s in bundle.graph)
    put(
        "graph.candidate_rules",
        tuple(sorted({s.rule_id for s in bundle.graph})) or None,
        graph_refs,
    )
    for rule in ("ARCH101", "ARCH102"):
        matching = tuple(f"graph:{s.candidate_id}" for s in bundle.graph if s.rule_id == rule)
        put(f"graph.{rule}", True if matching else None, matching)
    discovery_refs = tuple(f"discovery:{d.role_hypothesis_id}" for d in bundle.discovery)
    for name, attribute in (("roles", "role"), ("layers", "layer"), ("strengths", "role_strength")):
        put(
            f"discovery.{name}",
            tuple(sorted({getattr(d, attribute).value for d in bundle.discovery})) or None,
            discovery_refs,
        )
    put(
        "discovery.ambiguous",
        any(
            d.role_strength.value == "AMBIGUOUS" or d.layer.value == "AMBIGUOUS"
            for d in bundle.discovery
        )
        if bundle.discovery
        else None,
        discovery_refs,
    )
    for semantic_rule in range(201, 206):
        signals = tuple(s for s in bundle.ai if s.rule_id == f"ARCH{semantic_rule}")
        put(
            f"ai.ARCH{semantic_rule}.decisions",
            tuple(sorted({s.decision.value for s in signals})) or None,
            tuple(f"ai:{s.candidate_id}" for s in signals),
        )
    context_refs = tuple(f"context:{c.context_fingerprint}" for c in bundle.context)
    put(
        "context.strategies",
        tuple(sorted({c.strategy.value for c in bundle.context})) or None,
        context_refs,
    )
    put("context.truncated", bundle.completeness.context_truncated, context_refs)
    for name, attribute in (
        ("iam_complete", "iam_complete"),
        ("parse_errors", "parse_errors_present"),
        ("unresolved", "unresolved_references"),
        ("ambiguous", "ambiguous_references"),
        ("graph_complete", "graph_complete"),
        ("discovery_complete", "discovery_complete"),
        ("metrics_skipped", "metrics_skipped"),
        ("ai_requested", "ai_requested"),
        ("ai_completed", "ai_completed"),
        ("ai_insufficient", "ai_insufficient"),
        ("ai_partial", "ai_partial"),
    ):
        put(f"quality.{name}", getattr(bundle.completeness, attribute), (f"quality:{attribute}",))
    features = tuple(
        HybridFeature(
            name=definition.name,
            value_type=definition.value_type
            if values[definition.name] is not None
            else FeatureValueType.MISSING,
            value=values[definition.name],
            availability=FeatureAvailability.AVAILABLE
            if values[definition.name] is not None
            else FeatureAvailability.MISSING,
            provenance_refs=refs[definition.name],
        )
        for definition in feature_schema().definitions
    )
    return HybridFeatureVector(
        case_id=case.case_id,
        schema_version=VERSION,
        values=features,
        fingerprint=fingerprint(
            {"schema_version": VERSION, "values": [f.model_dump(mode="json") for f in features]}
        ),
    )
