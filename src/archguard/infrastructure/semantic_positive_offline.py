"""Label-blind source capabilities, existing context selection, immutable P016 bundles."""

import hashlib
import json
from pathlib import Path
from typing import Any

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_holdout import BlindedPacket, HoldoutSample
from archguard.benchmark.semantic_positive_experiment import (
    SYSTEM_PROMPT,
    PositiveAssessment,
    PositiveProtocol,
    RequestRecord,
    analysis_plan,
    ordered_product,
    prompt_contract,
    token_estimate,
)
from archguard.benchmark.semantic_preflight import QUESTIONS
from archguard.core.model.enums import NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.semantic_preflight import wire_payload
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

COHORT = Path("experiments/semantic-holdout/semantic-positive-holdout-v1")
SOURCES = Path("experiments/semantic-holdout/private/semantic-positive-holdout-v1")
FORBIDDEN_KEYS = {
    "final_category",
    "binary_eligible",
    "binary_excluded",
    "reviewer_identity",
    "a_decision",
    "b_decision",
    "adjudicator_decision",
    "resolution_provenance",
    "human_rationale",
    "human_evidence",
    "note",
    "notes",
    "pair_id",
    "operator_id",
    "mutation_operator",
    "control_case_id",
    "mutation_case_id",
    "expected_effect",
    "intended_positive",
    "construction_intent",
    "detector_result",
    "ai_output",
}


def audit_metadata(value: object) -> None:
    if isinstance(value, dict):
        if FORBIDDEN_KEYS & set(value):
            raise ValueError("prohibited experiment metadata in execution material")
        for child in value.values():
            audit_metadata(child)
    elif isinstance(value, (tuple, list)):
        for child in value:
            audit_metadata(child)


def capability_path(root: Path, relative: str) -> Path:
    path = root / relative
    if (
        path.is_symlink()
        or any(p.is_symlink() for p in path.parents)
        or not path.resolve().is_relative_to(root.resolve())
    ):
        raise ValueError("source capability escape/symlink forbidden")
    return path


