import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from archguard.cli import main
from archguard.iam.model import ArchitectureModel
from archguard.iam_building.models import IAMBuildResult


def test_iam_cli_json_full_export_summary_and_determinism(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "app.ts").write_text(
        "function work() {} function run() { work(); } // PRIVATE_MARKER"
    )
    a, b = tmp_path / "iam-a.json", tmp_path / "iam-b.json"
    assert (
        main(
            [
                "iam",
                "build",
                str(repository),
                "--json",
                "--output",
                str(a),
                "--namespace",
                "cli-fixture",
            ]
        )
        == 0
    )
    captured = capsys.readouterr()
    result = IAMBuildResult.model_validate_json(captured.out)
    assert ArchitectureModel.model_validate_json(a.read_text()) == result.iam
    assert "PRIVATE_MARKER" not in captured.out + captured.err + a.read_text()
    assert str(repository) not in captured.out + a.read_text()
    assert (
        main(["iam", "build", str(repository), "--output", str(b), "--namespace", "cli-fixture"])
        == 0
    )
    assert a.read_bytes() == b.read_bytes()
    output = capsys.readouterr().out
    assert "Files extracted: 1/1" in output and "declarations: 2" in output
    assert "IAM schema: 1.0" in output and "resolver: 1.0.0" in output
    assert "Extractor: typescript-syntax-extractor 1.1.0" in output


def test_iam_cli_zip_exclusions_and_strict(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    archive = tmp_path / "input.zip"
    with ZipFile(archive, "w") as zipped:
        zipped.writestr("app.ts", "export function work() {}")
        zipped.writestr("broken.java", "class Broken { int value = 1 }")
    assert (
        main(
            [
                "iam",
                "build",
                str(archive),
                "--source",
                "zip",
                "--exclude",
                "broken.java",
                "--no-gitignore",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["statistics"]["files_extracted"] == 1
    assert main(["iam", "build", str(archive), "--source", "zip", "--strict", "--json"]) == 3
    strict = json.loads(capsys.readouterr().out)
    assert not strict["is_valid"] and strict["statistics"]["files_extracted"] == 1


@pytest.mark.parametrize("error", ["missing_repository", "unwritable_output", "invalid_namespace"])
def test_iam_cli_typed_errors(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], error: str
) -> None:
    (tmp_path / "app.ts").write_text("export class Item {}")
    args = ["iam", "build", str(tmp_path), "--json"]
    if error == "missing_repository":
        args[2] = str(tmp_path / "absent")
    elif error == "unwritable_output":
        args.extend(["--output", str(tmp_path / "absent" / "iam.json")])
    else:
        args.extend(["--namespace", " "])
    assert main(args) == 2
    output = capsys.readouterr()
    assert "error" in json.loads(output.err.splitlines()[-1])
    assert not output.out
