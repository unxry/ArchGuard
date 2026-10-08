"""Offline P019 freezes, capability-limited workers and post-freeze evaluation."""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean, median
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Any

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.conformance.analyzer import StaticConformanceAnalyzer, iam_fingerprint
from archguard.architecture.conformance.models import StaticAnalysisConfig
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.builder import GraphBuilder
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.architecture.hybrid.calibration import numeric_values
from archguard.architecture.hybrid.features import extract_features
from archguard.architecture.hybrid.serialization import fingerprint
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.benchmark.component_holdout import (
    DATASET,
    STATIC_RULES,
    TRAIN_FAMILIES,
    V2,
    identity,
    metrics,
    oracle,
    plan,
    recipes,
    sources,
    specification,
    topology,
    validate_design,
)
from archguard.benchmark.materialization import EvaluationAnchor, MaterializeEvaluationCase
from archguard.benchmark.models import BenchmarkDataset, Locator, Subjects
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_holdout import BlindedPacket, HoldoutSample
from archguard.core.model.enums import Language, NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.benchmark import load_dataset
from archguard.infrastructure.calibration import load_policy
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.semantic_positive_evaluation_freeze import (
    append_sealed,
    evaluation_io,
)
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput

BASE = Path("experiments/component-holdout")
PRIVATE = BASE / "private" / DATASET
EXECUTION = PRIVATE / "execution"
OUTPUT = PRIVATE / "outputs"
SEMANTIC = Path("experiments/semantic-holdout")
P015 = SEMANTIC / "semantic-positive-holdout-v1"
P015_PRIVATE = SEMANTIC / "private/semantic-positive-holdout-v1"
POLICY = Path("experiments/results/structural-v2/policy.json")
PLAN = BASE / "p019-plan-v1.json"
HOLDOUT = BASE / "p019-holdout-freeze-v1.json"
AUDIT = BASE / "p019-access-audit-v1.jsonl"
COMPONENTS = ("STATIC", "GRAPH", "V2")
EXPECTED_OLD = {
    "p017-verification-v1.json": "1fe89f2b4f377043a49fa19c76de4a198ca30d93922a13acea16a1a3859990d2",
    "p018-verification-v1.json": "e24860669f84bddd46a71d830e96cc330768f9153b79d1319f8642bd58bcd9a6",
}


def offline(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}:
        raise PermissionError("P019 prohibits network/provider execution")
    if (
        event == "open"
        and not isinstance(args[0], int)
        and Path(os.fsdecode(args[0])).name.startswith(".env")
    ):
        raise PermissionError("P019 never reads credentials")


def read(path: Path) -> dict[str, Any]:
    value: dict[str, Any] = json.loads(path.read_bytes())
    if value.get("fingerprint") != digest({k: v for k, v in value.items() if k != "fingerprint"}):
        raise ValueError("P019 seal mismatch: " + path.name)
    return value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def event(name: str, artifact: str | None = None) -> None:
    rows = [json.loads(line) for line in AUDIT.read_text().splitlines()] if AUDIT.exists() else []
    if name in {r["event"] for r in rows}:
        raise ValueError("P019 stage already recorded; no repeat execution")
    value = dict(
        sequence=len(rows),
        event=name,
        timestamp=datetime.now(UTC).isoformat(),
        previous=rows[-1]["fingerprint"] if rows else None,
        artifact=artifact,
    )
    value["fingerprint"] = digest(value)
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT.open("a", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def chronology() -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in AUDIT.read_text().splitlines()]
    for i, row in enumerate(rows):
        if row["sequence"] != i or row["previous"] != (rows[i - 1]["fingerprint"] if i else None):
            raise ValueError("P019 audit chain broken")
        if digest({k: v for k, v in row.items() if k != "fingerprint"}) != row["fingerprint"]:
            raise ValueError("P019 audit tampered")
        if i and row["timestamp"] < rows[i - 1]["timestamp"]:
            raise ValueError("P019 time order broken")
    order = [r["event"] for r in rows]
    required = [
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
    ]
    if not read(PLAN)["capability"]["v2_allowed"]:
        required = [r for r in required if not r.startswith("V2_")]
    present = [r for r in required if r in order]
    if [order.index(r) for r in present] != sorted(order.index(r) for r in present):
        raise ValueError("P019 output/truth chronology violated")
    if "FIRST_TRUTH_JOIN" in order and any(r not in order for r in required[:-2]):
        raise ValueError("P019 truth joined before all outputs froze")
    return rows


