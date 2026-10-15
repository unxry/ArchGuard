"""P034 established skip-before-open custody guard, extended to private DEV stores."""

import os
import sys
from pathlib import Path
from typing import Any

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    root = Path(__file__).resolve().parents[3]
    forbidden = tuple(
        root / "experiments/security" / name / "private"
        for name in (
            "security-human-review-v1",
            "security-dev-baseline-v1",
            "security-dev-refinement-v3",
        )
    ) + (root / "experiments/security/security-benchmark-v1/private/coordinator",)

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket.connect"):
            pytest.skip("P034 offline suite: real network connections denied")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.path.realpath(os.fsdecode(args[0])))
        if any(path.is_relative_to(parent) for parent in forbidden) or (
            path.parent == root and path.name.startswith(".env") and path.name != ".env.example"
        ):
            pytest.skip(
                "P034 custody: protected truth/review/intent/DEV or credentials not mounted"
            )

    sys.addaudithook(guard)
