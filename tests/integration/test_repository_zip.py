import stat
import zipfile
from pathlib import Path

import pytest

from archguard.application.discover_repository import DiscoverRepository
from archguard.infrastructure.repository.local import LocalDirectorySource
from archguard.infrastructure.repository.zip_source import ZipRepositorySource
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import (
    RepositoryLimitExceeded,
    RepositoryNotFound,
    RepositoryReadError,
    UnsafeArchiveError,
)
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy


def write_zip(path: Path, entries: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)


def zip_discovery(parent: Path, policy: RepositoryScanPolicy | None = None) -> DiscoverRepository:
    return DiscoverRepository({RepositorySourceType.ZIP: ZipRepositorySource(parent)}, policy)


def test_safe_zip_lazy_access_fingerprint_and_cleanup(tmp_path: Path) -> None:
    local = tmp_path / "local"
    local.mkdir()
    entries = {"src/App.java": b"class App {}", "package.json": b"{}"}
    for name, content in entries.items():
        path = local / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    path = tmp_path / "safe.zip"
    write_zip(path, entries)
    workspaces = tmp_path / "workspaces"
    workspaces.mkdir()
    source = RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
    with zip_discovery(workspaces).open(source) as repository:
        assert len(list(workspaces.iterdir())) == 1
        assert repository.snapshot.statistics.total_files == 2
        with repository.workspace.open_source_file("src/App.java") as stream:
            assert stream.read() == entries["src/App.java"]
        snapshot = repository.snapshot
        workspace = repository.workspace
    assert list(workspaces.iterdir()) == []
    with pytest.raises(RepositoryReadError, match="closed"), workspace.open_file("src/App.java"):
        pass
    local_snapshot = DiscoverRepository(
        {RepositorySourceType.LOCAL: LocalDirectorySource()}
    ).execute(RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(local)))
    assert snapshot.fingerprint == local_snapshot.fingerprint


@pytest.mark.parametrize(
    "name",
    [
        "../escape.ts",
        "src/../../escape.ts",
        "/escape.ts",
        "C:/escape.ts",
        "C:escape.ts",
        "\\\\server\\escape.ts",
        "src\\..\\escape.ts",
        "./escape.ts",
        "src//escape.ts",
        "src/file:stream",
    ],
)
def test_zip_slip_and_drive_paths_are_blocked(name: str, tmp_path: Path) -> None:
    path = tmp_path / "unsafe.zip"
    write_zip(path, {name: b"unsafe"})
    parent = tmp_path / "workspaces"
    parent.mkdir()
    with pytest.raises(UnsafeArchiveError):
        zip_discovery(parent).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )
    assert list(parent.iterdir()) == []
    assert not (tmp_path / "escape.ts").exists()


def test_zip_symlink_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "symlink.zip"
    info = zipfile.ZipInfo("src/link.ts")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(info, "../../outside")
    with pytest.raises(UnsafeArchiveError, match="symlinks"):
        zip_discovery(tmp_path).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )


@pytest.mark.parametrize(
    "entries",
    [
        {"a.ts": b"a", "A.ts": b"b"},
        {"src": b"file", "src/App.java": b"source"},
        {"Src/a.ts": b"a", "src/b.ts": b"b"},
    ],
)
def test_zip_collisions_are_rejected(entries: dict[str, bytes], tmp_path: Path) -> None:
    path = tmp_path / "collision.zip"
    write_zip(path, entries)
    with pytest.raises(UnsafeArchiveError):
        zip_discovery(tmp_path).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )


def test_duplicate_zip_names_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "duplicate.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("a.ts", "first")
        with pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr("a.ts", "second")
    with pytest.raises(UnsafeArchiveError, match="duplicate"):
        zip_discovery(tmp_path).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )


@pytest.mark.parametrize(
    "policy",
    [
        RepositoryScanPolicy(max_files=1),
        RepositoryScanPolicy(max_single_file_bytes=5),
        RepositoryScanPolicy(max_total_uncompressed_bytes=10),
        RepositoryScanPolicy(max_archive_bytes=1),
        RepositoryScanPolicy(max_entries=1),
    ],
)
def test_zip_resource_limits_and_cleanup(policy: RepositoryScanPolicy, tmp_path: Path) -> None:
    path = tmp_path / "limited.zip"
    write_zip(path, {"one.ts": b"x" * 20, "two.ts": b"x" * 20})
    parent = tmp_path / "workspaces"
    parent.mkdir()
    with pytest.raises(RepositoryLimitExceeded):
        zip_discovery(parent, policy).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )
    assert list(parent.iterdir()) == []


def test_zip_limits_apply_before_default_exclusions(tmp_path: Path) -> None:
    path = tmp_path / "bomb.zip"
    write_zip(path, {"node_modules/large.js": b"x" * 100_000})
    with pytest.raises(RepositoryLimitExceeded):
        zip_discovery(tmp_path, RepositoryScanPolicy(max_total_uncompressed_bytes=100)).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )


def test_malformed_archive_and_missing_source(tmp_path: Path) -> None:
    path = tmp_path / "invalid.zip"
    path.write_bytes(b"not an archive")
    with pytest.raises(UnsafeArchiveError):
        zip_discovery(tmp_path).execute(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        )
    with pytest.raises(RepositoryNotFound):
        zip_discovery(tmp_path).execute(
            RepositoryInput(
                source_type=RepositorySourceType.ZIP, location=str(tmp_path / "missing.zip")
            )
        )


def test_workspace_cleanup_when_consumer_fails(tmp_path: Path) -> None:
    path = tmp_path / "safe.zip"
    write_zip(path, {"a.ts": b"fixture"})
    parent = tmp_path / "workspaces"
    parent.mkdir()
    with (
        pytest.raises(RuntimeError),
        zip_discovery(parent).open(
            RepositoryInput(source_type=RepositorySourceType.ZIP, location=str(path))
        ),
    ):
        raise RuntimeError("synthetic downstream failure")
    assert list(parent.iterdir()) == []
