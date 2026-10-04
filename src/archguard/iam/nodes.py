from pydantic import Field

from archguard.core.identifiers import ModuleId, NodeId, PackageId, SourceFileId, SymbolId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language, NodeKind
from archguard.core.model.types import JsonObject, NonEmptyString


class ArchitectureNode(DomainModel):
    id: NodeId
    kind: NodeKind
    name: NonEmptyString
    qualified_name: NonEmptyString
    language: Language = Language.UNKNOWN
    module: ModuleId | None = None
    package: PackageId | None = None
    file_id: SourceFileId | None = None
    symbol_id: SymbolId | None = None
    layer: NonEmptyString | None = None
    source_location: SourceLocation | None = None
    attributes: JsonObject = Field(default_factory=dict)
