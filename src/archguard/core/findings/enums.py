from enum import StrEnum


class FindingNamespace(StrEnum):
    ARCH = "ARCH"
    SEC = "SEC"


class Severity(StrEnum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DetectorSource(StrEnum):
    STATIC = "STATIC"
    GRAPH = "GRAPH"
    LLM = "LLM"
    HYBRID = "HYBRID"
    SECURITY_STATIC = "SECURITY_STATIC"
    SECURITY_DATAFLOW = "SECURITY_DATAFLOW"
    SECURITY_LLM = "SECURITY_LLM"


ARCHITECTURE_DETECTORS = frozenset(
    {DetectorSource.STATIC, DetectorSource.GRAPH, DetectorSource.LLM, DetectorSource.HYBRID}
)
