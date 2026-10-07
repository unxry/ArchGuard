"""Offline construction, source-only context diagnostics and immutable publication."""

import hashlib
import json
import subprocess
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.graph.builder import GraphBuilder
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.models import GraphBuildResult
from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.semantic_holdout import (
    LANGUAGES,
    RULES,
    SCENARIOS,
    VERSION,
    BlindedPacket,
    CaseRecord,
    HoldoutSample,
    Language,
    PrivatePair,
    SourceEvidence,
    fixture_sources,
    opaque_id,
    operators,
    target_name,
    validate_pairs,
)
from archguard.core.model.enums import NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam_building.models import IAMBuildResult
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

ARCHITECTURE = (
    "Layered HTTP service fixture. RequestHandler owns request/response mapping and delegates "
    "business decisions. ViewMapper owns presentation translation, delegating decisions. "
    "Application coordinates domain components; it must not own policy or concrete storage. "
    "Policy owns business decisions and belongs to domain; infrastructure contains adapters. "
    "FileLedger is a concrete filesystem adapter. Domain components must not call it directly. "
    "The domain slot, callers and decision implementation jointly establish policy ownership; "
    "a folder or component name alone is not evidence of a semantic violation. "
    "HttpRequest/HttpResponse provide the executable local HTTP boundary."
)
SCENARIO_DESCRIPTIONS = {
    "pricing": "Tiered order discounts at 500 and 1000 units.",
    "eligibility": "Age-based eligibility: under 18 ineligible, 65+ senior tier.",
    "inventory": "Reservation limits and handling allowance for quantities of 10 and 100.",
    "settlement": "Settlement fee of one twentieth, high-volume rebate and minimum fee.",
    "allocation": "Allocation tiers, a high-volume cap and proportional quotas.",
}
EXAMPLES = {
    "pricing": ((1000, 900), (600, 575), (100, 100)),
    "eligibility": ((15, 0), (30, 1), (70, 2)),
    "inventory": ((120, 90), (20, 18), (5, 5)),
    "settlement": ((2000, 1920), (100, 95), (40, 35)),
    "allocation": ((600, 300), (120, 80), (50, 25)),
}


def sealed(payload: dict[str, Any]) -> dict[str, Any]:
    return payload | {"fingerprint": digest(payload)}


def make_packet(
    seed: bytes, rule: str, language: Language, scenario: str, mutation: bool
) -> tuple[str, BlindedPacket]:
    identity = (VERSION, rule, language, scenario, mutation)
    case_id = "hc-" + opaque_id(seed, "case", identity)[:32]
    blind = "hb-" + opaque_id(seed, "review", identity)[:32]
    sources = fixture_sources(rule, language, scenario, mutation)
    target = target_name(rule)
    packet = seal(
        BlindedPacket,
        blinded_id=blind,
        rule_id=rule,
        language=language,
        project_alias="project-" + opaque_id(seed, "project-alias", identity)[:20],
        target_path=next(p for p in sources if p.rsplit("/", 1)[1].split(".")[0] == target),
        target_component=target,
        architecture_contract=ARCHITECTURE
        + " Business contract: "
        + SCENARIO_DESCRIPTIONS[scenario],
        evidence=tuple(
            SourceEvidence(
                evidence_id="ev-" + digest((blind, path))[:24],
                path=path,
                text=text,
                sha256=hashlib.sha256(text.encode()).hexdigest(),
            )
            for path, text in sorted(sources.items())
        ),
    )
    return case_id, packet


def future_context_input(packet: BlindedPacket) -> dict[str, Any]:
    """Capability boundary: only a sealed source packet, never construction/provenance."""
    packet = BlindedPacket.model_validate(packet)
    return {
        "blinded_id": packet.blinded_id,
        "rule_id": packet.rule_id,
        "target_component": packet.target_component,
        "target_path": packet.target_path,
        "architecture_contract": packet.architecture_contract,
        "source_evidence": [e.model_dump(mode="json") for e in packet.evidence],
    }


