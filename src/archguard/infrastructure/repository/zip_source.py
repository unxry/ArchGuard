import os
import stat
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from pydantic import TypeAdapter, ValidationError

from archguard.core.model.types import RepositoryPath
from archguard.infrastructure.repository.workspace import MaterializedRepository
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import (
    InvalidRepositorySource,
    RepositoryLimitExceeded,
    RepositoryNotFound,
    UnsafeArchiveError,
)
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy
from archguard.repository.ports import RepositoryWorkspace


def safe_archive_path(info: zipfile.ZipInfo) -> str:
    name = info.orig_filename
    path = name[:-1] if name.endswith("/") else name
    try:
        TypeAdapter(RepositoryPath).validate_python(path)
    except ValidationError as error:
        raise UnsafeArchiveError("archive contains an unsafe path") from error
    if ":" in path:
        raise UnsafeArchiveError("archive drive paths and alternate streams are not allowed")
    mode = info.external_attr >> 16
    if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
        raise UnsafeArchiveError("archive symlinks and special files are not allowed")
    return path


def validate_archive(
    archive: zipfile.ZipFile, policy: RepositoryScanPolicy
) -> list[tuple[str, zipfile.ZipInfo]]:
    entries = archive.infolist()
    if len(entries) > policy.max_entries:
        raise RepositoryLimitExceeded("archive entry count limit exceeded")
    files = 0
    total = 0
    seen: dict[str, bool] = {}
    spellings: dict[str, str] = {}
    result = []
    for info in entries:
        path = safe_archive_path(info)
        parts = path.split("/")
        for end in range(1, len(parts) + 1):
            prefix = "/".join(parts[:end])
            folded = prefix.casefold()
            if folded in spellings and spellings[folded] != prefix:
                raise UnsafeArchiveError("archive contains case-colliding path components")
            spellings[folded] = prefix
        key = path.casefold()
        if key in seen:
            raise UnsafeArchiveError("archive contains duplicate or case-colliding paths")
        seen[key] = info.is_dir()
        if info.flag_bits & 1:
            raise UnsafeArchiveError("encrypted archives are not supported")
        if not info.is_dir():
            files += 1
            total += info.file_size
            if files > policy.max_files or info.file_size > policy.max_single_file_bytes:
                raise RepositoryLimitExceeded(
                    "archive file count or single-file size limit exceeded"
                )
            if total > policy.max_total_uncompressed_bytes:
                raise RepositoryLimitExceeded("archive uncompressed size limit exceeded")
        result.append((path, info))
    for path, _ in result:
        for parent in PurePosixPath(path).parents:
            if str(parent) != "." and seen.get(str(parent).casefold()) is False:
                raise UnsafeArchiveError("archive file/directory paths collide")
    return sorted(result, key=lambda entry: entry[0])


def extract_archive(
    archive: zipfile.ZipFile, destination: Path, policy: RepositoryScanPolicy
) -> None:
    entries = validate_archive(archive, policy)
    total_written = 0
    for relative_path, info in entries:
        target = destination.joinpath(*relative_path.split("/"))
        if not target.is_relative_to(destination):
            raise UnsafeArchiveError("archive path escapes workspace")
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        with archive.open(info) as source, target.open("xb") as output:
            while chunk := source.read(64 * 1024):
                written += len(chunk)
                total_written += len(chunk)
                if (
                    written > policy.max_single_file_bytes
                    or total_written > policy.max_total_uncompressed_bytes
                ):
                    raise RepositoryLimitExceeded("actual archive payload exceeds resource limits")
                output.write(chunk)
        if written != info.file_size:
            raise UnsafeArchiveError("archive payload does not match declared size")


class ZipRepositorySource:
    def __init__(self, workspace_parent: Path | None = None) -> None:
        self._workspace_parent = workspace_parent

    @contextmanager
    def materialize(
        self, source: RepositoryInput, policy: RepositoryScanPolicy
    ) -> Iterator[RepositoryWorkspace]:
        if source.source_type != RepositorySourceType.ZIP:
            raise InvalidRepositorySource("ZIP source adapter requires ZIP input")
        archive_path = Path(source.location).expanduser()
        try:
            fd = os.open(archive_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        except FileNotFoundError as error:
            raise RepositoryNotFound("ZIP archive does not exist") from error
        except OSError as error:
            raise UnsafeArchiveError("ZIP archive cannot be opened") from error
        with os.fdopen(fd, "rb") as archive_stream:
            archive_stat = os.fstat(archive_stream.fileno())
            if not stat.S_ISREG(archive_stat.st_mode):
                raise InvalidRepositorySource("ZIP input must be a regular file")
            if archive_stat.st_size > policy.max_archive_bytes:
                raise RepositoryLimitExceeded("compressed archive size limit exceeded")
            with TemporaryDirectory(
                prefix="archguard-repo-", dir=self._workspace_parent
            ) as directory:
                root = Path(directory)
                try:
                    with zipfile.ZipFile(archive_stream) as archive:
                        extract_archive(archive, root, policy)
                except (
                    OSError,
                    zipfile.BadZipFile,
                    RuntimeError,
                    NotImplementedError,
                    EOFError,
                ) as error:
                    raise UnsafeArchiveError(
                        "ZIP archive is malformed or cannot be extracted safely"
                    ) from error
                workspace = MaterializedRepository(root, source)
                try:
                    yield workspace
                finally:
                    workspace.close()
