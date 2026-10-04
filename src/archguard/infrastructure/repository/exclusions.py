from dataclasses import dataclass

from pathspec import GitIgnoreSpec

from archguard.infrastructure.repository.filesystem import SafeRoot
from archguard.repository.enums import ExclusionReason
from archguard.repository.errors import RepositoryLimitExceeded
from archguard.repository.policy import RepositoryScanPolicy


@dataclass(frozen=True)
class IgnoreScope:
    directory: str
    spec: GitIgnoreSpec


def load_ignore_scope(root: SafeRoot, directory: str, policy: RepositoryScanPolicy) -> IgnoreScope:
    path = f"{directory}/.gitignore" if directory else ".gitignore"
    with root.open_file(path) as stream:
        content = stream.read(policy.max_gitignore_bytes + 1)
    if len(content) > policy.max_gitignore_bytes:
        raise RepositoryLimitExceeded("gitignore file exceeds configured size limit")
    return IgnoreScope(
        directory, GitIgnoreSpec.from_lines(content.decode("utf-8", errors="replace").splitlines())
    )


class Exclusions:
    def __init__(self, policy: RepositoryScanPolicy) -> None:
        self._policy = policy
        self._custom = GitIgnoreSpec.from_lines(policy.extra_exclusions)

    def reason(
        self, relative_path: str, is_directory: bool, scopes: tuple[IgnoreScope, ...]
    ) -> ExclusionReason | None:
        parts = relative_path.split("/")
        if any(part in self._policy.excluded_directories for part in parts):
            return ExclusionReason.DEFAULT
        candidate = relative_path + ("/" if is_directory else "")
        if self._custom.match_file(candidate):
            return ExclusionReason.CUSTOM
        ignored = False
        for scope in scopes:
            prefix = scope.directory + "/" if scope.directory else ""
            result = scope.spec.check_file(candidate.removeprefix(prefix))
            if result.include is not None:
                ignored = result.include
        return ExclusionReason.GITIGNORE if ignored else None
