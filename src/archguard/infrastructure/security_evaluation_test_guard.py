"""P035 custody guard: only its chronology-gated workflow can open original FINAL truth."""

import os
import sys
from pathlib import Path
from types import FrameType
from typing import Any

import pytest


def pytest_sessionstart(session: pytest.Session) -> None:
    root = Path(__file__).resolve().parents[3]
    human = root / "experiments/security/security-human-review-v1/private"
    final = human / "truth/FINAL/truth.json"
    metadata = human / "truth/freeze-index.json"
    denied = tuple(
        root / "experiments/security" / name / "private"
        for name in (
            "security-dev-baseline-v1",
            "security-dev-refinement-v3",
        )
    ) + (root / "experiments/security/security-benchmark-v1/private/coordinator",)

    def guard(event: str, args: tuple[Any, ...]) -> None:
        if event.startswith("socket.connect"):
            pytest.skip("P035 offline suite: real network connections denied")
        if event != "open" or isinstance(args[0], int):
            return
        path = Path(os.path.realpath(os.fsdecode(args[0])))
        if path in {final, metadata}:
            frame: FrameType | None = sys._getframe(1)
            permitted = False
            while frame is not None:
                if (
                    frame.f_globals.get("__name__")
                    == "archguard.infrastructure.security_final_evaluation"
                    and frame.f_code.co_name == "open_truth"
                ):
                    gate = frame.f_locals.get("gate")
                    permitted = getattr(gate, "ready", False) is True
                    break
                frame = frame.f_back
            if permitted:
                return
        if (
            path.is_relative_to(human)
            or any(path.is_relative_to(p) for p in denied)
            or (path.name.startswith(".env") and path.name != ".env.example")
        ):
            pytest.skip("P035 custody: unrelated truth/review/intent/DEV or credentials denied")

    sys.addaudithook(guard)
