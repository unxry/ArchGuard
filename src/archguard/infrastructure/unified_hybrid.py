"""P020 offline coordinator and capability-limited, label-blind workers."""

import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast

from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer, iam_fingerprint
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.builder import GraphBuilder
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.hybrid.calibration import numeric_values
from archguard.architecture.hybrid.features import extract_features
from archguard.architecture.hybrid.prospective_alignment import VERSION as ALIGNMENT
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import ContextSelectionConfig, StructuredLLMRequest
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.benchmark import component_holdout as structural
from archguard.benchmark import semantic_holdout as semantic
from archguard.benchmark import unified_hybrid as domain
from archguard.benchmark.materialization import EvaluationAnchor
from archguard.benchmark.models import Locator, Subjects
from archguard.benchmark.oss.models import canonical, digest, seal
from archguard.benchmark.prospective_materialization import ProspectiveMaterializeEvaluationCase
from archguard.benchmark.semantic_positive_experiment import SYSTEM_PROMPT, token_estimate
from archguard.benchmark.semantic_preflight import QUESTIONS, PricingAssumption
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    ReviewerBBundle,
    ReviewerBSubmission,
)
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure import component_holdout as historical
from archguard.infrastructure.calibration import load_policy
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.semantic_holdout import ARCHITECTURE, SCENARIO_DESCRIPTIONS
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    append_sealed,
    evaluation_io,
)
from archguard.infrastructure.semantic_positive_offline import audit_metadata
from archguard.infrastructure.semantic_preflight import wire_payload
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

BASE = Path("experiments/unified-hybrid")
PRIVATE = BASE / "private" / domain.VERSION
COORDINATOR = PRIVATE / "coordinator"
FINAL = PRIVATE / "final"
DEV = PRIVATE / "development"
ALIGNMENT_FREEZE = BASE / "p020-alignment-freeze-v2.json"
AUDIT = BASE / "p020-chronology-v1.jsonl"
P015 = historical.P015
P015_PRIVATE = historical.P015_PRIVATE
P019 = historical.PRIVATE
PRICING = Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json")
IMPLEMENTATION = (
    "src/archguard/benchmark/unified_hybrid.py",
    "src/archguard/infrastructure/unified_hybrid.py",
    "scripts/prompt020_offline.py",
    "tests/benchmark/test_unified_hybrid.py",
)


def sha(path: Path) -> str:
    if path.name.startswith(".env"):
        raise PermissionError("credentials are not scientific inputs")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict[str, Any]:
    return historical.read(path)


def event(name: str, binding: str) -> None:
    previous = "0" * 64
    if AUDIT.exists():
        previous = json.loads(AUDIT.read_text().splitlines()[-1])["fingerprint"]
    value = {
        "event": name,
        "utc": datetime.now(UTC).isoformat(),
        "binding": binding,
        "head": git_head(),
        "previous": previous,
    }
    with AUDIT.open("a") as stream:
        stream.write(canonical(value | {"fingerprint": digest(value)}) + "\n")


def git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()


def alignment_gate() -> dict[str, Any]:
    frozen = read(ALIGNMENT_FREEZE)
    placement_path = BASE / "p020-alignment-placement-freeze-v1.json"
    placement = read(placement_path) if placement_path.exists() else None
    expected = (
        placement["files"]
        if placement
        else {
            name: frozen[field]
            for name, field in (
                (
                    "src/archguard/architecture/hybrid/prospective_alignment.py",
                    "implementation_sha256",
                ),
                ("tests/hybrid/test_prospective_alignment.py", "tests_sha256"),
            )
        }
    )
    for name, value in expected.items():
        if sha(Path(name)) != value:
            raise ValueError("alignment implementation/test drift")
    commit = subprocess.check_output(
        ["git", "log", "-1", "--format=%H", "--", str(ALIGNMENT_FREEZE)], text=True
    ).strip()
    committed = subprocess.check_output(["git", "show", commit + ":" + str(ALIGNMENT_FREEZE)])
    if committed != ALIGNMENT_FREEZE.read_bytes():
        raise ValueError("alignment freeze must be committed before science")
    if placement:
        if placement["generation_alignment_fingerprint"] != frozen["fingerprint"]:
            raise ValueError("alignment placement lineage drift")
        bound = subprocess.check_output(["git", "show", "HEAD:" + str(placement_path)])
        if bound != placement_path.read_bytes():
            raise ValueError("alignment placement must be committed")
    return frozen | {"commit": commit}


def freeze_public(name: str, value: dict[str, Any]) -> dict[str, Any]:
    if (BASE / name).exists():
        old = read(BASE / name)
        if canonical({k: v for k, v in old.items() if k != "fingerprint"}) != canonical(value):
            raise ValueError("completed public freeze cannot be rewritten")
        return old
    result = append_sealed(BASE / name, value)
    event(name, result["fingerprint"])
    return result


def prior_inventory() -> dict[str, str]:
    roots = (Path("experiments/semantic-holdout"), Path("experiments/component-holdout"))
    inventory = {str(p): sha(p) for root in roots for p in root.rglob("*") if p.is_file()}
    inventory[str(historical.POLICY)] = sha(historical.POLICY)
    return inventory


def prepare_plan() -> dict[str, Any]:
    alignment = alignment_gate()
    if (BASE / "p020-plan-v1.json").exists():
        raise ValueError("plan already frozen")
    seed = os.urandom(32).hex()
    guards = prior_inventory()
    for name, expected in alignment["prior_seals"].items():
        if name == str(historical.POLICY):
            actual = load_policy(Path(name)).fingerprint
        else:
            value = json.loads(Path(name).read_bytes())
            actual = digest({k: v for k, v in value.items() if k != "fingerprint"})
        if actual != expected:
            raise ValueError("prior seal drift")
    append_sealed(COORDINATOR / "private-plan.json", {"seed": seed, "old_bytes": guards})
    return freeze_public(
        "p020-plan-v1.json",
        {
            "version": domain.VERSION,
            "alignment_commit": alignment["commit"],
            "alignment_fingerprint": alignment["fingerprint"],
            "seed_fingerprint": digest(seed),
            "old_bytes_fingerprint": digest(guards),
            "initial_head": alignment["initial_head"],
            "workspace_exception": alignment["workspace_exception"],
            "holdout": {
                "cases": 300,
                "pairs": 150,
                "rules": domain.RULES,
                "per_rule": 20,
                "pairs_per_rule": 10,
                "languages": {"JAVA": 150, "TYPESCRIPT": 150},
                "structural": 200,
                "semantic": 100,
            },
            "construction": (
                "FRESH_NAMESPACES_SOURCE_IDENTITIES; "
                "P019_RAW_TOPOLOGY_OPERATORS_INDEX5_9; "
                "P015_SEMANTIC_OPERATORS_UNCHANGED"
            ),
            "protocol": domain.protocol(),
            "hybrid": domain.hybrid_protocol(),
            "ablations": domain.ABLATIONS,
            "human_review": {
                "categories": ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
                "independent": ["A", "B"],
                "adjudication": "THIRD_HUMAN_CATEGORICAL_CONFLICTS_ONLY",
                "semantic_truth": "HUMAN_ONLY; CONSTRUCTION_INTENT_IS_NOT_TRUTH",
                "next_stage": "P021_HUMAN_REVIEW",
            },
            "implementation": {IMPLEMENTATION[0]: sha(Path(IMPLEMENTATION[0]))},
            "paid_execution_approved": False,
        },
    )


