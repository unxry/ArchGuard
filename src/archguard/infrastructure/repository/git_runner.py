import os
import signal
import subprocess
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path
from typing import Protocol

from archguard.repository.errors import GitCloneError, GitTimeoutError


class GitRunner(Protocol):
    def run(self, arguments: Sequence[str], timeout: float, cwd: Path | None = None) -> str: ...


class GitCommandFailure(Exception):
    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(f"Git command failed with exit code {returncode}")
        self.stderr = stderr


class SubprocessGitRunner:
    def run(self, arguments: Sequence[str], timeout: float, cwd: Path | None = None) -> str:
        env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
        env.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_ASKPASS": "/usr/bin/false",
                "GIT_LFS_SKIP_SMUDGE": "1",
                "LC_ALL": "C",
            }
        )
        try:
            process = subprocess.Popen(
                ["git", *arguments],
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                start_new_session=True,
            )
        except OSError as error:
            raise GitCloneError("Git CLI could not be started") from error
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
            raise GitTimeoutError("Git operation exceeded its configured timeout") from error
        finally:
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                process.communicate()
        if process.returncode != 0:
            raise GitCloneError(
                "public HTTPS Git operation failed; credentials are not supported"
            ) from GitCommandFailure(process.returncode, stderr)
        return stdout.strip()
