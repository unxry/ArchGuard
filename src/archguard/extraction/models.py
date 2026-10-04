from typing import Self

from pydantic import model_validator

from archguard.core.identifiers import SnapshotId
from archguard.core.locations import SourceLocation
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language, NodeKind
from archguard.core.model.types import NonEmptyString
from archguard.extraction.enums import (
    ExtractionDiagnosticCode,
    ImportKind,
    ReferenceKind,
    Visibility,
)
from archguard.parsing.enums import DiagnosticSeverity, ParserLanguage
from archguard.parsing.models import ParserRuntimeInfo
from archguard.parsing.registry import parser_language
from archguard.repository.models import NonnegativeInt, RepositoryFile

DECLARATION_KINDS = frozenset(
    {
        NodeKind.CLASS,
        NodeKind.INTERFACE,
        NodeKind.ENUM,
        NodeKind.FUNCTION,
        NodeKind.METHOD,
        NodeKind.CONSTRUCTOR,
        NodeKind.FIELD,
        NodeKind.PROPERTY,
        NodeKind.TYPE_ALIAS,
        NodeKind.MODULE,
    }
)


class ExtractorMetadata(DomainModel):
    extractor_id: NonEmptyString
    extractor_version: NonEmptyString
    dialect: ParserLanguage


class ExtractionDiagnostic(DomainModel):
    code: ExtractionDiagnosticCode
    message: NonEmptyString
    severity: DiagnosticSeverity = DiagnosticSeverity.WARNING
    source_location: SourceLocation | None = None


class ExtractedParameter(DomainModel):
    name: NonEmptyString
    type_name: NonEmptyString | None = None
    optional: bool = False
    is_rest: bool = False


class ExtractedDeclaration(DomainModel):
    key: NonEmptyString
    kind: NodeKind
    name: NonEmptyString
    qualified_name: NonEmptyString
    container_key: NonEmptyString | None = None
    signature: NonEmptyString | None = None
    visibility: Visibility = Visibility.DEFAULT
    modifiers: tuple[NonEmptyString, ...] = ()
    annotations: tuple[NonEmptyString, ...] = ()
    type_parameters: tuple[NonEmptyString, ...] = ()
    parameters: tuple[ExtractedParameter, ...] = ()
    type_name: NonEmptyString | None = None
    is_exported: bool = False
    is_default_export: bool = False
    shadowed_names: tuple[NonEmptyString, ...] = ()
    source_location: SourceLocation

    @model_validator(mode="after")
    def validate_kind(self) -> Self:
        if self.kind not in DECLARATION_KINDS:
            raise ValueError("kind is not a declaration kind")
        return self


class ExtractedImport(DomainModel):
    module_specifier: NonEmptyString
    imported_name: NonEmptyString | None = None
    local_alias: NonEmptyString | None = None
    kind: ImportKind
    is_wildcard: bool = False
    is_static: bool = False
    source_location: SourceLocation


class ExtractedExport(DomainModel):
    exported_name: NonEmptyString
    local_name: NonEmptyString | None = None
    module_specifier: NonEmptyString | None = None
    is_wildcard: bool = False
    source_location: SourceLocation


class SymbolReference(DomainModel):
    key: NonEmptyString
    name: NonEmptyString
    reference_kind: ReferenceKind
    source_key: NonEmptyString | None = None
    qualified_name_hint: NonEmptyString | None = None
    module_specifier: NonEmptyString | None = None
    import_index: NonnegativeInt | None = None
    receiver: NonEmptyString | None = None
    unknown_receiver: bool = False
    argument_count: NonnegativeInt | None = None
    blocked_by_local_binding: bool = False
    is_dynamic: bool = False
    source_location: SourceLocation


class ExtractedFileFacts(DomainModel):
    snapshot_id: SnapshotId
    source_file: RepositoryFile
    language: Language
    package_name: str | None = None
    declarations: tuple[ExtractedDeclaration, ...] = ()
    imports: tuple[ExtractedImport, ...] = ()
    exports: tuple[ExtractedExport, ...] = ()
    references: tuple[SymbolReference, ...] = ()
    shadowed_names: tuple[NonEmptyString, ...] = ()
    diagnostics: tuple[ExtractionDiagnostic, ...] = ()
    source_had_syntax_errors: bool = False
    extractor: ExtractorMetadata
    parser: ParserRuntimeInfo

    @model_validator(mode="after")
    def validate_structure(self) -> Self:
        expected = (
            Language.TYPESCRIPT
            if self.extractor.dialect == ParserLanguage.TSX
            else Language(self.extractor.dialect.value)
        )
        if (
            self.language != expected
            or self.parser.language != self.extractor.dialect
            or parser_language(self.source_file) != self.parser.language
        ):
            raise ValueError("fact language and parser/extractor dialect must agree")
        if (self.language == Language.JAVA) != (self.package_name is not None):
            raise ValueError("Java facts require a package identity; ES files have no Java package")
        declarations = {item.key: item for item in self.declarations}
        if len(declarations) != len(self.declarations):
            raise ValueError("duplicate incompatible declaration identity")
        if len({item.key for item in self.references}) != len(self.references):
            raise ValueError("reference keys must be unique within a file")
        records: tuple[
            ExtractedDeclaration | ExtractedImport | ExtractedExport | SymbolReference, ...
        ] = (*self.declarations, *self.imports, *self.exports, *self.references)
        for item in records:
            if item.source_location.file_path != self.source_file.relative_path:
                raise ValueError("fact location must match repository-relative file identity")
        complete: set[str] = set()
        for declaration in self.declarations:
            chain: set[str] = set()
            key: str | None = declaration.key
            while key is not None and key not in complete:
                if key in chain or key not in declarations:
                    raise ValueError("invalid or cyclic declaration container")
                chain.add(key)
                key = declarations[key].container_key
            complete.update(chain)
        for reference in self.references:
            if reference.source_key is not None and reference.source_key not in declarations:
                raise ValueError("reference source must be a declaration in its file")
            if reference.import_index is not None and reference.import_index >= len(self.imports):
                raise ValueError("reference points to an absent import")
        return self
