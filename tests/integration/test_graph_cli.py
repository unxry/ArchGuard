import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from archguard.architecture.graph.result import GraphAnalysisResult
from archguard.cli import main

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/graph"
SPEC = ROOT / "examples/architecture/circular-component.yaml"


def test_no_spec_and_spec_cycle_modes_and_architecture_check(
    capsys: pytest.CaptureFixture[str],
) -> None:
    base = ["graph", "analyze", str(FIXTURES / "cyclic/java")]
    assert main([*base, "--json"]) == 0
    result = GraphAnalysisResult.model_validate_json(capsys.readouterr().out)
    assert len(result.cycles) == 1 and not result.findings
    assert main([*base, "--spec", str(SPEC)]) == 1
    human = capsys.readouterr().out
    assert (
        "ARCH003 findings: 1" in human
        and "sample.a.A → sample.b.B → sample.c.C → sample.a.A" in human
    )
    assert "Graph conformance: NON_CONFORMANT" in human
    assert (
        main(
            ["architecture", "check", str(FIXTURES / "cyclic/java"), "--spec", str(SPEC), "--json"]
        )
        == 1
    )
    combined = json.loads(capsys.readouterr().out)
    assert combined["statistics"]["findings_by_rule"] == {"ARCH003": 1}
    assert combined["statistics"]["rules_evaluated"] == 1
    assert main(["architecture", "check", str(FIXTURES / "acyclic/java"), "--spec", str(SPEC)]) == 0
    assert "CONFORMANT" in capsys.readouterr().out


def test_graph_export_config_overrides_and_determinism(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = tmp_path / "a.json", tmp_path / "b.json"
    base = [
        "graph",
        "analyze",
        str(FIXTURES / "hub"),
        "--config",
        str(ROOT / "examples/graph/research-demo.json"),
    ]
    assert main([*base, "--json", "--output", str(first)]) == 0
    output = capsys.readouterr()
    assert first.read_text() == output.out
    parsed = json.loads(output.out)
    assert parsed["statistics"]["candidate_count_by_rule"] == {
        "ARCH101": 2,
        "ARCH102": 1,
        "ARCH103": 1,
        "ARCH104": 1,
        "ARCH105": 2,
    }
    assert main([*base, "--json", "--output", str(second)]) == 0
    capsys.readouterr()
    assert first.read_bytes() == second.read_bytes()
    assert (
        main(
            [
                "graph",
                "analyze",
                str(FIXTURES / "cyclic/java"),
                "--projection",
                "file",
                "--relations",
                "CREATES",
                "--json",
            ]
        )
        == 0
    )
    overrides = json.loads(capsys.readouterr().out)
    assert (
        overrides["graph"]["projection"]["projection"] == "file" and not overrides["graph"]["edges"]
    )
    assert "GRAPH_PRIVATE_SOURCE_MARKER" not in output.out + output.err
    assert str(ROOT) not in output.out


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "invalid",
        "too_large",
        "deep",
        "invalid_thresholds",
        "unsupported_relation",
        "missing_repository",
        "output",
    ],
)
def test_graph_cli_typed_input_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    config = tmp_path / "config.json"
    config.write_text("{}")
    args = ["graph", "analyze", str(FIXTURES / "acyclic/java"), "--config", str(config), "--json"]
    if case == "missing":
        config.unlink()
    elif case == "invalid":
        config.write_text("PRIVATE_INVALID_CONFIG")
    elif case == "too_large":
        config.write_text(" " * 131_073)
    elif case == "deep":
        config.write_text("[" * 2_000 + "0" + "]" * 2_000)
    elif case == "invalid_thresholds":
        config.write_text('{"candidates": {"god_min_members": 3}}')
    elif case == "unsupported_relation":
        args += ["--relations", "READS"]
    elif case == "missing_repository":
        args[2] = str(tmp_path / "absent")
    elif case == "output":
        args += ["--output", str(tmp_path / "absent" / "result.json")]
    assert main(args) == 2
    output = capsys.readouterr()
    assert not output.out and "error" in json.loads(output.err.splitlines()[-1])
    assert "PRIVATE_INVALID_CONFIG" not in output.err and "Traceback" not in output.err


def test_graph_cli_zip_filtering_and_graph_limit_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("A.ts", "export class A {}")
        zipped.writestr("broken.java", "class Broken { int x = 1 }")
    args = ["graph", "analyze", str(archive), "--source", "zip", "--no-gitignore", "--json"]
    assert main([*args, "--exclude", "broken.java"]) == 0
    assert len(json.loads(capsys.readouterr().out)["graph"]["nodes"]) == 1
    assert main([*args, "--strict"]) == 2
    assert not json.loads(capsys.readouterr().out)["is_valid"]
    config = tmp_path / "limits.json"
    config.write_text('{"max_graph_nodes": 1}')
    assert (
        main(["graph", "analyze", str(FIXTURES / "cyclic/java"), "--config", str(config), "--json"])
        == 2
    )
    assert json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "GRAPH_RESOURCE_LIMIT"


def test_target_projection_requires_spec_and_metric_skip_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert (
        main(["graph", "analyze", str(FIXTURES / "cyclic/java"), "--projection", "layer", "--json"])
        == 2
    )
    assert (
        json.loads(capsys.readouterr().out)["diagnostics"][0]["code"] == "CLASSIFICATION_REQUIRED"
    )
    config = tmp_path / "metrics.json"
    config.write_text('{"betweenness_node_limit": 1}')
    assert (
        main(["graph", "analyze", str(FIXTURES / "cyclic/java"), "--config", str(config), "--json"])
        == 3
    )
    output = json.loads(capsys.readouterr().out)
    assert output["statistics"]["metrics_skipped"] == ["betweenness"]
    assert all(item["betweenness_centrality"] is None for item in output["metrics"])
