from typing import Annotated

from pydantic import Field

from archguard.core.model.base import DomainModel
from archguard.core.model.types import NonEmptyString

DEFAULT_EXCLUSIONS = (
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "coverage",
    ".next",
    "out",
    ".gradle",
    ".idea",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    ".archguard",
)
PositiveInt = Annotated[int, Field(strict=True, gt=0)]


class RepositoryScanPolicy(DomainModel):
    excluded_directories: tuple[NonEmptyString, ...] = DEFAULT_EXCLUSIONS
    extra_exclusions: tuple[NonEmptyString, ...] = ()
    respect_gitignore: bool = True
    max_files: PositiveInt = 100_000
    max_entries: PositiveInt = 200_000
    max_source_file_bytes: PositiveInt = 2 * 1024 * 1024
    max_hash_file_bytes: PositiveInt = 8 * 1024 * 1024
    max_total_hash_bytes: PositiveInt = 256 * 1024 * 1024
    max_gitignore_bytes: PositiveInt = 64 * 1024
    max_archive_bytes: PositiveInt = 128 * 1024 * 1024
    max_single_file_bytes: PositiveInt = 64 * 1024 * 1024
    max_total_uncompressed_bytes: PositiveInt = 512 * 1024 * 1024
    git_timeout_seconds: Annotated[float, Field(strict=True, gt=0)] = 60.0
