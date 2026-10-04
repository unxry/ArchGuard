import hashlib
import stat
from pathlib import PurePosixPath

from archguard.infrastructure.repository.classification import classify
from archguard.infrastructure.repository.exclusions import (
    Exclusions,
    IgnoreScope,
    load_ignore_scope,
)
from archguard.infrastructure.repository.filesystem import Entry, SafeRoot
from archguard.repository.enums import (
    TARGET_LANGUAGES,
    ExclusionReason,
    HashStatus,
    RepositoryFileKind,
    SourceLanguage,
)
from archguard.repository.errors import RepositoryChangedError, RepositoryLimitExceeded
from archguard.repository.fingerprint import inventory_fingerprint, snapshot_id
from archguard.repository.models import (
    RepositoryExclusion,
    RepositoryFile,
    RepositoryInput,
    RepositorySnapshot,
    RepositoryStatistics,
    SourceRoot,
)
from archguard.repository.policy import RepositoryScanPolicy


def collect_entries(
    root: SafeRoot, policy: RepositoryScanPolicy
) -> tuple[list[Entry], tuple[RepositoryExclusion, ...]]:
    exclusions = Exclusions(policy)
    pending: list[tuple[str, tuple[IgnoreScope, ...]]] = [("", ())]
    files: list[Entry] = []
    skipped: list[RepositoryExclusion] = []
    visited = 0
    while pending:
        directory, scopes = pending.pop()
        entries = root.entries(directory, policy.max_entries - visited)
        visited += len(entries)
        if policy.respect_gitignore and any(
            entry.relative_path.rsplit("/", 1)[-1] == ".gitignore"
            and stat.S_ISREG(entry.stat.st_mode)
            for entry in entries
        ):
            scopes += (load_ignore_scope(root, directory, policy),)
        for entry in reversed(entries):
            is_directory = stat.S_ISDIR(entry.stat.st_mode)
            reason = exclusions.reason(entry.relative_path, is_directory, scopes)
            if stat.S_ISLNK(entry.stat.st_mode):
                reason = ExclusionReason.SYMLINK
            elif not is_directory and not stat.S_ISREG(entry.stat.st_mode):
                reason = ExclusionReason.SPECIAL_FILE
            if reason is not None:
                skipped.append(
                    RepositoryExclusion(
                        relative_path=entry.relative_path, reason=reason, is_directory=is_directory
                    )
                )
            elif is_directory:
                pending.append((entry.relative_path, scopes))
            else:
                files.append(entry)
                if len(files) > policy.max_files:
                    raise RepositoryLimitExceeded("repository file count limit exceeded")
    return sorted(files, key=lambda entry: entry.relative_path), tuple(
        sorted(skipped, key=lambda exclusion: exclusion.relative_path)
    )


def describe_file(
    root: SafeRoot, entry: Entry, policy: RepositoryScanPolicy, hash_budget: int
) -> RepositoryFile:
    with root.open_file(entry.relative_path, entry.stat) as stream:
        prefix = stream.read(min(4096, entry.stat.st_size + 1))
        if len(prefix) > entry.stat.st_size:
            raise RepositoryChangedError("repository file grew during discovery")
        classification = classify(entry.relative_path, prefix)
        digest: str | None = None
        if classification.binary:
            hash_status = HashStatus.BINARY
        elif entry.stat.st_size > policy.max_hash_file_bytes:
            hash_status = HashStatus.SIZE_LIMIT
        elif entry.stat.st_size > hash_budget:
            hash_status = HashStatus.BUDGET_LIMIT
        else:
            hasher = hashlib.sha256(prefix)
            read_bytes = len(prefix)
            while chunk := stream.read(min(64 * 1024, entry.stat.st_size - read_bytes + 1)):
                read_bytes += len(chunk)
                if read_bytes > entry.stat.st_size:
                    raise RepositoryChangedError("repository file grew while being hashed")
                hasher.update(chunk)
            if read_bytes != entry.stat.st_size:
                raise RepositoryChangedError("repository file size changed while being hashed")
            digest = hasher.hexdigest()
            hash_status = HashStatus.HASHED
    large = entry.stat.st_size > policy.max_source_file_bytes
    return RepositoryFile(
        relative_path=entry.relative_path,
        extension=classification.extension,
        size_bytes=entry.stat.st_size,
        language=classification.language,
        kind=classification.kind,
        is_generated=classification.generated,
        is_binary=classification.binary,
        is_large=large,
        analysis_eligible=(
            classification.language in TARGET_LANGUAGES
            and classification.kind in {RepositoryFileKind.SOURCE, RepositoryFileKind.TEST}
            and not classification.generated
            and not classification.binary
            and not large
        ),
        sha256=digest,
        hash_status=hash_status,
    )


def source_roots(files: tuple[RepositoryFile, ...]) -> tuple[SourceRoot, ...]:
    grouped: dict[tuple[str, bool], set[SourceLanguage]] = {}
    for file in files:
        if file.language not in TARGET_LANGUAGES or file.is_binary or file.is_generated:
            continue
        parts = PurePosixPath(file.relative_path).parts
        root_path = str(PurePosixPath(file.relative_path).parent)
        for index, part in enumerate(parts[:-1]):
            if part == "src":
                tail = parts[index : index + 3]
                end = index + (
                    3 if tail in {("src", "main", "java"), ("src", "test", "java")} else 1
                )
                root_path = "/".join(parts[:end])
                break
            if part.lower() in {"test", "tests", "__tests__"}:
                root_path = "/".join(parts[: index + 1])
                break
        key = root_path, file.kind == RepositoryFileKind.TEST
        grouped.setdefault(key, set()).add(file.language)
    return tuple(
        SourceRoot(relative_path=path, languages=tuple(sorted(languages)), is_test=is_test)
        for (path, is_test), languages in sorted(grouped.items())
    )


def build_snapshot(
    source: RepositoryInput,
    files: tuple[RepositoryFile, ...],
    exclusions: tuple[RepositoryExclusion, ...],
    revision: str | None,
) -> RepositorySnapshot:
    fingerprint = inventory_fingerprint(files)
    return RepositorySnapshot(
        snapshot_id=snapshot_id(fingerprint),
        repository_id=source.repository_id,
        source_type=source.source_type,
        revision=revision,
        files=files,
        detected_languages=tuple(sorted({file.language for file in files})),
        manifests=tuple(
            file.relative_path for file in files if file.kind == RepositoryFileKind.MANIFEST
        ),
        lockfiles=tuple(
            file.relative_path for file in files if file.kind == RepositoryFileKind.LOCKFILE
        ),
        source_roots=source_roots(files),
        exclusions=exclusions,
        statistics=RepositoryStatistics.from_files(files),
        supported_for_analysis=any(
            file.language in TARGET_LANGUAGES and not file.is_binary for file in files
        ),
        fingerprint=fingerprint,
        metadata={
            "classifier_version": "1.0",
            "fingerprint_algorithm": "inventory-sha256-v1",
            "submodules_present": any(file.relative_path == ".gitmodules" for file in files),
        },
    )