def prepare_material(
    protocol: PositiveProtocol, *, cohort: Path = COHORT, sources: Path = SOURCES
) -> tuple[dict[str, Any], tuple[RequestRecord, ...], dict[str, str]]:
    # The only decoded inputs are the public pre-label sample and strict source packets.
    sample = HoldoutSample.model_validate_json(
        capability_path(cohort, "sample-v1.json").read_bytes()
    )
    if sample.fingerprint != protocol.sample_fingerprint or any(
        c.technical_status != "VALID" for c in sample.cases
    ):
        raise ValueError("frozen source cohort drift")
    mapping = {
        c.case_id: digest(
            {"version": "p016-execution-case-v1", "sample": sample.fingerprint, "case": c.case_id}
        )
        for c in sample.cases
    }
    by_case = {mapping[c.case_id]: c for c in sample.cases}
    files: dict[str, Any] = {
        "protocol.json": protocol,
        "prompt-schema.json": prompt_contract(),
        "analysis-plan.json": analysis_plan(),
        "strategy-config.json": {
            "strategies": protocol.strategies,
            "graph_configuration": GraphAnalysisConfig(),
            "selection_implementation": "EXISTING_GRAPH_GUIDED_CONTEXT_BUILDER",
            "ranking": "TARGET_OUTGOING_INCOMING_CYCLE_DISTANCE_STABLE_NODE_ID",
            "snippet_order": "EXISTING_SELECTED_NODE_ORDER; STABLE_FRAGMENT_REFERENCES",
            "truncation": "EXISTING_SERIALIZED_CONTEXT_BUDGET; P014_LIMITS_UNCHANGED",
        },
    }
    generated: dict[tuple[str, str], RequestRecord] = {}
    execution_cases = []
    for execution_id, case in sorted(by_case.items()):
        packet = BlindedPacket.model_validate_json(
            capability_path(sources, "packets/" + case.blinded_id + ".json").read_bytes()
        )
        if packet.fingerprint != case.packet_fingerprint or (packet.rule_id, packet.language) != (
            case.rule_id,
            case.language,
        ):
            raise ValueError("frozen source packet drift")
        root = capability_path(sources, "sources/" + case.blinded_id)
        expected = {e.path for e in packet.evidence}
        actual = {
            p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() or p.is_symlink()
        }
        if actual != expected:
            raise ValueError("source-only workspace inventory drift")
        for evidence in packet.evidence:
            path = capability_path(root, evidence.path)
            if hashlib.sha256(path.read_bytes()).hexdigest() != evidence.sha256:
                raise ValueError("frozen source raw SHA mismatch")
        building = BuildIAM(
            ParseRepository(create_parser_registry()),
            create_extractor_registry(),
            ExtractionConfig(
                repository_namespace=packet.project_alias, project_name=packet.project_alias
            ),
        )
        with create_discovery().open(
            RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
        ) as repository:
            built = building.execute(repository.snapshot, repository.workspace)
            graph = GraphAnalyzer().analyze(built.iam, GraphAnalysisConfig())
            if not built.is_valid or not graph.is_valid:
                raise ValueError("frozen VALID IAM/graph cannot be reconstructed")
            targets = [
                n
                for n in built.iam.nodes
                if n.kind == NodeKind.CLASS
                and n.name == packet.target_component
                and n.source_location
                and n.source_location.file_path == packet.target_path
            ]
            if len(targets) != 1:
                raise ValueError("frozen target does not resolve uniquely")
            target = targets[0].id
            source_input = {
                "iam": built.iam,
                "graph": graph.graph,
                "cycles": graph.cycles,
                "graph_reproducibility": graph.reproducibility,
            }
            files["inputs/" + execution_id + ".json"] = source_input
            execution_cases.append(
                {
                    "execution_case_id": execution_id,
                    "target_rule": case.rule_id,
                    "language": case.language,
                    "source_input_fingerprint": digest(source_input),
                    "iam_fingerprint": iam_fingerprint(built.iam),
                    "iam_valid": built.is_valid,
                    "graph_valid": graph.is_valid,
                }
            )
            for config in protocol.strategies:
                pack = GraphGuidedContextBuilder().build(
                    target, built.iam, graph, repository.workspace, config
                )
                if not pack.fragments or not any(
                    target in f.reference.node_ids for f in pack.fragments
                ):
                    raise ValueError("missing usable target source context")
                context = pack.untrusted_data() | {
                    "architecture_contract": packet.architecture_contract,
                    "context_status": {
                        "truncated": pack.manifest.truncated,
                        "diagnostics": [d.code for d in pack.manifest.diagnostics],
                    },
                }
                audit_metadata(context)
                context_fp = digest(context)
                request_id = digest(
                    {
                        "execution_case_id": execution_id,
                        "target_rule": case.rule_id,
                        "language": case.language,
                        "strategy": config.strategy,
                        "context_fingerprint": context_fp,
                        "provider": protocol.provider,
                        "model": protocol.model,
                        "prompt_schema_fingerprint": protocol.prompt_schema_fingerprint,
                    }
                )
                request = StructuredLLMRequest(
                    prompt_version=protocol.prompt_version,
                    schema_version=protocol.prompt_version,
                    system_instructions=SYSTEM_PROMPT,
                    task={
                        "request_id": request_id,
                        "case_id": execution_id,
                        "candidate_rule_id": case.rule_id,
                        "candidate_question": QUESTIONS[case.rule_id],
                        "language": case.language,
                        "subject_node_id": str(target),
                    },
                    untrusted_context=context,
                    response_schema=PositiveAssessment.model_json_schema(),
                    timeout_seconds=protocol.timeout_seconds,
                    max_output_tokens=protocol.max_output_tokens,
                )
                visible = (
                    request.system_instructions
                    + canonical(
                        {"task": request.task, "untrusted_context": request.untrusted_context}
                    )
                    + canonical(request.response_schema)
                )
                estimate, upper = token_estimate(visible)
                row = RequestRecord(
                    request_id=request_id,
                    execution_case_id=execution_id,
                    strategy=config.strategy,
                    target_rule=case.rule_id,
                    language=case.language,
                    context_fingerprint=context_fp,
                    request_fingerprint=digest(request),
                    context_chars=len(canonical(context)),
                    source_chars=sum(len(f.text) for f in pack.fragments),
                    input_estimate=estimate,
                    conservative_input_upper=upper,
                    truncated=pack.manifest.truncated,
                    diagnostics=tuple(d.code for d in pack.manifest.diagnostics),
                    iam_valid=built.is_valid,
                    graph_valid=graph.is_valid,
                )
                generated[(execution_id, config.strategy.value)] = row
                artifact = {
                    "record": row,
                    "structured_request": request,
                    "provider_payload": wire_payload(request, protocol.model),
                    "context_manifest": pack.manifest,
                }
                audit_metadata(json.loads(canonical(artifact)))
                files["requests/" + request_id + ".json"] = artifact
    order = ordered_product(tuple(by_case))
    rows = tuple(generated[(case, strategy.value)] for case, strategy in order)
    files["execution-cases.json"] = {
        "schema_version": "p016-execution-cases-v1",
        "cases": execution_cases,
    }
    context_manifest = {
        "schema_version": "p016-context-manifest-v1",
        "protocol_fingerprint": protocol.fingerprint,
        "requests": rows,
        "execution_order": [r.request_id for r in rows],
        "live_calls": 0,
    }
    files["context-manifest.json"] = context_manifest | {"fingerprint": digest(context_manifest)}
    request_manifest = {
        "schema_version": "p016-request-manifest-v1",
        "protocol_fingerprint": protocol.fingerprint,
        "context_manifest_fingerprint": digest(context_manifest),
        "prompt_schema_fingerprint": protocol.prompt_schema_fingerprint,
        "requests": [
            {
                "request_id": r.request_id,
                "execution_case_id": r.execution_case_id,
                "strategy": r.strategy,
                "target_rule": r.target_rule,
                "language": r.language,
                "context_fingerprint": r.context_fingerprint,
                "request_fingerprint": r.request_fingerprint,
            }
            for r in rows
        ],
    }
    files["request-manifest.json"] = request_manifest | {"fingerprint": digest(request_manifest)}
    return files, rows, mapping


