import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from time import perf_counter

from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import RepositoryIntakeError, UnsupportedSourceError
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy
from archguard.repository.ports import RepositorySource, RepositoryWorkspace


@dataclass(frozen=True)
class DiscoveredRepository:
    snapshot: RepositorySnapshot
    workspace: RepositoryWorkspace


class DiscoverRepository:
    def __init__(
        self,
        sources: Mapping[RepositorySourceType, RepositorySource],
        policy: RepositoryScanPolicy | None = None,
    ) -> None:
        self._sources = dict(sources)
        self._policy = policy if policy is not None else RepositoryScanPolicy()

    @contextmanager
    def open(self, source: RepositoryInput) -> Iterator[DiscoveredRepository]:
        logger = logging.getLogger("archguard.repository")
        started = perf_counter()
        logger.info("repository intake started source=%s", source.source_type.value)
        try:
            adapter = self._sources.get(source.source_type)
            if adapter is None:
                raise UnsupportedSourceError("repository source type is not configured")
            with adapter.materialize(source, self._policy) as workspace:
                snapshot = workspace.discover(self._policy)
                logger.info(
                    "repository intake finished source=%s files=%d revision=%s duration=%.3fs",
                    source.source_type.value,
                    snapshot.statistics.total_files,
                    snapshot.revision,
                    perf_counter() - started,
                )
                yield DiscoveredRepository(snapshot=snapshot, workspace=workspace)
        except RepositoryIntakeError as error:
            logger.error(
                "repository intake failed source=%s code=%s duration=%.3fs",
                source.source_type.value,
                error.code,
                perf_counter() - started,
            )
            raise

    def execute(self, source: RepositoryInput) -> RepositorySnapshot:
        """Return durable inventory metadata; use open() to keep lazy file access alive."""
        with self.open(source) as repository:
            return repository.snapshot
