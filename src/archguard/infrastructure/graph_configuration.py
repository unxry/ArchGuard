import json
from pathlib import Path

from pydantic import ValidationError

from archguard.architecture.graph.config import GraphAnalysisConfig


class GraphConfigurationError(Exception):
    code = "INVALID_GRAPH_CONFIGURATION"


def load_graph_configuration(path: Path) -> GraphAnalysisConfig:
    try:
        with path.open("rb") as stream:
            data = stream.read(131_073)
        if len(data) > 131_072:
            raise GraphConfigurationError("graph configuration exceeds byte budget")
        return GraphAnalysisConfig.model_validate(json.loads(data.decode("utf-8")))
    except (OSError, UnicodeError, ValueError, ValidationError, RecursionError):
        raise GraphConfigurationError(
            "graph configuration could not be read or validated"
        ) from None
