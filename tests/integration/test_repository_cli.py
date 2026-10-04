import json
from pathlib import Path

import pytest

from archguard.cli import main


def test_cli_json_stdout_and_local_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "App.java").write_text("class App {}")
    assert main(["repo", "inspect", str(tmp_path), "--json"]) == 0
    output = capsys.readouterr()
    assert json.loads(output.out)["statistics"]["total_files"] == 1
    assert "repository intake finished" in output.err
    assert main(["repository", "inspect", str(tmp_path)]) == 0
    assert "Fingerprint:" in capsys.readouterr().out


def test_cli_failure_is_typed_and_does_not_expose_credentials(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert (
        main(
            [
                "repo",
                "inspect",
                "https://user:synthetic-private-token@example.org/repo",
                "--source",
                "git",
                "--json",
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert "invalid_repository_source" in output.err
    assert "synthetic-private-token" not in output.err