def _v2_capability() -> dict[str, Any]:
    artifact = load_policy(POLICY)
    dataset = BenchmarkDataset.model_validate_json(
        Path("benchmarks/v1/dataset-1.1.json").read_bytes()
    )
    historical = load_dataset(Path("benchmarks/v1/dataset-1.1.json"))
    mapping = {
        fingerprint(name): name for name in {r.repository_family_id for r in dataset.repositories}
    }
    families = tuple(sorted(mapping[h] for h in artifact.train_families))
    scope = {
        f: sorted(
            {
                r
                for repo in dataset.repositories
                if repo.repository_family_id == f
                for r in repo.annotation_scope.rules
            }
        )
        for f in families
    }
    allowed = (
        artifact.fingerprint == V2
        and artifact.status == "AWAITING_FRESH_HOLDOUT"
        and historical.fingerprint == artifact.dataset_fingerprint
        and artifact.selection_fingerprint
        == "2b8dc1b46ed44159aca269a0c2c0cea498b6eef2061a27aee56e4a89dfd85e36"
        and artifact.train_fingerprint
        == "496448e58c1fa0e4da9d5f067cecaeaca13322170d117308460c09efe79f314f"
        and artifact.validation_fingerprint
        == "0655b06ade4be0e3b33a3c74a366d83c1ab4ae058af4c5de37cf96d0ea713948"
        and scope == {f: list(TRAIN_FAMILIES[f]) for f in TRAIN_FAMILIES}
    )
    return dict(
        v2_allowed=allowed,
        v2_reason=None if allowed else "artifact/family lineage not verifiable",
        v2_fingerprint=artifact.fingerprint,
        v2_status=artifact.status,
        train_families=list(families),
        supported_rules=scope,
        validation_families=[mapping[h] for h in artifact.validation_families],
        family_interpretation=(
            "K counts artifact TRAIN repository families, not rule IDs; validation excluded"
        ),
        train_cases=artifact.train_cases,
        train_positive=artifact.train_positive,
        train_negative=artifact.train_negative,
        validation_cases=sum(
            (
                artifact.validation_metrics.tp,
                artifact.validation_metrics.fp,
                artifact.validation_metrics.tn,
                artifact.validation_metrics.fn,
            )
        ),
        dataset_fingerprint=artifact.dataset_fingerprint,
        threshold=artifact.threshold,
        preprocessor_fingerprint=artifact.preprocessor.fingerprint,
        feature_scope=list(artifact.preprocessor.selected_features),
        graph_configuration=GraphAnalysisConfig().model_dump(mode="json"),
        graph_configuration_fingerprint=GraphAnalysisConfig().fingerprint,
        static_configuration=StaticAnalysisConfig().model_dump(mode="json"),
        graph_anomalies={f"ARCH10{i}": "CANDIDATE_ONLY" for i in range(1, 6)},
    )


def capability() -> dict[str, Any]:
    try:
        return _v2_capability()
    except (OSError, ValueError, KeyError) as error:
        return dict(
            v2_allowed=False,
            v2_reason=type(error).__name__ + ": frozen lineage unavailable",
            v2_fingerprint=None,
            v2_status="UNVERIFIABLE",
            train_families=[],
            supported_rules={},
            validation_families=[],
            graph_configuration=GraphAnalysisConfig().model_dump(mode="json"),
            graph_configuration_fingerprint=GraphAnalysisConfig().fingerprint,
            static_configuration=StaticAnalysisConfig().model_dump(mode="json"),
            graph_anomalies={f"ARCH10{i}": "CANDIDATE_ONLY" for i in range(1, 6)},
        )


def lineage() -> list[str]:
    references = (
        "a1b466d",
        "8e242493",
        "df899b0",
        "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
        "c4e2ed358568e8b0992f8cc3838e688443bbfb5d",
        "802257d1211e519ae174736c8d83c3614f2678ea",
        "8a11b012dadde660318053f2cb6845703cae7547",
        "264e7cc237f96714fc1d066d04418944e397a6e2",
        "5a53531a06106b10c5a14986c8e9905c36fb816b",
        "7e96c87d2380dfa417f6df9cbf59d3f512bdb5fe",
        "c34ac13caf5e77ffb37ac7417366dd866664c412",
        "9b675f50eb06c81fef92b83cf2c69a5e36553bdd",
    )
    result = []
    for reference in references:
        commit = subprocess.check_output(
            ["git", "rev-parse", reference + "^{commit}"], text=True
        ).strip()
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], check=True)
        result.append(commit)
    return result


def old_guards() -> dict[str, str]:
    for name, expected in EXPECTED_OLD.items():
        if read(SEMANTIC / name)["fingerprint"] != expected:
            raise ValueError("P019 prior scientific freeze changed")
    manifest = Path("experiments/semantic-holdout/semantic-positive-holdout-v1/sample-v1.json")
    if (
        read(manifest)["fingerprint"]
        != "926cf3014e3c46f9c3a62df6421ce89886373559335411209f25780130e1f5fa"
    ):
        raise ValueError("P019 P015 sample changed")
    roots = [
        P015,
        P015_PRIVATE,
        SEMANTIC / "private/p016-execution-v1",
        SEMANTIC / "private/p016-live-v1",
        SEMANTIC / "private/p016-recovery-v1",
        SEMANTIC / "private/final-human-ground-truth-v1",
        SEMANTIC / "private/p017-evaluation-v1",
        SEMANTIC / "private/p018-diagnostic-v1",
    ]
    files = [p for root in roots if root.exists() for p in root.rglob("*") if p.is_file()]
    files += [p for p in SEMANTIC.glob("p01[678]*.json") if p.is_file()]
    return {str(p): sha(p) for p in sorted(set(files))}