def freeze_execution_bundle(destination: Path, files: dict[str, Any]) -> dict[str, Any]:
    receipt = {
        "schema_version": "p016-offline-execution-freeze-v1",
        "files": {
            name: hashlib.sha256((canonical(value) + "\n").encode()).hexdigest()
            for name, value in sorted(files.items())
        },
        "protocol_fingerprint": files["protocol.json"].fingerprint,
        "context_manifest_fingerprint": files["context-manifest.json"]["fingerprint"],
        "request_manifest_fingerprint": files["request-manifest.json"]["fingerprint"],
        "paid_execution_approved": False,
        "live_calls": 0,
    }
    receipt["fingerprint"] = digest(receipt)

    def build(stage: Path) -> None:
        stage.chmod(0o700)
        for name, value in files.items():
            path = stage / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.parent.chmod(0o700)
            write_new(path, value)
            path.chmod(0o600)
        write_new(stage / "execution-freeze.json", receipt)
        (stage / "execution-freeze.json").chmod(0o600)

    atomic_directory(destination, build)
    verify_execution_bundle(destination, receipt["fingerprint"])
    return receipt


def verify_execution_bundle(destination: Path, fingerprint: str) -> dict[str, Any]:
    from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal

    receipt: dict[str, Any] = json.loads(
        verify_opaque_seal(destination / "execution-freeze.json", fingerprint)
    )
    if destination.is_symlink() or any(p.is_symlink() for p in destination.rglob("*")):
        raise ValueError("execution bundle symlinks forbidden")
    expected = set(receipt["files"]) | {"execution-freeze.json"}
    actual = {p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_file()}
    if actual != expected or {
        p.relative_to(destination).as_posix() for p in destination.rglob("*") if p.is_dir()
    } != {"inputs", "requests"}:
        raise ValueError("execution bundle inventory drift")
    for name, sha in receipt["files"].items():
        path = capability_path(destination, name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("execution bundle bytes drift")
    return receipt
