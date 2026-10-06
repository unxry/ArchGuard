"""Build frozen source contexts offline. No provider factory, credential or human-answer input."""

from pathlib import Path
from typing import Any

from archguard.architecture.conformance.analyzer import iam_fingerprint
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import StructuredLLMRequest
from archguard.benchmark.oss.models import AnnotationSample, digest
from archguard.benchmark.semantic_preflight import (
    SYSTEM,
    PricingAssumption,
    RequestPreflight,
    SemanticAssessmentJudgment,
    SemanticExperimentManifest,
    cost_report,
    measure_request,
    research_request,
)
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_benchmark import (
    FrozenOSSCorpus,
    source_path,
    verify_acquisition,
    write_new,
)
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput


def wire_payload(request: StructuredLLMRequest, model: str) -> dict[str, Any]:
    # Match the production Responses transport without instantiating a credentialed provider.
    from archguard.architecture.intelligence.models import canonical

    return {
        "model": model,
        "store": False,
        "max_output_tokens": request.max_output_tokens,
        "input": [
            {"role": "system", "content": request.system_instructions},
            {
                "role": "user",
                "content": canonical(
                    {"task": request.task, "untrusted_context": request.untrusted_context}
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "architecture_assessment",
                "strict": True,
                "schema": request.response_schema,
            }
        },
    }


def prepare_contexts(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    graph_inputs: Path,
    manifest: SemanticExperimentManifest,
    private_output: Path,
) -> tuple[tuple[RequestPreflight, ...], dict[str, Any]]:
    if (bound.corpus.fingerprint, bound.freeze.fingerprint) != (
        manifest.corpus_fingerprint,
        manifest.corpus_freeze_fingerprint,
    ):
        raise ValueError("experiment does not match supplied corpus")
    if (
        sample.fingerprint,
        sample.corpus_fingerprint,
        sample.corpus_freeze_fingerprint,
        tuple(p.annotation_case_id for p in sample.packets),
    ) != (
        manifest.sample_fingerprint,
        manifest.corpus_fingerprint,
        manifest.corpus_freeze_fingerprint,
        manifest.cases,
    ):
        raise ValueError("experiment does not match frozen sample/corpus")
    configs = {c.strategy: c for c in manifest.strategies}
    rows: dict[tuple[str, str], RequestPreflight] = {}
    input_identities = []
    builder = GraphGuidedContextBuilder()

    def build(stage: Path) -> None:
        # Freeze the protocol before context construction; never publish partial preparation.
        write_new(stage / "experiment-manifest.json", manifest)
        requests = stage / "requests"
        requests.mkdir()
        for repo in bound.corpus.repositories:
            receipt = verify_acquisition(bound, repo, cache)
            raw = _read(graph_inputs / (repo.repository_id + ".json"), 134217728)
            if not isinstance(raw, dict) or (
                raw.get("repository_id"),
                raw.get("corpus_fingerprint"),
                raw.get("corpus_freeze_fingerprint"),
            ) != (repo.repository_id, bound.corpus.fingerprint, bound.freeze.fingerprint):
                raise ValueError("IAM/graph inputs do not belong to the pinned corpus")
            # Read only raw syntax/dependency models; no discovery or candidate targeting.
            iam = ArchitectureModel.model_validate(raw["iam"])
            graph = GraphAnalysisResult.model_validate(raw["graph"])
            if graph.reproducibility.iam_fingerprint != iam_fingerprint(iam):
                raise ValueError("IAM/graph fingerprint mismatch")
            input_identities.append(
                {
                    "repository_id": repo.repository_id,
                    "commit_sha": repo.commit_sha,
                    "source_content_fingerprint": receipt.content_fingerprint,
                    "iam_fingerprint": iam_fingerprint(iam),
                    "graph_input_fingerprint": digest(
                        {
                            "graph": graph.graph,
                            "cycles": graph.cycles,
                            "reproducibility": graph.reproducibility,
                        }
                    ),
                }
            )
            root = source_path(cache, repo)
            with create_discovery(bound.policy).open(
                RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
            ) as workspace:
                for packet in sample.packets:
                    if packet.repository_id != repo.repository_id:
                        continue
                    matches = [
                        n
                        for n in iam.nodes
                        if n.qualified_name == packet.subject.qualified_name
                        and n.kind == packet.subject.kind
                        and n.source_location
                        and n.source_location.file_path == packet.subject.path
                    ]
                    if len(matches) != 1:
                        raise ValueError("frozen subject does not resolve uniquely in pinned IAM")
                    target = matches[0].id
                    for strategy, config in configs.items():
                        pack = builder.build(
                            target,
                            iam,
                            graph,
                            workspace.workspace,
                            config,
                            allow_invalid_iam_context=True,
                        )
                        if (
                            not pack.fragments
                            or not any(target in f.reference.node_ids for f in pack.fragments)
                            or any(
                                d.code != "CONTEXT_INVALID_IAM_PARTIAL_DATA"
                                for d in pack.manifest.diagnostics
                            )
                        ):
                            raise ValueError("context preparation lacks usable target source")
                        request = research_request(
                            packet.annotation_case_id, packet.rule_id, pack, manifest
                        )
                        measured = measure_request(
                            packet.annotation_case_id, pack, request, manifest
                        )
                        rows[(packet.annotation_case_id, strategy.value)] = measured
                        name = digest((packet.annotation_case_id, strategy.value)) + ".json"
                        write_new(
                            requests / name,
                            {
                                "logical_case_id": packet.annotation_case_id,
                                "strategy": strategy.value,
                                "structured_request": request,
                                "provider_payload": wire_payload(request, manifest.model),
                                "context_manifest": pack.manifest,
                            },
                        )
        ordered = tuple(rows[(case, strategy.value)] for case, strategy in manifest.execution_order)
        payload = {
            "schema_version": "semantic-context-preflight-v1",
            "experiment_fingerprint": manifest.fingerprint,
            "requests": ordered,
            "source_inputs": input_identities,
            "request_order": manifest.execution_order,
            "live_api_calls": 0,
        }
        context_manifest = payload | {"fingerprint": digest(payload)}
        write_new(stage / "context-manifest.json", context_manifest)

    atomic_directory(private_output, build)
    ordered = tuple(rows[(case, strategy.value)] for case, strategy in manifest.execution_order)
    raw_context = _read(private_output / "context-manifest.json", 2097152)
    assert isinstance(raw_context, dict)
    return ordered, raw_context


def publish_preflight(
    manifest: SemanticExperimentManifest,
    rows: tuple[RequestPreflight, ...],
    context_manifest: dict[str, Any],
    pricing: PricingAssumption,
    destination: Path,
) -> dict[str, object]:
    if (
        context_manifest.get("fingerprint")
        != digest({k: v for k, v in context_manifest.items() if k != "fingerprint"})
        or context_manifest.get("experiment_fingerprint") != manifest.fingerprint
        or digest(context_manifest.get("requests")) != digest(rows)
    ):
        raise ValueError("context manifest identity or request measurements changed")
    report = cost_report(manifest, rows, pricing)
    report["context_manifest_fingerprint"] = context_manifest["fingerprint"]

    def build(stage: Path) -> None:
        write_new(stage / "semantic-context-v1.json", manifest)
        write_new(stage / "context-manifest-v1.json", context_manifest)
        write_new(
            stage / "research-response-schema-v1.json",
            SemanticAssessmentJudgment.model_json_schema(),
        )
        (stage / "research-system-prompt-v1.txt").write_text(SYSTEM + "\n", encoding="utf-8")

    atomic_directory(destination, build)
    return report
