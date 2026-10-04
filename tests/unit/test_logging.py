import json
import logging

import pytest

from archguard.infrastructure.logging import JsonFormatter, configure_logging
from archguard.infrastructure.settings import LogLevel


def test_formatter_emits_valid_json() -> None:
    record = logging.LogRecord(
        "archguard.test", logging.INFO, "test.py", 1, "Event %s", ("ok",), None
    )
    result = json.loads(JsonFormatter().format(record))
    assert result["message"] == "Event ok"
    assert result["level"] == "INFO"
    assert result["timestamp"].endswith("+00:00")


def test_logging_configuration_is_idempotent(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(LogLevel.INFO)
    configure_logging(LogLevel.INFO)
    logging.getLogger("archguard.test").info("Single event")
    lines = capsys.readouterr().out.splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["message"] == "Single event"
