import json
from pathlib import Path

import pytest

from archguard.cli import main
from archguard.parsing.models import ParseRepositoryResult


def test_parse_cli_json_metadata_and_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "App.java").write_text("class App {} // private-source-marker")
    assert main(["parse", "inspect", str(tmp_path), "--json"]) == 0
    output = capsys.readouterr()
    result = ParseRepositoryResult.model_validate_json(output.out)
    assert result.statistics.parsed_files == 1
    assert result.parser_versions[0].parser_id == "java-tree-sitter"
    assert "parsing finished" in output.err
    assert "private-source-marker" not in output.out + output.err
    assert main(["parse", "inspect", str(tmp_path)]) == 0
    summary = capsys.readouterr()
    assert "parsed: 1" in summary.out and "Tree-sitter" in summary.out
    assert "private-source-marker" not in summary.out + summary.err


def test_parse_cli_tolerant_strict_and_failed_exit_codes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    file = tmp_path / "App.java"
    file.write_text("class App { int value = 1 }")
    assert main(["parse", "inspect", str(tmp_path), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["statistics"]["syntax_error_files"] == 1
    assert main(["parse", "inspect", str(tmp_path), "--strict", "--json"]) == 3
    assert not json.loads(capsys.readouterr().out)["is_valid"]
    file.write_bytes(b"class \xff {}")
    assert main(["parse", "inspect", str(tmp_path), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["statistics"]["failed_files"] == 1


def test_parse_cli_invalid_source_uses_existing_typed_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["parse", "inspect", str(tmp_path / "absent"), "--json"]) == 2
    output = capsys.readouterr()
    assert output.out == "" and "repository_not_found" in output.err
