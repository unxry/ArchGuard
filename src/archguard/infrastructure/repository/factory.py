from archguard.application.discover_repository import DiscoverRepository
from archguard.infrastructure.repository.git_source import GitRepositorySource
from archguard.infrastructure.repository.local import LocalDirectorySource
from archguard.infrastructure.repository.zip_source import ZipRepositorySource
from archguard.repository.enums import RepositorySourceType
from archguard.repository.policy import RepositoryScanPolicy


def create_discovery(policy: RepositoryScanPolicy | None = None) -> DiscoverRepository:
    return DiscoverRepository(
        {
            RepositorySourceType.LOCAL: LocalDirectorySource(),
            RepositorySourceType.ZIP: ZipRepositorySource(),
            RepositorySourceType.GIT: GitRepositorySource(),
        },
        policy,
    )