def offline_context_diagnostics(
    packet: BlindedPacket, built: IAMBuildResult, graph: GraphBuildResult
) -> dict[str, Any]:
    target = next(
        (
            n
            for n in built.iam.nodes
            if n.kind == NodeKind.CLASS
            and n.name == packet.target_component
            and n.source_location
            and n.source_location.file_path == packet.target_path
        ),
        None,
    )
    node = next((n for n in graph.graph.nodes if target and target.id in n.iam_node_ids), None)
    neighbors = {node.id} if node else set()
    if node:
        for edge in graph.graph.edges:
            if node.id in (edge.source_id, edge.target_id):
                neighbors.update((edge.source_id, edge.target_id))
    neighbor_paths = {
        loc.file_path for n in graph.graph.nodes if n.id in neighbors for loc in n.locations
    }
    missing = [] if target and node else ["TARGET_OR_GRAPH_NODE_MISSING"]
    selections = {
        "LOCAL_ONLY": {packet.target_path},
        "GRAPH_GUIDED": neighbor_paths | {packet.target_path},
        "EXPANDED_BASELINE": {e.path for e in packet.evidence},
    }
    strategies = {}
    for strategy, paths in selections.items():
        sources = sorted((e for e in packet.evidence if e.path in paths), key=lambda e: e.path)
        available = sum(len(e.text) for e in sources)
        selected = sum(min(len(e.text), 4000) for e in sources[:10])
        strategies[strategy] = {
            "available_chars": available,
            "available_source_spans": len(sources),
            "source_span_lines": sum(len(e.text.splitlines()) for e in sources),
            "selected_source_chars": min(selected, 20000),
            "expected_truncation": (
                available > selected or selected > 20000 or len(sources) > 10 or len(neighbors) > 20
            ),
            "iam_valid": built.is_valid,
            "iam_complete": built.is_complete,
            "missing_evidence_reasons": missing,
            "graph_neighborhood_size": len(neighbors),
        }
    return sealed(
        {
            "schema_version": "holdout-offline-context-v1",
            "blinded_id": packet.blinded_id,
            "packet_fingerprint": packet.fingerprint,
            "budgets": {
                "hop_count": 1,
                "max_nodes": 20,
                "max_files": 10,
                "max_fragment_chars": 4000,
                "max_total_chars": 20000,
            },
            "strategies": strategies,
            "interpretation": "Engineering availability only; no predicted model judgment",
        }
    )


