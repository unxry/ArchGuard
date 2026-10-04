import hashlib
import os
from pathlib import Path

import pytest

from archguard.application.discover_repository import DiscoverRepository
from archguard.infrastructure.repository.local import LocalDirectorySource
from archguard.repository.enums import (
    ExclusionReason,
    HashStatus,
    RepositorySourceType,
    SourceLanguage,
)
from archguard.repository.errors import (
    InvalidRepositorySource,
    RepositoryChangedError,
    RepositoryLimitExceeded,
    RepositoryNotFound,
    RepositoryReadError,
    UnsupportedSourceError,
)
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import DEFAULT_EXCLUSIONS, RepositoryScanPolicy

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repositories"


def discover(path: Path, policy: RepositoryScanPolicy | None = None) -> RepositorySnapshot:
    return DiscoverRepository({RepositorySourceType.LOCAL: LocalDirectorySource()}, policy).execute(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    )


def test_java_maven_discovery() -> None:
    snapshot = discover(FIXTURES / "java_maven")
    assert snapshot.statistics.total_files == 3
    assert snapshot.statistics.source_files == 1
    assert snapshot.statistics.test_files == 1
    assert snapshot.statistics.language_counts[SourceLanguage.JAVA] == 2
    assert snapshot.manifests == ("pom.xml",)
    assert snapshot.supported_for_analysis
    assert {root.relative_path for root in snapshot.source_roots} == {
        "src/main/java",
        "src/test/java",
    }


def test_typescript_discovery_with_tests_and_generated_exclusion() -> None:
    snapshot = discover(FIXTURES / "typescript_node")
    assert snapshot.statistics.total_files == 5
    assert snapshot.statistics.source_files == 2
    assert snapshot.statistics.test_files == 1
    assert snapshot.manifests == ("package.json",)
    assert snapshot.lockfiles == ("package-lock.json",)
    assert any(exclusion.relative_path == "dist" for exclusion in snapshot.exclusions)


def test_mixed_and_unsupported_repositories() -> None:
    mixed = discover(FIXTURES / "mixed_java_ts")
    assert {SourceLanguage.JAVA, SourceLanguage.TYPESCRIPT} <= set(mixed.detected_languages)
    unsupported = discover(FIXTURES / "unsupported_project")
    assert unsupported.statistics.total_files == 1
    assert not unsupported.supported_for_analysis


def test_empty_project_is_valid(tmp_path: Path) -> None:
    snapshot = discover(tmp_path)
    assert snapshot.statistics.total_files == 0
    assert snapshot.statistics.total_bytes == 0
    assert snapshot.detected_languages == ()
    assert not snapshot.supported_for_analysis


def test_default_and_custom_exclusions(tmp_path: Path) -> None:
    for name in DEFAULT_EXCLUSIONS:
        directory = tmp_path / name
        directory.mkdir()
        (directory / "ignored.ts").write_text("ignored")
    (tmp_path / "keep.ts").write_text("keep")
    (tmp_path / "discard.tmp").write_text("discard")
    snapshot = discover(tmp_path, RepositoryScanPolicy(extra_exclusions=("*.tmp",)))
    assert [file.relative_path for file in snapshot.files] == ["keep.ts"]
    assert {item.reason for item in snapshot.exclusions} == {
        ExclusionReason.DEFAULT,
        ExclusionReason.CUSTOM,
    }


def test_nested_gitignore_and_negation(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("*.tmp\nignored/\n/root-only.ts\n")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".gitignore").write_text("!keep.tmp\n*.ts\n!allowed.ts\n")
    for name in ["keep.tmp", "drop.tmp", "hidden.ts", "allowed.ts", "root-only.ts"]:
        (nested / name).write_text("fixture")
    (tmp_path / "root-only.ts").write_text("fixture")
    ignored = tmp_path / "ignored"
    ignored.mkdir()
    (ignored / ".gitignore").write_text("!child.ts\n")
    (ignored / "child.ts").write_text("fixture")
    snapshot = discover(tmp_path)
    paths = {file.relative_path for file in snapshot.files}
    assert "nested/keep.tmp" in paths and "nested/allowed.ts" in paths
    assert "nested/hidden.ts" not in paths and "ignored/child.ts" not in paths
    assert "root-only.ts" not in paths and "nested/root-only.ts" not in paths
    assert any(item.reason == ExclusionReason.GITIGNORE for item in snapshot.exclusions)
    assert "root-only.ts" in {
        file.relative_path
        for file in discover(tmp_path, RepositoryScanPolicy(respect_gitignore=False)).files
    }


def test_binary_large_generated_and_hash_budget(tmp_path: Path) -> None:
    (tmp_path / "a.ts").write_bytes(b"x" * 20)
    (tmp_path / "b.ts").write_bytes(b"x" * 20)
    (tmp_path / "binary.ts").write_bytes(b"x\x00y")
    (tmp_path / "bundle.min.js").write_text("generated")
    (tmp_path / "large.ts").write_bytes(b"x" * 100)
    policy = RepositoryScanPolicy(
        max_source_file_bytes=15, max_hash_file_bytes=50, max_total_hash_bytes=25
    )
    snapshot = discover(tmp_path, policy)
    files = {file.relative_path: file for file in snapshot.files}
    assert files["a.ts"].is_large and not files["a.ts"].analysis_eligible
    assert files["a.ts"].sha256 == hashlib.sha256(b"x" * 20).hexdigest()
    assert files["b.ts"].hash_status == HashStatus.BUDGET_LIMIT
    assert files["binary.ts"].is_binary and files["binary.ts"].hash_status == HashStatus.BINARY
    assert files["large.ts"].hash_status == HashStatus.SIZE_LIMIT
    assert files["bundle.min.js"].is_generated
    assert snapshot.statistics.generated_files == 1 and snapshot.statistics.binary_files == 1
    assert snapshot.statistics.total_bytes == sum(file.size_bytes for file in snapshot.files)


