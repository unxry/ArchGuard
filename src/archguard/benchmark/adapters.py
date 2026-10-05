from uuid import UUID, uuid5

from archguard.architecture.graph.conformance import GraphConformanceResult
from archguard.architecture.graph.models import GraphNodeId
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.models import HybridAnalysisResult, HybridDecisionState
from archguard.architecture.intelligence.models import AIAnalysisResult, SemanticDecision
from archguard.benchmark.identity import resolved_key, subject_key
from archguard.benchmark.models import (
    BenchmarkPrediction,
    BenchmarkRepository,
    GroundTruthCase,
    HybridTrainingRecord,
    Mode,
    PredictionState,
    Subjects,
    Task,
)
from archguard.benchmark.resolver import LocatorResolver
from archguard.core.findings.model import Finding
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel


def prediction(
    namespace: UUID,
    repo: str,
    rule: str,
    subjects: Subjects,
    state: PredictionState,
    source: Mode,
    task: Task,
    origins: tuple[UUID, ...] = (),
) -> BenchmarkPrediction:
    return BenchmarkPrediction(
        prediction_id=uuid5(
            namespace, f"{repo}:{rule}:{subject_key(subjects)}:{source}:{task}:{state}"
        ),
        repository_id=repo,
        rule_id=rule,
        subjects=subjects,
        state=state,
        source=source,
        task=task,
        origin_artifact_ids=origins,
    )


def static_predictions(
    iam: ArchitectureModel, repo: str, findings: tuple[Finding, ...]
) -> tuple[BenchmarkPrediction, ...]:
    resolver = LocatorResolver(iam)
    result = []
    for finding in findings:
        if finding.rule_id == "ARCH003":
            raise ValueError("ARCH003 requires the SCC graph adapter")
        files = {n.file_id: n for n in iam.nodes if n.kind == NodeKind.FILE}
        source = files[
            next(k for k in files if str(k) == finding.metadata["source_component_file_id"])
        ]
        target = files[
            next(k for k in files if str(k) == finding.metadata["target_component_file_id"])
        ]
        subjects = resolver.from_ids((source.id, target.id), directed=True)
        result.append(
            prediction(
                iam.project.id,
                repo,
                finding.rule_id,
                subjects,
                PredictionState.POSITIVE,
                Mode.STATIC_ONLY,
                Task.CONFIRMED_VIOLATION_DETECTION,
                (finding.id,),
            )
        )
    return tuple(result)


def graph_predictions(
    iam: ArchitectureModel,
    repo: str,
    graph: GraphAnalysisResult,
    conformance: GraphConformanceResult | None = None,
    *,
    task: Task = Task.STRUCTURAL_SIGNAL_RETRIEVAL,
) -> tuple[BenchmarkPrediction, ...]:
    resolver = LocatorResolver(iam)
    result = []
    if task == Task.STRUCTURAL_SIGNAL_RETRIEVAL:
        nodes = {n.id: n for n in graph.graph.nodes}
        edges = {e.id: e for e in graph.graph.edges}

        def component(gid: GraphNodeId) -> NodeId:
            choices = [
                i for i in nodes[gid].iam_node_ids if resolver.nodes[i].kind == NodeKind.CLASS
            ]
            if len(choices) != 1:
                raise ValueError("benchmark graph adapter requires one class per component")
            return choices[0]

        ids: tuple[NodeId, ...]
        for candidate in graph.candidates:
            if candidate.subject_edge_id:
                edge = edges[candidate.subject_edge_id]
                ids = (component(edge.source_id), component(edge.target_id))
                directed = True
            elif candidate.subject_node_id:
                ids = (component(candidate.subject_node_id),)
                directed = False
            else:
                raise ValueError("candidate subject missing")
            subjects = resolver.from_ids(ids, directed=directed)
            result.append(
                prediction(
                    iam.project.id,
                    repo,
                    candidate.rule_id,
                    subjects,
                    PredictionState.CANDIDATE,
                    Mode.GRAPH_ONLY,
                    task,
                    (candidate.candidate_id,),
                )
            )
    elif task == Task.CONFIRMED_VIOLATION_DETECTION:
        if conformance is None or conformance.graph is None:
            return ()
        scc_nodes = {str(n.id): n for n in conformance.graph.nodes}
        for finding in conformance.findings:
            members = finding.metadata["scc_members"]
            if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
                raise ValueError("invalid SCC members")
            ids = tuple(
                i
                for m in members
                for i in scc_nodes[str(m)].iam_node_ids
                if resolver.nodes[i].kind == NodeKind.CLASS
            )
            subjects = resolver.from_ids(ids)
            result.append(
                prediction(
                    iam.project.id,
                    repo,
                    finding.rule_id,
                    subjects,
                    PredictionState.POSITIVE,
                    Mode.GRAPH_ONLY,
                    task,
                    (finding.id,),
                )
            )
    else:
        raise ValueError("unsupported graph task")
    return tuple(result)