def locator(iam: ArchitectureModel, name: str, path: str | None = None) -> dict[str, Any]:
    nodes = [
        n
        for n in iam.nodes
        if n.kind == NodeKind.CLASS
        and n.name == name
        and n.source_location
        and (path is None or n.source_location.file_path == path)
    ]
    if len(nodes) != 1:
        raise ValueError("target must resolve uniquely")
    n = nodes[0]
    assert n.source_location is not None
    return Locator(
        path=n.source_location.file_path,
        language=n.language,
        qualified_name=n.qualified_name,
        kind=NodeKind.CLASS,
    ).model_dump(mode="json")


def renamed_semantic(
    rule: str, language: str, index: int, mutation: bool, case: str
) -> tuple[dict[str, str], str, str]:
    originals = semantic.fixture_sources(
        rule, cast(Literal["JAVA", "TYPESCRIPT"], language), semantic.SCENARIOS[index], mutation
    )
    names = {Path(p).stem: Path(p).stem + case[:12] for p in originals}

    def rename(text: str) -> str:
        for old, new in names.items():
            text = re.sub(r"\b" + old + r"\b", new, text)
        return text.replace("fixture.", "fresh" + case[:12] + ".").replace(
            "ledger.txt", "ledger" + case[:12] + ".txt"
        )

    files = {rename(p): rename(text) for p, text in originals.items()}
    contract = (
        rename(ARCHITECTURE)
        + " Business contract: "
        + SCENARIO_DESCRIPTIONS[semantic.SCENARIOS[index]]
    )
    return files, names[semantic.target_name(rule)], contract


def source_inventory(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(root.rglob("*")) if p.is_file()}


