from enum import StrEnum


class GraphProjection(StrEnum):
    COMPONENT = "component"
    FILE = "file"
    PACKAGE = "package"
    TARGET_LAYER = "layer"
    TARGET_MODULE = "module"


class NeighbourhoodDirection(StrEnum):
    IN = "IN"
    OUT = "OUT"
    BOTH = "BOTH"
