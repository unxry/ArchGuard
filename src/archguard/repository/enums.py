from enum import StrEnum


class RepositorySourceType(StrEnum):
    LOCAL = "LOCAL"
    ZIP = "ZIP"
    GIT = "GIT"


class SourceLanguage(StrEnum):
    JAVA = "JAVA"
    TYPESCRIPT = "TYPESCRIPT"
    JAVASCRIPT = "JAVASCRIPT"
    PYTHON = "PYTHON"
    JSON = "JSON"
    YAML = "YAML"
    XML = "XML"
    TOML = "TOML"
    DOCKERFILE = "DOCKERFILE"
    SHELL = "SHELL"
    MARKDOWN = "MARKDOWN"
    UNKNOWN = "UNKNOWN"


TARGET_LANGUAGES = frozenset(
    {SourceLanguage.JAVA, SourceLanguage.TYPESCRIPT, SourceLanguage.JAVASCRIPT}
)


class RepositoryFileKind(StrEnum):
    SOURCE = "SOURCE"
    TEST = "TEST"
    CONFIG = "CONFIG"
    MANIFEST = "MANIFEST"
    LOCKFILE = "LOCKFILE"
    DOCUMENTATION = "DOCUMENTATION"
    GENERATED = "GENERATED"
    BINARY = "BINARY"
    OTHER = "OTHER"


class HashStatus(StrEnum):
    HASHED = "HASHED"
    BINARY = "BINARY"
    SIZE_LIMIT = "SIZE_LIMIT"
    BUDGET_LIMIT = "BUDGET_LIMIT"


class ExclusionReason(StrEnum):
    DEFAULT = "DEFAULT"
    CUSTOM = "CUSTOM"
    GITIGNORE = "GITIGNORE"
    SYMLINK = "SYMLINK"
    SPECIAL_FILE = "SPECIAL_FILE"