def old_identities() -> dict[str, set[str]]:
    # Identity/content metadata only; no previous predictions or correctness.
    old = read(P019 / "independence-v1.json")
    identities: set[str] = set()
    hashes: set[str] = set()

    def collect(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for k, v in value.items():
                collect(v, k)
        elif isinstance(value, list):
            for v in value:
                collect(v, key)
        elif isinstance(value, str):
            if "case" in key or "id" in key:
                identities.add(value)
            if len(value) == 64:
                hashes.add(value)

    collect(old)
    execution = read(P019 / "execution/manifest-v1.json")
    identities.update(r["case_id"] for r in execution["rows"])
    sample = semantic.HoldoutSample.model_validate_json((P015 / "sample-v1.json").read_bytes())
    identities.update(c.case_id for c in sample.cases)
    identities.update(c.project_alias for c in sample.cases)
    for root in (P019 / "sources", P015_PRIVATE / "sources"):
        hashes.update(sha(p) for p in root.rglob("*") if p.is_file())
    return {"ids": identities, "units": hashes}


def construct_final() -> dict[str, Any]:
    alignment_gate()
    plan = read(BASE / "p020-plan-v1.json")
    seed = read(COORDINATOR / "private-plan.json")["seed"]
    if digest(seed) != plan["seed_fingerprint"]:
        raise ValueError("seed drift")
    old = old_identities()
    execution: list[dict[str, Any]] = []
    common: list[dict[str, Any]] = []
    truths: list[dict[str, Any]] = []
    intents: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    packets: list[dict[str, Any]] = []
    for rule in domain.RULES:
        for language in ("JAVA", "TYPESCRIPT"):
            for index in range(5):
                for positive in (False, True):
                    case = structural.identity(seed, "scientific", rule, language, index, positive)
                    eid = structural.identity(seed, "execution", case)
                    project = structural.identity(seed, "project", case)
                    repo_family = structural.identity(seed, "repository-family", case)
                    pair = structural.identity(seed, "pair", rule, language, index)
                    root = FINAL / "inputs/sources" / eid
                    is_semantic = rule.startswith("ARCH2")
                    if is_semantic:
                        files, target, contract = renamed_semantic(
                            rule, language, index, positive, eid
                        )
                        spec = {"version": "1.0", "architecture": {}, "rules": []}
                    else:
                        facts = structural.topology(rule, index + 5, positive)
                        files = structural.sources(eid, language, facts)
                        spec = structural.specification(rule)["spec"]
                        contract = canonical(spec)
                    for relative, text in files.items():
                        path = root / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        with path.open("x") as stream:
                            stream.write(text)
                        if sha(path) in old["units"]:
                            raise ValueError("prior source unit reused")
                    iam, receipt = historical.build(root, project)
                    raw_graph = GraphBuilder().build(iam, GraphAnalysisConfig())
                    if is_semantic:
                        locators = [locator(iam, target)]
                    else:
                        observed = historical.normalized(iam)
                        if (
                            observed["edges"] != facts["edges"]
                            or observed["nodes"] != facts["nodes"]
                        ):
                            raise ValueError("new topology/source mismatch")
                        if any(observed["methods"][i] != n for i, n in enumerate(facts["methods"])):
                            raise ValueError("method-count construction mismatch")
                        locators = [
                            locator(iam, "Unit" + eid[:12] + "N" + str(i)) for i in facts["target"]
                        ]
                        oracle = structural.oracle(rule, facts, structural.specification(rule))
                        if oracle != positive:
                            raise ValueError("independent oracle failed")
                        truths.append(
                            dict(
                                scientific_case_id=case,
                                category="POSITIVE" if oracle else "NEGATIVE",
                                facts=facts,
                                oracle_spec=structural.specification(rule),
                            )
                        )
                    inventory = source_inventory(root)
                    subjects = dict(locators=locators, directed=len(locators) == 2)
                    input_row = dict(
                        execution_id=eid,
                        project_alias=project,
                        target_rule_id=rule,
                        language=language,
                        iam_file=eid + ".json",
                        source_root=eid,
                        subjects=subjects,
                        spec=spec,
                        architecture_contract=contract,
                        source_snapshot_fingerprint=digest(inventory),
                        iam_fingerprint=iam_fingerprint(iam),
                        graph_fingerprint=digest(raw_graph.graph),
                    )
                    audit_metadata(input_row)
                    append_sealed(
                        FINAL / "inputs/iam" / (eid + ".json"),
                        dict(iam=iam.model_dump(mode="json")),
                    )
                    execution.append(input_row)
                    common.append(
                        dict(
                            scientific_case_id=case,
                            project_id=str(iam.project.id),
                            repository_family_id=repo_family,
                            language=language,
                            target_rule_id=rule,
                            target_rule_family=domain.family(rule),
                            source_snapshot_fingerprint=digest(inventory),
                            iam_fingerprint=iam_fingerprint(iam),
                            graph_fingerprint=digest(raw_graph.graph),
                            architecture_contract_fingerprint=digest(contract),
                            context_evidence_manifest_fingerprint=digest(
                                dict(
                                    subjects=subjects, source_inventory=inventory, contract=contract
                                )
                            ),
                            execution_safe_id=eid,
                        )
                    )
                    intents.append(
                        dict(
                            scientific_case_id=case,
                            pair_id=pair,
                            rule=rule,
                            language=language,
                            intended_positive=positive,
                            operator=next(
                                (o.operator_id for o in semantic.operators() if o.rule_id == rule),
                                "P019_INDEPENDENT_TOPOLOGY",
                            ),
                        )
                    )
                    validation.append(dict(execution_id=eid, **receipt))
                    if is_semantic:
                        blind = "hb-" + structural.identity(seed, "human", case)
                        evidence = tuple(
                            semantic.SourceEvidence(
                                evidence_id="ev-" + digest((blind, p))[:24],
                                path=p,
                                text=t,
                                sha256=hashlib.sha256(t.encode()).hexdigest(),
                            )
                            for p, t in sorted(files.items())
                        )
                        packet = seal(
                            semantic.BlindedPacket,
                            blinded_id=blind,
                            rule_id=rule,
                            language=language,
                            project_alias=project,
                            target_path=locators[0]["path"],
                            target_component=target,
                            architecture_contract=contract,
                            evidence=evidence,
                        )
                        audit_metadata(packet.model_dump(mode="json"))
                        append_sealed(
                            FINAL / "review/packets" / (blind + ".json"),
                            packet.model_dump(mode="json"),
                        )
                        packets.append(
                            dict(
                                blinded_id=blind,
                                fingerprint=packet.fingerprint,
                                source_fingerprint=digest(inventory),
                            )
                        )
                        append_sealed(
                            COORDINATOR / "review-map" / (blind + ".json"),
                            dict(scientific_case_id=case, execution_id=eid),
                        )
    if len(execution) != 300 or len({r["execution_id"] for r in execution}) != 300:
        raise ValueError("300 unique final cases required")
    if {r["scientific_case_id"] for r in common} & old["ids"]:
        raise ValueError("old identity reused")
    if {r["project_alias"] for r in execution} & old["ids"]:
        raise ValueError("old project reused")
    components = {
        "execution": append_sealed(
            FINAL / "inputs/manifest.json",
            dict(rows=sorted(execution, key=lambda r: digest(r["execution_id"]))),
        ),
        "cases": append_sealed(COORDINATOR / "final-cases.json", dict(rows=common)),
        "structural_truth": append_sealed(
            COORDINATOR / "structural-truth.json",
            dict(rows=truths, oracle="INDEPENDENT_RAW_SPEC_ADJACENCY_MATH; NO_COMPONENT"),
        ),
        "intent": append_sealed(
            COORDINATOR / "construction-intent.json", dict(rows=intents, semantic_truth=False)
        ),
        "validation": append_sealed(
            COORDINATOR / "validation.json",
            dict(rows=validation, native=historical.native_validation(FINAL / "inputs/sources")),
        ),
        "packets": append_sealed(FINAL / "review/packet-inventory.json", dict(rows=packets)),
    }
    template: list[dict[str, Any]] = [
        dict(blinded_id=p["blinded_id"], decision=None, rationale="", evidence=[], note="")
        for p in sorted(packets, key=lambda p: digest(p["blinded_id"]))
    ]
    for reviewer in ("A", "B"):
        append_sealed(
            FINAL / "review" / reviewer / "submission-template.json",
            dict(reviewer=reviewer, rows=template),
        )
    review = append_sealed(
        FINAL / "review/protocol.json",
        dict(
            version="p020-independent-human-review-v1",
            assignment="ONE_INDEPENDENT_HUMAN_PER_A_B; NO_ACCESS_TO_OTHER_ANSWERS",
            categories=["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
            instructions=(
                "Judge supplied target rule from source/contract only. Record "
                "human rationale and supplied evidence references. No model aid "
                "or access to paired construction. Naming alone insufficient. "
                "Uncertainty and applicability distinct."
            ),
            adjudicator=(
                "THIRD_INDEPENDENT_HUMAN_ONLY_CATEGORICAL_CONFLICTS; LATER_FROZEN_CONFLICT_PACKET"
            ),
            packet_fingerprint=components["packets"]["fingerprint"],
            human_labels_created=False,
        ),
    )
    guidance = append_sealed(
        FINAL / "review/guidance.json",
        dict(
            instructions=(
                "Judge independently from source and contract; cite evidence_id and valid lines. "
                "Require human rationale for all categories. No AI assistance or comparison of "
                "packets. A/B must be distinct humans attesting REAL_HUMAN_INDEPENDENT_REVIEW."
            ),
            categories=dict(
                POSITIVE="Supported target violation",
                NEGATIVE="Sufficient evidence without target violation",
                UNCERTAIN="Evidence insufficient/ambiguous",
                OUT_OF_SCOPE="Question does not apply",
            ),
        ),
    )
    packet_models = tuple(
        semantic.BlindedPacket.model_validate_json(
            (FINAL / "review/packets" / (p["blinded_id"] + ".json")).read_bytes()
        )
        for p in packets
    )
    assignments = []
    for slot, model, submission in (
        ("A", ReviewerABundle, ReviewerASubmission),
        ("B", ReviewerBBundle, ReviewerBSubmission),
    ):
        bundle = seal(
            model,
            schema_version="blank-independent-human-bundle-v1",
            reviewer_slot=slot,
            status="WAITING_FOR_REAL_INDEPENDENT_HUMAN",
            packets=packet_models,
            protocol=review,
            guidance=guidance,
        )
        append_sealed(FINAL / "review" / slot / "bundle.json", bundle.model_dump(mode="json"))
        append_sealed(
            FINAL / "review" / slot / "submission-schema.json",
            dict(schema=submission.model_json_schema()),
        )
        components["reviewer_" + slot] = {"fingerprint": bundle.fingerprint}
        assignments.append(
            dict(
                reviewer_slot=slot,
                bundle_fingerprint=bundle.fingerprint,
                packet_count=100,
                independent=True,
            )
        )
    assignment = append_sealed(
        FINAL / "review/assignment-manifest.json",
        dict(rows=assignments, third_human="CATEGORICAL_CONFLICTS_ONLY"),
    )
    inventory = append_sealed(
        COORDINATOR / "final-inventory.json", dict(files=source_inventory(FINAL / "inputs"))
    )
    return freeze_public(
        "p020-final-holdout-freeze-v1.json",
        dict(
            counts=dict(
                cases=300,
                pairs=len({r["pair_id"] for r in intents}),
                JAVA=150,
                TYPESCRIPT=150,
                intended_positive=150,
                controls=150,
                per_rule=dict(Counter(r["rule"] for r in intents)),
                families=dict(Counter(domain.family(r["rule"]) for r in intents)),
            ),
            fingerprints={k: v["fingerprint"] for k, v in components.items()},
            inventory_fingerprint=inventory["fingerprint"],
            review_protocol_fingerprint=review["fingerprint"],
            review_assignment_fingerprint=assignment["fingerprint"],
            overlaps=dict(P010_P011=0, P015=0, P019=0, development_projects=0),
            IAM=dict(VALID=300, PARTIAL=0, INVALID=0),
            oracle_independent=True,
            component_used_as_truth=False,
            semantic_truth_created=False,
            alignment_commit=plan["alignment_commit"],
            human_review_ready=True,
        ),
    )


def prepare_development() -> dict[str, Any]:
    alignment_gate()
    rows, labels = [], []
    old = read(P019 / "execution/manifest-v1.json")
    # Coordinator alone can consume known development labels, never old correctness.
    truth = {r["case_id"]: r["truth"] for r in read(P019 / "truth-v1.json")["rows"]}
    for r in old["rows"]:
        case = r["case_id"]
        iam_dict = read(P019 / "execution/iam" / r["iam_file"])
        append_sealed(DEV / "inputs/iam" / (case + ".json"), dict(iam=iam_dict["iam"]))
        rows.append(
            dict(
                execution_id=case,
                project_alias=case,
                target_rule_id=r["rule"],
                language=r["language"],
                iam_file=case + ".json",
                source_root=str((P019 / "sources" / case).resolve()),
                subjects=r["subjects"],
                spec=r["spec"],
                architecture_contract=canonical(r["spec"]),
                iam_fingerprint=r["iam_fingerprint"],
            )
        )
        labels.append(
            dict(
                scientific_case_id=case,
                project_id=str(iam_dict["iam"]["project"]["id"]),
                target_rule_id=r["rule"],
                language=r["language"],
                category="POSITIVE" if truth[case] else "NEGATIVE",
            )
        )
    human = read(
        Path(
            "experiments/semantic-holdout/private/final-human-ground-truth-v1/ground-truth-v1.json"
        )
    )
    human_labels = {r["scientific_case_id"]: r["final_category"] for r in human["cases"]}
    sample = semantic.HoldoutSample.model_validate_json((P015 / "sample-v1.json").read_bytes())
    mapping = read(
        Path("experiments/semantic-holdout/private/p016-coordinator-v1/identity-map.json")
    )["execution_case_mapping"]
    normalized = read(
        Path("experiments/semantic-holdout/private/p016-live-v1/normalized-assessments.json")
    )
    assessments = [a for a in normalized["assessments"] if a["strategy"] == "GRAPH_GUIDED"]
    if len(assessments) != 100 or len({a["execution_case_id"] for a in assessments}) != 100:
        raise ValueError("100 unique accepted semantic assessments required")
    by_execution = {a["execution_case_id"]: a for a in assessments}
    reuse = []
    for c in sample.cases:
        packet = semantic.BlindedPacket.model_validate_json(
            (P015_PRIVATE / "packets" / (c.blinded_id + ".json")).read_bytes()
        )
        if packet.fingerprint != c.packet_fingerprint:
            raise ValueError("P015 packet drift")
        root = P015_PRIVATE / "sources" / c.blinded_id
        iam, _ = historical.build(root, c.project_alias)
        append_sealed(
            DEV / "inputs/iam" / (c.case_id + ".json"), dict(iam=iam.model_dump(mode="json"))
        )
        rows.append(
            dict(
                execution_id=c.case_id,
                project_alias=c.project_alias,
                target_rule_id=c.rule_id,
                language=c.language,
                iam_file=c.case_id + ".json",
                source_root=str(root.resolve()),
                subjects=dict(
                    locators=[locator(iam, packet.target_component, packet.target_path)],
                    directed=False,
                ),
                spec={"version": "1.0", "architecture": {}, "rules": []},
                architecture_contract=packet.architecture_contract,
                iam_fingerprint=iam_fingerprint(iam),
            )
        )
        labels.append(
            dict(
                scientific_case_id=c.case_id,
                project_id=str(iam.project.id),
                target_rule_id=c.rule_id,
                language=c.language,
                category=human_labels[c.case_id],
            )
        )
        a = by_execution[mapping[c.case_id]]
        reuse.append(
            dict(
                scientific_case_id=c.case_id,
                accepted_assessment=a,
                normalized_fingerprint=normalized["fingerprint"],
            )
        )
    if len(rows) != 280:
        raise ValueError("280 development cases required")
    audit_metadata(rows)
    manifest = append_sealed(
        DEV / "inputs/manifest.json",
        dict(rows=sorted(rows, key=lambda r: digest(r["execution_id"]))),
    )
    split = append_sealed(COORDINATOR / "development-split.json", domain.grouped_split(labels))
    reuse_freeze = append_sealed(COORDINATOR / "development-semantic-reuse.json", dict(rows=reuse))
    binary = sum(r["category"] in {"POSITIVE", "NEGATIVE"} for r in labels)
    if binary != 276:
        raise ValueError("276 binary and4 nonbinary required")
    final_projects = {r["project_id"] for r in read(COORDINATOR / "final-cases.json")["rows"]}
    if final_projects & {r["project_id"] for r in labels}:
        raise ValueError("final project overlap")
    by_split = {
        s: dict(
            cases=sum(r["split"] == s for r in split["rows"]),
            projects=len({r["project_id"] for r in split["rows"] if r["split"] == s}),
            categories=dict(Counter(r["category"] for r in split["rows"] if r["split"] == s)),
            rule_category=dict(
                Counter(
                    r["target_rule_id"] + ":" + r["category"]
                    for r in split["rows"]
                    if r["split"] == s
                )
            ),
            languages=dict(Counter(r["language"] for r in split["rows"] if r["split"] == s)),
        )
        for s in ("TRAIN", "VALIDATION")
    }
    return freeze_public(
        "p020-development-freeze-v1.json",
        dict(
            cases=280,
            structural=180,
            semantic=100,
            binary=276,
            nonbinary=4,
            projects=split["projects"],
            by_split=by_split,
            split_fingerprint=split["fingerprint"],
            manifest_fingerprint=manifest["fingerprint"],
            reuse_fingerprint=reuse_freeze["fingerprint"],
            semantic_reused=100,
            missing=0,
            duplicates=0,
            project_overlap=0,
            final_overlap=0,
            split_seed_fingerprint=digest(domain.GROUP_SEED),
            split_method=(
                "HASH_RANK_PROJECT_GROUPS; FIXED_RULE_CATEGORY_STRATA; NO_PERFORMANCE_OPTIMIZATION"
            ),
        ),
    )


def evidence_record(row: dict[str, Any], iam: ArchitectureModel, policy: Any) -> dict[str, Any]:
    start = perf_counter()
    spec = ArchitectureSpecification.model_validate(row["spec"])
    static = StaticConformanceAnalyzer().analyze(iam, spec)
    graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig(), spec)
    if not all((static.is_valid, static.is_complete, graph.is_valid, graph.is_complete)):
        raise ValueError("incomplete component evidence")
    materializer = ProspectiveMaterializeEvaluationCase(iam, static, graph, None)
    materializer.use_prospective_alignment()
    materialized = materializer.execute(
        EvaluationAnchor(
            repository_id=row["project_alias"],
            rule_id=row["target_rule_id"],
            subjects=Subjects.model_validate(row["subjects"]),
        )
    )
    base = extract_features(materialized.case, materialized.bundle)
    values = {f.name: f.value for f in base.values}
    for side in ("source", "target"):
        for name in ("Ca", "Ce", "I"):
            values[f"graph.{side}.{name}"] = next(
                f.value for f in materialized.features.values if f.name == f"graph.{side}.{name}"
            )
    rule = row["target_rule_id"]
    score = None
    static_state = "NOT_APPLICABLE"
    if rule in structural.STATIC_RULES:
        static_state = (
            "SUPPORTED" if any(f.rule_id == rule for f in static.findings) else "NOT_SUPPORTED"
        )
    graph_state = "NOT_APPLICABLE"
    if rule == "ARCH003":
        graph_state = (
            "SUPPORTED" if any(f.rule_id == rule for f in graph.findings) else "NOT_SUPPORTED"
        )
    elif rule.startswith("ARCH1"):
        score = policy.model.score(
            policy.preprocessor.transform(numeric_values(values, policy.preprocessor.feature_spec))
        )
        graph_state = "SUPPORTED" if score >= policy.threshold else "NOT_SUPPORTED"
    return dict(
        execution_id=row["execution_id"],
        target_rule_id=rule,
        iam_fingerprint=iam_fingerprint(iam),
        STATIC=static_state,
        GRAPH=graph_state,
        v2_score=score,
        v2_threshold=policy.threshold,
        static_proof=static_state == "SUPPORTED",
        cycle_proof=rule == "ARCH003" and graph_state == "SUPPORTED",
        existing_contract=materialized.bundle.model_dump(mode="json"),
        existing_features=values,
        static=static.model_dump(mode="json"),
        graph=graph.model_dump(mode="json"),
        seconds=perf_counter() - start,
    )


def evidence_worker(stream: str) -> dict[str, Any]:
    root = DEV if stream == "DEVELOPMENT" else FINAL
    inputs = root / "inputs"
    output = root / "evidence"
    allowed: tuple[Path, ...] = (
        inputs,
        historical.POLICY,
        BASE / "p020-plan-v1.json",
        ALIGNMENT_FREEZE,
    )
    if stream == "DEVELOPMENT":
        allowed += (P019 / "sources", P015_PRIVATE / "sources")
    with evaluation_io(Path("experiments"), allowed, output):
        manifest = read(inputs / "manifest.json")
        audit_metadata(manifest)
        policy = load_policy(historical.POLICY)
        if policy.fingerprint != structural.V2:
            raise ValueError("original V2 drift")
        records = []
        for row in manifest["rows"]:
            iam = ArchitectureModel.model_validate(read(inputs / "iam" / row["iam_file"])["iam"])
            records.append(evidence_record(row, iam, policy))
        expected = 280 if stream == "DEVELOPMENT" else 300
        if len(records) != expected or len({r["execution_id"] for r in records}) != expected:
            raise ValueError("evidence identity mismatch")
        static_output = append_sealed(
            output / "static-output.json",
            dict(
                rows=[
                    {k: r[k] for k in ("execution_id", "target_rule_id", "STATIC", "static_proof")}
                    for r in records
                ]
            ),
        )
        graph_output = append_sealed(
            output / "graph-output.json",
            dict(
                rows=[
                    {
                        k: r[k]
                        for k in (
                            "execution_id",
                            "target_rule_id",
                            "GRAPH",
                            "v2_score",
                            "v2_threshold",
                            "cycle_proof",
                        )
                    }
                    for r in records
                ]
            ),
        )
        return append_sealed(
            output / "evidence.json",
            dict(
                records=records,
                static_output_fingerprint=static_output["fingerprint"],
                graph_output_fingerprint=graph_output["fingerprint"],
                alignment_version=ALIGNMENT,
                input_fingerprint=manifest["fingerprint"],
                truth_accessed=False,
                intent_accessed=False,
                historical_correctness_accessed=False,
                semantic_heuristics=False,
            ),
        )


def candidate_values(
    record: dict[str, Any], assessment: domain.UnifiedAssessment | None, *, truncated: bool
) -> dict[str, float | None]:
    """Whitelist only actual component signals; no labels or identities enter predictors."""
    raw = record["existing_features"]
    values: dict[str, float | None] = {
        "static.positive": float(record["STATIC"] == "SUPPORTED"),
        "static.applicable": float(record["STATIC"] != "NOT_APPLICABLE"),
        "static.evidence_count": float(len(record["existing_contract"]["static"])),
        "static.unresolved": raw.get("quality.unresolved"),
        "graph.positive": float(record["GRAPH"] == "SUPPORTED"),
        "graph.applicable": float(record["GRAPH"] != "NOT_APPLICABLE"),
        "graph.v2_score": record["v2_score"],
    }
    for name in domain.GRAPH_FEATURES:
        value = raw.get("graph.cyclic" if name == "is_cyclic" else "graph." + name)
        values["graph." + name] = float(value) if value is not None else None
    decisions = {
        "llm.supported": "SUPPORTED",
        "llm.not_supported": "NOT_SUPPORTED",
        "llm.abstention": "INSUFFICIENT_CONTEXT",
        "llm.not_applicable": "NOT_APPLICABLE",
    }
    for name, state in decisions.items():
        values[name] = float(assessment.decision == state) if assessment is not None else None
    values["llm.evidence_available"] = (
        float(bool(assessment.evidence_refs)) if assessment is not None else None
    )
    values["llm.truncated"] = float(truncated) if assessment is not None else None
    if set(values) != {n for names in domain.FEATURES.values() for n in names}:
        raise ValueError("Hybrid whitelist mismatch")
    return values


def request_material(
    row: dict[str, Any], iam: ArchitectureModel, graph: Any, workspace: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    resolved = Subjects.model_validate(row["subjects"])
    from archguard.benchmark.resolver import LocatorResolver

    target_ids = LocatorResolver(iam).subjects(resolved)
    if not target_ids:
        raise ValueError("request target missing")
    config = ContextSelectionConfig(
        include_spec=False, include_discovery=False, include_metrics=False
    )
    target = LocatorResolver(iam).normalize(target_ids[0], NodeKind.CLASS).id
    for _budget_pass in range(4):
        pack = GraphGuidedContextBuilder().build(target, iam, graph, workspace, config)
        context = pack.untrusted_data() | {
            "architecture_contract": row["architecture_contract"],
            "target_subject_ids": [str(s) for s in target_ids],
            "context_status": {
                "truncated": pack.manifest.truncated,
                "diagnostics": [d.code for d in pack.manifest.diagnostics],
            },
        }
        rule = row["target_rule_id"]
        if not rule.startswith("ARCH2"):
            # Raw topology/metrics for selected subjects, never oracle truth or component opinions.
            selected = {s.node_id for s in pack.manifest.selected_nodes}
            context["graph_measurements"] = [
                m.model_dump(mode="json") for m in graph.metrics if m.node_id in selected
            ]
            context["target_constraint"] = row["spec"]
        audit_metadata(context)
        request_id = digest(
            dict(
                execution_id=row["execution_id"],
                context_fingerprint=digest(context),
                protocol_fingerprint=digest(domain.protocol()),
            )
        )
        request = StructuredLLMRequest(
            prompt_version="unified-structural-020-v1"
            if not rule.startswith("ARCH2")
            else "positive-semantic-assessment-016-v1-envelope020",
            schema_version="unified-assessment-020-v1",
            system_instructions=SYSTEM_PROMPT
            if rule.startswith("ARCH2")
            else domain.STRUCTURAL_SYSTEM,
            task=dict(
                request_id=request_id,
                target_rule_id=rule,
                target_question=QUESTIONS[rule]
                if rule.startswith("ARCH2")
                else domain.STRUCTURAL_QUESTIONS[rule],
                language=row["language"],
                subject_node_id=str(target),
            ),
            untrusted_context=context,
            response_schema=domain.UnifiedAssessment.model_json_schema(),
            timeout_seconds=90,
            max_output_tokens=2000,
        )
        visible = (
            request.system_instructions
            + canonical(dict(task=request.task, untrusted_context=context))
            + canonical(request.response_schema)
        )
        estimate, upper = token_estimate(visible)
        chars = len(canonical(context))
        if chars <= 20000 and upper <= 32768:
            break
        reduced = config.max_total_chars - max(chars - 20000, upper - 32768) - 256
        if reduced < 512:
            raise ValueError("supplemental context cannot fit frozen total budget")
        config = config.model_copy(update={"max_total_chars": reduced})
    else:
        raise ValueError("context budget did not converge within four offline passes")
    if not pack.fragments:
        raise ValueError("usable target source context required")
    material = dict(
        request_id=request_id,
        execution_id=row["execution_id"],
        context=context,
        context_manifest=pack.manifest.model_dump(mode="json"),
        wire_payload=wire_payload(request, "gpt-6-luna"),
    )
    metadata = dict(
        request_id=request_id,
        execution_id=row["execution_id"],
        target_rule_id=rule,
        language=row["language"],
        context_fingerprint=digest(context),
        request_fingerprint=digest(material["wire_payload"]),
        input_estimate=estimate,
        input_upper=upper,
        context_chars=chars,
        source_chars=sum(len(f.text) for f in pack.fragments),
        truncated=pack.manifest.truncated,
    )
    return material, metadata


def requests_worker(stream: str) -> dict[str, Any]:
    root = DEV if stream == "DEVELOPMENT" else FINAL
    inputs = root / "inputs"
    output = root / "requests"
    allowed: tuple[Path, ...] = (inputs, BASE / "p020-plan-v1.json")
    if stream == "DEVELOPMENT":
        allowed += (P019 / "sources", P015_PRIVATE / "sources")
    with evaluation_io(Path("experiments"), allowed, output):
        manifest = read(inputs / "manifest.json")
        audit_metadata(manifest)
        metadata = []
        for row in manifest["rows"]:
            if stream == "DEVELOPMENT" and row["target_rule_id"].startswith("ARCH2"):
                continue
            iam = ArchitectureModel.model_validate(read(inputs / "iam" / row["iam_file"])["iam"])
            graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
            root_source = (
                Path(row["source_root"])
                if stream == "DEVELOPMENT"
                else inputs / "sources" / row["source_root"]
            )
            with create_discovery().open(
                RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root_source))
            ) as repo:
                material, meta = request_material(row, iam, graph, repo.workspace)
            audit_request(material)
            path = output / "payloads" / (meta["request_id"] + ".json")
            if path.exists():
                if read(path)["fingerprint"] != digest(material):
                    raise ValueError("prepared payload cannot be changed")
            else:
                append_sealed(path, material)
            metadata.append(meta)
        metadata.sort(key=lambda r: digest(r["execution_id"]))
        expected = 180 if stream == "DEVELOPMENT" else 300
        if len(metadata) != expected or len({r["execution_id"] for r in metadata}) != expected:
            raise ValueError("request count mismatch")
        contexts = append_sealed(
            output / "contexts.json",
            dict(
                rows=[
                    {
                        k: r[k]
                        for k in (
                            "execution_id",
                            "context_fingerprint",
                            "context_chars",
                            "source_chars",
                            "truncated",
                        )
                    }
                    for r in metadata
                ]
            ),
        )
        return append_sealed(
            output / "manifest.json",
            dict(
                stream=stream,
                rows=metadata,
                context_manifest_fingerprint=contexts["fingerprint"],
                protocol_fingerprint=digest(domain.protocol()),
                truth_accessed=False,
                intent_accessed=False,
                leakage_findings=0,
            ),
        )


