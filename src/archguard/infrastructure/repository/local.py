from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from archguard.infrastructure.repository.workspace import MaterializedRepository
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import (
    InvalidRepositorySource,
    RepositoryNotFound,
    RepositoryReadError,
)
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy
from archguard.repository.ports import RepositoryWorkspace


class LocalDirectorySource:
    @contextmanager
    def materialize(
        self, source: RepositoryInput, policy: RepositoryScanPolicy
    ) -> Iterator[RepositoryWorkspace]:
        if source.source_type != RepositorySourceType.LOCAL:
            raise InvalidRepositorySource("local source adapter requires LOCAL input")
        try:
            root = Path(source.location).expanduser().resolve(strict=True)
            if not root.is_dir():
                raise InvalidRepositorySource("local source must be a directory")
            workspace = MaterializedRepository(root, source)
        except FileNotFoundError as error:
            raise RepositoryNotFound("local repository directory does not exist") from error
        except OSError as error:
            raise RepositoryReadError("local repository directory cannot be opened") from error
        try:
            yield workspace
        finally:
            workspace.close()
