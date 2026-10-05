import json
from pathlib import Path

from pydantic import ValidationError

from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig


class DiscoveryConfigurationError(Exception):
    code = "INVALID_DISCOVERY_CONFIGURATION"


def load_discovery_configuration(path: Path) -> ArchitectureDiscoveryConfig:
    try:
        with path.open("rb") as stream:
            data = stream.read(131_073)
        if len(data) > 131_072:
            raise DiscoveryConfigurationError("discovery configuration exceeds byte budget")
        return ArchitectureDiscoveryConfig.model_validate(json.loads(data.decode("utf-8")))
    except (OSError, UnicodeError, ValueError, ValidationError, RecursionError):
        raise DiscoveryConfigurationError(
            "discovery configuration could not be read or validated"
        ) from None
