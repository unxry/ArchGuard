import re
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic
from urllib.parse import urlsplit

from archguard.infrastructure.repository.git_runner import GitRunner, SubprocessGitRunner
from archguard.infrastructure.repository.workspace import MaterializedRepository
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import GitCloneError, GitTimeoutError, InvalidRepositorySource
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy
from archguard.repository.ports import RepositoryWorkspace


def validate_public_url(location: str) -> None:
    try:
        url = urlsplit(location)
        invalid = (
            url.scheme != "https"
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or url.query
            or url.fragment
            or not url.path.strip("/")
            or any(character.isspace() or ord(character) < 32 for character in location)
            or "\\" in location
            or "%" in url.netloc
        )
        _ = url.port
    except ValueError as error:
        raise InvalidRepositorySource(
            "Git source requires a public HTTPS URL without credentials"
        ) from error
    if invalid:
        raise InvalidRepositorySource("Git source requires a public HTTPS URL without credentials")


class GitRepositorySource:
    def __init__(
        self, runner: GitRunner | None = None, workspace_parent: Path | None = None
    ) -> None:
        self._runner = runner if runner is not None else SubprocessGitRunner()
        self._workspace_parent = workspace_parent

    @contextmanager
    def materialize(
        self, source: RepositoryInput, policy: RepositoryScanPolicy
    ) -> Iterator[RepositoryWorkspace]:
        if source.source_type != RepositorySourceType.GIT:
            raise InvalidRepositorySource("Git source adapter requires GIT input")
        validate_public_url(source.location)
        deadline = monotonic() + policy.git_timeout_seconds
        config = [
            "-c",
            "protocol.allow=never",
            "-c",
            "protocol.https.allow=always",
            "-c",
            "protocol.file.allow=never",
            "-c",
            "protocol.ext.allow=never",
            "-c",
            "core.hooksPath=" + str(Path("/dev/null")),
            "-c",
            "core.fsmonitor=false",
            "-c",
            "credential.helper=",
            "-c",
            "http.followRedirects=false",
        ]

        def run(arguments: list[str], cwd: Path | None = None) -> str:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise GitTimeoutError("Git operation exceeded its configured timeout")
            return self._runner.run([*config, *arguments], remaining, cwd)

        with TemporaryDirectory(prefix="archguard-repo-", dir=self._workspace_parent) as directory:
            root = Path(directory) / "repository"
            template = Path(directory) / "empty-template"
            template.mkdir()
            arguments = [
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--no-recurse-submodules",
                "--template",
                str(template),
            ]
            commit_ref = (
                source.ref is not None
                and re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", source.ref) is not None
            )
            if source.ref is not None and not commit_ref:
                arguments += ["--branch", source.ref]
            run([*arguments, "--", source.location, str(root)])
            if commit_ref and source.ref is not None:
                run(["fetch", "--quiet", "--depth", "1", "origin", source.ref], root)
                run(["checkout", "--quiet", "--detach", "FETCH_HEAD"], root)
            revision = run(["rev-parse", "--verify", "HEAD"], root)
            if re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision) is None:
                raise GitCloneError("Git source did not produce a valid commit revision")
            workspace = MaterializedRepository(root, source, revision)
            try:
                yield workspace
            finally:
                workspace.close()