FORBIDDEN = {
    "positive",
    "negative",
    "mutation",
    "control",
    "pair_id",
    "pair_role",
    "category",
    "final_category",
    "truth",
    "oracle",
    "expected_direction",
    "expected_effect",
    "intended_positive",
    "construction_intent",
    "reviewer_answers",
}


def audit_request(value: Any) -> None:
    audit_metadata(value)
    if isinstance(value, dict):
        if FORBIDDEN & {str(k).lower() for k in value}:
            raise ValueError("request metadata leakage")
        for child in value.values():
            audit_request(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            audit_request(child)
    elif isinstance(value, str):
        if re.search(r"(?:\bsk-[A-Za-z0-9_-]{10,}|\bBearer\s+\S+)", value):
            raise ValueError("credential-like request material")
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except ValueError:
                return
            audit_request(decoded)


def run_workers(script: Path) -> dict[str, Any]:
    results = {}
    for stream in ("DEVELOPMENT", "FINAL"):
        for action in ("evidence", "requests"):
            root = DEV if stream == "DEVELOPMENT" else FINAL
            filename = "evidence.json" if action == "evidence" else "manifest.json"
            if not (root / action / filename).exists():
                subprocess.run(
                    [sys.executable, str(script), "--worker", action, "--stream", stream],
                    check=True,
                    env={
                        "PATH": os.environ.get("PATH", ""),
                        "PYTHONPATH": "src",
                        "PYTHONDONTWRITEBYTECODE": "1",
                    },
                    stdout=subprocess.DEVNULL,
                )
            result = read(root / action / filename)
            results[stream + "_" + action] = result["fingerprint"]
            freeze_public(
                "p020-" + stream.lower() + "-" + action + "-freeze-v1.json",
                dict(
                    fingerprint_binding=result["fingerprint"],
                    records=len(result["records"] if action == "evidence" else result["rows"]),
                    missing=0,
                    duplicates=0,
                    truth_accessed=False,
                    intent_accessed=False,
                    alignment_version=ALIGNMENT if action == "evidence" else None,
                    context_fingerprint=result.get("context_manifest_fingerprint"),
                    static_output_fingerprint=result.get("static_output_fingerprint"),
                    graph_output_fingerprint=result.get("graph_output_fingerprint"),
                ),
            )
    return results


def verify_worker(stream: str) -> dict[str, Any]:
    root = DEV if stream == "DEVELOPMENT" else FINAL
    allowed: tuple[Path, ...] = (
        root / "inputs",
        root / "evidence",
        root / "requests",
        historical.POLICY,
    )
    if stream == "DEVELOPMENT":
        allowed += (P019 / "sources", P015_PRIVATE / "sources")
    with evaluation_io(Path("experiments"), allowed, root / "verification-readonly"):
        manifest = read(root / "inputs/manifest.json")
        audit_metadata(manifest)
        policy = load_policy(historical.POLICY)
        if policy.fingerprint != structural.V2:
            raise ValueError("V2 fingerprint drift")
        evidence = read(root / "evidence/evidence.json")
        by_id = {r["execution_id"]: r for r in manifest["rows"]}
        for frozen in evidence["records"]:
            row = by_id[frozen["execution_id"]]
            iam = ArchitectureModel.model_validate(
                read(root / "inputs/iam" / row["iam_file"])["iam"]
            )
            replay = evidence_record(row, iam, policy)
            if canonical({k: v for k, v in replay.items() if k != "seconds"}) != canonical(
                {k: v for k, v in frozen.items() if k != "seconds"}
            ):
                raise ValueError("deterministic prospective evidence replay drift")
        req = read(root / "requests/manifest.json")
        for r in req["rows"]:
            payload = read(root / "requests/payloads" / (r["request_id"] + ".json"))
            audit_request(payload)
            row = by_id[r["execution_id"]]
            iam = ArchitectureModel.model_validate(
                read(root / "inputs/iam" / row["iam_file"])["iam"]
            )
            graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
            source = (
                Path(row["source_root"])
                if stream == "DEVELOPMENT"
                else root / "inputs/sources" / row["source_root"]
            )
            with create_discovery().open(
                RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(source))
            ) as repo:
                regenerated, meta = request_material(row, iam, graph, repo.workspace)
            if meta != r or digest(regenerated) != payload["fingerprint"]:
                raise ValueError("deterministic blinded request replay drift")
        return dict(
            status="P020_BLIND_REPLAY_PASS",
            stream=stream,
            evidence=len(evidence["records"]),
            requests=len(req["rows"]),
        )


