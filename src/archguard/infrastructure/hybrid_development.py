"""Development-only P023 inputs, isolated TRAIN fitting and immutable selection."""

import ast
import contextvars
import json
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from archguard.benchmark import unified_hybrid as frozen
from archguard.benchmark.oss.models import canonical, digest
from archguard.calibration import hybrid_development as kernel
from archguard.infrastructure import development_llm_executor as live
from archguard.infrastructure import development_llm_preflight as p022
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure import unified_hybrid as old
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal

INPUT = io.PRIVATE / "p023-development-inputs-v1"
OUTPUT = io.PRIVATE / "p023-hybrid-models-v1"
RUN_CONTROL = io.PRIVATE / "p023-run-control-v1/execution-started.json"
EXECUTION_SOURCE = io.PRIVATE / "p023-execution-source-v1"
CORRECTION = io.BASE / "p023-boundary-correction-v1.json"
COORDINATOR = io.PRIVATE / "p023-development-join-v1"
P016 = Path("experiments/semantic-holdout/private/p016-execution-v1")
P016_NORMAL = Path("experiments/semantic-holdout/private/p016-live-v1/normalized-assessments.json")
SEMANTIC_TRUTH = Path(
    "experiments/semantic-holdout/private/final-human-ground-truth-v1/ground-truth-v1.json"
)
PUB = io.BASE / "p023-hybrid-development-v1.json"
SOURCES = (
    "src/archguard/calibration/hybrid_development.py",
    "src/archguard/infrastructure/hybrid_development.py",
    "scripts/prompt023_hybrid_development.py",
    "tests/benchmark/test_hybrid_development.py",
)
LEGACY = (
    "src/archguard/benchmark/unified_hybrid.py",
    "src/archguard/calibration/unified.py",
    "src/archguard/calibration/numeric.py",
    "src/archguard/infrastructure/unified_hybrid.py",
)
PUBLIC = (
    *SOURCES,
    str(PUB),
    str(CORRECTION),
    str(io.BASE / "p023-verification-v1.json"),
    "docs/verification/PROMPT_023.md",
)
ANCHORS = p022.ANCHORS | {
    "P022": "8629d728bf80b4a5ba3009e8730ec14062a77abc",
    "P022.LIVE": "c416b1c1376009c8591026165323268201882495",
}
_OFFLINE: contextvars.ContextVar[bool] = contextvars.ContextVar("p023_offline", default=False)
_BOUNDARY: contextvars.ContextVar[tuple[Path, Path, str] | None] = contextvars.ContextVar(
    "p023_boundary", default=None
)
_INSTALLED = False
_VALIDATION_OPENS: contextvars.ContextVar[int] = contextvars.ContextVar(
    "p023_validation_opens", default=0
)
_RUNTIME = tuple(
    p.resolve() for p in (Path(__file__).parents[2], Path(sys.prefix), Path(sys.base_prefix))
)


def audit_hook(event: str, args: tuple[Any, ...]) -> None:
    if not _OFFLINE.get():
        return
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}:
        raise PermissionError("P023_OFFLINE_NO_PROVIDER_OR_NETWORK")
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if path.name.startswith(".env"):
        raise PermissionError("P023_NO_CREDENTIAL_ACCESS")
    if path.is_relative_to(io.FINAL.resolve()) or path.is_relative_to(
        (io.PRIVATE / "human-intake").resolve()
    ):
        raise PermissionError("P023_FINAL_OR_REVIEWER_DATA_DENIED")
    coor = (io.PRIVATE / "coordinator").resolve()
    if path.is_relative_to(coor) and path.name not in {
        "development-split.json",
        "development-semantic-reuse.json",
    }:
        raise PermissionError("P023_FINAL_COORDINATOR_DATA_DENIED")
    boundary = _BOUNDARY.get()
    if boundary is None:
        return
    inputs, outputs, phase = boundary
    writes = any(c in (args[1] or "") for c in "wax+") or bool(
        args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    )
    if path.is_relative_to(outputs):
        return
    allowed = {"metadata.json", "train.json"}
    if phase in {"VALIDATE", "VERIFY"}:
        allowed |= {"validation-features.json", "validation-labels.json"}
    if not writes and path.parent == inputs and path.name in allowed:
        if path.name == "validation-labels.json":
            _VALIDATION_OPENS.set(_VALIDATION_OPENS.get() + 1)
        return
    if (
        not writes
        and path.suffix in {".py", ".pyc", ".so"}
        and any(path.is_relative_to(r) for r in _RUNTIME)
    ):
        return
    raise PermissionError("P023_DEVELOPMENT_POSITIVE_ALLOWLIST_DENIED")


def enable_offline() -> None:
    global _INSTALLED
    if not _INSTALLED:
        sys.addaudithook(audit_hook)
        _INSTALLED = True
    _OFFLINE.set(True)


