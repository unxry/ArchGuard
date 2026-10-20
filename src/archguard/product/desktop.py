"""Private native-shell launcher; no browser bridge or additional HTTP capabilities."""

import argparse
import asyncio
import fcntl
import json
import os
import re
import shutil
import signal
import socket
import sys
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import uvicorn

from archguard.product.app import create_product_app


class DesktopServer(uvicorn.Server):
    @contextmanager
    def capture_signals(self) -> Iterator[None]:
        # Uvicorn re-raises captured signals before our outer cleanup can run.
        yield


def clean_stale_sessions(root: Path) -> None:
    for folder in root.iterdir():
        if (
            not re.fullmatch(r"run-[0-9a-f]{32}", folder.name)
            or folder.is_symlink()
            or not folder.is_dir()
        ):
            continue
        try:
            with (folder / "owner.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                shutil.rmtree(folder)
        except (BlockingIOError, FileNotFoundError):
            continue


async def serve(root: Path, state: Path, sessions: Path) -> None:
    sessions.mkdir(parents=True, exist_ok=True, mode=0o700)
    clean_stale_sessions(sessions)
    folder = sessions / ("run-" + uuid4().hex)
    folder.mkdir(mode=0o700)
    owner = (folder / "owner.lock").open("w")
    fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
    previous_temp = tempfile.tempdir
    tempfile.tempdir = str(folder)
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server: uvicorn.Server | None = None
    lifeline: asyncio.Task[None] | None = None
    try:
        # Keep the bound socket: there is no find-free-port/rebind race.
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        port = listener.getsockname()[1]
        app = create_product_app(root, state, port=port)
        config = uvicorn.Config(app, log_config=None, log_level="critical", access_log=False)
        server = DesktopServer(config)
        loop = asyncio.get_running_loop()
        for number in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(number, setattr, server, "should_exit", True)
        running = asyncio.create_task(server.serve(sockets=[listener]))

        async def parent_lifeline() -> None:
            loop = asyncio.get_running_loop()
            closed: asyncio.Future[None] = loop.create_future()

            def readable() -> None:
                os.read(sys.stdin.fileno(), 1)
                if not closed.done():
                    closed.set_result(None)

            loop.add_reader(sys.stdin.fileno(), readable)
            try:
                await closed
                server.should_exit = True
            finally:
                loop.remove_reader(sys.stdin.fileno())

        lifeline = asyncio.create_task(parent_lifeline())
        while not server.started and not running.done():
            await asyncio.sleep(0.02)
        if server.started and not server.should_exit:
            print(json.dumps({"ready": True, "port": port}), flush=True)
        await running
    finally:
        if server is not None:
            await app.state.runtime.close()
            for number in (signal.SIGTERM, signal.SIGINT):
                asyncio.get_running_loop().remove_signal_handler(number)
        if lifeline is not None:
            lifeline.cancel()
        listener.close()
        tempfile.tempdir = previous_temp
        shutil.rmtree(folder)
        owner.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--projects-root", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--sessions-dir", type=Path, required=True)
    args = parser.parse_args()
    # The native owner supplies a pipe; never start a detached daemon from a terminal.
    if sys.stdin.isatty():
        raise SystemExit("NATIVE_OWNER_REQUIRED")
    try:
        asyncio.run(serve(args.projects_root, args.state_dir, args.sessions_dir))
    except Exception:
        print(json.dumps({"error": "BACKEND_START_FAILED"}), flush=True)
        os._exit(1)


if __name__ == "__main__":
    main()
