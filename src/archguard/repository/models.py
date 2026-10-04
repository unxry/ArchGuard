import re
from collections import Counter
from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, TypeAdapter, field_validator, model_validator

from archguard.core.identifiers import RepositoryId, SnapshotId
from archguard.core.model.base import DomainModel
from archguard.core.model.types import JsonObject, NonEmptyString, RepositoryPath
from archguard.repository.enums import (
    TARGET_LANGUAGES,
    ExclusionReason,
    HashStatus,
    RepositoryFileKind,
    RepositorySourceType,
    SourceLanguage,
)
from archguard.repository.fingerprint import inventory_fingerprint, snapshot_id

Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonnegativeInt = Annotated[int, Field(strict=True, ge=0)]


class RepositoryInput(DomainModel):
    source_type: RepositorySourceType
    location: NonEmptyString = Field(repr=False)
    repository_id: RepositoryId | None = None
    ref: NonEmptyString | None = None

    @field_validator("location")
    @classmethod
    def validate_location(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("repository location must not contain NUL")
        return value

    @model_validator(mode="after")
    def validate_ref(self) -> Self:
        if self.ref is not None and (
            self.source_type != RepositorySourceType.GIT
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", self.ref) is None
        ):
            raise ValueError("ref requires a Git source and a safe branch/tag or full commit SHA")
        return self


class RepositoryFile(DomainModel):
    relative_path: RepositoryPath
    extension: str
    size_bytes: NonnegativeInt
    language: SourceLanguage
    kind: RepositoryFileKind
    is_generated: bool = False
    is_binary: bool = False
    is_large: bool = False
    analysis_eligible: bool
    sha256: Sha256 | None = None
    hash_status: HashStatus
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_flags(self) -> Self:
        if (self.hash_status == HashStatus.HASHED) != (self.sha256 is not None):
            raise ValueError("sha256 is required exactly for HASHED files")
        if self.is_binary != (self.kind == RepositoryFileKind.BINARY):
            raise ValueError("binary flag must agree with file kind")
        if self.is_binary != (self.hash_status == HashStatus.BINARY):
            raise ValueError("binary flag must agree with hash status")
        if self.kind == RepositoryFileKind.GENERATED and not self.is_generated:
            raise ValueError("generated file kind requires the generated flag")
        expected = (
            self.language in TARGET_LANGUAGES
            and self.kind in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST}
            and not self.is_generated
            and not self.is_binary
            and not self.is_large
        )
        if self.analysis_eligible != expected:
            raise ValueError("analysis eligibility must agree with file classification and flags")
        return self


class RepositoryExclusion(DomainModel):
    relative_path: RepositoryPath
    reason: ExclusionReason
    is_directory: bool = False


class SourceRoot(DomainModel):
    relative_path: str
    languages: tuple[SourceLanguage, ...]
    is_test: bool = False

    @field_validator("relative_path")
    @classmethod
    def validate_root(cls, value: str) -> str:
        if value != ".":
            TypeAdapter(RepositoryPath).validate_python(value)
        return value


class RepositoryStatistics(DomainModel):
    total_files: NonnegativeInt
    source_files: NonnegativeInt
    test_files: NonnegativeInt
    generated_files: NonnegativeInt
    binary_files: NonnegativeInt
    eligible_files: NonnegativeInt
    total_bytes: NonnegativeInt
    language_counts: dict[SourceLanguage, NonnegativeInt]

    @classmethod
    def from_files(cls, files: tuple[RepositoryFile, ...]) -> Self:
        counts = Counter(file.language for file in files)
        return cls(
            total_files=len(files),
            source_files=sum(file.kind == RepositoryFileKind.SOURCE for file in files),
            test_files=sum(file.kind == RepositoryFileKind.TEST for file in files),
            generated_files=sum(file.is_generated for file in files),
            binary_files=sum(file.is_binary for file in files),
            eligible_files=sum(file.analysis_eligible for file in files),
            total_bytes=sum(file.size_bytes for file in files),
            language_counts={language: counts[language] for language in sorted(counts)},
        )


class RepositorySnapshot(DomainModel):
    repository_schema_version: Literal["1.0"] = "1.0"
    snapshot_id: SnapshotId
    repository_id: RepositoryId | None = None
    source_type: RepositorySourceType
    root: Literal["."] = "."
    revision: Annotated[str, Field(pattern=r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")] | None = None
    created_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    files: tuple[RepositoryFile, ...]
    detected_languages: tuple[SourceLanguage, ...]
    manifests: tuple[RepositoryPath, ...]
    lockfiles: tuple[RepositoryPath, ...]
    source_roots: tuple[SourceRoot, ...] = ()
    exclusions: tuple[RepositoryExclusion, ...] = ()
    statistics: RepositoryStatistics
    supported_for_analysis: bool
    fingerprint: Sha256
    metadata: JsonObject = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_inventory(self) -> Self:
        paths = tuple(file.relative_path for file in self.files)
        if paths != tuple(sorted(set(paths))):
            raise ValueError("inventory paths must be unique and sorted")
        if self.statistics != RepositoryStatistics.from_files(self.files):
            raise ValueError("statistics must agree with inventory")
        if self.detected_languages != tuple(sorted({file.language for file in self.files})):
            raise ValueError("detected languages must agree with inventory")
        for listed, kind in (
            (self.manifests, RepositoryFileKind.MANIFEST),
            (self.lockfiles, RepositoryFileKind.LOCKFILE),
        ):
            if listed != tuple(file.relative_path for file in self.files if file.kind == kind):
                raise ValueError("manifest/lockfile lists must agree with inventory")
        supported = any(
            file.language in TARGET_LANGUAGES and not file.is_binary for file in self.files
        )
        if self.supported_for_analysis != supported:
            raise ValueError("analysis support must agree with target language presence")
        if (self.source_type == RepositorySourceType.GIT) != (self.revision is not None):
            raise ValueError("revision is required exactly for Git snapshots")
        if self.fingerprint != inventory_fingerprint(self.files):
            raise ValueError("fingerprint must agree with inventory")
        if self.snapshot_id != snapshot_id(self.fingerprint):
            raise ValueError("snapshot_id must agree with fingerprint")
        return self
