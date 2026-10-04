import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO

from archguard.infrastructure.repository.discovery import (
    build_snapshot,
    collect_entries,
    describe_file,
)
from archguard.infrastructure.repository.filesystem import SafeRoot
from archguard.repository.enums import HashStatus
from archguard.repository.errors import RepositoryReadError
from archguard.repository.models import RepositoryFile, RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy


class MaterializedRepository:
    def __init__(self, root: Path, source: RepositoryInput, revision: str | None = None) -> None:
        self._reader = SafeRoot(root)
        self._source = source
        self._revision = revision
        self._files: dict[str, RepositoryFile] = {}
        self._stats: dict[str, os.stat_result] = {}

    def close(self) -> None:
        self._reader.close()

    def discover(self, policy: RepositoryScanPolicy) -> RepositorySnapshot:
        entries, exclusions = collect_entries(self._reader, policy)
        budget = policy.max_total_hash_bytes
        files = []
        for entry in entries:
            file = describe_file(self._reader, entry, policy, budget)
            if file.hash_status == HashStatus.HASHED:
                budget -= file.size_bytes
            files.append(file)
        self._files = {file.relative_path: file for file in files}
        self._stats = {entry.relative_path: entry.stat for entry in entries}
        return build_snapshot(self._source, tuple(files), exclusions, self._revision)

    @contextmanager
    def open_file(self, relative_path: str) -> Iterator[BinaryIO]:
        if relative_path not in self._files:
            raise RepositoryReadError("file is not part of the discovered inventory")
        with self._reader.open_file(relative_path, self._stats[relative_path]) as stream:
            yield stream

    @contextmanager
    def open_source_file(self, relative_path: str) -> Iterator[BinaryIO]:
        file = self._files.get(relative_path)
        if file is None or not file.analysis_eligible:
            raise RepositoryReadError("file is not eligible for the future source parser")
        with self.open_file(relative_path) as stream:
            yield stream
