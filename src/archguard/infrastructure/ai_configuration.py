import json
from pathlib import Path

from archguard.architecture.intelligence.models import AIAnalysisConfig


class AIConfigurationError(Exception):
    code = "INVALID_AI_CONFIGURATION"


def load_ai_configuration(path: Path) -> AIAnalysisConfig:
    try:
        with path.open("rb") as stream:
            data = stream.read(131073)
        if len(data) > 131072:
            raise ValueError("configuration exceeds byte budget")
        return AIAnalysisConfig.model_validate(json.loads(data))
    except (OSError, ValueError, RecursionError):
        raise AIConfigurationError("AI configuration could not be read or validated") from None
