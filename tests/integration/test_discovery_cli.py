import json
import shutil
from pathlib import Path
from zipfile import ZipFile

import pytest

from archguard.cli import main

ROOT = Path(__file__).parents[2]
FIXTURES = ROOT / "tests/fixtures/discovery"


def test_human_summary_and_separation(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["architecture", "discover", str(FIXTURES / "mixed")]) == 0
    output = capsys.readouterr().out
    assert "Discovery results are hypotheses, not architecture conformance findings." in output
    assert "NOT CALIBRATED" in output and "Components: 12" in output
    assert "Discovered dependency: PRESENTATION → APPLICATION: 2" in output
    assert "Layer Violation" not in output and "Architecture does not conform" not in output
    assert "NOT CALIBRATED" in output


def test_export_bytes_match_stdout_and_repeat_without_leaking_source(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "discovery.json"
    args = [
        "architecture",
        "discover",
        str(FIXTURES / "mixed"),
        "--namespace",
        "cli-discovery",
        "--json",
        "--output",
        str(output),
    ]
    assert main(args) == 0
    first = capsys.readouterr().out
    assert output.read_text() == first
    assert main(args) == 0 and capsys.readouterr().out == first
    assert "PRIVATE_DECORATOR_ARGUMENT" not in first and "PRIVATE_JSX_CONTENT" not in first
    assert str(ROOT) not in first
    data = json.loads(first)
    assert data["statistics"]["components_total"] == 12 and not data["graph"]["findings"]
    assert not (tmp_path / "architecture.yaml").exists()


def test_no_target_spec_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        main(["architecture", "discover", str(FIXTURES / "mixed"), "--spec", "architecture.yaml"])
    assert error.value.code == 2
    assert "unrecognized arguments: --spec" in capsys.readouterr().err


def test_existing_target_file_does_not_define_discovery(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shutil.copytree(FIXTURES / "typescript-layered", tmp_path, dirs_exist_ok=True)
    (tmp_path / "architecture.yaml").write_text("THIS IS NOT A VALID TARGET SPEC")
    assert main(["architecture", "discover", str(tmp_path), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["statistics"]["components_total"] == 6
    assert data["graph"]["reproducibility"]["architecture_spec_fingerprint"] is None


@pytest.mark.parametrize(
    "case",
    [
        "missing_config",
        "invalid_json",
        "oversized",
        "deep",
        "invalid_profile",
        "bad_strength",
        "target_graph",
        "invalid_root",
        "missing_repository",
        "write_failure",
    ],
)
def test_typed_configuration_input_and_output_errors(
    case: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.json"
    args = ["architecture", "discover", str(FIXTURES / "mixed"), "--json"]
    if case == "missing_repository":
        args[2] = str(tmp_path / "missing")
    elif case == "write_failure":
        args += ["--output", str(tmp_path)]
    else:
        raw = {
            "invalid_profile": {"profile": "AI"},
            "bad_strength": {"minimum_role_strength": "AMBIGUOUS"},
            "target_graph": {"graph": {"projection": {"projection": "layer"}}},
            "invalid_root": {"module_root_hints": ["../src"]},
        }.get(case, {})
        if case != "missing_config":
            config.write_text(
                "PRIVATE_INVALID_CONFIG"
                if case == "invalid_json"
                else " " * 131073
                if case == "oversized"
                else "[" * 2000 + "]" * 2000
                if case == "deep"
                else json.dumps(raw)
            )
        args += ["--config", str(config)]
    assert main(args) == 2
    output = capsys.readouterr()
    assert not output.out and "PRIVATE_INVALID_CONFIG" not in output.err
    if case not in {"missing_repository", "write_failure"}:
        assert "INVALID_DISCOVERY_CONFIGURATION" in output.err


def test_config_exclusions_zip_and_incomplete_status(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "framework_signals": False,
                "graph_refinement": False,
                "graph": {"betweenness_node_limit": 1},
            }
        )
    )
    assert (
        main(
            [
                "architecture",
                "discover",
                str(FIXTURES / "mixed"),
                "--config",
                str(config),
                "--json",
                "--exclude",
                "typescript/**",
            ]
        )
        == 3
    )
    data = json.loads(capsys.readouterr().out)
    assert data["statistics"]["components_total"] == 6 and data["status"] == "INCOMPLETE"
    assert "ANNOTATION" not in data["statistics"]["evidence_count_by_type"]
    archive = tmp_path / "project.zip"
    with ZipFile(archive, "w") as stream:
        for path in sorted((FIXTURES / "typescript-layered").rglob("*")):
            if path.is_file():
                stream.write(path, str(path.relative_to(FIXTURES / "typescript-layered")))
    assert (
        main(
            [
                "architecture",
                "discover",
                str(archive),
                "--source",
                "zip",
                "--no-gitignore",
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["statistics"]["components_total"] == 6


def test_cycles_unknown_and_ambiguity_are_valid_hypotheses(
    capsys: pytest.CaptureFixture[str],
) -> None:
    for fixture, field in (("unknown", "role_unknown"), ("conflict", "layer_ambiguous")):
        assert main(["architecture", "discover", str(FIXTURES / fixture), "--json"]) == 0
        data = json.loads(capsys.readouterr().out)
        assert data["statistics"][field] > 0 and not data["graph"]["findings"]


def test_strict_and_graph_budget_invalid_exit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.json"
    config.write_text('{"graph":{"max_graph_nodes":1}}')
    assert (
        main(
            ["architecture", "discover", str(FIXTURES / "mixed"), "--config", str(config), "--json"]
        )
        == 2
    )
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID"
    (tmp_path / "bad.ts").write_text("export class {")
    assert main(["architecture", "discover", str(tmp_path), "--strict", "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID"