def finish() -> dict[str, Any]:
    plan = read(BASE / "p020-plan-v1.json")
    if plan["protocol"] != json.loads(canonical(domain.protocol())) or plan["hybrid"] != json.loads(
        canonical(domain.hybrid_protocol())
    ):
        raise ValueError("prospective protocol implementation drift")
    pricing = PricingAssumption.model_validate_json(PRICING.read_bytes())
    dev = read(DEV / "requests/manifest.json")
    final = read(FINAL / "requests/manifest.json")
    review_inventory = append_sealed(
        COORDINATOR / "review-inventory.json", dict(files=source_inventory(FINAL / "review"))
    )
    review_receipt = freeze_public(
        "p020-review-material-freeze-v1.json",
        dict(
            inventory_fingerprint=review_inventory["fingerprint"],
            packets=100,
            independent_slots=["A", "B"],
            human_labels_created=False,
            third_human="CATEGORICAL_CONFLICTS_ONLY",
        ),
    )
    cost = freeze_public(
        "p020-cost-preflight-v1.json",
        dict(
            pricing_assumption_fingerprint=pricing.fingerprint,
            pricing_metadata_path=str(PRICING),
            DEVELOPMENT=domain.costs(dev["rows"], pricing),
            FINAL=domain.costs(final["rows"], pricing),
            TOTAL=domain.costs(dev["rows"] + final["rows"], pricing),
            provider_calls=0,
            connectivity_calls=0,
            paid_execution_approved=False,
            estimate_not_invoice=True,
        ),
    )
    hybrid = freeze_public("p020-hybrid-protocol-v1.json", domain.hybrid_protocol())
    ablation = freeze_public(
        "p020-ablation-protocol-v1.json",
        dict(
            configurations=domain.ABLATIONS,
            multi_component_candidates=["H0", "H1", "H2"],
            refit_each_multi_component=True,
            fit="DEVELOPMENT_TRAIN_ONLY",
            selection="DEVELOPMENT_VALIDATION_ONCE",
            test_fit=False,
        ),
    )
    registry = freeze_public(
        "p020-registry-v1.json",
        dict(
            plan_fingerprint=plan["fingerprint"],
            review_material_fingerprint=review_receipt["fingerprint"],
            context_budget_amendment=read(BASE / "p020-context-budget-amendment-v1.json")[
                "fingerprint"
            ],
            alignment_fingerprint=plan["alignment_fingerprint"],
            alignment_commit=plan["alignment_commit"],
            development=read(BASE / "p020-development-freeze-v1.json")["fingerprint"],
            final_holdout=read(BASE / "p020-final-holdout-freeze-v1.json")["fingerprint"],
            development_evidence=read(DEV / "evidence/evidence.json")["fingerprint"],
            final_evidence=read(FINAL / "evidence/evidence.json")["fingerprint"],
            development_requests=dev["fingerprint"],
            final_requests=final["fingerprint"],
            final_context=final["context_manifest_fingerprint"],
            structural_prompt=digest(
                dict(
                    system=domain.STRUCTURAL_SYSTEM,
                    questions=domain.STRUCTURAL_QUESTIONS,
                    schema=domain.UnifiedAssessment.model_json_schema(),
                )
            ),
            semantic_prompt_schema=domain.protocol()["semantic_schema_lineage"],
            hybrid_protocol=hybrid["fingerprint"],
            ablation_protocol=ablation["fingerprint"],
            cost_preflight=cost["fingerprint"],
            prior_component_registry=read(ALIGNMENT_FREEZE)["prior_seals"][
                "experiments/component-holdout/p019-component-registry-v1.json"
            ],
            graph_component_artifact=structural.V2,
            graph_component_refit=False,
            real_hybrid_trained=False,
            implementation={n: sha(Path(n)) for n in IMPLEMENTATION},
            real_hybrid_frozen=False,
            final_predictions=False,
            truth_join=False,
            final_metrics=False,
            pending="180_STRUCTURAL_DEV_LLM_PLUS_FINAL_HUMAN_REVIEW_PLUS_300_BLIND_FINAL_LLM",
            paid_execution_approved=False,
        ),
    )
    return registry