def validate_fixture(
    root: Path,
    packet: BlindedPacket,
    scenario: str,
    node_executable: Path | None = None,
    javac_executable: Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
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
        replay = building.execute(repository.snapshot, repository.workspace)
    graph = GraphBuilder().build(built.iam, GraphAnalysisConfig())
    diagnostics = offline_context_diagnostics(packet, built, graph)
    spans = {
        e.path: any(
            n.source_location and n.source_location.file_path == e.path and n.kind == NodeKind.CLASS
            for n in built.iam.nodes
        )
        for e in packet.evidence
    }
    native: dict[str, Any] = {
        "status": "NOT_RUN",
        "level": "PARSE_IAM_GRAPH_REPLAY",
        "reason": "Native compiler/runtime unavailable",
    }
    with TemporaryDirectory(prefix="archguard-holdout-validation-") as working:
        if packet.language == "JAVA" and javac_executable:
            command = [
                str(javac_executable),
                "-d",
                working,
                *(str(root / e.path) for e in packet.evidence),
            ]
            run = subprocess.run(command, capture_output=True, timeout=60)
            native = {
                "status": "PASSED" if run.returncode == 0 else "FAILED",
                "level": "JAVAC_COMPILE",
                "exit_code": run.returncode,
                "diagnostic_sha256": hashlib.sha256(run.stderr).hexdigest(),
            }
        elif packet.language == "TYPESCRIPT" and node_executable:
            request = (root / "src/presentation/HttpRequest.ts").resolve().as_uri()
            handler = (root / "src/presentation/RequestHandler.ts").resolve().as_uri()
            script = (
                f"import {{HttpRequest}} from {json.dumps(request)};\n"
                f"import {{RequestHandler}} from {json.dumps(handler)};\n"
                f"for(const [value,expected] of {json.dumps(EXAMPLES[scenario])}) {{ "
                "const response=RequestHandler.handle(new HttpRequest(value)); "
                "if(response.status!==200 || response.body!==expected) "
                "throw Error('HTTP fixture failed'); }\n"
            )
            run = subprocess.run(
                [str(node_executable), "--experimental-strip-types", "--input-type=module"],
                input=script.encode(),
                cwd=working,
                capture_output=True,
                timeout=60,
            )
            native = {
                "status": "PASSED" if run.returncode == 0 else "FAILED",
                "level": "NODE_TYPE_STRIPPED_HTTP_RUNTIME_TESTS",
                "exit_code": run.returncode,
                "test_examples": 3,
                "typecheck": "NOT_RUN_TYPESCRIPT_COMPILER_UNAVAILABLE",
            }
    valid = (
        built.is_valid
        and built.is_complete
        and graph.is_valid
        and graph.is_complete
        and all(spans.values())
        and built.statistics.files_with_parse_errors == 0
        and digest(built.iam) == digest(replay.iam)
        and bool(graph.graph.edges)
        and not diagnostics["strategies"]["GRAPH_GUIDED"]["missing_evidence_reasons"]
        and native["status"] != "FAILED"
    )
    status = "VALID" if valid else "PARTIAL" if built.parsing.is_valid else "INVALID"
    receipt = sealed(
        {
            "schema_version": "holdout-technical-validation-v1",
            "blinded_id": packet.blinded_id,
            "packet_fingerprint": packet.fingerprint,
            "technical_status": status,
            "intake_succeeded": True,
            "parser_valid": built.parsing.is_valid,
            "iam_valid": built.is_valid,
            "iam_complete": built.is_complete,
            "source_spans_resolved": spans,
            "graph_valid": graph.is_valid,
            "graph_complete": graph.is_complete,
            "graph_nodes": len(graph.graph.nodes),
            "graph_edges": len(graph.graph.edges),
            "dependency_extraction_replay_equal": digest(built.iam) == digest(replay.iam),
            "parser_versions": {
                f.parser.language.value: f.parser.model_dump(mode="json")
                for f in built.parsing.files
                if f.parser
            },
            "iam_fingerprint": digest(built.iam),
            "statistics": built.statistics.model_dump(mode="json"),
            "resolver_diagnostics": dict(Counter(d.code.value for d in built.diagnostics)),
            "native_validation": native,
            "technical_status_policy": "All source parses, valid and complete IAM/graph, "
            "target/spans/dependencies "
            "present, replay equal, native checks pass if available. "
            "Resolver completeness is reported separately; external stdlib "
            "implementations are not required evidence.",
            "semantic_truth": "NOT_ESTABLISHED_BY_TECHNICAL_VALIDATION",
        }
    )
    return receipt, diagnostics


def verify_file_freeze(root: Path, freeze: dict[str, Any]) -> None:
    if freeze["fingerprint"] != digest({k: v for k, v in freeze.items() if k != "fingerprint"}):
        raise ValueError("freeze fingerprint mismatch")
    for relative, expected in freeze["files"].items():
        path = (root / relative).resolve()
        if (
            not path.is_relative_to(root.resolve())
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("frozen artifact changed or path escaped")
    actual = {
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and p.name not in {"sample-freeze-v1.json", "private-freeze-v1.json"}
    }
    if actual != set(freeze["files"]):
        raise ValueError("frozen inventory contains added or missing files")


def construct_holdout(
    public: Path,
    private: Path,
    seed: bytes,
    p014_commit: str,
    p013_ids: set[str],
    protocol: dict[str, Any],
    guidance: dict[str, Any],
    analysis_plan: dict[str, Any],
    node_executable: Path | None = None,
    javac_executable: Path | None = None,
    construction_lineage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if public.exists() or private.exists():
        raise ValueError("existing prospective construction/freeze must never be overwritten")
    public.mkdir(parents=True)
    private.mkdir(parents=True, mode=0o700)
    if construction_lineage is not None:
        write_new(public / "lineage-v1.json", construction_lineage)
    for directory in ("packets", "mutation-receipts", "review/A", "review/B"):
        (private / directory).mkdir(parents=True)
    records = []
    pairs = []
    packets = []
    receipts = []
    context_rows = []
    for rule in RULES:
        operator = next(o for o in operators() if o.rule_id == rule)
        for language_value in LANGUAGES:
            language: Language = "JAVA" if language_value == "JAVA" else "TYPESCRIPT"
            for scenario in SCENARIOS:
                members = []
                hashes = []
                validation_hashes = []
                for mutation in (False, True):
                    case_id, packet = make_packet(seed, rule, language, scenario, mutation)
                    workspace = private / "sources" / packet.blinded_id
                    for evidence in packet.evidence:
                        path = workspace / evidence.path
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(evidence.text)
                    validation, context = validate_fixture(
                        workspace, packet, scenario, node_executable, javac_executable
                    )
                    write_new(private / "packets" / (packet.blinded_id + ".json"), packet)
                    records.append(
                        CaseRecord(
                            case_id=case_id,
                            blinded_id=packet.blinded_id,
                            rule_id=rule,
                            language=language,
                            project_alias=packet.project_alias,
                            technical_status=validation["technical_status"],
                            packet_fingerprint=packet.fingerprint,
                            validation_fingerprint=validation["fingerprint"],
                            context_diagnostics_fingerprint=context["fingerprint"],
                        )
                    )
                    packets.append(packet)
                    receipts.append(validation)
                    context_rows.append(context)
                    members.append(case_id)
                    hashes.append({e.path: e.sha256 for e in packet.evidence})
                    validation_hashes.append(validation["fingerprint"])
                pairs.append(
                    PrivatePair(
                        pair_id="hp-" + opaque_id(seed, "pair", (rule, language, scenario))[:32],
                        rule_id=rule,
                        language=language,
                        origin_project=f"{language.lower()}-{scenario}",
                        operator_id=operator.operator_id,
                        control_case_id=members[0],
                        mutation_case_id=members[1],
                        before_hashes=hashes[0],
                        after_hashes=hashes[1],
                        control_validation_fingerprint=validation_hashes[0],
                        mutation_validation_fingerprint=validation_hashes[1],
                    )
                )
    sample = seal(HoldoutSample, cases=tuple(sorted(records, key=lambda c: c.case_id)))
    validate_pairs(sample, tuple(pairs), p013_ids)
    for pair in pairs:
        write_new(
            private / "mutation-receipts" / (pair.pair_id + ".json"),
            sealed(
                {
                    "schema_version": "private-mutation-validation-v1",
                    "operator_id": pair.operator_id,
                    "operator_version": "1.0.0",
                    "pair_id": pair.pair_id,
                    "source_before_sha256": pair.before_hashes,
                    "source_after_sha256": pair.after_hashes,
                    "control_validation_fingerprint": pair.control_validation_fingerprint,
                    "mutation_validation_fingerprint": pair.mutation_validation_fingerprint,
                    "source_materially_changed": True,
                    "preserved_invariants": [
                        "Language/framework",
                        "HTTP contract",
                        "Business results",
                        "Target component type",
                        "Surrounding source",
                    ],
                    "neighborhood_change_reason": "Only the predefined target rule transformation",
                    "semantic_truth_established": False,
                }
            ),
        )
    provenance = sealed(
        {
            "schema_version": "private-holdout-construction-v1",
            "dataset_id": VERSION,
            "private_blinding_seed": seed.hex(),
            "pairs": [p.model_dump(mode="json") for p in pairs],
            "construction_intent_only": {"MUTATION_CANDIDATE": 50, "MATCHED_CONTROL": 50},
            "operators": [o.model_dump(mode="json") for o in operators()],
            "construction_access": {
                k: False
                for k in (
                    "p014_ai_answers",
                    "new_human_labels",
                    "reviewer_answers",
                    "hybrid_predictions",
                    "structural_v2_predictions",
                    "semantic_predictions",
                    "detector_predictions",
                )
            },
            "allowed_inputs": [
                "Original fixture source",
                "Architecture contract",
                "Parser/IAM",
                "Dependency graph",
                "Versioned recipe",
                "Engineering validation",
            ],
            "p014_commit": p014_commit,
            "construction_code_fingerprints": {
                "fixture_recipes_and_contracts": digest(
                    (Path(__file__).parents[1] / "benchmark/semantic_holdout.py").read_text()
                ),
                "construction_validation_and_freeze": digest(Path(__file__).read_text()),
            },
        }
    )
    write_new(private / "provenance-v1.json", provenance)
    bundles = {}
    for slot in ("A", "B"):
        order = sorted(packets, key=lambda p: opaque_id(seed, "review-order-" + slot, p.blinded_id))
        bundle = sealed(
            {
                "schema_version": "blank-independent-human-bundle-v1",
                "reviewer_slot": slot,
                "status": "WAITING_FOR_REAL_INDEPENDENT_HUMAN",
                "packets": [p.model_dump(mode="json") for p in order],
                "protocol": protocol,
                "guidance": guidance,
            }
        )
        write_new(private / "review" / slot / "bundle-v1.json", bundle)
        bundles[slot] = bundle["fingerprint"]
    write_new(public / "sample-v1.json", sample)
    write_new(public / "validation-receipts-v1.json", sealed({"cases": receipts}))
    write_new(public / "context-diagnostics-v1.json", sealed({"cases": context_rows}))
    write_new(public / "review-protocol-v1.json", protocol)
    write_new(public / "reviewer-guidance-v1.json", guidance)
    write_new(public / "analysis-plan-v1.json", analysis_plan)
    corpus = sealed(
        {
            "dataset_id": VERSION,
            "source_kind": "NEW_ORIGINAL_CONTROLLED_FIXTURES",
            "projects": [
                {
                    "project_id": f"{lang.lower()}-{scenario}",
                    "language": lang,
                    "framework": "Original HTTP request/response fixture",
                    "cases": 10,
                }
                for lang in LANGUAGES
                for scenario in SCENARIOS
            ],
            "third_party_source_copied": False,
            "oss_repository_overlap": [],
            "p013_case_overlap": [],
            "construction_target_only": {"mutation": 50, "control": 50},
            "human_truth_status": "NONE",
            "semantic_prevalence_estimate": False,
            "license_provenance": (
                "Original project-authored private source; no third-party redistribution"
            ),
        }
    )
    write_new(public / "corpus-v1.json", corpus)
    private_files = {
        str(p.relative_to(private)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(private.rglob("*"))
        if p.is_file()
    }
    private_freeze = sealed(
        {"files": private_files, "provenance_fingerprint": provenance["fingerprint"]}
    )
    write_new(private / "private-freeze-v1.json", private_freeze)
    public_files = {
        str(p.relative_to(public)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(public.rglob("*"))
        if p.is_file()
    }
    freeze = sealed(
        {
            "dataset_id": VERSION,
            "status": "WAITING_FOR_HUMAN_REVIEW",
            "p014_commit": p014_commit,
            "sample_fingerprint": sample.fingerprint,
            "corpus_fingerprint": corpus["fingerprint"],
            "private_freeze_fingerprint": private_freeze["fingerprint"],
            "private_provenance_fingerprint": provenance["fingerprint"],
            "reviewer_bundle_fingerprints": bundles,
            "analysis_plan_fingerprint": analysis_plan["fingerprint"],
            "files": public_files,
            "technical_counts": dict(Counter(c.technical_status for c in sample.cases)),
            "construction_counts_only": {
                "intended_mutation_candidates": 50,
                "matched_controls": 50,
            },
            "matched_pairs": 50,
            "human_labels": "NONE",
            "live_ai_calls": 0,
            "structural_v2": "NOT_RUN",
            "hybrid": "NOT_RUN",
            "security_analysis": "NOT_RUN",
        }
    )
    write_new(public / "sample-freeze-v1.json", freeze)
    verify_file_freeze(public, freeze)
    verify_file_freeze(private, private_freeze)
    return freeze
