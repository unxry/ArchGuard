import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from archguard.architecture.conformance.models import StaticConformanceResult
from archguard.cli import main

EXAMPLES = Path(__file__).parents[2] / "examples" / "architecture"
FIXTURES = Path(__file__).parents[1] / "fixtures" / "conformance"


def test_spec_validate_json_and_human(capsys: pytest.CaptureFixture[str]) -> None:
    path = str(EXAMPLES / "layered-strict.yaml")
    assert main(["architecture", "validate", path, "--json"]) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["is_valid"] and len(output["specification"]["rules"]) == 4
    assert not output["diagnostics"] and len(output["fingerprint"]) == 64
    assert main(["architecture", "validate", path]) == 0
    human = capsys.readouterr().out
    assert "Valid: True" in human and "ARCH004" in human and "Specification: 1.0" in human


def test_check_exports_canonical_json_and_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "architecture",
        "check",
        str(FIXTURES / "violating/java"),
        "--spec",
        str(EXAMPLES / "layered-clean.yaml"),
    ]
    first, second = tmp_path / "result-a.json", tmp_path / "result-b.json"
    assert main([*args, "--json", "--output", str(first)]) == 1
    output = capsys.readouterr()
    result = StaticConformanceResult.model_validate_json(output.out)
    assert result.statistics.findings_by_rule == {"ARCH002": 1}
    assert first.read_text() == output.out
    assert "PRIVATE_CONFORMANCE_MARKER" not in output.out + output.err
    assert str(FIXTURES) not in output.out
    assert main([*args, "--output", str(second)]) == 1
    assert first.read_bytes() == second.read_bytes()
    human = capsys.readouterr().out
    assert "NON_CONFORMANT" in human and '"HIGH": 1' in human
    assert "IAM nodes:" in human and "Rules evaluated: 1/1" in human


def test_clean_mixed_check_exit_zero(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "architecture",
                "check",
                str(FIXTURES / "clean"),
                "--spec",
                str(EXAMPLES / "layered-clean.yaml"),
                "--json",
            ]
        )
        == 0
    )
    assert json.loads(capsys.readouterr().out)["status"] == "CONFORMANT"


@pytest.mark.parametrize(
    "case",
    [
        "missing_spec",
        "bad_yaml",
        "unsupported_rule",
        "missing_repository",
        "unwritable_output",
        "invalid_namespace",
    ],
)
def test_cli_input_errors_are_typed_and_do_not_leak(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], case: str
) -> None:
    spec = tmp_path / "architecture.yaml"
    spec.write_text((EXAMPLES / "layered-clean.yaml").read_text())
    args = ["architecture", "check", str(FIXTURES / "clean/java"), "--spec", str(spec), "--json"]
    if case == "missing_spec":
        spec.unlink()
    elif case == "bad_yaml":
        spec.write_text("version: [PRIVATE_YAML_MARKER")
    elif case == "unsupported_rule":
        spec.write_text(
            'version: "1.0"\narchitecture: {}\nrules: [{id: ARCH003, type: future_cycle}]'
        )
    elif case == "missing_repository":
        args[2] = str(tmp_path / "absent")
    elif case == "unwritable_output":
        args += ["--output", str(tmp_path / "absent" / "result.json")]
    else:
        args += ["--namespace", " "]
    assert main(args) == 2
    output = capsys.readouterr()
    assert not output.out
    assert "error" in json.loads(output.err.splitlines()[-1])
    assert "PRIVATE_YAML_MARKER" not in output.err


def test_invalid_validate_exit_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    spec = tmp_path / "architecture.yaml"
    spec.write_text("[")
    assert main(["architecture", "validate", str(spec), "--json"]) == 2
    assert (
        json.loads(capsys.readouterr().err)["error"]["code"] == "INVALID_ARCHITECTURE_SPECIFICATION"
    )


def test_cli_zip_strict_exclusions_and_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("controller/A.ts", "export class A {}")
        zipped.writestr("broken.java", "class Broken { int value = 1 }")
        zipped.writestr("other.py", "pass")
    args = [
        "architecture",
        "check",
        str(archive),
        "--source",
        "zip",
        "--spec",
        str(EXAMPLES / "layered-clean.yaml"),
        "--json",
        "--no-gitignore",
    ]
    assert main([*args, "--exclude", "broken.java", "--exclude", "other.py"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["statistics"]["findings_total"] == 0
    assert main([*args, "--strict", "--exclude", "other.py"]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "INVALID"
    assert main([*args, "--exclude", "broken.java"]) == 3
    incomplete = json.loads(capsys.readouterr().out)
    assert incomplete["status"] == "INCOMPLETE" and not incomplete["is_complete"]


def test_cli_overlap_is_diagnostic_and_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    spec = tmp_path / "architecture.yaml"
    spec.write_text(
        'version: "1.0"\narchitecture:\n  layers:\n'
        '    - {name: first, include: ["**"]}\n'
        '    - {name: second, include: ["**"]}\n'
    )
    assert (
        main(["architecture", "check", str(FIXTURES / "clean/java"), "--spec", str(spec), "--json"])
        == 2
    )
    result = json.loads(capsys.readouterr().out)
    assert not result["findings"] and not result["is_valid"]
    assert result["diagnostics"][0]["code"] == "AMBIGUOUS_LAYER_MATCH"