@contextmanager
def training_scope(inputs: Path, outputs: Path, phase: str) -> Iterator[None]:
    previous = _OFFLINE.get()
    enable_offline()
    token = _BOUNDARY.set((inputs.resolve(), outputs.resolve(), phase))
    try:
        yield
    finally:
        _BOUNDARY.reset(token)
        _OFFLINE.set(previous)


def seal(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    value = payload | {"fingerprint": digest(payload)}
    if path.exists():
        if io.read_seal(path) != value:
            raise ValueError("P023_IMMUTABLE_ARTIFACT_DRIFT")
        return value
    return io.append_seal(path, payload)


def git_gate() -> None:
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        PUBLIC,
    )
    for sha in ANCHORS.values():
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P023_LINEAGE_DRIFT")
    chain = ("P019", "P020_CLOSURE", "P021.A", "P021.B.1", "P021.B", "P022", "P022.LIVE")
    for a, b in zip(chain, chain[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", ANCHORS[a], ANCHORS[b]], capture_output=True
        ).returncode:
            raise ValueError("P023_LINEAGE_ORDER_DRIFT")
    for name in LEGACY:
        committed = subprocess.check_output(["git", "show", f"{ANCHORS['P020_CLOSURE']}:{name}"])
        if committed != Path(name).read_bytes():
            raise ValueError("P023_FROZEN_IMPLEMENTATION_DRIFT")


def protocol_gate() -> dict[str, Any]:
    registry = io.read_seal(
        io.BASE / "p020-registry-v2.json",
        "2bec29bb5d19419d90e8a5627a49044c82c33f7f13528116d587ade70d0a4116",
    )
    hp = io.read_seal(
        io.BASE / "p020-hybrid-protocol-v1.json",
        "331ffb2bc8d9c9d8b99c2bd4d12fd5e929ba50b584b02eb49360b2e9eba2b77a",
    )
    ab = io.read_seal(
        io.BASE / "p020-ablation-protocol-v1.json",
        "b0f57d269f7c945afa10d9ecd604700d1c1892eb95a98dac2e197fed0dc4b959",
    )
    if digest(
        frozen.FEATURES
    ) != "1febc401be51406691f4816557e504b0a5f3698b29473951c497adc9e12728f2" or canonical(
        hp
    ) != canonical({**frozen.hybrid_protocol(), "fingerprint": digest(frozen.hybrid_protocol())}):
        raise ValueError("P023_PROTOCOL_SEMANTIC_DRIFT")
    if registry[
        "model_selection_fingerprint"
    ] != "7019b8638d9830ff5bb6a6cf7ae7263d7b9d5ca08d2c2a79f3808139c54d01e2" or ab[
        "configurations"
    ] != [list(c) for c in frozen.ABLATIONS]:
        raise ValueError("P023_SELECTION_OR_ABLATION_DRIFT")
    return registry


def prepare() -> dict[str, Any]:
    enable_offline()
    git_gate()
    registry = protocol_gate()
    dev = io.read_seal(io.BASE / "p020-development-freeze-v1.json", registry["development_freeze"])
    manifest = io.read_seal(old.DEV / "inputs/manifest.json", dev["manifest_fingerprint"])
    split = io.read_seal(
        io.PRIVATE / "coordinator/development-split.json",
        "159aae41b351cc2e100f082ae91f5eec382329730c7c5f4a4a54b67246f6504a",
    )
    evidence = io.read_seal(old.DEV / "evidence/evidence.json", registry["development_evidence"])
    for n, key in (
        ("static-output.json", "static_output_fingerprint"),
        ("graph-output.json", "graph_output_fingerprint"),
    ):
        verify_opaque_seal(old.DEV / "evidence" / n, evidence[key])
    normalized = io.read_seal(
        p022.LEDGER / "normalized-assessments.json",
        "da3f8f3f027eeaed0140c9ae2ce3fa137715e274977e5396522be4522855be81",
    )
    snapshots = io.PRIVATE / "p022-development-live-freeze-v1"
    pins = {
        "raw-ledger.json": "0a2a683cb7b9b53649b16510ca0bb82335e288b08d88276f93a57f2c9c9c8a9f",
        "usage-ledger.json": "4f058bdc0d528663af86516ab5bcb8ee92bb5219618e43036bd895041935f3bb",
        "execution-lineage.json": (
            "9be63a388cf6d56002d9b4958705377f68e5696681afc2552af4e490aa344723"
        ),
        "completion-receipt.json": (
            "7c67c7cc118b33a99e3a559584a975c740ddb11d88a5f9b929b15d13f115dc2c"
        ),
        "freeze-receipt.json": "8856006a895018463c76a1a085f84725ae49dcf23c9dad51e8ddf77fda0ca71a",
    }
    for n, fp in pins.items():
        verify_opaque_seal(snapshots / n, fp)
    receipt = io.read_seal(snapshots / "freeze-receipt.json", pins["freeze-receipt.json"])
    io.verify_files(
        snapshots,
        receipt["files"] | {"freeze-receipt.json": io.sha(snapshots / "freeze-receipt.json")},
    )
    if any(io.sha(p022.LEDGER / n) != h for n, h in receipt["original_ledger_files"].items()):
        raise ValueError("P023_BLOCKED_P022_LIVE_DRIFT")
    with live.executor_scope(p022.ROOT, p022.LEDGER):
        rm, config, pricing = live.load_bundle(p022.ROOT)
        state = live.ledger_state(p022.LEDGER, rm, config, pricing)
    if len(state["accepted"]) != 180 or state["provider_invocations"] != 180 or state["ambiguous"]:
        raise ValueError("P023_BLOCKED_P022_LIVE_DRIFT")
    semantic = io.read_seal(
        P016_NORMAL, "a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273"
    )
    reuse = io.read_seal(
        io.PRIVATE / "coordinator/development-semantic-reuse.json", registry["semantic_reuse"]
    )
    sem_requests = io.read_seal(
        P016 / "request-manifest.json",
        "ec83ee1485a1275846b7c14ecfafad9db4749f0ca15e06d633d6ee9254c071b5",
    )
    sem_contexts = io.read_seal(
        P016 / "context-manifest.json", sem_requests["context_manifest_fingerprint"]
    )
    structural_truth = io.read_seal(
        old.P019 / "truth-v1.json",
        "f53ab09564d0481025ffb00a8cbef868a8085b69dca7ceaf2a390d577aeb0e24",
    )
    human = io.read_seal(
        SEMANTIC_TRUTH, "1186f5bd6bc942a1e29da3d1861b3dbab8e330d2d38f5e17ca84ed97cac84276"
    )

    def unique(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
        mapped = {r[key]: r for r in rows}
        if len(mapped) != len(rows):
            raise ValueError("P023_DUPLICATE_BINDING")
        return mapped

    inputs = unique(manifest["rows"], "execution_id")
    components = unique(evidence["records"], "execution_id")
    memberships = unique(split["rows"], "scientific_case_id")
    struct_labels = unique(structural_truth["rows"], "case_id")
    semantic_labels = unique(human["cases"], "scientific_case_id")
    semantic_sources = unique(
        [a for a in semantic["assessments"] if a["strategy"] == "GRAPH_GUIDED"], "execution_case_id"
    )
    graph_contexts = unique(
        [r for r in sem_contexts["requests"] if r["strategy"] == "GRAPH_GUIDED"], "request_id"
    )
    structural_sources = {r["execution_id"]: state["accepted"][r["request_id"]] for r in rm["rows"]}
    struct_contexts = {r["execution_id"]: r for r in rm["rows"]}
    semantic_reuse = unique(reuse["rows"], "scientific_case_id")
    if (
        set(inputs) != set(memberships)
        or set(inputs) != set(components)
        or len(inputs) != 280
        or len(structural_sources) != 180
        or len(semantic_reuse) != 100
        or evidence["alignment_version"] != "evidence-alignment-v2"
        or dev["final_overlap"] != 0
    ):
        raise ValueError("P023_INCOMPLETE_DEVELOPMENT_JOIN")
    joined = []
    llm_inventory = []
    truth_binding = []
    for cid in sorted(inputs, key=digest):
        inp = inputs[cid]
        member = memberships[cid]
        component = components[cid]
        rule = inp["target_rule_id"]
        if cid in structural_sources:
            accepted = structural_sources[cid]
            assessment = accepted["assessment"]
            category = "POSITIVE" if struct_labels[cid]["truth"] else "NEGATIVE"
            if struct_labels[cid]["rule"] != rule:
                raise ValueError("P023_TRUTH_RULE_DRIFT")
            source = "P022.LIVE"
            normal_fp = normalized["fingerprint"]
            truncated = struct_contexts[cid]["truncated"]
        else:
            item = semantic_reuse[cid]
            accepted = item["accepted_assessment"]
            if (
                accepted != semantic_sources[accepted["execution_case_id"]]
                or item["normalized_fingerprint"] != semantic["fingerprint"]
            ):
                raise ValueError("P023_SEMANTIC_REUSE_DRIFT")
            original = accepted["assessment"]
            context = graph_contexts[accepted["request_id"]]
            if (
                context["target_rule"] != rule
                or context["execution_case_id"] != accepted["execution_case_id"]
                or original["candidate_rule_id"] != rule
                or semantic_labels[cid]["target_rule"] != rule
            ):
                raise ValueError("P023_SEMANTIC_RULE_BINDING_DRIFT")
            assessment = dict(
                request_id=original["request_id"],
                target_rule_id=rule,
                decision=original["judgment"],
                subject_node_ids=original["subject_node_ids"],
                short_reason=original["short_reason"],
                evidence_refs=original["evidence_refs"],
                limitations=original["limitations"],
            )
            category = semantic_labels[cid]["final_category"]
            source = "P016"
            normal_fp = semantic["fingerprint"]
            truncated = context["truncated"]
        if (
            member["category"] != category
            or member["target_rule_id"] != rule
            or component["target_rule_id"] != rule
        ):
            raise ValueError("P023_AUTHORITATIVE_TRUTH_BINDING_DRIFT")
        carrier = frozen.UnifiedAssessment.model_validate(assessment)
        values = old.candidate_values(component, carrier, truncated=truncated)
        if component["cycle_proof"] and rule != "ARCH003":
            raise ValueError("P023_PRECEDENCE_ROUTING_DRIFT")
        raw = carrier.decision
        label = 1 if category == "POSITIVE" else 0 if category == "NEGATIVE" else None
        ev = {c: component[c] for c in ("STATIC", "GRAPH")} | dict(
            LLM="INSUFFICIENT_EVIDENCE" if raw == "INSUFFICIENT_CONTEXT" else raw,
            static_proof=component["static_proof"],
            cycle_proof=component["cycle_proof"],
        )
        joined.append(
            dict(
                case_id=cid,
                project_id=member["project_id"],
                rule_id=rule,
                language=inp["language"],
                cohort="DEVELOPMENT",
                split=member["split"],
                category=category,
                label=label,
                llm_bound=True,
                llm_decision=raw,
                values=values,
                evidence=ev,
            )
        )
        llm_inventory.append(
            dict(
                case_id=cid,
                rule_id=rule,
                source=source,
                normalized_source_fingerprint=normal_fp,
                accepted_source_fingerprint=digest(accepted),
                request_id=carrier.request_id,
                decision=raw,
                truncated=truncated,
            )
        )
        truth_binding.append(
            dict(
                case_id=cid,
                rule_id=rule,
                category=category,
                source="P019" if source == "P022.LIVE" else "P015",
                source_fingerprint=structural_truth["fingerprint"]
                if source == "P022.LIVE"
                else human["fingerprint"],
            )
        )
    train = [r for r in joined if r["split"] == "TRAIN"]
    val = [r for r in joined if r["split"] == "VALIDATION"]
    kernel.development_contract(joined, llm_inventory, truth_binding)
    source_bindings = {n: io.sha(Path(n)) for n in (*SOURCES, *LEGACY)}
    llm = seal(
        COORDINATOR / "llm-inventory.json",
        dict(rows=llm_inventory, expected=280, structural=180, semantic=100),
    )
    truth = seal(COORDINATOR / "truth-binding.json", dict(rows=truth_binding))
    join = seal(
        COORDINATOR / "development-join.json",
        dict(
            rows=joined,
            llm_fingerprint=llm["fingerprint"],
            truth_fingerprint=truth["fingerprint"],
            component_fingerprint=evidence["fingerprint"],
            split_fingerprint=split["fingerprint"],
        ),
    )
    metadata = dict(
        version="p023-development-inputs-v1",
        development_cases=280,
        structural=180,
        semantic=100,
        TRAIN=196,
        VALIDATION=84,
        train_projects=196,
        validation_projects=84,
        project_overlap=0,
        final_overlap=0,
        final_overlap_authority=dev["fingerprint"],
        source_bindings=source_bindings,
        implementation_fingerprint=digest(source_bindings),
        llm_evidence_fingerprint=llm["fingerprint"],
        truth_binding_fingerprint=truth["fingerprint"],
        join_fingerprint=join["fingerprint"],
        component_fingerprint=evidence["fingerprint"],
        split_fingerprint=split["fingerprint"],
        feature_schema_fingerprint=digest(frozen.FEATURES),
        hybrid_protocol_fingerprint=registry["hybrid_protocol"],
        ablation_protocol_fingerprint=registry["ablation_protocol"],
        selection_rule_fingerprint=registry["model_selection_fingerprint"],
        provider_calls=0,
        paid_execution_approved=False,
        final_truth_reads=0,
    )
    validation_features = [
        {k: v for k, v in r.items() if k not in {"category", "label"}} for r in val
    ]
    validation_labels = [{k: r[k] for k in ("case_id", "category", "label")} for r in val]
    files = {
        "train.json": dict(rows=train),
        "validation-features.json": dict(rows=validation_features),
        "validation-labels.json": dict(rows=validation_labels),
    }
    metadata["data_files"] = {name: digest(payload) for name, payload in files.items()}
    if not INPUT.exists():

        def build(stage: Path) -> None:
            for name, payload in files.items():
                io.append_seal(stage / name, payload)
            io.append_seal(stage / "metadata.json", metadata)

        atomic_directory(INPUT, build)
    for name, payload in files.items():
        if io.read_seal(INPUT / name) != payload | {"fingerprint": digest(payload)}:
            raise ValueError("P023_INPUT_DRIFT")
    if io.read_seal(INPUT / "metadata.json") != metadata | {"fingerprint": digest(metadata)}:
        raise ValueError("P023_IMPLEMENTATION_OR_INPUT_DRIFT")
    return metadata


def matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return dict(
        feature_order=kernel.NAMES,
        feature_schema_fingerprint=digest(frozen.FEATURES),
        rows=[
            dict(case_id=r["case_id"], values=[r["values"][n] for n in kernel.NAMES]) for r in rows
        ],
    )


def labeled_predictions(
    rows: list[dict[str, Any]], models: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    result = {}
    for configuration, components in kernel.ABLATIONS.items():
        keys = (
            [configuration]
            if len(components) == 1
            else [f"{configuration}-{m}" for m in ("H0", "H1", "H2")]
        )
        for key in keys:
            result[key] = [
                kernel.component_prediction(r, components[0])
                if len(components) == 1
                else kernel.prediction(r, models[key])
                for r in rows
            ]
    return result


def fit_runs(inputs: Path, stage: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    """Both independent TRAIN runs finish before the single validation-label read."""
    _VALIDATION_OPENS.set(0)
    with training_scope(inputs, stage, "FIT"):
        train = io.read_seal(inputs / "train.json", metadata["data_files"]["train.json"])["rows"]
        models_a = kernel.fitted_candidates(train, metadata["implementation_fingerprint"])
        models_b = kernel.fitted_candidates(
            json.loads(canonical(train)), metadata["implementation_fingerprint"]
        )
        if canonical(models_a) != canonical(models_b):
            raise ValueError("P023_CANDIDATE_REPRODUCIBILITY_FAILURE")
        for run, models in (("primary", models_a), ("reproduction", models_b)):
            for key, model in models.items():
                seal(
                    stage / run / "candidates" / f"{key}.json",
                    {k: v for k, v in model.items() if k != "fingerprint"},
                )
            seal(
                stage / run / "train-candidates-freeze.json",
                dict(
                    candidates={k: m["fingerprint"] for k, m in models.items()},
                    train_only=True,
                    validation_opened=False,
                ),
            )
        train_matrix = seal(stage / "matrices/train-features.json", matrix(train))
        train_labels = seal(
            stage / "matrices/train-labels.json",
            dict(rows=[{k: r[k] for k in ("case_id", "category", "label")} for r in train]),
        )
        train_predictions = labeled_predictions(train, models_a)
        train_metrics = {
            key: kernel.views(
                train,
                decisions,
                tuple(models_a[key]["artifact"]["components"])
                if key in models_a
                else kernel.ABLATIONS[key],
            )
            for key, decisions in train_predictions.items()
        }
        if _VALIDATION_OPENS.get() != 0:
            raise ValueError("P023_VALIDATION_ACCESSED_DURING_FIT")
    with training_scope(inputs, stage, "VALIDATE"):
        features = io.read_seal(
            inputs / "validation-features.json", metadata["data_files"]["validation-features.json"]
        )["rows"]
        labels = io.read_seal(
            inputs / "validation-labels.json", metadata["data_files"]["validation-labels.json"]
        )["rows"]
        by_id = {r["case_id"]: r for r in labels}
        if len(by_id) != len(labels) or set(by_id) != {r["case_id"] for r in features}:
            raise ValueError("P023_VALIDATION_LABEL_JOIN_DRIFT")
        validation = [
            r | {k: by_id[r["case_id"]][k] for k in ("label", "category")}
            for r in sorted(features, key=lambda r: digest(r["case_id"]))
        ]
        kernel.validate_rows(validation, "VALIDATION")
        tables, predictions, selected = kernel.validation_selection(validation, models_a)
        replay_tables, replay_predictions, replay_selected = kernel.validation_selection(
            validation, models_b
        )
        if canonical((tables, predictions, selected)) != canonical(
            (replay_tables, replay_predictions, replay_selected)
        ):
            raise ValueError("P023_SELECTION_REPRODUCIBILITY_FAILURE")
        if _VALIDATION_OPENS.get() != 1:
            raise ValueError("P023_VALIDATION_OPEN_COUNT_DRIFT")
        val_matrix = seal(stage / "matrices/validation-features.json", matrix(validation))
        val_labels = seal(stage / "matrices/validation-labels.json", dict(rows=labels))
        matrix_reproductions = {}
        for run, train_rows, val_rows in (
            ("primary", train, validation),
            ("reproduction", json.loads(canonical(train)), json.loads(canonical(validation))),
        ):
            matrix_reproductions[run] = {
                partition: seal(stage / run / f"{partition}-features.json", matrix(data))[
                    "fingerprint"
                ]
                for partition, data in (("train", train_rows), ("validation", val_rows))
            }
        if matrix_reproductions["primary"] != matrix_reproductions["reproduction"]:
            raise ValueError("P023_MATRIX_REPRODUCIBILITY_FAILURE")
        selection = seal(
            stage / "validation-selection-receipt.json",
            dict(
                version="p023-one-pass-selection-v1",
                candidate_fingerprints={k: m["fingerprint"] for k, m in models_a.items()},
                validation_metrics=tables,
                selected=selected,
                selection_rule_fingerprint=metadata["selection_rule_fingerprint"],
                chronology=[
                    "PRIMARY_TRAIN_CANDIDATES_FROZEN",
                    "INDEPENDENT_REPRODUCTION_TRAIN_CANDIDATES_FROZEN",
                    "VALIDATION_FEATURES_OPENED",
                    "VALIDATION_LABELS_OPENED_ONCE",
                    "PRIMARY_SELECTION_ONCE",
                    "IDENTICAL_REPRODUCTION_SELECTION_REPLAY",
                ],
                validation_label_file_opens=1,
                primary_comparisons=1,
                reproduction_replays=1,
                all_train_candidates_before_validation=True,
                post_selection_refit=False,
                final_test_access=False,
            ),
        )
        registry_rows = {}
        for configuration, choice in selected.items():
            key = f"{configuration}-{choice['family']}"
            model = models_a[key]
            registry_rows[configuration] = dict(
                configuration=configuration,
                selected_family=choice["family"],
                candidate_fingerprint=model["fingerprint"],
                threshold=model["artifact"]["threshold"],
                preprocessing_fingerprint=model["preprocessing_fingerprint"],
                parameter_fingerprint=model["parameter_fingerprint"],
                precedence_fingerprint=model["precedence_fingerprint"],
                implementation_fingerprint=model["implementation_fingerprint"],
                train_split_fingerprint=metadata["split_fingerprint"],
                validation_selection_receipt=selection["fingerprint"],
                final_full_hybrid_model=configuration == "A7",
            )
            seal(
                stage / "selected" / f"{configuration}.json",
                {k: v for k, v in model.items() if k != "fingerprint"},
            )
        registry = seal(
            stage / "selected-model-registry.json",
            dict(
                version="p023-selected-models-v1", models=registry_rows, post_selection_refit=False
            ),
        )
        reproduced_registry = seal(
            stage / "reproduction/selected-model-registry.json",
            dict(
                version="p023-selected-models-v1",
                models={
                    config: entry
                    | {
                        "candidate_fingerprint": models_b[
                            f"{config}-{replay_selected[config]['family']}"
                        ]["fingerprint"]
                    }
                    for config, entry in registry_rows.items()
                },
                post_selection_refit=False,
            ),
        )
        if reproduced_registry != registry:
            raise ValueError("P023_REGISTRY_REPRODUCIBILITY_FAILURE")
        final_model = models_a[f"A7-{selected['A7']['family']}"]
        seal(
            stage / "final-full-hybrid-model.json",
            {k: v for k, v in final_model.items() if k != "fingerprint"},
        )
        prediction_registry = {}
        for run, run_models, run_tables, run_predictions, run_selected in (
            ("primary", models_a, tables, predictions, selected),
            ("reproduction", models_b, replay_tables, replay_predictions, replay_selected),
        ):
            train_preds = labeled_predictions(train, run_models)
            for partition, rows, outputs in (
                ("TRAIN", train, train_preds),
                ("VALIDATION", validation, run_predictions),
            ):
                for config, choice in run_selected.items():
                    outputs[f"SELECTED-{config}"] = outputs[f"{config}-{choice['family']}"]
                snapshot = seal(
                    stage / run / f"{partition.lower()}-predictions.json",
                    dict(
                        partition=partition,
                        predictions={
                            key: [
                                dict(case_id=r["case_id"], decision=d)
                                for r, d in zip(rows, ds, strict=True)
                            ]
                            for key, ds in outputs.items()
                        },
                    ),
                )
                prediction_registry[f"{run}:{partition}"] = snapshot["fingerprint"]
            seal(stage / run / "selection.json", dict(metrics=run_tables, selected=run_selected))
        predictions_receipt = seal(
            stage / "development-prediction-registry.json",
            dict(fingerprints=prediction_registry, final_predictions=0),
        )
        reproduced = seal(
            stage / "reproducibility.json",
            dict(
                candidate_equal=True,
                metrics_equal=True,
                selected_equal=True,
                feature_matrices_equal=True,
                preprocessing_equal=True,
                selected_registry_equal=True,
                selected_models={
                    k: {"first": v, "second": replay_selected[k]} for k, v in selected.items()
                },
                train_matrix_fingerprint=train_matrix["fingerprint"],
                validation_matrix_fingerprint=val_matrix["fingerprint"],
                independent_matrix_fingerprints=matrix_reproductions,
                selected_registry_fingerprint=registry["fingerprint"],
            ),
        )
        a7 = predictions[f"A7-{selected['A7']['family']}"]
        comparisons = {
            **{k: predictions[k] for k in ("A1", "A2", "A3")},
            **{k: predictions[f"{k}-{selected[k]['family']}"] for k in ("A4", "A5", "A6")},
        }
        paired = {}
        for name, other in comparisons.items():
            counts: Counter[str] = Counter()
            transitions: Counter[str] = Counter()
            for r, x, y in zip(validation, a7, other, strict=True):
                if r["label"] is None:
                    continue
                expected = "SUPPORTED" if r["label"] else "NOT_SUPPORTED"
                x_correct = x == expected
                y_correct = y == expected
                counts[
                    "both_correct"
                    if x_correct and y_correct
                    else "hybrid_only_correct"
                    if x_correct
                    else "baseline_only_correct"
                    if y_correct
                    else "both_incorrect"
                ] += 1
                transitions[f"{x}->{y}"] += 1
            paired[name] = dict(
                counts={
                    n: counts[n]
                    for n in (
                        "both_correct",
                        "hybrid_only_correct",
                        "baseline_only_correct",
                        "both_incorrect",
                    )
                },
                categorical_transitions=dict(transitions),
            )
        strata = {}
        for name, field in (("rule", "rule_id"), ("language", "language"), ("family", "rule_id")):
            keys = sorted(
                {frozen.family(r[field]) if name == "family" else r[field] for r in validation}
            )
            strata[name] = {
                key: kernel.metrics(
                    [
                        r
                        for r in validation
                        if (frozen.family(r[field]) if name == "family" else r[field]) == key
                    ],
                    [
                        d
                        for r, d in zip(validation, a7, strict=True)
                        if (frozen.family(r[field]) if name == "family" else r[field]) == key
                    ],
                )
                for key in keys
            }
    if canonical(models_a) != canonical(models_b):
        raise ValueError("P023_MODEL_CHANGED_AFTER_VALIDATION")
    return dict(
        version="p023-hybrid-development-v1",
        status="P023_HYBRID_DEVELOPMENT_TRAINING_COMPLETE",
        development_inputs={
            k: metadata[k]
            for k in (
                "development_cases",
                "structural",
                "semantic",
                "TRAIN",
                "VALIDATION",
                "train_projects",
                "validation_projects",
                "project_overlap",
                "final_overlap",
            )
        },
        train_binary_cases=sum(r["label"] is not None for r in train),
        validation_binary_cases=sum(r["label"] is not None for r in validation),
        train_nonbinary=dict(Counter(r["category"] for r in train if r["label"] is None)),
        validation_nonbinary=dict(Counter(r["category"] for r in validation if r["label"] is None)),
        validation_label="DEVELOPMENT VALIDATION — NON-FINAL",
        train_label="TRAIN_DIAGNOSTIC_ONLY",
        validation_metrics=tables,
        train_metrics=train_metrics,
        selected_models=registry_rows,
        final_full_hybrid_family=selected["A7"]["family"],
        final_full_hybrid_model_fingerprint=final_model["fingerprint"],
        candidate_fingerprints={k: m["fingerprint"] for k, m in models_a.items()},
        candidate_thresholds={k: m["artifact"]["threshold"] for k, m in models_a.items()},
        solver_convergence={k: m["solver"] for k, m in models_a.items()},
        fingerprints=dict(
            llm_evidence=metadata["llm_evidence_fingerprint"],
            component_evidence=metadata["component_fingerprint"],
            truth_binding=metadata["truth_binding_fingerprint"],
            evidence_join=metadata["join_fingerprint"],
            TRAIN_features=train_matrix["fingerprint"],
            TRAIN_labels=train_labels["fingerprint"],
            VALIDATION_features=val_matrix["fingerprint"],
            VALIDATION_labels=val_labels["fingerprint"],
            selection_receipt=selection["fingerprint"],
            selected_registry=registry["fingerprint"],
            prediction_registry=predictions_receipt["fingerprint"],
            reproducibility=reproduced["fingerprint"],
            feature_schema=metadata["feature_schema_fingerprint"],
            hybrid_protocol=metadata["hybrid_protocol_fingerprint"],
            ablation_protocol=metadata["ablation_protocol_fingerprint"],
            selection_rule=metadata["selection_rule_fingerprint"],
        ),
        paired_diagnostics=paired,
        strata_descriptive=strata,
        validation_opens=1,
        reproduction_validation_replays=1,
        all_train_candidates_before_validation=True,
        post_selection_refit=False,
        final_truth_reads=0,
        final_evidence_fitting=False,
        final_hybrid_predictions=0,
        final_ablation_predictions=0,
        final_llm_calls=0,
        provider_calls=0,
        connectivity_calls=0,
        spend_usd=0,
        paid_execution_approved=False,
        security=False,
        hypothesis_conclusion=False,
    )


def verify_implementation(metadata: dict[str, Any]) -> None:
    current = {n: io.sha(Path(n)) for n in (*SOURCES, *LEGACY)}
    if metadata["source_bindings"] == current:
        return
    correction = io.read_seal(CORRECTION)
    if (
        correction["original_source_bindings"] != metadata["source_bindings"]
        or correction["corrected_source_bindings"] != current
        or correction["original_implementation_fingerprint"]
        != metadata["implementation_fingerprint"]
        or correction["scientific_refit"] is not False
    ):
        raise ValueError("P023_IMPLEMENTATION_DRIFT")
    archive = io.read_seal(EXECUTION_SOURCE / "execution-source-freeze.json")
    if archive["implementation_fingerprint"] != metadata["implementation_fingerprint"]:
        raise ValueError("P023_EXECUTION_SOURCE_DRIFT")
    io.verify_files(
        EXECUTION_SOURCE,
        archive["source_bindings"]
        | {
            "execution-source-freeze.json": io.sha(
                EXECUTION_SOURCE / "execution-source-freeze.json"
            )
        },
    )
    original_kernel = "src/archguard/benchmark/hybrid_development.py"
    if archive["source_bindings"][original_kernel] != current[SOURCES[0]]:
        raise ValueError("P023_CALIBRATION_RELOCATION_SEMANTIC_DRIFT")
    original = ast.parse((EXECUTION_SOURCE / SOURCES[1]).read_text())
    corrected = ast.parse(Path(SOURCES[1]).read_text())
    before = {
        n.name: ast.dump(n, include_attributes=False)
        for n in original.body
        if isinstance(n, ast.FunctionDef)
    }
    after = {
        n.name: ast.dump(n, include_attributes=False)
        for n in corrected.body
        if isinstance(n, ast.FunctionDef)
    }
    unchanged = tuple(k for k in before if k not in {"execute", "verify_outputs"})
    if any(before[k] != after[k] for k in unchanged):
        raise ValueError("P023_SCIENTIFIC_ORCHESTRATION_DRIFT")
    if any(metadata["source_bindings"][n] != current[n] for n in LEGACY):
        raise ValueError("P023_FROZEN_IMPLEMENTATION_DRIFT")


def verify_outputs() -> dict[str, Any]:
    enable_offline()
    metadata = io.read_seal(INPUT / "metadata.json")
    verify_implementation(metadata)
    io.verify_files(
        INPUT, {n: io.sha(INPUT / n) for n in (*metadata["data_files"], "metadata.json")}
    )
    for name, fp in metadata["data_files"].items():
        io.read_seal(INPUT / name, fp)
    receipt = io.read_seal(OUTPUT / "output-freeze.json")
    io.verify_files(
        OUTPUT, receipt["files"] | {"output-freeze.json": io.sha(OUTPUT / "output-freeze.json")}
    )
    result = io.read_seal(OUTPUT / "public-result.json")
    if result["fingerprint"] != receipt["public_result_fingerprint"]:
        raise ValueError("P023_OUTPUT_BINDING_DRIFT")
    if CORRECTION.exists():
        correction = io.read_seal(CORRECTION)
        if (
            correction["scientific_result_fingerprint"] != result["fingerprint"]
            or correction["scientific_model_fingerprint"]
            != result["final_full_hybrid_model_fingerprint"]
        ):
            raise ValueError("P023_CORRECTION_MODEL_BINDING_DRIFT")
    for configuration, entry in result["selected_models"].items():
        selected = io.read_seal(OUTPUT / "selected" / f"{configuration}.json")
        original = io.read_seal(
            OUTPUT / "primary/candidates" / f"{configuration}-{entry['selected_family']}.json"
        )
        if selected != original or selected["fingerprint"] != entry["candidate_fingerprint"]:
            raise ValueError("P023_POST_SELECTION_REFIT_DRIFT")
    if io.read_seal(OUTPUT / "final-full-hybrid-model.json") != io.read_seal(
        OUTPUT / "selected/A7.json"
    ):
        raise ValueError("P023_FINAL_MODEL_BINDING_DRIFT")
    if io.read_seal(OUTPUT / "selected-model-registry.json") != io.read_seal(
        OUTPUT / "reproduction/selected-model-registry.json"
    ):
        raise ValueError("P023_REGISTRY_REPRODUCIBILITY_FAILURE")
    return result


def execute() -> dict[str, Any]:
    if OUTPUT.exists():
        git_gate()
        protocol_gate()
        result = verify_outputs()
        seal(PUB, {k: v for k, v in result.items() if k != "fingerprint"})
        return result
    metadata = prepare()
    if RUN_CONTROL.exists():
        raise ValueError("P023_BLOCKED_INTERRUPTED_RUN_NO_AUTOMATIC_REFIT")
    io.append_seal(
        RUN_CONTROL,
        dict(
            input_fingerprint=digest(metadata),
            implementation_fingerprint=metadata["implementation_fingerprint"],
            automatic_restart_allowed=False,
        ),
    )

    def build(stage: Path) -> None:
        result = fit_runs(INPUT, stage, metadata)
        public = seal(stage / "public-result.json", result)
        io.append_seal(
            stage / "output-freeze.json",
            dict(
                version="p023-model-freeze-v1",
                files={
                    f.relative_to(stage).as_posix(): io.sha(f)
                    for f in stage.rglob("*")
                    if f.is_file()
                },
                public_result_fingerprint=public["fingerprint"],
                post_selection_refit=False,
                final_truth_access=False,
            ),
        )

    atomic_directory(OUTPUT, build)
    result = verify_outputs()
    seal(PUB, {k: v for k, v in result.items() if k != "fingerprint"})
    return result
