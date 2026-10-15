"""P032 full-suite custody fence; protected integration reads skip before file open."""

import os
import sys
from pathlib import Path
from typing import Any

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    root = Path(__file__).resolve().parents[3]
    forbidden = (
        root / "experiments/security/security-human-review-v1/private",
        root / "experiments/security/security-benchmark-v1/private/coordinator",
    )

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket.connect"):
            pytest.skip("P032 offline suite: real network connections denied")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.path.realpath(os.fsdecode(args[0])))
        if any(path.is_relative_to(parent) for parent in forbidden) or (
            path.parent == root
            and (path.name == ".env" or path.name.startswith(".env."))
            and path.name != ".env.example"
        ):
            pytest.skip(
                "P032 custody: historical private review/truth/intent or credentials not mounted"
            )

    sys.addaudithook(guard)
