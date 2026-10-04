from pydantic import Field

from archguard.core.identifiers import ModuleId, PackageId, ProjectId, SourceFileId, SymbolId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language, NodeKind
from archguard.core.model.types import JsonObject, NonEmptyString, RepositoryPath


class Project(DomainModel):
    id: ProjectId
    name: NonEmptyString
    description: str | None = None


class Module(DomainModel):
    id: ModuleId
    project_id: ProjectId
    name: NonEmptyString
    attributes: JsonObject = Field(default_factory=dict)


class Package(DomainModel):
    id: PackageId
    module_id: ModuleId
    name: NonEmptyString
    qualified_name: str
    attributes: JsonObject = Field(default_factory=dict)


class SourceFile(DomainModel):
    id: SourceFileId
    module_id: ModuleId
    package_id: PackageId | None = None
    file_path: RepositoryPath
    language: Language
    attributes: JsonObject = Field(default_factory=dict)


class Symbol(DomainModel):
    id: SymbolId
    file_id: SourceFileId
    kind: NodeKind
    name: NonEmptyString
    qualified_name: NonEmptyString
    signature: NonEmptyString | None = None
    source_location: SourceLocation | None = None
    attributes: JsonObject = Field(default_factory=dict)
