from collections import defaultdict

from pydantic import JsonValue

from archguard.core.identifiers import (
    ModuleId,
    NodeId,
    PackageId,
    SourceFileId,
    SymbolId,
    stable_edge_id,
    stable_node_id,
)
from archguard.core.locations import SourceLocation
from archguard.core.model.entities import Module, Package, Project, SourceFile, Symbol
from archguard.core.model.enums import EdgeKind, Language, NodeKind
from archguard.core.model.types import JsonObject
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ExtractionDiagnosticCode, ReferenceKind, ResolutionStatus
from archguard.extraction.errors import IAMValidationError
from archguard.extraction.identity import canonical_identity, declaration_key, entity_id, project_id
from archguard.extraction.models import ExtractedFileFacts, ExtractionDiagnostic
from archguard.extraction.resolution.models import ResolutionResult
from archguard.iam.edges import ArchitectureEdge
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode
from archguard.iam_building.validation import validate_built_iam
from archguard.parsing.models import ParseRepositoryResult
from archguard.repository.models import RepositorySnapshot

BUILDER_VERSION = "1.0.0"
RELATIONS = {
    ReferenceKind.IMPORT: EdgeKind.IMPORTS,
    ReferenceKind.EXTENDS: EdgeKind.INHERITS,
    ReferenceKind.IMPLEMENTS: EdgeKind.IMPLEMENTS,
    ReferenceKind.CALL: EdgeKind.CALLS,
    ReferenceKind.CREATE: EdgeKind.CREATES,
    ReferenceKind.TYPE_USE: EdgeKind.USES,
}


