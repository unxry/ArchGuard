import gc
import json
import logging
import weakref
import zipfile
from contextlib import closing, contextmanager
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from archguard.application.discover_repository import DiscoveredRepository, DiscoverRepository
from archguard.application.parse_repository import ParseRepository
from archguard.core.identifiers import SnapshotId
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.repository.zip_source import ZipRepositorySource
from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import (
    ParserDiagnosticCode,
    ParserLanguage,
    ParseSkipReason,
    ParseStatus,
)
from archguard.parsing.factory import create_parser_registry
from archguard.parsing.models import FileParseMetadata, ParsedSourceFile, ParseRepositoryResult
from archguard.parsing.registry import ParserRegistry
from archguard.parsing.tree_sitter_adapters import JavaParser
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import RepositoryReadError
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy

FIXTURES = Path(__file__).parents[1] / "fixtures"


def local_source(root: Path) -> RepositoryInput:
    return RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))


class TrackedReader:
    def __init__(self, repository: DiscoveredRepository) -> None:
        self.wrapped = repository.workspace
        self.paths: list[str] = []
        self.live_streams = self.peak_streams = 0

    @contextmanager
    def open_source_file(self, path: str):
        self.paths.append(path)
        self.live_streams += 1
        self.peak_streams = max(self.peak_streams, self.live_streams)
        try:
            with self.wrapped.open_source_file(path) as stream:
                yield stream
        finally:
            self.live_streams -= 1


def test_mixed_selection_only_opens_eligible_files(tmp_path: Path) -> None:
    sources = {
        "App.java": "class App {}",
        "service.ts": "export const value: number = 1;",
        "tests/service.test.ts": "export const test = () => true;",
        "view.tsx": "export const View = () => <main/>;",
        "worker.js": "export const worker = async () => 1;",
        "generated/generated.js": "export const generated = 1;",
        "README.md": "# Documentation",
        "main.py": "print('never execute')",
        "unsupported.txt": "unclassified file",
        "excluded.java": "class Excluded {}",
        "large.java": "class Large {}" + " " * 300,
    }
    for relative_path, content in sources.items():
        path = tmp_path / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    (tmp_path / "binary.java").write_bytes(b"class Binary {}\x00")
    policy = RepositoryScanPolicy(max_source_file_bytes=200, extra_exclusions=("excluded.java",))
    with create_discovery(policy).open(local_source(tmp_path)) as repository:
        reader = TrackedReader(repository)
        result = ParseRepository(create_parser_registry()).execute(repository.snapshot, reader)
        stats = result.statistics
        assert (stats.total_files, stats.total_candidates, stats.parsed_files) == (11, 5, 5)
        assert (stats.skipped_files, stats.unsupported_files, stats.failed_files) == (4, 2, 0)
        expected = sorted(
            ["App.java", "service.ts", "tests/service.test.ts", "view.tsx", "worker.js"]
        )
        assert reader.paths == expected
        assert reader.live_streams == 0 and reader.peak_streams == 1
        assert set(result.language_stats) == set(ParserLanguage)
        assert result.language_stats[ParserLanguage.TYPESCRIPT].parsed == 2
        assert result.is_valid
        assert ParseRepositoryResult.model_validate_json(result.model_dump_json()) == result
        for item in result.files:
            assert item.source_file in repository.snapshot.files
        assert "never execute" not in result.model_dump_json()


@pytest.mark.parametrize("strict", [False, True])
def test_syntax_errors_continue_in_both_modes(tmp_path: Path, strict: bool) -> None:
    (tmp_path / "A.java").write_text("class A {}")
    (tmp_path / "B.java").write_text("class B { int value = 1 }")
    (tmp_path / "C.ts").write_text("const value: = ;")
    (tmp_path / "D.tsx").write_text("export const View = () => <main/>;")
    with create_discovery().open(local_source(tmp_path)) as repository:
        result = ParseRepository(
            create_parser_registry(), ParserConfig(strict_syntax_errors=strict)
        ).execute(repository.snapshot, repository.workspace)
        assert result.statistics.parsed_files == 4
        assert result.statistics.failed_files == 0
        assert result.statistics.syntax_error_files == 2
        assert result.statistics.invalid_files == (2 if strict else 0)
        assert result.is_valid == (not strict)
        assert result.files[-1].status == ParseStatus.PARSED
        assert result.diagnostics
    with pytest.raises(RepositoryReadError), repository.workspace.open_source_file("A.java"):
        pass


