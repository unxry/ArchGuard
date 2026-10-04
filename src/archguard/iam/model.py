from typing import Literal, Self

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel
from archguard.core.model.entities import Module, Package, Project, SourceFile, Symbol
from archguard.core.model.enums import Language
from archguard.core.model.types import JsonObject
from archguard.iam.edges import ArchitectureEdge
from archguard.iam.nodes import ArchitectureNode

IAM_SCHEMA_VERSION: Literal["1.0"] = "1.0"


class ArchitectureModel(DomainModel):
    iam_schema_version: Literal["1.0"] = IAM_SCHEMA_VERSION
    project: Project
    modules: tuple[Module, ...] = ()
    packages: tuple[Package, ...] = ()
    source_files: tuple[SourceFile, ...] = ()
    symbols: tuple[Symbol, ...] = ()
    nodes: tuple[ArchitectureNode, ...] = ()
    edges: tuple[ArchitectureEdge, ...] = ()
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        for records in (
            self.modules,
            self.packages,
            self.source_files,
            self.symbols,
            self.nodes,
            self.edges,
        ):
            ids = [record.id for record in records]
            if len(ids) != len(set(ids)):
                raise ValueError("identifiers must be unique within each IAM collection")

        modules = {module.id: module for module in self.modules}
        packages = {package.id: package for package in self.packages}
        files = {file.id: file for file in self.source_files}
        symbols = {symbol.id: symbol for symbol in self.symbols}
        node_ids = {node.id for node in self.nodes}

        if any(module.project_id != self.project.id for module in self.modules):
            raise ValueError("module must belong to the IAM project")
        if any(package.module_id not in modules for package in self.packages):
            raise ValueError("package references an unknown module")
        for file in self.source_files:
            if file.module_id not in modules:
                raise ValueError("source file references an unknown module")
            if file.package_id is not None and (
                file.package_id not in packages
                or packages[file.package_id].module_id != file.module_id
            ):
                raise ValueError("source file package must belong to its module")
        for symbol in self.symbols:
            if symbol.file_id not in files:
                raise ValueError("symbol references an unknown source file")
            if (
                symbol.source_location is not None
                and symbol.source_location.file_path != files[symbol.file_id].file_path
            ):
                raise ValueError("symbol location must match its source file")
        for node in self.nodes:
            if node.module is not None and node.module not in modules:
                raise ValueError("node references an unknown module")
            if node.package is not None and (
                node.package not in packages
                or (node.module is not None and packages[node.package].module_id != node.module)
            ):
                raise ValueError("node package/module references are inconsistent")
            if node.symbol_id is not None and node.symbol_id not in symbols:
                raise ValueError("node references an unknown symbol")
            if node.file_id is not None and node.file_id not in files:
                raise ValueError("node references an unknown source file")
            linked_file_id = node.file_id
            if node.symbol_id is not None:
                symbol_file_id = symbols[node.symbol_id].file_id
                if linked_file_id is not None and linked_file_id != symbol_file_id:
                    raise ValueError("node symbol/file references are inconsistent")
                linked_file_id = symbol_file_id
            if linked_file_id is not None:
                file = files[linked_file_id]
                if (
                    (node.module is not None and node.module != file.module_id)
                    or (node.package is not None and node.package != file.package_id)
                    or (node.language != Language.UNKNOWN and node.language != file.language)
                    or (
                        node.source_location is not None
                        and node.source_location.file_path != file.file_path
                    )
                ):
                    raise ValueError("node references must match its linked source file")
        if any(
            edge.source_id not in node_ids or edge.target_id not in node_ids for edge in self.edges
        ):
            raise ValueError("edge endpoints must exist in the IAM snapshot")
        return self