def prepare_plan() -> dict[str, Any]:
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        # Implementation files may already be committed; plan always starts from clean Git.
        raise ValueError("P019 plan preparation requires clean working tree")
    if PLAN.exists():
        raise ValueError("P019 prospective plan already frozen")
    input_path = PRIVATE / "plan-inputs-v1.json"
    if input_path.exists():
        inputs = read(input_path)
        if inputs["old_hashes"] != old_guards():
            raise ValueError("P019 prior scientific inputs changed during plan preparation")
        seed = inputs["seed"]
    else:
        seed = os.urandom(32).hex()
        inputs = append_sealed(input_path, dict(seed=seed, old_hashes=old_guards()))
    cap = capability()
    cap["lineage"] = lineage()
    cap["engine_source_hashes"] = {
        str(p): sha(p)
        for p in (
            Path("src/archguard/architecture/conformance/analyzer.py"),
            Path("src/archguard/architecture/rules/registry.py"),
            Path("src/archguard/architecture/graph/analyzer.py"),
            Path("src/archguard/architecture/graph/builder.py"),
            Path("src/archguard/architecture/graph/config.py"),
            Path("src/archguard/architecture/graph/candidates.py"),
            Path("src/archguard/architecture/graph/metrics.py"),
            Path("src/archguard/architecture/hybrid/calibration.py"),
            Path("src/archguard/architecture/hybrid/features.py"),
            Path("src/archguard/architecture/hybrid/assembler.py"),
        )
    }
    value = plan(digest(seed), cap)
    append_sealed(PLAN, value)
    event("PLAN_FROZEN", value["fingerprint"])
    return dict(plan=value["fingerprint"], input_seal=inputs["fingerprint"])


def public_privacy(paths: list[Path]) -> None:
    for path in paths:
        if ("experiments" in path.parts and "private" in path.parts) or path.name.startswith(
            ".env"
        ):
            raise ValueError("P019 private file in public scope")
        text = path.read_text()
        if re.search(r"sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_.-]{16,}", text):
            raise ValueError("P019 credential-like value in public artifact")
        if path.suffix in {".json", ".jsonl"} and re.search(
            r'"(?:case_id|pair_id|rationale|reviewer_id|authorization|api_key|source_text)"\s*:',
            text,
        ):
            raise ValueError("P019 private scientific material in public artifact")


def blind_manifest(value: dict[str, Any]) -> None:
    if set(value) != {"rows", "fingerprint"}:
        raise ValueError("P019 blind manifest contains undeclared material")
    expected = {"case_id", "rule", "language", "iam_file", "subjects", "spec", "iam_fingerprint"}
    rows = value["rows"]
    if any(set(r) != expected for r in rows) or len({r["case_id"] for r in rows}) != len(rows):
        raise ValueError("P019 blind rows contain truth/membership or duplicate identities")


def build(root: Path, namespace: str) -> tuple[ArchitectureModel, dict[str, Any]]:
    builder = BuildIAM(
        ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=True)),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace=namespace, project_name=namespace),
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as repo:
        result = builder.execute(repo.snapshot, repo.workspace)
        replay = builder.execute(repo.snapshot, repo.workspace)
    graph = GraphBuilder().build(result.iam, GraphAnalysisConfig())
    if (
        not result.is_valid
        or not result.is_complete
        or result.statistics.files_with_parse_errors
        or not graph.is_valid
        or not graph.is_complete
        or iam_fingerprint(result.iam) != iam_fingerprint(replay.iam)
    ):
        raise ValueError("P019 intake/IAM/Graph/replay failed")
    return result.iam, dict(
        iam_fingerprint=iam_fingerprint(result.iam),
        statistics=result.statistics.model_dump(mode="json"),
        graph_nodes=len(graph.graph.nodes),
        graph_edges=len(graph.graph.edges),
        replay=True,
        status="VALID",
    )


def normalized(iam: ArchitectureModel) -> dict[str, Any]:
    graph = GraphBuilder().build(iam, GraphAnalysisConfig()).graph
    nodes = {n.id: n for n in iam.nodes}
    index = {
        n.id: int(
            next(nodes[i].name for i in n.iam_node_ids if nodes[i].kind == NodeKind.CLASS).rsplit(
                "N", 1
            )[1]
        )
        for n in graph.nodes
    }
    return dict(
        nodes=sorted(index.values()),
        edges=sorted({(index[e.source_id], index[e.target_id]) for e in graph.edges}),
        methods={index[n.id]: n.method_count for n in graph.nodes},
    )


