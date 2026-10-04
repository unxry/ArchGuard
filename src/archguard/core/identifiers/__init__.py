from typing import NewType
from uuid import UUID, uuid5

ProjectId = NewType("ProjectId", UUID)
ModuleId = NewType("ModuleId", UUID)
PackageId = NewType("PackageId", UUID)
SourceFileId = NewType("SourceFileId", UUID)
SymbolId = NewType("SymbolId", UUID)
NodeId = NewType("NodeId", UUID)
EdgeId = NewType("EdgeId", UUID)
FindingId = NewType("FindingId", UUID)
AnalysisId = NewType("AnalysisId", UUID)
EvidenceId = NewType("EvidenceId", UUID)
TraceId = NewType("TraceId", UUID)
RepositoryId = NewType("RepositoryId", UUID)
SnapshotId = NewType("SnapshotId", UUID)


def _stable_uuid(project_id: ProjectId, category: str, identity: str) -> UUID:
    if project_id.int == 0 or not identity.strip() or "\x00" in identity:
        raise ValueError("a non-nil project UUID and a nonblank canonical identity are required")
    return uuid5(project_id, f"{category}:{identity}")


def stable_node_id(project_id: ProjectId, identity: str) -> NodeId:
    """The parser owns canonical identities, including overload/signature distinctions."""
    return NodeId(_stable_uuid(project_id, "node", identity))


def stable_edge_id(project_id: ProjectId, identity: str) -> EdgeId:
    """Include relation, endpoints and call-site identity for parallel edges."""
    return EdgeId(_stable_uuid(project_id, "edge", identity))
