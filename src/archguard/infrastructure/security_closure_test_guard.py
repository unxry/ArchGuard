"""P036 full-suite offline custody guard; synthetic non-benchmark tests remain allowed."""

import sys
from pathlib import Path
from typing import Any

import pytest

from archguard.infrastructure.security_extension_closure import guard_reason


def pytest_sessionstart(session: pytest.Session) -> None:
    root = Path(__file__).resolve().parents[3]

    def guard(event: str, args: tuple[Any, ...]) -> None:
        reason = guard_reason(event, args, root)
        if reason:
            pytest.skip("P036 closure custody/offline guard: " + reason)

    sys.addaudithook(guard)
