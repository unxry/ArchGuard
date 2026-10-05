import json
from pathlib import Path

from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig
from archguard.architecture.intelligence.models import AIAnalysisResult


class HybridConfigurationError(ValueError):
    code = "INVALID_HYBRID_ARTIFACT"


def _unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
    if len({name for name, _ in pairs}) != len(pairs):
        raise ValueError("duplicate artifact properties")
    return dict(pairs)


def _source_free(value: object) -> None:
    pending = [value]
    forbidden = {
        "source_fragments",
        "text",
        "untrusted_context",
        "system_instructions",
        "raw_prompt",
        "raw_response",
        "messages",
        "api_key",
        "authorization",
    }
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            if any(str(key).casefold() in forbidden for key in item):
                raise ValueError("artifact contains raw source or provider payload")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)


def _read(path: Path, limit: int) -> object:
    try:
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("artifact exceeds byte budget")
        result = json.loads(data, object_pairs_hook=_unique)
        _source_free(result)
        return result
    except (OSError, ValueError, RecursionError):
        raise HybridConfigurationError("Hybrid artifact could not be read or validated") from None


def load_hybrid_configuration(path: Path) -> HybridAnalysisConfig:
    try:
        return HybridAnalysisConfig.model_validate(_read(path, 131072))
    except (ValueError, RecursionError):
        raise HybridConfigurationError(
            "Hybrid configuration could not be read or validated"
        ) from None


def load_hybrid_ai_result(path: Path) -> AIAnalysisResult:
    try:
        return AIAnalysisResult.model_validate(_read(path, 8388608))
    except (ValueError, RecursionError):
        raise HybridConfigurationError("Saved AI result could not be read or validated") from None
