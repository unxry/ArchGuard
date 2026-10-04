from enum import StrEnum

from archguard.core.identifiers import NodeId, SourceFileId
from archguard.core.model.base import DomainModel
from archguard.core.model.types import RepositoryPath


class ClassificationStatus(StrEnum):
    CLASSIFIED = "CLASSIFIED"
    UNCLASSIFIED = "UNCLASSIFIED"
    AMBIGUOUS = "AMBIGUOUS"


class ConformanceDiagnostic(DomainModel):
    code: str
    message: str
    node_id: NodeId | None = None
    file_path: RepositoryPath | None = None


class NodeClassification(DomainModel):
    node_id: NodeId
    file_id: SourceFileId
    file_path: RepositoryPath
    layer: str | None = None
    module: str | None = None
    layer_candidates: tuple[str, ...] = ()
    module_candidates: tuple[str, ...] = ()

    @property
    def status(self) -> ClassificationStatus:
        if len(self.layer_candidates) > 1 or len(self.module_candidates) > 1:
            return ClassificationStatus.AMBIGUOUS
        return (
            ClassificationStatus.CLASSIFIED
            if self.layer or self.module
            else ClassificationStatus.UNCLASSIFIED
        )


class ArchitectureClassification(DomainModel):
    nodes: tuple[NodeClassification, ...]
    diagnostics: tuple[ConformanceDiagnostic, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics
