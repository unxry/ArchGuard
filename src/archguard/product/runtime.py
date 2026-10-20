"""Local sessions with a fixed operation, OS sandbox, bounded intake and cancellation."""

import asyncio
import json
import os
import secrets
import shutil
import signal
import sys
import tempfile
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from archguard.product.intake import IntakeError, projects, snapshot

STAGES = {"PREPARING", "READING", "ANALYZING", "SERIALIZING", "READY"}
MAX_RESULT = 32 * 1024 * 1024


def sandbox_profile(job: Path) -> str:
    package = Path(__file__).resolve().parents[1]
    read = {
        Path(sys.prefix),
        Path(sys.base_prefix),
        package,
        job,
        Path("/System/Library"),
        Path("/usr/lib"),
        Path("/usr/share/zoneinfo"),
        Path("/dev/null"),
        Path("/dev/urandom"),
        Path("/dev/random"),
    }
    rules = " ".join(f"(subpath {json.dumps(str(p.resolve()))})" for p in sorted(read))
    executable = json.dumps(str(Path(sys.executable).resolve()))
    return f"""(version 1)
(deny default)
(allow file-read-metadata)
(allow file-read-data (literal "/") (literal {json.dumps(str(package.parent))}))
(allow file-read* {rules})
(allow file-write* (subpath {json.dumps(str(job.resolve()))}) (literal "/dev/null"))
(allow process-exec (literal {executable}))
(allow sysctl-read)
(allow signal (target self))
"""


@dataclass
class Job:
    id: str
    project_id: str
    project_name: str
    status: str = "PREPARING"
    stages: list[str] = field(default_factory=lambda: ["PREPARING"])
    error: str | None = None
    task: asyncio.Task[None] | None = None
    process: asyncio.subprocess.Process | None = None
    cancelled: bool = False
    termination: asyncio.Task[None] | None = None

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project_name,
            "status": self.status,
            "stages": self.stages,
            "error": self.error,
        }