def test_generated_directories_can_be_included_explicitly() -> None:
    policy = RepositoryScanPolicy(
        excluded_directories=tuple(name for name in DEFAULT_EXCLUSIONS if name != "dist")
    )
    snapshot = discover(FIXTURES / "typescript_node", policy)
    generated = next(file for file in snapshot.files if file.relative_path == "dist/generated.js")
    assert generated.is_generated and not generated.analysis_eligible


def test_fingerprint_determinism_and_content_change(tmp_path: Path) -> None:
    for name in ["z.ts", "a.ts", "m.ts"]:
        (tmp_path / name).write_text("one")
    first, second = discover(tmp_path), discover(tmp_path)
    assert first.files == second.files and first.statistics == second.statistics
    assert first.fingerprint == second.fingerprint and first.snapshot_id == second.snapshot_id
    assert [file.relative_path for file in first.files] == ["a.ts", "m.ts", "z.ts"]
    os.utime(tmp_path / "a.ts", (1000, 1000))
    assert discover(tmp_path).fingerprint == first.fingerprint
    (tmp_path / "a.ts").write_text("two")
    assert discover(tmp_path).fingerprint != first.fingerprint


def test_hash_is_chunked_and_correct(tmp_path: Path) -> None:
    content = b"x" * 200_000
    (tmp_path / "chunked.ts").write_bytes(content)
    assert discover(tmp_path).files[0].sha256 == hashlib.sha256(content).hexdigest()


def test_symlinks_and_special_files_are_never_followed(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    external = tmp_path / "external"
    external.mkdir()
    (external / "secret.ts").write_text("external")
    (root / "safe.ts").write_text("safe")
    (root / "external").symlink_to(external, target_is_directory=True)
    (root / "link.ts").symlink_to(external / "secret.ts")
    (root / "internal.ts").symlink_to(root / "safe.ts")
    os.mkfifo(root / "pipe")
    snapshot = discover(root)
    assert [file.relative_path for file in snapshot.files] == ["safe.ts"]
    assert sum(item.reason == ExclusionReason.SYMLINK for item in snapshot.exclusions) == 3
    assert any(item.reason == ExclusionReason.SPECIAL_FILE for item in snapshot.exclusions)


def test_lazy_reader_lifecycle_and_no_path_escape(tmp_path: Path) -> None:
    (tmp_path / "App.java").write_text("class App {}")
    (tmp_path / "image.bin").write_bytes(b"binary")
    use_case = DiscoverRepository({RepositorySourceType.LOCAL: LocalDirectorySource()})
    source = RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    with use_case.open(source) as repository:
        with repository.workspace.open_source_file("App.java") as stream:
            assert stream.read() == b"class App {}"
        for path in ["../outside", "/absolute", "image.bin"]:
            with pytest.raises(RepositoryReadError), repository.workspace.open_source_file(path):
                pass
        workspace = repository.workspace
    with pytest.raises(RepositoryReadError, match="closed"), workspace.open_file("App.java"):
        pass
    assert (tmp_path / "App.java").exists()


def test_lazy_reader_rejects_changed_file_and_symlink_parent(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    directory = root / "src"
    directory.mkdir()
    (directory / "App.java").write_text("original")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "App.java").write_text("outside")
    use_case = DiscoverRepository({RepositorySourceType.LOCAL: LocalDirectorySource()})
    with use_case.open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as repository:
        (directory / "App.java").write_text("changed!")
        with pytest.raises(RepositoryChangedError), repository.workspace.open_file("src/App.java"):
            pass
        (directory / "App.java").unlink()
        directory.rmdir()
        directory.symlink_to(outside, target_is_directory=True)
        with pytest.raises(RepositoryReadError), repository.workspace.open_file("src/App.java"):
            pass


@pytest.mark.parametrize(
    "policy", [RepositoryScanPolicy(max_files=1), RepositoryScanPolicy(max_entries=1)]
)
def test_scan_count_limits(policy: RepositoryScanPolicy, tmp_path: Path) -> None:
    for name in ["a.ts", "b.ts"]:
        (tmp_path / name).write_text("fixture")
    with pytest.raises(RepositoryLimitExceeded):
        discover(tmp_path, policy)


def test_gitignore_size_limit(tmp_path: Path) -> None:
    (tmp_path / ".gitignore").write_text("x" * 100)
    with pytest.raises(RepositoryLimitExceeded):
        discover(tmp_path, RepositoryScanPolicy(max_gitignore_bytes=10))


def test_typed_invalid_source_errors(tmp_path: Path) -> None:
    with pytest.raises(RepositoryNotFound):
        discover(tmp_path / "missing")
    file = tmp_path / "file"
    file.write_text("fixture")
    with pytest.raises(InvalidRepositorySource):
        discover(file)
    with pytest.raises(UnsupportedSourceError):
        DiscoverRepository({}).execute(
            RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
        )