class IAMBuilder:
    version = BUILDER_VERSION

    def build(
        self,
        snapshot: RepositorySnapshot,
        files: tuple[ExtractedFileFacts, ...],
        resolutions: tuple[ResolutionResult, ...],
        config: ExtractionConfig,
        parsing: ParseRepositoryResult,
        resolver_version: str,
    ) -> tuple[ArchitectureModel, tuple[ExtractionDiagnostic, ...]]:
        self._validate_input(snapshot, files, resolutions, parsing)
        namespace = (
            str(snapshot.repository_id) if snapshot.repository_id else config.repository_namespace
        )
        project = Project(id=project_id(namespace), name=config.project_name)
        root_id = stable_node_id(project.id, "project")
        nodes = [
            ArchitectureNode(
                id=root_id, kind=NodeKind.PROJECT, name=project.name, qualified_name="project"
            )
        ]
        modules: dict[str, Module] = {}
        packages: dict[str, Package] = {}
        source_files = []
        symbols = []
        file_nodes: dict[str, NodeId] = {}
        symbol_nodes: dict[str, NodeId] = {}
        symbol_ids = {
            declaration.key: SymbolId(entity_id(project.id, "symbol", declaration.key))
            for file in files
            for declaration in file.declarations
        }
        for file in files:
            path = file.source_file.relative_path
            java = file.language == Language.JAVA
            module_key = "java" if java else "es:" + path
            if module_key not in modules:
                module = Module(
                    id=ModuleId(entity_id(project.id, "module", module_key)),
                    project_id=project.id,
                    name=module_key,
                    attributes={"semantics": "java_source_group" if java else "es_file_module"},
                )
                modules[module_key] = module
                nodes.append(
                    ArchitectureNode(
                        id=stable_node_id(project.id, "module:" + module_key),
                        kind=NodeKind.MODULE,
                        name=module.name,
                        qualified_name=module_key,
                        module=module.id,
                        attributes={"parent_node_id": str(root_id), **module.attributes},
                    )
                )
            module = modules[module_key]
            parent_id = stable_node_id(project.id, "module:" + module_key)
            package_id = None
            if java:
                qualified = file.package_name or ""
                segments = qualified.split(".") if qualified else []
                prefixes = [".".join(segments[:i]) for i in range(1, len(segments) + 1)] or [""]
                for prefix in prefixes:
                    package_key = "java:" + prefix
                    package_node_id = stable_node_id(project.id, "package:" + package_key)
                    if package_key not in packages:
                        package = Package(
                            id=PackageId(entity_id(project.id, "package", package_key)),
                            module_id=module.id,
                            name=prefix.rsplit(".", 1)[-1] or "<default>",
                            qualified_name=prefix,
                        )
                        packages[package_key] = package
                        nodes.append(
                            ArchitectureNode(
                                id=package_node_id,
                                kind=NodeKind.PACKAGE,
                                name=package.name,
                                qualified_name="java:" + (prefix or "<default>"),
                                language=Language.JAVA,
                                module=module.id,
                                package=package.id,
                                attributes={"parent_node_id": str(parent_id)},
                            )
                        )
                    package_id = packages[package_key].id
                    parent_id = package_node_id
            file_identity = canonical_identity("file-v1", path, file.language.value)
            file_id = SourceFileId(entity_id(project.id, "file", file_identity))
            file_node_id = stable_node_id(project.id, file_identity)
            file_nodes[path] = file_node_id
            file_attributes: JsonObject = {
                "sha256": file.source_file.sha256,
                "source_had_syntax_errors": file.source_had_syntax_errors,
                "parser_dialect": file.parser.language.value,
            }
            source_files.append(
                SourceFile(
                    id=file_id,
                    module_id=module.id,
                    package_id=package_id,
                    file_path=path,
                    language=file.language,
                    attributes=file_attributes,
                )
            )
            nodes.append(
                ArchitectureNode(
                    id=file_node_id,
                    kind=NodeKind.FILE,
                    name=path.rsplit("/", 1)[-1],
                    qualified_name=path,
                    language=file.language,
                    module=module.id,
                    package=package_id,
                    file_id=file_id,
                    source_location=SourceLocation(file_path=path, start_line=1),
                    attributes={"parent_node_id": str(parent_id), **file_attributes},
                )
            )
            for declaration in file.declarations:
                symbol_id = symbol_ids[declaration.key]
                node_id = stable_node_id(project.id, declaration.key)
                symbol_nodes[declaration.key] = node_id
                container = declaration.container_key
                attributes: JsonObject = {
                    "container_symbol_id": str(symbol_ids[container]) if container else None,
                    "visibility": declaration.visibility.value,
                    "modifiers": list(declaration.modifiers),
                    "annotations": list(declaration.annotations),
                    "type_parameters": list(declaration.type_parameters),
                    "parameters": [item.model_dump(mode="json") for item in declaration.parameters],
                    "type_name": declaration.type_name,
                    "is_exported": declaration.is_exported,
                    "is_default_export": declaration.is_default_export,
                }
                symbols.append(
                    Symbol(
                        id=symbol_id,
                        file_id=file_id,
                        kind=declaration.kind,
                        name=declaration.name,
                        qualified_name=declaration.qualified_name,
                        signature=declaration.signature,
                        source_location=declaration.source_location,
                        attributes=attributes,
                    )
                )
                nodes.append(
                    ArchitectureNode(
                        id=node_id,
                        kind=declaration.kind,
                        name=declaration.name,
                        qualified_name=declaration.qualified_name,
                        language=file.language,
                        module=module.id,
                        package=package_id,
                        file_id=file_id,
                        symbol_id=symbol_id,
                        source_location=declaration.source_location,
                        attributes={
                            "parent_node_id": str(
                                stable_node_id(project.id, container) if container else file_node_id
                            )
                        },
                    )
                )
        grouped: dict[tuple[NodeId, NodeId, EdgeKind], list[ResolutionResult]] = defaultdict(list)
        external_nodes: dict[str, NodeId] = {}
        extractor_ids = {
            file.source_file.relative_path: file.extractor.extractor_id for file in files
        }
        for result in resolutions:
            reference = result.reference
            target_id: NodeId | None = None
            if result.status == ResolutionStatus.RESOLVED:
                if reference.reference_kind == ReferenceKind.IMPORT:
                    target_id = file_nodes[result.target_file or ""]
                elif result.target_key:
                    target_id = symbol_nodes[result.target_key]
            elif (
                result.status == ResolutionStatus.EXTERNAL
                and reference.reference_kind == ReferenceKind.IMPORT
            ):
                external = result.external
                assert external is not None
                if external.identity not in external_nodes:
                    external_id = stable_node_id(project.id, external.identity)
                    external_nodes[external.identity] = external_id
                    nodes.append(
                        ArchitectureNode(
                            id=external_id,
                            kind=NodeKind.EXTERNAL_DEPENDENCY,
                            name=external.namespace,
                            qualified_name=external.identity,
                            language=Language.JAVA
                            if external.ecosystem == "java_namespace"
                            else Language.UNKNOWN,
                            attributes={
                                "parent_node_id": str(root_id),
                                "ecosystem": external.ecosystem,
                                "namespace": external.namespace,
                            },
                        )
                    )
                target_id = external_nodes[external.identity]
            if target_id is None:
                continue
            source_id = (
                file_nodes[result.source_file]
                if reference.reference_kind == ReferenceKind.IMPORT or reference.source_key is None
                else symbol_nodes[reference.source_key]
            )
            grouped[(source_id, target_id, RELATIONS[reference.reference_kind])].append(result)
        edges = []
        diagnostics = []
        for (source_id, target_id, kind), results in sorted(
            grouped.items(), key=lambda item: tuple(str(value) for value in item[0])
        ):
            ordered = sorted(
                results,
                key=lambda item: (
                    item.source_file,
                    item.reference.source_location.start_line,
                    item.reference.source_location.start_column,
                    item.reference.key,
                ),
            )
            retained = ordered[: config.max_provenance_per_edge]
            provenance: list[JsonValue] = [
                {
                    "source_location": item.reference.source_location.model_dump(mode="json"),
                    "reference_kind": item.reference.reference_kind.value,
                    "resolution_status": item.status.value,
                    "resolution_method": item.method.value,
                    "extractor_id": extractor_ids[item.source_file],
                }
                for item in retained
            ]
            truncated = len(ordered) - len(retained)
            if truncated:
                diagnostics.append(
                    ExtractionDiagnostic(
                        code=ExtractionDiagnosticCode.PROVENANCE_LIMIT,
                        message="edge provenance exceeded its configured limit",
                        source_location=retained[0].reference.source_location,
                    )
                )
            edges.append(
                ArchitectureEdge(
                    id=stable_edge_id(
                        project.id,
                        canonical_identity("edge-v1", str(source_id), str(target_id), kind.value),
                    ),
                    source_id=source_id,
                    target_id=target_id,
                    kind=kind,
                    source_location=retained[0].reference.source_location,
                    attributes={
                        "occurrences": len(ordered),
                        "provenance_truncated": truncated,
                        "provenance": provenance,
                    },
                )
            )
        metadata: JsonObject = {
            "snapshot_id": str(snapshot.snapshot_id),
            "snapshot_fingerprint": snapshot.fingerprint,
            "repository_namespace": namespace,
            "builder_version": self.version,
            "resolver_version": resolver_version,
            "extraction_config": config.model_dump(mode="json"),
            "parser_config": parsing.config.model_dump(mode="json"),
            "parser_versions": [item.model_dump(mode="json") for item in parsing.parser_versions],
            "extractor_versions": [
                item.model_dump(mode="json")
                for item in sorted(
                    {file.extractor for file in files}, key=lambda item: item.extractor_id
                )
            ],
            "source_coordinates": "one-based UTF-8 byte columns; inclusive end",
            "containment_convention": "parent_node_id / container_symbol_id v1",
        }
        model = ArchitectureModel(
            project=project,
            modules=tuple(sorted(modules.values(), key=lambda item: str(item.id))),
            packages=tuple(sorted(packages.values(), key=lambda item: str(item.id))),
            source_files=tuple(sorted(source_files, key=lambda item: str(item.id))),
            symbols=tuple(sorted(symbols, key=lambda item: str(item.id))),
            nodes=tuple(sorted(nodes, key=lambda item: str(item.id))),
            edges=tuple(sorted(edges, key=lambda item: str(item.id))),
            metadata=metadata,
        )
        validate_built_iam(model)
        return model, tuple(diagnostics)

    @staticmethod
    def _validate_input(
        snapshot: RepositorySnapshot,
        files: tuple[ExtractedFileFacts, ...],
        resolutions: tuple[ResolutionResult, ...],
        parsing: ParseRepositoryResult,
    ) -> None:
        inventory = {file.relative_path: file for file in snapshot.files}
        extracted = {file.source_file.relative_path: file for file in files}
        if len(extracted) != len(files) or parsing.snapshot_id != snapshot.snapshot_id:
            raise IAMValidationError("build input contains duplicate files or mismatched snapshot")
        declarations = {
            declaration.key: (file, declaration)
            for file in files
            for declaration in file.declarations
        }
        references = {
            (file.source_file.relative_path, ref.key): ref
            for file in files
            for ref in file.references
        }
        if len(declarations) != sum(len(file.declarations) for file in files):
            raise IAMValidationError("duplicate declaration identity")
        for file in files:
            if (
                file.snapshot_id != snapshot.snapshot_id
                or inventory.get(file.source_file.relative_path) != file.source_file
            ):
                raise IAMValidationError("facts do not belong to snapshot inventory")
            for declaration in file.declarations:
                if declaration.key != declaration_key(
                    file.source_file.relative_path,
                    file.language,
                    declaration.kind,
                    declaration.qualified_name,
                    declaration.signature,
                ):
                    raise IAMValidationError("declaration identity is not canonical")
        if len(resolutions) != len(references) or len(
            {(item.source_file, item.reference.key) for item in resolutions}
        ) != len(resolutions):
            raise IAMValidationError("resolutions must cover every reference exactly once")
        for result in resolutions:
            if references.get((result.source_file, result.reference.key)) != result.reference:
                raise IAMValidationError("resolution reference does not match extraction facts")
            if result.status == ResolutionStatus.RESOLVED:
                ref = result.reference
                if ref.is_dynamic or ref.unknown_receiver or ref.blocked_by_local_binding:
                    raise IAMValidationError("uncertain binding cannot be resolved")
                if result.target_file not in extracted:
                    raise IAMValidationError("resolved target file is absent")
                if (extracted[result.source_file].language == Language.JAVA) != (
                    extracted[result.target_file].language == Language.JAVA
                ):
                    raise IAMValidationError(
                        "Java and ES targets cannot be linked by syntax resolution"
                    )
                if result.target_key is not None:
                    target = declarations.get(result.target_key)
                    if target is None or target[0].source_file.relative_path != result.target_file:
                        raise IAMValidationError(
                            "resolved declaration target is absent or mismatched"
                        )
                    if (
                        ref.reference_kind == ReferenceKind.CREATE
                        and target[1].kind != NodeKind.CLASS
                    ):
                        raise IAMValidationError(
                            "creation target must be an explicitly resolved class"
                        )
                elif result.reference.reference_kind != ReferenceKind.IMPORT:
                    raise IAMValidationError(
                        "resolved symbol relation requires a declaration target"
                    )