def ai_predictions(
    iam: ArchitectureModel, repo: str, artifact: AIAnalysisResult
) -> tuple[BenchmarkPrediction, ...]:
    resolver = LocatorResolver(iam)
    result = []
    mapping = {
        SemanticDecision.SUPPORTED: PredictionState.CANDIDATE,
        SemanticDecision.NOT_SUPPORTED: PredictionState.NEGATIVE,
        SemanticDecision.INSUFFICIENT_CONTEXT: PredictionState.ABSTAIN,
    }
    for candidate in artifact.candidates:
        a = candidate.assessment
        if not any(
            t.candidate_rule_id == a.candidate_rule_id and t.node_id in a.subject_node_ids
            for t in artifact.targets
        ):
            raise ValueError("AI assessment not requested")
        subjects = resolver.from_ids(a.subject_node_ids, kind=NodeKind.CLASS)
        result.append(
            prediction(
                iam.project.id,
                repo,
                a.candidate_rule_id,
                subjects,
                mapping[a.decision],
                Mode.LLM_ONLY,
                Task.SEMANTIC_CANDIDATE_DETECTION,
                (candidate.candidate_id,),
            )
        )
    return tuple(result)


def hybrid_subjects(resolver: LocatorResolver, rule: str, ids: tuple[NodeId, ...]) -> Subjects:
    if rule in {"ARCH001", "ARCH002", "ARCH004", "ARCH005"}:
        return resolver.from_ids(ids, directed=True, kind=NodeKind.FILE)
    return resolver.from_ids(ids, kind=NodeKind.CLASS)


def hybrid_predictions(
    iam: ArchitectureModel, repo: str, artifact: HybridAnalysisResult
) -> tuple[BenchmarkPrediction, ...]:
    resolver = LocatorResolver(iam)
    result = []
    for case, decision in zip(artifact.cases, artifact.decisions, strict=True):
        if decision.state != HybridDecisionState.CONFIRMED_DETERMINISTIC:
            continue
        ids = case.primary_subject_ids
        if case.subject_pairs and case.rule_id != "ARCH003":
            ids = (case.subject_pairs[0].source_id, case.subject_pairs[0].target_id)
        result.append(
            prediction(
                iam.project.id,
                repo,
                case.rule_id,
                hybrid_subjects(resolver, case.rule_id, ids),
                PredictionState.POSITIVE,
                Mode.HYBRID,
                Task.CONFIRMED_VIOLATION_DETECTION,
                case.anchor_ids,
            )
        )
    return tuple(result)


def training_records(
    iam: ArchitectureModel,
    repo: BenchmarkRepository,
    truths: tuple[GroundTruthCase, ...],
    result: HybridAnalysisResult,
) -> tuple[HybridTrainingRecord, ...]:
    resolver = LocatorResolver(iam)
    labels = {
        (t.rule_id, resolved_key(t.subjects, ids)): t
        for t in truths
        if t.repository_id == repo.repository_id
        and (ids := resolver.subjects(t.subjects)) is not None
    }
    records = []
    for case, vector in zip(result.cases, result.features, strict=True):
        ids = case.primary_subject_ids
        if case.subject_pairs and case.rule_id != "ARCH003":
            ids = (case.subject_pairs[0].source_id, case.subject_pairs[0].target_id)
        subjects = (
            resolver.from_ids(ids, directed=True, kind=NodeKind.CLASS)
            if case.rule_id == "ARCH104"
            else hybrid_subjects(resolver, case.rule_id, ids)
        )
        truth = labels.get(
            (case.rule_id, resolved_key(subjects, resolver.subjects(subjects) or ()))
        )
        if truth is None or resolver.subjects(truth.subjects) is None:
            continue
        records.append(
            HybridTrainingRecord(
                repository_id=repo.repository_id,
                repository_family_id=repo.repository_family_id,
                split=repo.dataset_split,
                case_id=truth.case_id,
                hybrid_case_id=case.case_id,
                rule_family=truth.rule_family,
                subjects=subjects,
                subject_ids=resolver.subjects(subjects) or (),
                feature_schema_version=vector.schema_version,
                feature_fingerprint=vector.fingerprint,
                features=vector,
                ground_truth_label=truth.label,
                annotation_status=truth.annotation_status,
                evidence_availability=tuple(str(f.availability) for f in vector.values),
            )
        )
    return tuple(sorted(records, key=lambda r: str(r.case_id)))
