import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archguard.product.app import create_product_app
from archguard.product.intake import IntakeError, projects, snapshot
from archguard.product.runtime import Runtime, sandbox_profile

SAMPLE = Path(__file__).resolve().parents[2] / "examples/product/observatory-ts"
MAC = sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").exists()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    folder = tmp_path / "projects"
    shutil.copytree(SAMPLE, folder / "sample")
    return folder


def test_intake_excludes_credentials_and_dependencies(root: Path, tmp_path: Path) -> None:
    p = root / "sample"
    (p / ".env").write_text("PRIVATE_CANARY")
    (p / ".ssh").mkdir()
    (p / ".ssh/key.ts").write_text("PRIVATE_CANARY")
    (p / "node_modules").mkdir()
    (p / "node_modules/vendor.ts").write_text("PRIVATE_CANARY")
    (p / "credentials.json").write_text("PRIVATE_CANARY")
    receipt = snapshot(root, "sample", tmp_path / "copy")
    assert receipt["files"] == 5
    assert not any(
        "PRIVATE_CANARY" in f.read_text() for f in (tmp_path / "copy").rglob("*") if f.is_file()
    )


@pytest.mark.parametrize("name", ["../sample", "/etc", "sample/.."])
def test_intake_rejects_path_escape(root: Path, tmp_path: Path, name: str) -> None:
    with pytest.raises(IntakeError, match="PROJECT_UNAVAILABLE"):
        snapshot(root, name, tmp_path / "copy")


def test_single_project_intake_never_reads_siblings(tmp_path: Path) -> None:
    selected = tmp_path / "Selected Project"
    selected.mkdir()
    (selected / "index.ts").write_text("export class Selected {}")
    other = tmp_path / "Private Sibling"
    other.mkdir()
    (other / "secret.ts").write_text("PRIVATE_CANARY")
    catalog = projects(selected, single_project=True)
    assert list(catalog.values()) == [selected.name]
    with pytest.raises(IntakeError):
        snapshot(selected, other.name, tmp_path / "rejected", single_project=True)
    receipt = snapshot(selected, selected.name, tmp_path / "copy", single_project=True)
    assert receipt["files"] == 1
    assert [p.name for p in (tmp_path / "copy").iterdir()] == ["index.ts"]


def test_saved_result_deletion_requires_session_and_origin(root: Path, tmp_path: Path) -> None:
    state = tmp_path / "state"
    app = create_product_app(root, state)
    result_id = "a" * 32
    raw = {"project": {"name": "Test"}, "provenance": {"snapshot_fingerprint": "b" * 64}}
    for index in range(18):
        (state / (f"{index:032x}" + ".json")).write_text(json.dumps(raw))
    (state / (result_id + ".json")).write_text("{damaged")
    (state / ("c" * 32 + ".json")).write_text("[]")
    with TestClient(app, base_url="http://127.0.0.1:8790") as client:
        token = client.get("/api/product/session").json()["token"]
        headers = {"X-ArchGuard-Token": token, "Origin": "http://127.0.0.1:8790"}
        route = "/api/product/results/" + result_id
        assert client.request("DELETE", route, json={}).status_code == 401
        assert (
            client.request(
                "DELETE", route, json={}, headers={"X-ArchGuard-Token": token}
            ).status_code
            == 403
        )
        assert client.get(route, headers=headers).status_code == 422
        assert len(client.get("/api/product/results", headers=headers).json()) == 20
        assert client.request("DELETE", route, json={}, headers=headers).json() == {"deleted": True}
        assert (
            client.request(
                "DELETE", "/api/product/results/invalid", json={}, headers=headers
            ).status_code
            == 404
        )
        assert (
            client.request(
                "DELETE", "/api/product/results/" + "0" * 32, json={}, headers=headers
            ).status_code
            == 200
        )
        assert len(client.get("/api/product/results", headers=headers).json()) == 18
        assert not (state / ("0" * 32 + ".json")).exists()


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "oversize", "binary"])
def test_intake_rejects_unsafe_sources(root: Path, tmp_path: Path, kind: str) -> None:
    outside = tmp_path / "outside.ts"
    outside.write_text("PRIVATE_CANARY")
    target = root / "sample/bad.ts"
    if kind == "symlink":
        target.symlink_to(outside)
    elif kind == "hardlink":
        os.link(outside, target)
    else:
        target.write_bytes(b"x" * (256 * 1024 + 1) if kind == "oversize" else b"\0")
    with pytest.raises(IntakeError):
        snapshot(root, "sample", tmp_path / "copy")