def test_unexpected_adapter_failure_is_visible_isolated_and_private(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    secret = "synthetic-source-secret"
    for name in ["A", "B", "C"]:
        (tmp_path / f"{name}.java").write_text(f"class {name} {{}} // {secret}")

    class BrokenParser(JavaParser):
        def parse(self, snapshot_id, source_file, source, config):
            if source_file.relative_path == "B.java":
                raise RuntimeError(secret)
            return super().parse(snapshot_id, source_file, source, config)

    with create_discovery().open(local_source(tmp_path)) as repository:
        with caplog.at_level(logging.INFO, logger="archguard.parsing"):
            result = ParseRepository(ParserRegistry((BrokenParser(),))).execute(
                repository.snapshot, repository.workspace
            )
        assert [item.status for item in result.files] == [
            ParseStatus.PARSED,
            ParseStatus.FAILED,
            ParseStatus.PARSED,
        ]
        assert result.statistics.failed_files == 1 and result.statistics.parsed_files == 2
        assert result.files[1].diagnostics[0].code == ParserDiagnosticCode.EXECUTION_ERROR
        assert result.files[1].parser is not None
        assert not result.is_valid
        assert secret not in caplog.text and secret not in result.model_dump_json()
        assert "attempted=3 parsed=2" in caplog.text


def test_read_and_decoding_errors_are_isolated(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_bytes(b"class A {}")
    (tmp_path / "B.java").write_bytes(b"class \xff {}")
    (tmp_path / "C.java").write_bytes(b"class C {}")
    with create_discovery().open(local_source(tmp_path)) as repository:
        (tmp_path / "A.java").unlink()
        result = ParseRepository(create_parser_registry()).execute(
            repository.snapshot, repository.workspace
        )
        assert [item.status for item in result.files] == [
            ParseStatus.FAILED,
            ParseStatus.FAILED,
            ParseStatus.PARSED,
        ]
        assert [item.code for item in result.diagnostics] == [
            ParserDiagnosticCode.SOURCE_READ_ERROR,
            ParserDiagnosticCode.DECODING_ERROR,
        ]
        assert result.diagnostics[1].column == 7


def test_nul_outside_intake_prefix_is_rejected_before_native_parsing(tmp_path: Path) -> None:
    (tmp_path / "A.java").write_bytes(b"class A {} /* " + b"x" * 5000 + b"\x00 */")
    (tmp_path / "B.java").write_bytes(b"class B {}")
    with create_discovery().open(local_source(tmp_path)) as repository:
        assert repository.snapshot.files[0].analysis_eligible
        result = ParseRepository(create_parser_registry()).execute(
            repository.snapshot, repository.workspace
        )
        assert result.files[0].status == ParseStatus.FAILED
        assert result.files[0].diagnostics[0].code == ParserDiagnosticCode.SOURCE_INELIGIBLE
        assert result.files[1].status == ParseStatus.PARSED


def test_empty_repository_missing_parser_and_disabled_language(tmp_path: Path) -> None:
    with create_discovery().open(local_source(tmp_path)) as repository:
        result = ParseRepository(create_parser_registry()).execute(
            repository.snapshot, repository.workspace
        )
        assert result.statistics.total_files == 0 and result.is_valid
    (tmp_path / "App.java").write_text("class App {}")
    with create_discovery().open(local_source(tmp_path)) as repository:
        reader = TrackedReader(repository)
        unsupported = ParseRepository(ParserRegistry()).execute(repository.snapshot, reader)
        assert unsupported.statistics.unsupported_files == 1
        disabled = ParseRepository(
            create_parser_registry(), ParserConfig(enabled_languages=())
        ).execute(repository.snapshot, reader)
        assert disabled.files[0].skip_reason == ParseSkipReason.DISABLED_LANGUAGE
        limited = ParseRepository(
            create_parser_registry(), ParserConfig(max_source_file_bytes=1)
        ).execute(repository.snapshot, reader)
        assert limited.files[0].skip_reason == ParseSkipReason.SIZE_LIMIT
        assert reader.paths == []


def test_streaming_results_and_metadata_are_deterministic(tmp_path: Path) -> None:
    (tmp_path / "Z.tsx").write_text("export const View = () => <main/>;")
    (tmp_path / "A.java").write_text("class A {}")
    (tmp_path / "README.md").write_text("# docs")
    parser = ParseRepository(create_parser_registry())
    with create_discovery().open(local_source(tmp_path)) as repository:
        first = parser.execute(repository.snapshot, repository.workspace)
        second = parser.execute(repository.snapshot, repository.workspace)
        assert first.model_dump_json() == second.model_dump_json()
        outcomes = list(parser.iter_parse(repository.snapshot, repository.workspace))
        assert isinstance(outcomes[0], ParsedSourceFile)
        assert isinstance(outcomes[1], FileParseMetadata)
        assert isinstance(outcomes[2], ParsedSourceFile)
        assert outcomes[2].metadata.language == ParserLanguage.TSX
        assert not outcomes[2].root.has_error
        assert outcomes[0].metadata.source_file.sha256 == repository.snapshot.files[0].sha256
    assert outcomes[0].root.type == "program"


def test_zip_strict_mode_and_early_stream_stop_clean_workspaces(tmp_path: Path) -> None:
    archive = tmp_path / "project.zip"
    with zipfile.ZipFile(archive, "w") as output:
        output.writestr("App.java", "class App { int value = 1 }")
    workspace_parent = tmp_path / "workspaces"
    workspace_parent.mkdir()
    discovery = DiscoverRepository(
        {RepositorySourceType.ZIP: ZipRepositorySource(workspace_parent=workspace_parent)}
    )
    source = RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(archive))
    parser = ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=True))
    with discovery.open(source) as repository:
        result = parser.execute(repository.snapshot, repository.workspace)
        assert not result.is_valid
    assert list(workspace_parent.iterdir()) == []
    with (
        pytest.raises(RuntimeError, match="consumer stopped"),
        discovery.open(source) as repository,
        closing(parser.iter_parse(repository.snapshot, repository.workspace)) as iterator,
    ):
        parsed = next(iterator)
        assert isinstance(parsed, ParsedSourceFile)
        raise RuntimeError("consumer stopped")
    assert list(workspace_parent.iterdir()) == []