def verify() -> dict[str, Any]:
    alignment_gate()
    old = read(COORDINATOR / "private-plan.json")["old_bytes"]
    if any(sha(Path(p)) != h for p, h in old.items()):
        raise ValueError("immutable historical bytes drift")
    plan = read(BASE / "p020-plan-v1.json")
    if any(sha(Path(p)) != h for p, h in plan["implementation"].items()):
        raise ValueError("P020 implementation drift")
    frozen = read(BASE / "p020-final-holdout-freeze-v1.json")
    paths = {
        "execution": FINAL / "inputs/manifest.json",
        "cases": COORDINATOR / "final-cases.json",
        "structural_truth": COORDINATOR / "structural-truth.json",
        "intent": COORDINATOR / "construction-intent.json",
        "validation": COORDINATOR / "validation.json",
        "packets": FINAL / "review/packet-inventory.json",
        "reviewer_A": FINAL / "review/A/bundle.json",
        "reviewer_B": FINAL / "review/B/bundle.json",
    }
    for key, path in paths.items():
        if read(path)["fingerprint"] != frozen["fingerprints"][key]:
            raise ValueError("holdout frozen binding drift")
    for slot, model in (("A", ReviewerABundle), ("B", ReviewerBBundle)):
        model.model_validate_json((FINAL / "review" / slot / "bundle.json").read_bytes())
    for path, key in (
        (COORDINATOR / "final-inventory.json", "inventory_fingerprint"),
        (FINAL / "review/protocol.json", "review_protocol_fingerprint"),
        (FINAL / "review/assignment-manifest.json", "review_assignment_fingerprint"),
    ):
        if read(path)["fingerprint"] != frozen[key]:
            raise ValueError("review/source freeze drift")
    dev_freeze = read(BASE / "p020-development-freeze-v1.json")
    for path, key in (
        (DEV / "inputs/manifest.json", "manifest_fingerprint"),
        (COORDINATOR / "development-split.json", "split_fingerprint"),
        (COORDINATOR / "development-semantic-reuse.json", "reuse_fingerprint"),
    ):
        if read(path)["fingerprint"] != dev_freeze[key]:
            raise ValueError("development freeze drift")
    files = read(COORDINATOR / "final-inventory.json")["files"]
    if source_inventory(FINAL / "inputs") != files:
        raise ValueError("final source/IAM/manifest drift")
    common = read(COORDINATOR / "final-cases.json")["rows"]
    intent = read(COORDINATOR / "construction-intent.json")["rows"]
    if len(common) != 300 or len({r["execution_safe_id"] for r in common}) != 300:
        raise ValueError("final cases mismatch")
    if len({r["pair_id"] for r in intent}) != 150 or Counter(
        r["rule"] for r in intent
    ) != dict.fromkeys(domain.RULES, 20):
        raise ValueError("pair/rule imbalance")
    split = read(COORDINATOR / "development-split.json")
    replay = domain.grouped_split(
        [{k: v for k, v in r.items() if k != "split"} for r in split["rows"]]
    )
    if digest(replay) != split["fingerprint"]:
        raise ValueError("development split replay drift")
    train = {r["project_id"] for r in split["rows"] if r["split"] == "TRAIN"}
    val = {r["project_id"] for r in split["rows"] if r["split"] == "VALIDATION"}
    if train & val or (train | val) & {r["project_id"] for r in common}:
        raise ValueError("project leakage")
    packet_inventory = read(FINAL / "review/packet-inventory.json")
    for r in packet_inventory["rows"]:
        packet = semantic.BlindedPacket.model_validate_json(
            (FINAL / "review/packets" / (r["blinded_id"] + ".json")).read_bytes()
        )
        if packet.fingerprint != r["fingerprint"]:
            raise ValueError("packet drift")
        audit_metadata(packet.model_dump(mode="json"))
    for stream, root, n, requests in (("DEVELOPMENT", DEV, 280, 180), ("FINAL", FINAL, 300, 300)):
        manifest = read(root / "inputs/manifest.json")
        audit_metadata(manifest)
        evidence = read(root / "evidence/evidence.json")
        evidence_public = read(BASE / ("p020-" + stream.lower() + "-evidence-freeze-v1.json"))
        if evidence["fingerprint"] != evidence_public["fingerprint_binding"]:
            raise ValueError("evidence public binding drift")
        for name in ("static", "graph"):
            if (
                read(root / "evidence" / (name + "-output.json"))["fingerprint"]
                != evidence[name + "_output_fingerprint"]
            ):
                raise ValueError("component output drift")
        if len(evidence["records"]) != n or {r["execution_id"] for r in evidence["records"]} != {
            r["execution_id"] for r in manifest["rows"]
        }:
            raise ValueError("evidence binding drift")
        req = read(root / "requests/manifest.json")
        if (
            req["fingerprint"]
            != read(BASE / ("p020-" + stream.lower() + "-requests-freeze-v1.json"))[
                "fingerprint_binding"
            ]
        ):
            raise ValueError("request public binding drift")
        if len(req["rows"]) != requests or len({r["request_id"] for r in req["rows"]}) != requests:
            raise ValueError("request binding drift")
        if req["rows"] != sorted(req["rows"], key=lambda r: digest(r["execution_id"])):
            raise ValueError("order drift")
        contexts = read(root / "requests/contexts.json")
        if contexts["fingerprint"] != req["context_manifest_fingerprint"]:
            raise ValueError("contexts binding drift")
        for r in req["rows"]:
            payload = read(root / "requests/payloads" / (r["request_id"] + ".json"))
            audit_request(payload)
            if (
                digest(payload["wire_payload"]) != r["request_fingerprint"]
                or digest(payload["context"]) != r["context_fingerprint"]
            ):
                raise ValueError("payload fingerprint drift")
    registry = read(BASE / "p020-registry-v1.json")
    review_receipt = read(BASE / "p020-review-material-freeze-v1.json")
    review_inventory = read(COORDINATOR / "review-inventory.json")
    if (
        review_inventory["fingerprint"] != review_receipt["inventory_fingerprint"]
        or source_inventory(FINAL / "review") != review_inventory["files"]
    ):
        raise ValueError("review material inventory drift")
    if review_receipt["fingerprint"] != registry["review_material_fingerprint"]:
        raise ValueError("review registry drift")
    implementation_path = BASE / "p020-implementation-freeze-v2.json"
    if not implementation_path.exists():
        implementation_path = BASE / "p020-implementation-freeze-v1.json"
    implementation = read(implementation_path) if implementation_path.exists() else registry
    if (
        implementation.get("generation_registry_fingerprint", registry["fingerprint"])
        != registry["fingerprint"]
    ):
        raise ValueError("implementation registry binding drift")
    if any(sha(Path(n)) != h for n, h in implementation["implementation"].items()):
        raise ValueError("implementation freeze drift")
    for stream in ("DEVELOPMENT", "FINAL"):
        subprocess.run(
            [
                sys.executable,
                "scripts/prompt020_offline.py",
                "--worker",
                "verify",
                "--stream",
                stream,
            ],
            check=True,
            env={
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": "src",
                "PYTHONDONTWRITEBYTECODE": "1",
            },
            stdout=subprocess.DEVNULL,
        )
    for path in BASE.glob("*.json"):
        historical.public_privacy([path])
        read(path)
    for p in PRIVATE.rglob("*"):
        if p.is_dir() and p.stat().st_mode & 0o077:
            raise ValueError("private directory permissions")
        if p.is_file() and p.stat().st_mode & 0o077:
            raise ValueError("private file permissions")
        if p.is_symlink():
            raise ValueError("scientific symlinks prohibited")
        if p.is_file() and (
            p.name.startswith(".env")
            or re.search(
                rb"(?:\bsk-[A-Za-z0-9_-]{10,}|\bBearer\s+\S+|\"(?:api_key|authorization|access_token|session_token)\"\s*:)",
                p.read_bytes(),
            )
        ):
            raise ValueError("secret-bearing scientific material prohibited")
    previous = "0" * 64
    for line in AUDIT.read_text().splitlines():
        item = json.loads(line)
        if item["previous"] != previous or item["fingerprint"] != digest(
            {k: v for k, v in item.items() if k != "fingerprint"}
        ):
            raise ValueError("chronology chain drift")
        previous = item["fingerprint"]
    return {
        "status": "P020_OFFLINE_PREPARED",
        "prior_bytes_unchanged": True,
        "cases": 300,
        "development_evidence": 280,
        "final_evidence": 300,
        "requests": 480,
        "semantic_reused": 100,
        "human_packets": 100,
        "all_freezes_verified": True,
        "provider_calls": 0,
        "connectivity_calls": 0,
        "paid_execution_approved": False,
        "holdout_fingerprint": frozen["fingerprint"],
        "registry_fingerprint": read(BASE / "p020-registry-v1.json")["fingerprint"],
    }