def test_gateway_boundary(root: Path, tmp_path: Path) -> None:
    app = create_product_app(root, tmp_path / "state")
    with TestClient(app, base_url="http://127.0.0.1:8790") as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
        assert (
            client.get(
                "/api/product/session", headers={"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert client.get("/api/product/projects").status_code == 401
        info = client.get("/api/product/session").json()
        assert not info["capabilities"]["provider_calls"]
        headers = {"X-ArchGuard-Token": info["token"]}
        assert client.post("/api/product/jobs", json={}, headers=headers).status_code == 403
        headers["Origin"] = "http://127.0.0.1:8790"
        assert (
            client.post(
                "/api/product/jobs", json={"project_id": "../etc"}, headers=headers
            ).status_code
            == 422
        )
        project = client.get("/api/product/projects", headers=headers).json()[0]["id"]
        assert (
            client.post(
                "/api/product/jobs",
                json={"project_id": project, "command": "echo unsafe"},
                headers=headers,
            ).status_code
            == 422
        )
        assert (
            client.post("/api/product/jobs", content="x" * 2049, headers=headers).status_code == 413
        )
        assert client.get("/api/product/results/evil", headers=headers).status_code == 404
        app.state.runtime.sandbox = False
        assert (
            client.post("/api/product/jobs", json={"project_id": project}, headers=headers).json()[
                "detail"
            ]
            == "OS_SANDBOX_UNAVAILABLE"
        )


@pytest.mark.skipif(not MAC, reason="macOS OS sandbox required")
def test_os_sandbox_denies_outside_reads_network_and_exec(tmp_path: Path) -> None:
    job = tmp_path / "job"
    job.mkdir()
    canary = tmp_path / "private-canary"
    canary.write_text("NOT_A_CREDENTIAL")
    profile = job / "sandbox.sb"
    profile.write_text(sandbox_profile(job))
    program = f"""
import json, socket, subprocess
result = {{}}
try:
    open({str(canary)!r}).read()
    result['read'] = 'ALLOWED'
except PermissionError: result['read'] = 'DENIED'
try:
    socket.create_connection(('127.0.0.1', 9), timeout=1)
    result['network'] = 'ALLOWED'
except PermissionError: result['network'] = 'DENIED'
try:
    subprocess.run(['/bin/sh', '-c', 'exit 0'], check=True)
    result['exec'] = 'ALLOWED'
except PermissionError: result['exec'] = 'DENIED'
open('allowed-output', 'w').write('ok')
print(json.dumps(result))
"""
    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-f", str(profile), sys.executable, "-B", "-I", "-c", program],
        cwd=job,
        env={"PATH": "/usr/bin:/bin", "HOME": str(job), "TMPDIR": str(job)},
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    assert json.loads(result.stdout) == dict.fromkeys(["read", "network", "exec"], "DENIED")
    assert (job / "allowed-output").read_text() == "ok"


@pytest.mark.skipif(not MAC, reason="macOS OS sandbox required")
def test_real_analysis_result_and_reopen(
    root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from archguard.product import runtime as module

    folders: list[Path] = []
    original = module.tempfile.mkdtemp

    def tracked(**kwargs: str) -> str:
        folder = original(**kwargs)
        folders.append(Path(folder))
        return folder

    monkeypatch.setattr(module.tempfile, "mkdtemp", tracked)

    async def run() -> None:
        runtime = Runtime(root, tmp_path / "state")
        job = runtime.start(next(iter(projects(root))), True, True)
        with pytest.raises(ValueError, match="ANALYSIS_BUSY"):
            runtime.start(job.project_id, True, True)
        await job.task
        assert job.status == "READY", job.public()
        result = json.loads((runtime.state / f"{job.id}.json").read_text())
        assert result["schema"] == "archguard-product-v1"
        assert len(result["graph"]["graph"]["nodes"]) == 4
        assert len(result["graph"]["graph"]["edges"]) == 3
        assert result["architecture"]["findings"][0]["rule_id"] == "ARCH002"
        assert result["security"][0]["findings"][0]["rule_id"] == "SEC002"
        assert result["security"][0]["zero_findings_is_security_guarantee"] is False
        assert result["provenance"]["provider_calls"] == 0
        assert result["provenance"]["source_code_executed"] is False
        assert "/Users/" not in json.dumps(result)
        assert "/private/var/" not in json.dumps(result)
        assert folders and all(not folder.exists() for folder in folders)
        assert Runtime(root, runtime.state).saved()[0]["id"] == job.id
        await runtime.close()

    asyncio.run(run())


@pytest.mark.skipif(not MAC, reason="macOS OS sandbox required")
@pytest.mark.parametrize("mode", ["timeout", "cancel", "shutdown", "missing_spec"])
def test_termination_and_failure(root: Path, tmp_path: Path, mode: str) -> None:
    async def run() -> None:
        runtime = Runtime(root, tmp_path / "state", timeout=0.001 if mode == "timeout" else 45)
        if mode == "missing_spec":
            (root / "sample/architecture.yaml").unlink()
        job = runtime.start(next(iter(projects(root))), True, True)
        if mode in {"cancel", "shutdown"}:
            for _ in range(300):
                if job.process:
                    break
                await asyncio.sleep(0.001)
            if mode == "shutdown":
                await runtime.close()
            else:
                runtime.cancel(job)
        await job.task
        assert (
            job.status
            == {
                "timeout": "TIMED_OUT",
                "cancel": "CANCELLED",
                "shutdown": "CANCELLED",
                "missing_spec": "FAILED",
            }[mode]
        )
        assert not runtime.saved()
        if job.process:
            assert job.process.returncode is not None
        if mode == "missing_spec":
            assert job.error == "ARCHITECTURE_SPEC_REQUIRED"
        await runtime.close()

    asyncio.run(run())


@pytest.mark.skipif(not MAC, reason="macOS OS sandbox required")
@pytest.mark.parametrize("security", [False, True])
def test_optional_operations_do_not_create_other_results(
    root: Path, tmp_path: Path, security: bool
) -> None:
    (root / "sample/src/controller/SearchController.ts").unlink()

    async def run() -> None:
        runtime = Runtime(root, tmp_path / "state")
        job = runtime.start(next(iter(projects(root))), False, security)
        await job.task
        assert job.status == "READY", job.public()
        result = json.loads((runtime.state / f"{job.id}.json").read_text())
        assert result["architecture"] is None
        assert result["classification"] is None
        assert len(result["graph"]["graph"]["nodes"]) == 3
        assert len(result["security"]) == int(security)
        if security:
            assert result["security"][0]["findings"] == []
            assert result["security"][0]["zero_findings_is_security_guarantee"] is False
        await runtime.close()

    asyncio.run(run())
