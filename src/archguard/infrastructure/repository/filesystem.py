import os
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from pydantic import TypeAdapter, ValidationError

from archguard.core.model.types import RepositoryPath
from archguard.repository.errors import (
    InvalidRepositorySource,
    RepositoryChangedError,
    RepositoryLimitExceeded,
    RepositoryReadError,
)


def stat_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns


@dataclass(frozen=True)
class Entry:
    relative_path: str
    stat: os.stat_result


class SafeRoot:
    """POSIX descriptor-relative access; every component rejects symlinks and special files."""

    def __init__(self, root: Path) -> None:
        self._fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            os.close(self._fd)
            self._closed = True

    @contextmanager
    def _directory(self, parts: tuple[str, ...]) -> Iterator[int]:
        if self._closed:
            raise RepositoryReadError("repository workspace is closed")
        fd = os.dup(self._fd)
        try:
            for part in parts:
                next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            yield fd
        except OSError as error:
            raise RepositoryReadError("repository directory cannot be read safely") from error
        finally:
            os.close(fd)

    def entries(self, relative_directory: str, remaining_entries: int) -> list[Entry]:
        parts = tuple(relative_directory.split("/")) if relative_directory else ()
        entries: list[Entry] = []
        with self._directory(parts) as fd, os.scandir(fd) as iterator:
            for entry in iterator:
                if len(entries) >= remaining_entries:
                    raise RepositoryLimitExceeded("repository traversal entry limit exceeded")
                relative_path = (
                    f"{relative_directory}/{entry.name}" if relative_directory else entry.name
                )
                try:
                    TypeAdapter(RepositoryPath).validate_python(relative_path)
                    entries.append(Entry(relative_path, entry.stat(follow_symlinks=False)))
                except ValidationError as error:
                    raise InvalidRepositorySource(
                        "repository contains a non-portable path"
                    ) from error
                except OSError as error:
                    raise RepositoryChangedError("repository changed during traversal") from error
        return sorted(entries, key=lambda entry: entry.relative_path)

    @contextmanager
    def open_file(
        self, relative_path: str, expected: os.stat_result | None = None
    ) -> Iterator[BinaryIO]:
        try:
            TypeAdapter(RepositoryPath).validate_python(relative_path)
        except ValidationError as error:
            raise InvalidRepositorySource("invalid repository-relative file path") from error
        parts = tuple(relative_path.split("/"))
        try:
            with self._directory(parts[:-1]) as parent_fd:
                fd = os.open(
                    parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd
                )
            with os.fdopen(fd, "rb") as stream:
                before = os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):
                    raise RepositoryReadError("only regular repository files may be opened")
                if expected is not None and stat_identity(before) != stat_identity(expected):
                    raise RepositoryChangedError("repository file changed since discovery")
                yield stream
                if stream.closed:
                    raise RepositoryReadError(
                        "repository stream was closed before its context exited"
                    )
                if stat_identity(os.fstat(stream.fileno())) != stat_identity(before):
                    raise RepositoryChangedError("repository file changed while being read")
        except OSError as error:
            raise RepositoryReadError("repository file cannot be read safely") from error
