import os
import shlex
import signal
import subprocess
import time
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

import pytest

from archguard.application.discover_repository import DiscoverRepository
from archguard.infrastructure.repository.git_runner import SubprocessGitRunner
from archguard.infrastructure.repository.git_source import GitRepositorySource
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import GitCloneError, GitTimeoutError, InvalidRepositorySource
from archguard.repository.models import RepositoryInput

PUBLIC_TEST_URL = "https://offline.invalid/synthetic.git"


def git(*arguments: str, cwd: Path | None = None) -> str:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", "-c", "commit.gpgsign=false", *arguments],
        cwd=cwd,
        env=env,
        text=True,
        stderr=subprocess.PIPE,
    ).strip()


@pytest.fixture
def local_git(tmp_path: Path) -> Path:
    root = tmp_path / "origin"
    root.mkdir()
    git("init", "-b", "main", str(root))
    git("config", "user.name", "Synthetic Test", cwd=root)
    git("config", "user.email", "synthetic@example.invalid", cwd=root)
    (root / "App.java").write_text("class App {}")
    (root / ".gitignore").write_text("*.tmp\n")
    (root / "bad.tmp").write_text("ignored")
    (root / "outside-link").symlink_to(tmp_path, target_is_directory=True)
    git("add", ".", cwd=root)
    git("commit", "-m", "Synthetic discovery fixture", cwd=root)
    git("tag", "fixture-tag", cwd=root)
    git("checkout", "-b", "feature", cwd=root)
    (root / "feature.ts").write_text("export const feature=true")
    git("add", ".", cwd=root)
    git("commit", "-m", "Synthetic feature", cwd=root)
    git("checkout", "main", cwd=root)
    return root


class OfflineTransport:
    """Test-only file:// transport for real Git; production URL validation still requires HTTPS."""

    def __init__(self, origin: Path) -> None:
        self.origin = origin
        self.commands: list[list[str]] = []

    def run(self, arguments: Sequence[str], timeout: float, cwd: Path | None = None) -> str:
        self.commands.append(list(arguments))
        translated = [
            "protocol.file.allow=always" if value == "protocol.file.allow=never" else value
            for value in arguments
        ]
        translated = [
            self.origin.as_uri() if value == PUBLIC_TEST_URL else value for value in translated
        ]
        return SubprocessGitRunner().run(translated, timeout, cwd)


@pytest.mark.parametrize("ref", [None, "feature", "fixture-tag", "commit"])
def test_real_offline_git_clone_revision_ref_and_cleanup(
    ref: str | None, local_git: Path, tmp_path: Path
) -> None:
    expected_ref = ref if ref not in {None, "commit"} else "main"
    expected = git("rev-parse", str(expected_ref), cwd=local_git)
    selected = expected if ref == "commit" else ref
    parent = tmp_path / "workspaces"
    parent.mkdir()
    runner = OfflineTransport(local_git)
    use_case = DiscoverRepository({RepositorySourceType.GIT: GitRepositorySource(runner, parent)})
    with use_case.open(
        RepositoryInput(
            source_type=RepositorySourceType.GIT, location=PUBLIC_TEST_URL, ref=selected
        )
    ) as repository:
        snapshot = repository.snapshot
        assert snapshot.revision == expected
        paths = {file.relative_path for file in snapshot.files}
        assert "App.java" in paths and "bad.tmp" not in paths and "outside-link" not in paths
        assert ("feature.ts" in paths) == (ref == "feature")
        with repository.workspace.open_source_file("App.java") as stream:
            assert stream.read() == b"class App {}"
    assert list(parent.iterdir()) == []
    clone = next(command for command in runner.commands if "clone" in command)
    assert "--depth" in clone and "--no-recurse-submodules" in clone
    assert "core.hooksPath=/dev/null" in clone and "credential.helper=" in clone


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/repo",
        "ext::sh -c command",
        "/tmp/repo",
        "git@example.org:repo.git",
        "ssh://example.org/repo",
        "http://example.org/repo",
        "https://user:password@example.org/repo",
        "https://user@example.org/repo",
        "https://example.org/repo?token=secret",
        "https://example.org/repo#fragment",
        "https://example.org/repo\ncommand",
        "https://example.org:invalid/repo",
    ],
)
def test_git_rejects_unsafe_sources_without_running_git(url: str, tmp_path: Path) -> None:
    source = RepositoryInput(source_type=RepositorySourceType.GIT, location=url)
    with pytest.raises(InvalidRepositorySource):
        DiscoverRepository(
            {RepositorySourceType.GIT: GitRepositorySource(workspace_parent=tmp_path)}
        ).execute(source)
    assert list(tmp_path.iterdir()) == []


def test_git_timeout_cleans_materialization(tmp_path: Path) -> None:
    class TimeoutRunner:
        def run(self, arguments: Sequence[str], timeout: float, cwd: Path | None = None) -> str:
            raise GitTimeoutError("synthetic Git timeout")

    with pytest.raises(GitTimeoutError):
        DiscoverRepository(
            {RepositorySourceType.GIT: GitRepositorySource(TimeoutRunner(), tmp_path)}
        ).execute(RepositoryInput(source_type=RepositorySourceType.GIT, location=PUBLIC_TEST_URL))
    assert list(tmp_path.iterdir()) == []


def test_git_failure_keeps_internal_cause_and_no_credentials(
    caplog: pytest.LogCaptureFixture, tmp_path: Path
) -> None:
    with pytest.raises(GitCloneError) as captured:
        SubprocessGitRunner().run(["--invalid-option"], timeout=2)
    assert captured.value.__cause__ is not None
    assert "--invalid-option" not in str(captured.value)
    credential_url = "https://user:synthetic-private-token@example.org/repo"
    with pytest.raises(InvalidRepositorySource):
        DiscoverRepository({RepositorySourceType.GIT: GitRepositorySource()}).execute(
            RepositoryInput(source_type=RepositorySourceType.GIT, location=credential_url)
        )
    assert "synthetic-private-token" not in caplog.text and credential_url not in caplog.text


def test_real_git_process_timeout_terminates_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pid_file = tmp_path / "child.pid"
    script = (
        "sleep 30 & child=$!; printf '%s' \"$child\" > " + shlex.quote(str(pid_file)) + "; wait"
    )
    real_popen = subprocess.Popen

    def ready_process(arguments: list[str], **kwargs: object) -> subprocess.Popen[str]:
        assert arguments[0] == "git"
        process = real_popen(["/bin/sh", "-c", script], **kwargs)
        deadline = time.monotonic() + 5
        while not pid_file.exists():
            if process.poll() is not None or time.monotonic() > deadline:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
                pytest.fail("synthetic Git process did not reach its ready marker")
            time.sleep(0.01)
        return process

    with monkeypatch.context() as patch:
        patch.setattr(subprocess, "Popen", ready_process)
        with pytest.raises(GitTimeoutError):
            SubprocessGitRunner().run(["clone"], timeout=0.1)
    assert pid_file.exists()
    pid = int(pid_file.read_text())
    deadline = time.monotonic() + 2
    while True:
        state = subprocess.run(
            ["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True
        ).stdout.strip()
        if not state or state.startswith("Z"):
            break
        if time.monotonic() > deadline:
            pytest.fail("Git child process survived timeout")
        time.sleep(0.02)
