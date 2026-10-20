import json
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from archguard.product.desktop import clean_stale_sessions

SAMPLE = Path(__file__).resolve().parents[2] / "examples/product"


def launch(
    tmp_path: Path, root: Path = SAMPLE, *, single_project: bool = False
) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "archguard.product.desktop",
            "--project-dir" if single_project else "--projects-root",
            str(root),
            "--state-dir",
            str(tmp_path / "state"),
            "--sessions-dir",
            str(tmp_path / "sessions"),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def ready(child: subprocess.Popen[str]) -> dict:
    assert child.stdout is not None
    assert select.select([child.stdout], [], [], 10)[0], "No startup result"
    return json.loads(child.stdout.readline())


def request(port: int, route: str, token: str = "", body: dict | None = None) -> dict | list:
    url = f"http://127.0.0.1:{port}"
    req = urllib.request.Request(
        url + route,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Origin": url, "X-ArchGuard-Token": token, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=4) as response:
        return json.load(response)


def close(child: subprocess.Popen[str]) -> None:
    assert child.stdin is not None
    child.stdin.close()
    child.wait(timeout=6)
    assert child.stdout is not None and child.stderr is not None
    child.stdout.close()
    child.stderr.close()


def closed(port: int) -> bool:
    with socket.socket() as probe:
        return probe.connect_ex(("127.0.0.1", port)) != 0


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS execution sandbox")
def test_dynamic_ports_real_analysis_and_owner_eof(tmp_path: Path) -> None:
    first, second = launch(tmp_path / "one"), launch(tmp_path / "two")
    try:
        ports = [ready(first)["port"], ready(second)["port"]]
        assert ports[0] != ports[1]
        port = ports[0]
        session = request(port, "/api/product/session")
        token = session["token"]
        catalog = request(port, "/api/product/projects", token)
        job = request(
            port,
            "/api/product/jobs",
            token,
            {"project_id": catalog[0]["id"], "architecture": True, "security": True},
        )
        for _ in range(200):
            status = request(port, "/api/product/jobs/" + job["id"], token)
            if status["status"] in {"READY", "FAILED"}:
                break
            time.sleep(0.02)
        assert status["status"] == "READY", status
        result = request(port, "/api/product/results/" + job["id"], token)
        assert len(result["graph"]["graph"]["nodes"]) == 4
        assert len(result["graph"]["graph"]["edges"]) == 3
    finally:
        close(first)
        close(second)
    assert all(closed(port) for port in ports)
    assert not list(tmp_path.glob("*/sessions/run-*"))


def test_invalid_root_reports_safe_failure(tmp_path: Path) -> None:
    child = launch(tmp_path, tmp_path / "absent")
    try:
        assert ready(child) == {"error": "BACKEND_START_FAILED"}
        assert child.wait(timeout=4) == 1
    finally:
        close(child)
    assert not list((tmp_path / "sessions").glob("run-*"))


def test_backend_sigterm_does_not_hang_on_parent_pipe(tmp_path: Path) -> None:
    child = launch(tmp_path)
    port = ready(child)["port"]
    child.terminate()
    assert child.wait(timeout=4) in (0, -signal.SIGTERM)
    close(child)
    assert closed(port)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS execution sandbox")
def test_open_actual_project_folder_without_spec(tmp_path: Path) -> None:
    project = tmp_path / "Workspace with spaces" / "Actual Project"
    shutil.copytree(SAMPLE / "observatory-ts", project)
    (project / "architecture.yaml").unlink()
    (project.parent / "Private Sibling").mkdir()
    child = launch(tmp_path / "state", project, single_project=True)
    try:
        port = ready(child)["port"]
        session = request(port, "/api/product/session")
        assert session["capabilities"]["native_project_picker"] is True
        token = session["token"]
        catalog = request(port, "/api/product/projects", token)
        assert len(catalog) == 1
        assert catalog[0]["name"] == "Actual Project"
        assert catalog[0]["architecture_available"] is False
        job = request(
            port,
            "/api/product/jobs",
            token,
            {"project_id": catalog[0]["id"], "architecture": False, "security": True},
        )
        for _ in range(300):
            status = request(port, "/api/product/jobs/" + job["id"], token)
            if status["status"] in {"READY", "FAILED"}:
                break
            time.sleep(0.02)
        assert status["status"] == "READY", status
        result = request(port, "/api/product/results/" + job["id"], token)
        assert len(result["graph"]["graph"]["nodes"]) == 4
        assert len(result["graph"]["graph"]["edges"]) == 3
        assert result["classification"] is None
    finally:
        close(child)
    assert closed(port)
    assert not list((tmp_path / "sessions").glob("run-*"))


def test_stale_sessions_recovered_without_touching_active_or_unrelated(tmp_path: Path) -> None:
    child = launch(tmp_path)
    port = ready(child)["port"]
    sessions = tmp_path / "sessions"
    folder = next(sessions.glob("run-*"))
    clean_stale_sessions(sessions)
    assert folder.exists()
    unrelated = sessions / "unrelated"
    unrelated.mkdir()
    sentinel = tmp_path / "user-data"
    sentinel.mkdir()
    link = sessions / ("run-" + "f" * 32)
    link.symlink_to(sentinel, target_is_directory=True)
    child.kill()
    child.wait(timeout=4)
    close(child)
    clean_stale_sessions(sessions)
    assert not folder.exists() and unrelated.exists() and sentinel.exists() and link.is_symlink()
    assert closed(port)
    again = launch(tmp_path)
    ready(again)
    close(again)


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS execution sandbox")
def test_worker_exits_if_backend_is_killed(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    project = root / "large"
    project.mkdir(parents=True)
    for i in range(200):
        (project / f"m{i}.ts").write_text(f"export class C{i} {{ value: number = {i}; }}\n" * 70)
    child = launch(tmp_path, root)
    port = ready(child)["port"]
    token = request(port, "/api/product/session")["token"]
    catalog = request(port, "/api/product/projects", token)
    request(
        port,
        "/api/product/jobs",
        token,
        {"project_id": catalog[0]["id"], "architecture": False, "security": True},
    )
    worker = None
    for _ in range(150):
        table = subprocess.check_output(["/bin/ps", "-axo", "pid=,ppid=,command="], text=True)
        for line in table.splitlines():
            parts = line.split(None, 2)
            if (
                len(parts) == 3
                and parts[1] == str(child.pid)
                and ("sandbox-exec" in parts[2] or "archguard.product.worker" in parts[2])
            ):
                worker = int(parts[0])
                break
        if worker:
            break
        time.sleep(0.01)
    try:
        assert worker is not None
        # Allow the isolated interpreter to install its parent watchdog.
        time.sleep(0.15)
        child.kill()
        child.wait(timeout=4)
        for _ in range(150):
            try:
                os.kill(worker, 0)
            except ProcessLookupError:
                break
            time.sleep(0.02)
        else:
            raise AssertionError("Worker survived parent death")
    finally:
        close(child)
    assert closed(port)