class Runtime:
    def __init__(
        self, root: Path, state: Path, timeout: float = 45, single_project: bool = False
    ) -> None:
        self.root, self.state, self.timeout = root.resolve(strict=True), state.resolve(), timeout
        if not self.root.is_dir():
            raise ValueError("PROJECT_DIRECTORY_REQUIRED")
        self.single_project = single_project
        self.state.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state, 0o700)
        self.token = secrets.token_urlsafe(32)
        self.jobs: dict[str, Job] = {}
        self.sandbox = sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file()
        self.slots = asyncio.Semaphore(1)

    def catalog(self) -> list[dict[str, Any]]:
        items = []
        for key, name in projects(self.root, self.single_project).items():
            folder = self.root if self.single_project else self.root / name
            spec = folder / "architecture.yaml"
            items.append(
                {
                    "id": key,
                    "name": name,
                    "architecture_available": spec.is_file() and not spec.is_symlink(),
                }
            )
        return items

    def start(self, project_id: str, architecture: bool, security: bool) -> Job:
        if not self.sandbox:
            raise ValueError("OS_SANDBOX_UNAVAILABLE")
        name = projects(self.root, self.single_project).get(project_id)
        if name is None:
            raise ValueError("PROJECT_UNAVAILABLE")
        if any(j.status in STAGES - {"READY"} for j in self.jobs.values()):
            raise ValueError("ANALYSIS_BUSY")
        if len(list(self.state.glob("*.json"))) >= 20:
            raise ValueError("RESULT_STORAGE_LIMIT")
        job = Job(secrets.token_hex(16), project_id, name)
        self.jobs[job.id] = job
        job.task = asyncio.create_task(self.execute(job, architecture, security))
        return job

    async def execute(self, job: Job, architecture: bool, security: bool) -> None:
        async with self.slots:
            folder = Path(tempfile.mkdtemp(prefix="archguard-job-")).resolve()
            try:
                receipt = await asyncio.to_thread(
                    snapshot, self.root, job.project_name, folder / "source", self.single_project
                )
                if job.cancelled:
                    return
                if architecture and not (folder / "source/architecture.yaml").is_file():
                    raise IntakeError("ARCHITECTURE_SPEC_REQUIRED")
                request = {
                    "project_id": job.project_id,
                    "project_name": job.project_name,
                    "architecture": architecture,
                    "security": security,
                    "source_digest": receipt["sha256"],
                }
                (folder / "request.json").write_text(json.dumps(request))
                (folder / "sandbox.sb").write_text(sandbox_profile(folder))
                # Fixed trusted module path; user input is never executable command text.
                source_root = str(Path(__file__).resolve().parents[2])
                program = (
                    f"import sys;sys.path.insert(0,{source_root!r});"
                    f"from archguard.product.worker import main;main(parent_pid={os.getpid()})"
                )
                job.process = await asyncio.create_subprocess_exec(
                    "/usr/bin/sandbox-exec",
                    "-f",
                    str(folder / "sandbox.sb"),
                    sys.executable,
                    "-B",
                    "-I",
                    "-c",
                    program,
                    str(folder),
                    cwd=folder,
                    env={
                        "PATH": "/usr/bin:/bin",
                        "LANG": "en_US.UTF-8",
                        "HOME": str(folder),
                        "TMPDIR": str(folder),
                    },
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    start_new_session=True,
                    limit=4096,
                )
                if job.cancelled:
                    await self.kill(job)
                    return

                async def consume() -> None:
                    assert job.process is not None and job.process.stdout is not None
                    while line := await job.process.stdout.readline():
                        event = json.loads(line)
                        stage = event.get("stage")
                        if stage in STAGES and stage != "READY" and not job.cancelled:
                            job.status = stage
                            if stage not in job.stages:
                                job.stages.append(stage)
                    await job.process.wait()

                async def memory_limit() -> None:
                    assert job.process is not None
                    while job.process.returncode is None:
                        probe = await asyncio.create_subprocess_exec(
                            "/bin/ps",
                            "-o",
                            "rss=",
                            "-p",
                            str(job.process.pid),
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        output, _ = await probe.communicate()
                        if output.strip().isdigit() and int(output) > 2 * 1024 * 1024:
                            job.error = "MEMORY_LIMIT"
                            await self.kill(job)
                            return
                        await asyncio.sleep(0.25)

                monitor = asyncio.create_task(memory_limit())
                try:
                    await asyncio.wait_for(consume(), self.timeout)
                finally:
                    monitor.cancel()
                    with suppress(asyncio.CancelledError):
                        await monitor
                if job.cancelled:
                    return
                if job.process.returncode != 0:
                    raise ValueError("ANALYZER_FAILED")
                result_path = folder / "result.json"
                if result_path.stat().st_size > MAX_RESULT:
                    raise ValueError("RESULT_SIZE_LIMIT")
                raw = json.loads(result_path.read_text())
                if raw.get("schema") != "archguard-product-v1":
                    raise ValueError("RESULT_SCHEMA_INVALID")
                temp = self.state / (job.id + ".pending")
                temp.write_text(json.dumps(raw, ensure_ascii=False))
                os.chmod(temp, 0o600)
                temp.replace(self.state / (job.id + ".json"))
                job.status = "READY"
                job.stages.append("READY")
            except TimeoutError:
                await self.kill(job)
                job.status, job.error = "TIMED_OUT", "TIME_LIMIT"
            except (IntakeError, ValueError, OSError) as error:
                if not job.cancelled:
                    job.status = "FAILED"
                    job.error = job.error or (
                        str(error) if isinstance(error, IntakeError) else "ANALYZER_FAILED"
                    )
            finally:
                await self.kill(job)
                if job.process:
                    await job.process.wait()
                shutil.rmtree(folder)

    @staticmethod
    async def kill(job: Job) -> None:
        for _ in range(100):
            if not job.process or job.process.returncode is not None:
                return
            try:
                os.killpg(job.process.pid, signal.SIGKILL)
                return
            except ProcessLookupError:
                return
            except PermissionError:
                # sandbox-exec briefly changes credentials before exec of Python.
                await asyncio.sleep(0.01)
        raise RuntimeError("CHILD_TERMINATION_FAILED")

    def cancel(self, job: Job) -> None:
        if job.status in {"READY", "FAILED", "TIMED_OUT", "CANCELLED"}:
            return
        job.cancelled, job.status = True, "CANCELLED"
        job.termination = asyncio.create_task(self.kill(job))

    async def close(self) -> None:
        for job in self.jobs.values():
            self.cancel(job)
        await asyncio.gather(
            *(task for j in self.jobs.values() for task in (j.task, j.termination) if task)
        )

    def saved(self) -> list[dict[str, Any]]:
        items = []
        files = [p for p in self.state.glob("*.json") if p.is_file() and not p.is_symlink()]
        for file in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            if len(file.stem) != 32 or any(c not in "0123456789abcdef" for c in file.stem):
                continue
            try:
                if file.stat().st_size > MAX_RESULT:
                    raise ValueError("RESULT_SIZE_LIMIT")
                raw = json.loads(file.read_text())
                if (
                    not isinstance(raw, dict)
                    or not isinstance(raw.get("project"), dict)
                    or not isinstance(raw["project"].get("name"), str)
                    or not isinstance(raw.get("provenance"), dict)
                    or not isinstance(raw["provenance"].get("snapshot_fingerprint"), str)
                ):
                    raise ValueError("RESULT_INVALID")
                items.append(
                    {
                        "id": file.stem,
                        "project": raw["project"],
                        "snapshot": raw["provenance"]["snapshot_fingerprint"],
                    }
                )
            except (OSError, ValueError, KeyError):
                items.append(
                    {
                        "id": file.stem,
                        "project": {"name": file.stem[:12]},
                        "snapshot": "",
                        "invalid": True,
                    }
                )
        return items
