import json
from uuid import uuid5

import pytest

from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.adapters import (
    ai_predictions,
    graph_predictions,
    hybrid_predictions,
    static_predictions,
    training_records,
)
from archguard.benchmark.models import Label, PredictionArtifact, PredictionState, Task
from archguard.benchmark.resolver import LocatorResolver
from archguard.cli import main
from archguard.core.model.enums import NodeKind
from archguard.infrastructure.benchmark import prepared, safe_path
from archguard.infrastructure.hybrid_configuration import load_hybrid_ai_result
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.hybrid.conftest import semantic


def test_static_graph_and_hybrid_granularity(loaded):
    repo = "static-java-2-clean-arch002"
    pipeline, inputs = prepared(loaded, repo)
    static = static_predictions(inputs.iam, repo, inputs.static.findings)
    assert len(static) == 1
    assert all(x.kind == NodeKind.FILE for x in static[0].subjects.locators)
    hybrid = pipeline.execute_prepared(inputs)
    predictions = hybrid_predictions(inputs.iam, repo, hybrid)
    assert len(predictions) == 1 and predictions[0].subjects == static[0].subjects
    records = training_records(
        inputs.iam,
        next(r for r in loaded.dataset.repositories if r.repository_id == repo),
        loaded.truths,
        hybrid,
    )
    assert len(records) == 1
    assert records[0].ground_truth_label == Label.POSITIVE
    changed_truths = tuple(t.model_copy(update={"label": Label.NEGATIVE}) for t in loaded.truths)
    changed = training_records(
        inputs.iam,
        next(r for r in loaded.dataset.repositories if r.repository_id == repo),
        changed_truths,
        hybrid,
    )
    assert changed[0].ground_truth_label == Label.NEGATIVE
    assert changed[0].features == records[0].features
    assert changed[0].feature_fingerprint == records[0].feature_fingerprint
    assert "ground_truth" not in canonical(changed[0].features)
    assert "rationale" not in canonical(changed[0].features)
    assert not training_records(
        inputs.iam,
        next(r for r in loaded.dataset.repositories if r.repository_id == repo),
        (),
        hybrid,
    )
    for language in ("java", "typescript"):
        repo = f"static-{language}-3-clean-arch003"
        pipeline, inputs = prepared(loaded, repo)
        graph = graph_predictions(
            inputs.iam,
            repo,
            inputs.graph,
            inputs.graph_conformance,
            task=Task.CONFIRMED_VIOLATION_DETECTION,
        )
        assert len(graph) == 1 and len(graph[0].subjects.locators) == 3
        assert len(hybrid_predictions(inputs.iam, repo, pipeline.execute_prepared(inputs))) == 1
        with pytest.raises(ValueError):
            static_predictions(inputs.iam, repo, inputs.graph_conformance.findings)
    pipeline, inputs = prepared(loaded, "graph-java")
    structural = graph_predictions(inputs.iam, "graph-java", inputs.graph)
    assert {p.rule_id for p in structural} == {f"ARCH10{i}" for i in range(1, 6)}
    assert not hybrid_predictions(inputs.iam, "graph-java", pipeline.execute_prepared(inputs))
    assert all(p.state == PredictionState.CANDIDATE for p in structural)
    with pytest.raises(ValueError):
        graph_predictions(
            inputs.iam, "graph-java", inputs.graph, task=Task.SEMANTIC_CANDIDATE_DETECTION
        )


@pytest.mark.parametrize(
    "decision,state",
    [
        ("SUPPORTED", PredictionState.CANDIDATE),
        ("NOT_SUPPORTED", PredictionState.NEGATIVE),
        ("INSUFFICIENT_CONTEXT", PredictionState.ABSTAIN),
    ],
)
def test_saved_ai_adapter_contract_only(loaded, tmp_path, decision, state):
    repo_id = "semantic-java"
    pipeline, inputs = prepared(loaded, repo_id)
    truth = next(
        t
        for t in loaded.truths
        if t.repository_id == repo_id and t.rule_id == "ARCH202" and t.label == Label.NEGATIVE
    )
    target = LocatorResolver(inputs.iam).subjects(truth.subjects)[0]
    repo = next(r for r in loaded.dataset.repositories if r.repository_id == repo_id)
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(safe_path(loaded.root, repo.source_path)),
        )
    ) as repository:
        artifact = semantic(inputs, repository.workspace, target, "ARCH202", decision)
    path = tmp_path / "saved-ai.json"
    path.write_text(canonical(artifact))
    saved = load_hybrid_ai_result(path)
    predictions = ai_predictions(inputs.iam, repo_id, saved)
    assert len(predictions) == 1 and predictions[0].state == state
    assert predictions[0].subjects == truth.subjects
    with pytest.raises(ValueError):
        ai_predictions(inputs.iam, repo_id, saved.model_copy(update={"targets": ()}))
    # Join checks are independent of the test provider's answer; no quality metric.
    h = pipeline.execute_prepared(inputs, saved)
    records = training_records(inputs.iam, repo, loaded.truths, h)
    assert len(records) == 1 and records[0].ground_truth_label == Label.NEGATIVE
    assert "short_reason" not in canonical(records[0])


