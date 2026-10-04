import json
import logging
import sys
from datetime import UTC, datetime

from archguard.infrastructure.settings import LogLevel


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            },
            ensure_ascii=False,
        )


def configure_logging(level: LogLevel) -> None:
    """Configure the application namespace explicitly; settings and credentials are never logged."""
    logger = logging.getLogger("archguard")
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
        handler.close()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level.value)
    logger.propagate = False
