from contextlib import AbstractContextManager
from typing import BinaryIO, Protocol

from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy


class RepositoryWorkspace(Protocol):
    def discover(self, policy: RepositoryScanPolicy) -> RepositorySnapshot: ...

    def open_file(self, relative_path: str) -> AbstractContextManager[BinaryIO]: ...

    def open_source_file(self, relative_path: str) -> AbstractContextManager[BinaryIO]: ...


class RepositorySource(Protocol):
    def materialize(
        self, source: RepositoryInput, policy: RepositoryScanPolicy
    ) -> AbstractContextManager[RepositoryWorkspace]: ...