def test_method_to_component_and_ambiguity(loaded):
    _, inputs = prepared(loaded, "semantic-java")
    resolver = LocatorResolver(inputs.iam)
    method = next(n for n in inputs.iam.nodes if n.kind == NodeKind.METHOD)
    loc = resolver.from_ids((method.id,), kind=NodeKind.CLASS)
    assert loc.locators[0].kind == NodeKind.CLASS
    file_node = resolver.normalize(method.id, NodeKind.FILE)
    twin = resolver.normalize(method.id, NodeKind.CLASS).model_copy(
        update={"id": uuid5(method.id, "another-class")}
    )
    ambiguous = LocatorResolver(inputs.iam.model_copy(update={"nodes": (*inputs.iam.nodes, twin)}))
    with pytest.raises(ValueError):
        ambiguous.normalize(file_node.id, NodeKind.CLASS)


@pytest.mark.parametrize(
    "mode,task,expected",
    [
        ("STATIC_ONLY", "CONFIRMED_VIOLATION_DETECTION", (8, 0, 2, 10)),
        ("GRAPH_ONLY", "CONFIRMED_VIOLATION_DETECTION", (2, 0, 8, 10)),
        ("GRAPH_ONLY", "STRUCTURAL_SIGNAL_RETRIEVAL", (10, 0, 0, 12)),
    ],
)
def test_real_smoke_and_saved_predictions(loaded, tmp_path, capsys, mode, task, expected):
    dataset = str(loaded.root / "dataset.json")
    output = tmp_path / "run.json"
    args = ["benchmark", "smoke", dataset, "--mode", mode, "--task", task, "--output", str(output)]
    assert main(args) == 0
    r = json.loads(capsys.readouterr().out)
    c = r["confusion"]
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == expected
    artifact = tmp_path / "predictions.json"
    artifact.write_text(
        canonical(
            PredictionArtifact.model_validate(
                {
                    "dataset_fingerprint": loaded.fingerprint,
                    "closed_world_complete": True,
                    "predictions": r["predictions"],
                }
            )
        )
    )
    assert (
        main(
            [
                "benchmark",
                "evaluate",
                dataset,
                "--mode",
                mode,
                "--task",
                task,
                "--predictions",
                str(artifact),
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out) == r
    assert main([*args, "--split", "TEST"]) == 0
    capsys.readouterr()
    broken = json.loads(artifact.read_text())
    broken["dataset_fingerprint"] = "0" * 64
    artifact.write_text(json.dumps(broken))
    assert (
        main(
            [
                "benchmark",
                "evaluate",
                dataset,
                "--mode",
                mode,
                "--task",
                task,
                "--predictions",
                str(artifact),
            ]
        )
        == 2
    )


def test_export_partitions_are_source_free(loaded, tmp_path, capsys):
    output = tmp_path / "features"
    assert (
        main(
            [
                "benchmark",
                "export-features",
                str(loaded.root / "dataset.json"),
                "--output",
                str(output),
            ]
        )
        == 0
    )
    summary = json.loads(capsys.readouterr().out)
    assert summary["fitting"] is False
    assert all(summary["records"].values())
    for path in output.glob("*.jsonl"):
        for line in path.read_text().splitlines():
            record = json.loads(line)
            assert record["split"].lower() == path.stem
            assert record["features"]["fingerprint"] == record["feature_fingerprint"]
            for forbidden in (
                "raw_prompt",
                "source_fragments",
                "short_reason",
                "api_key",
                "/Users/",
            ):
                assert forbidden not in line
    second = tmp_path / "again"
    assert (
        main(
            [
                "benchmark",
                "export-features",
                str(loaded.root / "dataset.json"),
                "--output",
                str(second),
            ]
        )
        == 0
    )
    assert all(
        path.read_bytes() == (second / path.name).read_bytes() for path in output.glob("*.jsonl")
    )
    assert (
        main(
            [
                "benchmark",
                "export-features",
                str(loaded.root / "dataset.json"),
                "--output",
                str(output),
            ]
        )
        == 2
    )