def native_validation(source_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for lang, executable in (("JAVA", "javac"), ("TYPESCRIPT", "tsc")):
        binary = shutil.which(executable)
        if not binary:
            result[lang] = dict(status="UNAVAILABLE", runtime="NOT_RUN")
            continue
        check = subprocess.run(
            [binary, "-version" if lang == "JAVA" else "--version"], capture_output=True, timeout=30
        )
        if check.returncode:
            result[lang] = dict(
                status="UNAVAILABLE",
                reason="installed launcher reports no compiler runtime",
                runtime="NOT_RUN",
            )
            continue
        with TemporaryDirectory(prefix="p019-native-") as temp:
            files = sorted(
                str(p) for p in source_root.rglob("*.java" if lang == "JAVA" else "*.ts")
            )
            args = (
                [binary, "-d", temp]
                if lang == "JAVA"
                else [binary, "--noEmit", "--target", "ES2020"]
            )
            checked = subprocess.run([*args, *files], capture_output=True, timeout=60)
            result[lang] = dict(
                status="PASS" if checked.returncode == 0 else "FAIL",
                source_units=len(files),
                tool_version=check.stdout.decode().strip() or check.stderr.decode().strip(),
                runtime="NOT_RUN",
            )
            if checked.returncode:
                raise ValueError("P019 native compilation failed: " + lang)
    return result


def construct() -> dict[str, Any]:
    prospective = read(PLAN)
    seed = read(PRIVATE / "plan-inputs-v1.json")["seed"]
    if digest(seed) != prospective["seed_fingerprint"]:
        raise ValueError("P019 seed changed")
    families = tuple(prospective["track_b"]["families"])
    truth, execution, validation = [], [], []
    old_manifests = (Path("benchmarks/v1/dataset.json"), Path("benchmarks/v1/dataset-1.1.json"))
    old = [BenchmarkDataset.model_validate_json(p.read_bytes()) for p in old_manifests]
    old_units = {
        sha(p)
        for dataset in old
        for repo in dataset.repositories
        for p in (Path("benchmarks/v1") / repo.source_path).rglob("*")
        if p.is_file() and p.suffix in {".java", ".ts"}
    }
    old_ids = {str(case.case_id) for path in old_manifests for case in load_dataset(path).truths}
    source_hashes = {}
    for recipe in recipes(families):
        parts = (recipe["track"], recipe["family"], recipe["language"], recipe["index"])
        case_id = identity(seed, "case", *parts, recipe["positive"])
        facts = topology(recipe["rule"], recipe["index"], recipe["positive"])
        spec = specification(recipe["rule"])
        ArchitectureSpecification.model_validate(spec["spec"])
        expected = oracle(recipe["rule"], facts, spec)
        if expected != recipe["positive"] or case_id in old_ids:
            raise ValueError("P019 construction/oracle/identity failed")
        files = sources(case_id, recipe["language"], facts)
        root = PRIVATE / "sources" / case_id
        for relative, text in files.items():
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with target.open("x", encoding="utf-8") as stream:
                stream.write(text)
            target.chmod(0o600)
            unit = sha(target)
            if unit in old_units:
                raise ValueError("P019 old source unit reused")
            source_hashes[str(target.relative_to(PRIVATE))] = unit
        iam, receipt = build(root, case_id)
        observed = normalized(iam)
        if observed["nodes"] != facts["nodes"] or observed["edges"] != facts["edges"]:
            raise ValueError("P019 normalized source adjacency differs from construction")
        if any(observed["methods"][i] != count for i, count in enumerate(facts["methods"])):
            raise ValueError("P019 normalized method facts differ")
        iam_file = EXECUTION / "iam" / (case_id + ".json")
        append_sealed(iam_file, dict(iam=iam.model_dump(mode="json")))
        locators = []
        for index in facts["target"]:
            node = next(
                n
                for n in iam.nodes
                if n.kind == NodeKind.CLASS and n.name.endswith("N" + str(index))
            )
            assert node.source_location is not None
            locators.append(
                Locator(
                    path=node.source_location.file_path,
                    language=Language(recipe["language"]),
                    qualified_name=node.qualified_name,
                    kind=NodeKind.CLASS,
                ).model_dump(mode="json")
            )
        execution.append(
            dict(
                case_id=case_id,
                rule=recipe["rule"],
                language=recipe["language"],
                iam_file=iam_file.name,
                subjects=dict(locators=locators, directed=len(locators) == 2),
                spec=spec["spec"],
                iam_fingerprint=receipt["iam_fingerprint"],
            )
        )
        truth.append(
            dict(
                case_id=case_id,
                pair_id=identity(seed, "pair", *parts),
                rule=recipe["rule"],
                track=recipe["track"],
                family=recipe["family"],
                source_family_id="p019-family-"
                + identity(seed, "family", *parts[:-1], recipe["index"]),
                language=recipe["language"],
                truth=expected,
                facts=facts,
                specification=spec,
            )
        )
        validation.append(receipt)
    validate_design(truth, families)
    independence = append_sealed(
        PRIVATE / "independence-v1.json",
        dict(
            old_case_ids=sorted(old_ids),
            old_source_hashes=sorted(old_units),
            manifests={str(p): sha(p) for p in old_manifests},
            new_case_overlap=0,
            new_source_unit_overlap=0,
            source_family_ids=sorted({r["source_family_id"] for r in truth}),
        ),
    )
    labels = append_sealed(
        PRIVATE / "truth-v1.json", dict(rows=sorted(truth, key=lambda r: r["case_id"]))
    )
    manifest = append_sealed(
        EXECUTION / "manifest-v1.json", dict(rows=sorted(execution, key=lambda r: r["case_id"]))
    )
    units = append_sealed(PRIVATE / "source-inventory-v1.json", dict(files=source_hashes))
    receipts = append_sealed(
        PRIVATE / "validation-v1.json",
        dict(rows=validation, native=native_validation(PRIVATE / "sources")),
    )
    artifact = append_sealed(
        HOLDOUT,
        dict(
            dataset=DATASET,
            cases=len(truth),
            pairs=len(truth) // 2,
            Java=sum(r["language"] == "JAVA" for r in truth),
            TypeScript=sum(r["language"] == "TYPESCRIPT" for r in truth),
            P=sum(r["truth"] for r in truth),
            N=sum(not r["truth"] for r in truth),
            IAM=dict(VALID=len(truth), PARTIAL=0, INVALID=0),
            malformed_pairs=0,
            old_case_overlap=0,
            old_source_unit_overlap=0,
            source_units=len(source_hashes),
            execution_manifest_fingerprint=manifest["fingerprint"],
            truth_fingerprint=labels["fingerprint"],
            source_inventory_fingerprint=units["fingerprint"],
            independence_fingerprint=independence["fingerprint"],
            oracle_fingerprint=digest(prospective["oracle_predicates"]),
            validation_fingerprint=receipts["fingerprint"],
            native=receipts["native"],
            plan_fingerprint=prospective["fingerprint"],
        ),
    )
    for folder in PRIVATE.rglob("*"):
        if folder.is_dir():
            folder.chmod(0o700)
    event("HOLDOUT_FROZEN", artifact["fingerprint"])
    event("LABELS_SEALED", labels["fingerprint"])
    return artifact


def verify_holdout() -> dict[str, Any]:
    frozen = read(HOLDOUT)
    if read(PLAN)["fingerprint"] != frozen["plan_fingerprint"]:
        raise ValueError("P019 prospective plan drift")
    for path, field in (
        (EXECUTION / "manifest-v1.json", "execution_manifest_fingerprint"),
        (PRIVATE / "truth-v1.json", "truth_fingerprint"),
        (PRIVATE / "source-inventory-v1.json", "source_inventory_fingerprint"),
        (PRIVATE / "validation-v1.json", "validation_fingerprint"),
        (PRIVATE / "independence-v1.json", "independence_fingerprint"),
    ):
        if read(path)["fingerprint"] != frozen[field]:
            raise ValueError("P019 holdout freeze drift")
    truths = read(PRIVATE / "truth-v1.json")["rows"]
    validate_design(truths, tuple(read(PLAN)["track_b"]["families"]))
    for row in truths:
        if oracle(row["rule"], row["facts"], row["specification"]) != row["truth"]:
            raise ValueError("P019 independent oracle replay differs")
    inventory = read(PRIVATE / "source-inventory-v1.json")["files"]
    if set(inventory) != {
        str(p.relative_to(PRIVATE)) for p in (PRIVATE / "sources").rglob("*") if p.is_file()
    }:
        raise ValueError("P019 source inventory differs")
    for relative, expected in inventory.items():
        if sha(PRIVATE / relative) != expected:
            raise ValueError("P019 source changed")
    independent = read(PRIVATE / "independence-v1.json")
    if set(inventory.values()) & set(independent["old_source_hashes"]) or (
        set(truths[i]["case_id"] for i in range(len(truths))) & set(independent["old_case_ids"])
    ):
        raise ValueError("P019 legacy overlap")
    for row in read(EXECUTION / "manifest-v1.json")["rows"]:
        iam = ArchitectureModel.model_validate(read(EXECUTION / "iam" / row["iam_file"])["iam"])
        if iam_fingerprint(iam) != row["iam_fingerprint"]:
            raise ValueError("P019 frozen IAM changed")
    for file, expected in read(PRIVATE / "plan-inputs-v1.json")["old_hashes"].items():
        if sha(Path(file)) != expected:
            raise ValueError("P019 prior artifact drift")
    cap = read(PLAN)["capability"]
    if cap["v2_allowed"] and load_policy(POLICY).fingerprint != cap["v2_fingerprint"]:
        raise ValueError("P019 frozen V2 changed")
    if any(sha(Path(file)) != expected for file, expected in cap["engine_source_hashes"].items()):
        raise ValueError("P019 production engine changed")
    chronology()
    return frozen


def worker(component: str) -> dict[str, Any]:
    """Fresh subprocess, no construction/truth/old-result capability."""
    destination = OUTPUT / component.lower()
    graph_output = OUTPUT / "graph/output-v1.json"
    inputs = (PLAN, HOLDOUT, EXECUTION, POLICY) + ((graph_output,) if component == "V2" else ())
    with evaluation_io(Path("experiments"), inputs, destination):
        prospective = read(PLAN)
        manifest = read(EXECUTION / "manifest-v1.json")
        blind_manifest(manifest)
        if manifest["fingerprint"] != read(HOLDOUT)["execution_manifest_fingerprint"]:
            raise ValueError("P019 blind manifest mismatch")
        artifact = load_policy(POLICY) if component == "V2" else None
        graph_rows = {r["case_id"]: r for r in read(graph_output)["rows"]} if artifact else {}
        if artifact and artifact.fingerprint != prospective["capability"]["v2_fingerprint"]:
            raise ValueError("P019 frozen V2 mismatch")
        rows = []
        for row in manifest["rows"]:
            graph_rule = row["rule"].startswith("ARCH1")
            if (component == "STATIC" and graph_rule) or (component == "V2" and not graph_rule):
                continue
            start = perf_counter()
            iam = ArchitectureModel.model_validate(read(EXECUTION / "iam" / row["iam_file"])["iam"])
            spec = ArchitectureSpecification.model_validate(row["spec"])
            scope = (
                "BINARY"
                if (
                    component == "V2"
                    or component == "STATIC"
                    and row["rule"] in STATIC_RULES
                    or component == "GRAPH"
                    and row["rule"] == "ARCH003"
                )
                else ("CANDIDATE_ONLY" if graph_rule else "UNSUPPORTED")
            )
            prediction, detail = None, {}
            if component == "STATIC":
                result = StaticConformanceAnalyzer().analyze(iam, spec)
                detail = result.model_dump(mode="json")
                valid = result.is_valid and result.is_complete
                if scope == "BINARY" and valid:
                    prediction = any(f.rule_id == row["rule"] for f in result.findings)
            else:
                graph = (
                    GraphAnalysisResult.model_validate(graph_rows[row["case_id"]]["detail"])
                    if artifact
                    else GraphAnalyzer().analyze(iam, GraphAnalysisConfig(), spec)
                )
                detail = graph.model_dump(mode="json")
                valid = graph.is_valid and graph.is_complete
                if component == "GRAPH" and scope == "BINARY" and valid:
                    prediction = any(f.rule_id == row["rule"] for f in graph.findings)
                if component == "V2":
                    assert artifact is not None
                    anchor = EvaluationAnchor(
                        repository_id=row["case_id"],
                        rule_id=row["rule"],
                        subjects=Subjects.model_validate(row["subjects"]),
                    )
                    materialized = MaterializeEvaluationCase(iam, None, graph, None).execute(anchor)
                    base = extract_features(materialized.case, materialized.bundle)
                    values = {f.name: f.value for f in base.values}
                    for side in ("source", "target"):
                        for name in ("Ca", "Ce", "I"):
                            values[f"graph.{side}.{name}"] = next(
                                f.value
                                for f in materialized.features.values
                                if f.name == f"graph.{side}.{name}"
                            )
                    numeric = numeric_values(values, artifact.preprocessor.feature_spec)
                    score = artifact.model.score(artifact.preprocessor.transform(numeric))
                    detail = dict(
                        input=numeric,
                        score=score,
                        threshold=artifact.threshold,
                        graph=detail,
                        feature_fingerprint=base.fingerprint,
                    )
                    if valid:
                        prediction = score >= artifact.threshold
            rows.append(
                dict(
                    case_id=row["case_id"],
                    rule=row["rule"],
                    scope=scope,
                    prediction=prediction,
                    error=None if valid else "INCOMPLETE_COMPONENT",
                    seconds=perf_counter() - start,
                    detail=detail,
                )
            )
        return append_sealed(
            destination / "output-v1.json",
            dict(
                component=component,
                manifest_fingerprint=manifest["fingerprint"],
                truth_accessed=False,
                rows=rows,
            ),
        )


def run_components(script: Path) -> dict[str, str]:
    verify_holdout()
    for path in (PLAN, HOLDOUT):
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", str(path)], check=True, stdout=subprocess.DEVNULL
        )
        subprocess.run(["git", "diff", "--exit-code", "HEAD", "--", str(path)], check=True)
    output = {}
    for component in COMPONENTS:
        if component == "V2" and not read(PLAN)["capability"]["v2_allowed"]:
            continue
        event(component + "_EXECUTION")
        subprocess.run(
            [sys.executable, str(script), "--worker", component],
            check=True,
            env={"PATH": os.defpath, "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
        )
        value = read(OUTPUT / component.lower() / "output-v1.json")
        receipt = append_sealed(
            BASE / ("p019-" + component.lower() + "-output-freeze-v1.json"),
            dict(
                component=component,
                cases=len(value["rows"]),
                output_fingerprint=value["fingerprint"],
                output_sha256=sha(OUTPUT / component.lower() / "output-v1.json"),
                truth_accessed=False,
                holdout_fingerprint=read(HOLDOUT)["fingerprint"],
            ),
        )
        event(component + "_OUTPUT_FROZEN", receipt["fingerprint"])
        output[component] = value["fingerprint"]
    return output


def semantic_evidence() -> dict[str, Any]:
    destination = OUTPUT / "semantic-evidence"
    with evaluation_io(
        Path("experiments"),
        (P015 / "sample-v1.json", P015_PRIVATE / "sources", P015_PRIVATE / "packets"),
        destination,
    ):
        sample = HoldoutSample.model_validate_json((P015 / "sample-v1.json").read_bytes())
        rows = []
        for case in sorted(sample.cases, key=lambda c: c.case_id):
            packet = BlindedPacket.model_validate_json(
                (P015_PRIVATE / "packets" / (case.blinded_id + ".json")).read_bytes()
            )
            if packet.fingerprint != case.packet_fingerprint:
                raise ValueError("P019 semantic source packet drift")
            root = P015_PRIVATE / "sources" / case.blinded_id
            for evidence in packet.evidence:
                if sha(root / evidence.path) != evidence.sha256:
                    raise ValueError("P019 semantic source drift")
            iam, _ = build(root, packet.project_alias)
            spec = ArchitectureSpecification.model_validate(dict(version="1.0", architecture={}))
            static = StaticConformanceAnalyzer().analyze(iam, spec)
            graph = GraphAnalyzer().analyze(iam, GraphAnalysisConfig())
            discovery = ArchitectureDiscoveryAnalyzer().analyze(iam, graph)
            node = next(
                n
                for n in iam.nodes
                if n.kind == NodeKind.CLASS
                and n.name == packet.target_component
                and n.source_location
                and n.source_location.file_path == packet.target_path
            )
            anchor = EvaluationAnchor(
                repository_id=packet.project_alias,
                rule_id=packet.rule_id,
                subjects=Subjects(
                    locators=(
                        Locator(
                            path=packet.target_path,
                            language=node.language,
                            qualified_name=node.qualified_name,
                            kind=NodeKind.CLASS,
                        ),
                    )
                ),
            )
            materialized = MaterializeEvaluationCase(iam, static, graph, discovery).execute(anchor)
            rows.append(
                dict(
                    case_id=case.case_id,
                    rule_id=case.rule_id,
                    packet_fingerprint=packet.fingerprint,
                    iam_fingerprint=iam_fingerprint(iam),
                    existing_contract=materialized.bundle.model_dump(mode="json"),
                    existing_features=extract_features(
                        materialized.case, materialized.bundle
                    ).model_dump(mode="json"),
                    static=static.model_dump(mode="json"),
                    graph=graph.model_dump(mode="json"),
                    discovery=discovery.model_dump(mode="json"),
                    dependencies=[e.model_dump(mode="json") for e in iam.edges],
                    normative_spec_status=(
                        "NO_MACHINE_EXECUTABLE_STATIC_SPEC; empty rule set, no semantic heuristic"
                    ),
                )
            )
        if len(rows) != 100 or len({r["case_id"] for r in rows}) != 100:
            raise ValueError("P019 requires exactly 100 semantic evidence records")
        return append_sealed(
            destination / "evidence-v1.json",
            dict(
                records=rows,
                sample_fingerprint=sample.fingerprint,
                human_truth_accessed=False,
                p017_correctness_accessed=False,
                p018_intent_accessed=False,
                semantic_decisions_created=False,
                hybrid_executed=False,
            ),
        )


def run_evidence(script: Path) -> dict[str, Any]:
    event("SEMANTIC_EVIDENCE_EXECUTION")
    subprocess.run(
        [sys.executable, str(script), "--semantic-worker"],
        check=True,
        env={"PATH": os.defpath, "PYTHONPATH": "src", "PYTHONDONTWRITEBYTECODE": "1"},
    )
    path = OUTPUT / "semantic-evidence/evidence-v1.json"
    value = read(path)
    receipt = append_sealed(
        BASE / "p019-semantic-evidence-freeze-v1.json",
        dict(
            records=100,
            missing=0,
            duplicates=0,
            evidence_fingerprint=value["fingerprint"],
            evidence_sha256=sha(path),
            sample_fingerprint=value["sample_fingerprint"],
            human_truth_accessed=False,
            p017_correctness_accessed=False,
            p018_intent_accessed=False,
            semantic_heuristics_created=False,
            hybrid_executed=False,
        ),
    )
    event("SEMANTIC_EVIDENCE_FROZEN", receipt["fingerprint"])
    return receipt


def evaluate() -> dict[str, Any]:
    verify_holdout()
    values = {}
    for component in COMPONENTS:
        if component == "V2" and not read(PLAN)["capability"]["v2_allowed"]:
            continue
        receipt = read(BASE / ("p019-" + component.lower() + "-output-freeze-v1.json"))
        value = read(OUTPUT / component.lower() / "output-v1.json")
        if value["fingerprint"] != receipt["output_fingerprint"]:
            raise ValueError("P019 output freeze differs")
        values[component] = value
    chronology()
    event("FIRST_TRUTH_JOIN")
    if "V2" in values:
        lifecycle = append_sealed(
            BASE / "p019-v2-fresh-access-v1.json",
            dict(
                status="ACCESSED",
                dataset=DATASET,
                frozen_artifact_fingerprint=read(PLAN)["capability"]["v2_fingerprint"],
                previous_status="AWAITING_FRESH_HOLDOUT",
                output_fingerprint=values["V2"]["fingerprint"],
                first_truth_join_timestamp=chronology()[-1]["timestamp"],
                tuning=False,
                artifact_changed=False,
            ),
        )
        event("V2_FRESH_HOLDOUT_ACCESSED", lifecycle["fingerprint"])
    truth = {r["case_id"]: r for r in read(PRIVATE / "truth-v1.json")["rows"]}
    aggregate: dict[str, Any] = {}
    for component, value in values.items():
        rows = [
            row
            | {"truth": truth[row["case_id"]]["truth"], "family": truth[row["case_id"]]["family"]}
            for row in value["rows"]
        ]
        if len(rows) != len({r["case_id"] for r in rows}):
            raise ValueError("P019 duplicate result identity")
        joined = append_sealed(
            PRIVATE / (component.lower() + "-join-v1.json"),
            dict(
                rows=rows,
                output_fingerprint=value["fingerprint"],
                truth_fingerprint=read(HOLDOUT)["truth_fingerprint"],
            ),
        )
        primary = [r for r in rows if r["scope"] == "BINARY"]
        group = "family" if component == "V2" else "rule"
        aggregate[component] = dict(
            overall=metrics(primary),
            recorded_scope=metrics(rows),
            by_scope={
                key: metrics([r for r in primary if r[group] == key])
                for key in sorted({r[group] for r in primary})
            },
            join_fingerprint=joined["fingerprint"],
            output_fingerprint=value["fingerprint"],
        )
        if component == "V2":
            groups: dict[str, Any] = {}
            for family in sorted({r["family"] for r in rows}):
                groups[family] = {}
                for label in (False, True):
                    subset = [r for r in rows if r["family"] == family and r["truth"] == label]
                    features = {}
                    for name in read(PLAN)["capability"]["feature_scope"]:
                        numbers = [
                            r["detail"]["input"][name]
                            for r in subset
                            if r["detail"]["input"][name] is not None
                        ]
                        features[name] = dict(
                            available=len(numbers),
                            missing=len(subset) - len(numbers),
                            mean=mean(numbers) if numbers else None,
                            median=median(numbers) if numbers else None,
                        )
                    groups[family]["POSITIVE" if label else "NEGATIVE"] = features
            append_sealed(
                BASE / "p019-graph-feature-diagnostic-v1.json",
                dict(
                    interpretation="DESCRIPTIVE",
                    feature_scope="existing frozen V2 whitelist only",
                    groups=groups,
                    thresholds_tuned=False,
                    output_fingerprint=value["fingerprint"],
                ),
            )
    artifact = append_sealed(
        BASE / "p019-baseline-aggregate-v1.json",
        dict(
            components=aggregate,
            holdout_fingerprint=read(HOLDOUT)["fingerprint"],
            cross_cohort_winner_metric=None,
            provider_calls=0,
            paid_execution=False,
            hybrid_executed=False,
            thresholds_changed=False,
            v2_refit=False,
        ),
    )
    event("METRICS", artifact["fingerprint"])
    return artifact


def registry() -> dict[str, Any]:
    component = {
        name: read(BASE / ("p019-" + name.lower() + "-output-freeze-v1.json"))["output_fingerprint"]
        for name in COMPONENTS
        if name != "V2" or read(PLAN)["capability"]["v2_allowed"]
    }
    evidence = read(BASE / "p019-semantic-evidence-freeze-v1.json")
    value = append_sealed(
        BASE / "p019-component-registry-v1.json",
        dict(
            components=component,
            v2_artifact_fingerprint=V2,
            v2_status="ACCESSED" if "V2" in component else "NOT_EVALUATED",
            llm_assessments_fingerprint="a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273",
            p017_evaluation_fingerprint="992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091",
            semantic_evidence_fingerprint=evidence["evidence_fingerprint"],
            combined_score=None,
            baseline_aggregate_fingerprint=read(BASE / "p019-baseline-aggregate-v1.json")[
                "fingerprint"
            ],
            readiness="READY_FOR_HYBRID_EXPERIMENT_FOUNDATION",
        ),
    )
    event("REGISTRY_FROZEN", value["fingerprint"])
    return value


def verify_results() -> dict[str, Any]:
    verify_holdout()
    events = chronology()
    frozen = read(HOLDOUT)
    truth = {r["case_id"]: r for r in read(PRIVATE / "truth-v1.json")["rows"]}
    aggregate = read(BASE / "p019-baseline-aggregate-v1.json")
    event_map = {e["event"]: e for e in events}
    if event_map["PLAN_FROZEN"]["artifact"] != read(PLAN)["fingerprint"] or (
        event_map["HOLDOUT_FROZEN"]["artifact"] != frozen["fingerprint"]
    ):
        raise ValueError("P019 audit freeze binding differs")
    for component, evaluation in aggregate["components"].items():
        path = OUTPUT / component.lower() / "output-v1.json"
        receipt = read(BASE / ("p019-" + component.lower() + "-output-freeze-v1.json"))
        if event_map[component + "_OUTPUT_FROZEN"]["artifact"] != receipt["fingerprint"]:
            raise ValueError("P019 output audit binding differs")
        value = read(path)
        expected_ids = {
            i
            for i, t in truth.items()
            if component == "GRAPH" or t["track"] == ("B" if component == "V2" else "A")
        }
        if {r["case_id"] for r in value["rows"]} != expected_ids or len(value["rows"]) != len(
            expected_ids
        ):
            raise ValueError("P019 output coverage mismatch")
        if (
            sha(path) != receipt["output_sha256"]
            or value["fingerprint"] != evaluation["output_fingerprint"]
        ):
            raise ValueError("P019 output drift")
        rows = read(PRIVATE / (component.lower() + "-join-v1.json"))["rows"]
        if rows != [
            r | {"truth": truth[r["case_id"]]["truth"], "family": truth[r["case_id"]]["family"]}
            for r in value["rows"]
        ]:
            raise ValueError("P019 identity join mismatch")
        if metrics([r for r in rows if r["scope"] == "BINARY"]) != evaluation["overall"]:
            raise ValueError("P019 aggregate replay differs")
    receipt = read(BASE / "p019-semantic-evidence-freeze-v1.json")
    path = OUTPUT / "semantic-evidence/evidence-v1.json"
    evidence = read(path)
    sample = HoldoutSample.model_validate_json((P015 / "sample-v1.json").read_bytes())
    if (
        sha(path) != receipt["evidence_sha256"]
        or evidence["fingerprint"] != receipt["evidence_fingerprint"]
        or len(evidence["records"]) != 100
        or {r["case_id"] for r in evidence["records"]} != {r.case_id for r in sample.cases}
    ):
        raise ValueError("P019 semantic evidence freeze differs")
    if event_map["SEMANTIC_EVIDENCE_FROZEN"]["artifact"] != receipt["fingerprint"]:
        raise ValueError("P019 evidence audit binding differs")
    public_privacy(list(BASE.glob("*.json")) + [AUDIT])
    if (
        "V2" in aggregate["components"]
        and read(BASE / "p019-v2-fresh-access-v1.json")["status"] != "ACCESSED"
    ):
        raise ValueError("P019 consumed fresh holdout cannot await access")
    return dict(
        holdout=frozen["fingerprint"],
        plan=read(PLAN)["fingerprint"],
        aggregate=aggregate["fingerprint"],
        registry=read(BASE / "p019-component-registry-v1.json")["fingerprint"],
        evidence=evidence["fingerprint"],
        chronology_events=len(events),
        provider_calls=0,
        verification="PASS",
    )
