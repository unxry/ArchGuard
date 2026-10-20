"""Loopback-only product API and packaged browser frontend."""

import argparse
import json
import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from archguard.api.app import create_app as foundation_app
from archguard.product.runtime import MAX_RESULT, Runtime


class AnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    project_id: Annotated[str, Field(pattern=r"^[0-9a-f]{16}$")]
    architecture: bool = False
    security: bool = True


def create_product_app(
    root: Path,
    state: Path,
    port: int = 8790,
    timeout: float = 45,
    *,
    single_project: bool = False,
    desktop: bool = False,
) -> FastAPI:
    runtime = Runtime(root, state, timeout, single_project)
    origin = f"http://127.0.0.1:{port}"
    app = foundation_app()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        await runtime.close()

    app.router.lifespan_context = lifespan
    app.state.runtime = runtime

    @app.middleware("http")
    async def local_boundary(request: Request, call_next: Any) -> Response:
        if request.headers.get("host") != f"127.0.0.1:{port}":
            return JSONResponse({"error": "LOCAL_HOST_REQUIRED"}, status_code=403)
        if (
            request.headers.get("origin") not in (None, origin)
            or request.headers.get("sec-fetch-site") == "cross-site"
        ):
            return JSONResponse({"error": "LOCAL_ORIGIN_REQUIRED"}, status_code=403)
        if (
            request.url.path.startswith("/api/product/")
            and request.url.path != "/api/product/session"
        ):
            supplied = request.headers.get("x-archguard-token", "")
            if not secrets.compare_digest(supplied, runtime.token):
                return JSONResponse({"error": "SESSION_REQUIRED"}, status_code=401)
        if request.method not in {"GET", "HEAD"}:
            if request.headers.get("origin") != origin:
                return JSONResponse({"error": "ORIGIN_REQUIRED"}, status_code=403)
            length = request.headers.get("content-length", "")
            if not length.isdecimal() or int(length) > 2048:
                return JSONResponse({"error": "BODY_LIMIT"}, status_code=413)
        response: Response = await call_next(request)
        response.headers.update(
            {
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
                "Referrer-Policy": "no-referrer",
                "X-Frame-Options": "DENY",
                "Content-Security-Policy": "default-src 'self'; script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; "
                "frame-ancestors 'none'; form-action 'none'",
            }
        )
        return response

    @app.get("/api/product/session")
    def session() -> dict[str, Any]:
        return {
            "token": runtime.token,
            "sandbox_available": runtime.sandbox,
            "capabilities": {
                "local": runtime.sandbox,
                "git": False,
                "zip": False,
                "provider_calls": False,
                "source_execution": False,
                "native_project_picker": desktop,
            },
            "limits": {"files": 200, "source_bytes": 4194304, "timeout_seconds": timeout},
        }

    @app.get("/api/product/projects")
    def list_projects() -> list[dict[str, Any]]:
        return runtime.catalog()

    @app.post("/api/product/jobs", status_code=202)
    async def begin(request: AnalysisRequest) -> dict[str, Any]:
        try:
            return runtime.start(
                request.project_id, request.architecture, request.security
            ).public()
        except ValueError as error:
            raise HTTPException(409, str(error)) from None

    @app.get("/api/product/jobs/{identifier}")
    def job_status(identifier: str) -> dict[str, Any]:
        job = runtime.jobs.get(identifier)
        if job is None:
            raise HTTPException(404, "JOB_UNAVAILABLE")
        return job.public()

    @app.post("/api/product/jobs/{identifier}/cancel")
    async def cancel(identifier: str) -> dict[str, Any]:
        job = runtime.jobs.get(identifier)
        if job is None:
            raise HTTPException(404, "JOB_UNAVAILABLE")
        runtime.cancel(job)
        return job.public()

    @app.get("/api/product/results")
    def results() -> list[dict[str, Any]]:
        return runtime.saved()

    @app.get("/api/product/results/{identifier}")
    def result(identifier: str) -> Any:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise HTTPException(404, "RESULT_UNAVAILABLE")
        file = runtime.state / (identifier + ".json")
        if not file.is_file() or file.is_symlink() or file.stat().st_size > MAX_RESULT:
            raise HTTPException(404, "RESULT_UNAVAILABLE")
        try:
            return json.loads(file.read_text())
        except (OSError, ValueError):
            raise HTTPException(422, "RESULT_INVALID") from None

    @app.delete("/api/product/results/{identifier}")
    def delete_result(identifier: str) -> dict[str, bool]:
        if not re.fullmatch(r"[0-9a-f]{32}", identifier):
            raise HTTPException(404, "RESULT_UNAVAILABLE")
        file = runtime.state / (identifier + ".json")
        if not file.is_file() or file.is_symlink():
            raise HTTPException(404, "RESULT_UNAVAILABLE")
        try:
            file.unlink()
        except OSError:
            raise HTTPException(409, "RESULT_DELETE_FAILED") from None
        return {"deleted": True}

    app.mount("/", StaticFiles(directory=Path(__file__).parent / "web", html=True), name="frontend")
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="ArchGuard local Cinematic application")
    parser.add_argument("--projects-root", type=Path, required=True)
    parser.add_argument(
        "--state-dir", type=Path, default=Path.home() / ".local/share/archguard/product"
    )
    parser.add_argument("--port", type=int, default=8790)
    options = parser.parse_args()
    if not 1024 <= options.port <= 65535:
        parser.error("port must be 1024–65535")
    uvicorn.run(
        create_product_app(options.projects_root, options.state_dir, options.port),
        host="127.0.0.1",
        port=options.port,
        access_log=False,
    )


if __name__ == "__main__":
    main()