def test_dozens_of_files_are_sequential_and_do_not_retain_all_trees(tmp_path: Path) -> None:
    for index in range(60):
        source = f"class App{index} {{}} /* " + "padding " * 4096 + " */"
        (tmp_path / f"App{index:02d}.java").write_text(source)
    handles: list[weakref.ReferenceType[ParsedSourceFile]] = []
    peak = 0

    class TrackingParser(JavaParser):
        def parse(self, snapshot_id, source_file, source, config):
            nonlocal peak
            parsed = super().parse(snapshot_id, source_file, source, config)
            handles.append(weakref.ref(parsed))
            peak = max(peak, sum(handle() is not None for handle in handles))
            return parsed

    with create_discovery().open(local_source(tmp_path)) as repository:
        reader = TrackedReader(repository)
        result = ParseRepository(ParserRegistry((TrackingParser(),))).execute(
            repository.snapshot, reader
        )
        assert result.statistics.parsed_files == 60
        assert len(reader.paths) == len(set(reader.paths)) == 60
        assert reader.peak_streams == 1
        assert peak <= 2
        gc.collect()
        assert all(handle() is None for handle in handles)
        assert "padding" not in result.model_dump_json()


def test_adapter_identity_mismatch_is_failed(tmp_path: Path) -> None:
    (tmp_path / "App.java").write_text("class App {}")

    class WrongIdentityParser(JavaParser):
        def parse(self, snapshot_id, source_file, source, config):
            parsed = super().parse(snapshot_id, source_file, source, config)
            return replace(
                parsed,
                metadata=parsed.metadata.model_copy(update={"snapshot_id": SnapshotId(uuid4())}),
            )

    with create_discovery().open(local_source(tmp_path)) as repository:
        result = ParseRepository(ParserRegistry((WrongIdentityParser(),))).execute(
            repository.snapshot, repository.workspace
        )
        assert result.statistics.failed_files == 1
        assert result.diagnostics[0].code == ParserDiagnosticCode.EXECUTION_ERROR


@pytest.mark.parametrize(
    "mutation",
    [
        "snapshot_id",
        "snapshot_fingerprint",
        "statistics",
        "language_stats",
        "parser_versions",
        "is_valid",
    ],
)
def test_aggregate_metadata_rejects_corrupt_identity_and_statistics(
    tmp_path: Path, mutation
) -> None:
    (tmp_path / "App.java").write_text("class App {}")
    with create_discovery().open(local_source(tmp_path)) as repository:
        result = ParseRepository(create_parser_registry()).execute(
            repository.snapshot, repository.workspace
        )
        values = json.loads(result.model_dump_json())
        if mutation == "snapshot_id":
            values[mutation] = str(uuid4())
        elif mutation == "snapshot_fingerprint":
            values[mutation] = "0" * 64
        elif mutation == "statistics":
            values[mutation]["parsed_files"] = 10
        elif mutation == "language_stats":
            values[mutation] = {}
        elif mutation == "parser_versions":
            values[mutation] = []
        else:
            values[mutation] = False
        with pytest.raises(ValidationError):
            ParseRepositoryResult.model_validate(values)


def test_existing_mixed_repository_fixture_parses_without_regression() -> None:
    with create_discovery().open(
        local_source(FIXTURES / "repositories" / "mixed_java_ts")
    ) as repository:
        result = ParseRepository(create_parser_registry()).execute(
            repository.snapshot, repository.workspace
        )
        assert result.statistics.parsed_files == 2
        assert result.statistics.failed_files == result.statistics.syntax_error_files == 0
        assert result.language_stats[ParserLanguage.TSX].parsed == 1
