from dataclasses import dataclass
from pathlib import PurePosixPath
from types import MappingProxyType

from archguard.repository.enums import RepositoryFileKind, SourceLanguage

EXTENSION_LANGUAGES = MappingProxyType(
    {
        ".java": SourceLanguage.JAVA,
        ".ts": SourceLanguage.TYPESCRIPT,
        ".tsx": SourceLanguage.TYPESCRIPT,
        ".js": SourceLanguage.JAVASCRIPT,
        ".jsx": SourceLanguage.JAVASCRIPT,
        ".py": SourceLanguage.PYTHON,
        ".json": SourceLanguage.JSON,
        ".yaml": SourceLanguage.YAML,
        ".yml": SourceLanguage.YAML,
        ".xml": SourceLanguage.XML,
        ".toml": SourceLanguage.TOML,
        ".sh": SourceLanguage.SHELL,
        ".md": SourceLanguage.MARKDOWN,
    }
)
MANIFEST_NAMES = frozenset(
    {
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "package.json",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    }
)
LOCKFILE_NAMES = frozenset({"package-lock.json", "yarn.lock", "pnpm-lock.yaml"})
BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".pdf",
        ".zip",
        ".jar",
        ".class",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".bin",
        ".woff",
        ".woff2",
        ".ttf",
        ".mp4",
        ".mp3",
    }
)


@dataclass(frozen=True)
class Classification:
    language: SourceLanguage
    kind: RepositoryFileKind
    extension: str
    generated: bool
    binary: bool


def classify(relative_path: str, prefix: bytes) -> Classification:
    path = PurePosixPath(relative_path)
    extension = path.suffix.lower()
    language = (
        SourceLanguage.DOCKERFILE
        if path.name == "Dockerfile"
        else EXTENSION_LANGUAGES.get(extension, SourceLanguage.UNKNOWN)
    )
    generated = any(
        part in {"dist", "build", "target", "generated"} for part in path.parts[:-1]
    ) or any(
        path.name.endswith(suffix)
        for suffix in (".min.js", ".min.css", ".generated.ts", ".generated.js", ".generated.java")
    )
    binary = extension in BINARY_EXTENSIONS or b"\x00" in prefix
    is_test = (
        any(part.lower() in {"test", "tests", "__tests__"} for part in path.parts[:-1])
        or any(marker in path.name for marker in (".test.", ".spec."))
        or path.name.endswith("Test.java")
    )
    if binary:
        kind = RepositoryFileKind.BINARY
    elif path.name in LOCKFILE_NAMES:
        kind = RepositoryFileKind.LOCKFILE
    elif path.name in MANIFEST_NAMES:
        kind = RepositoryFileKind.MANIFEST
    elif generated:
        kind = RepositoryFileKind.GENERATED
    elif language in {
        SourceLanguage.JAVA,
        SourceLanguage.TYPESCRIPT,
        SourceLanguage.JAVASCRIPT,
        SourceLanguage.PYTHON,
    }:
        kind = RepositoryFileKind.TEST if is_test else RepositoryFileKind.SOURCE
    elif language in {
        SourceLanguage.JSON,
        SourceLanguage.YAML,
        SourceLanguage.XML,
        SourceLanguage.TOML,
        SourceLanguage.SHELL,
    } or path.name in {".gitignore", ".gitattributes", ".env", ".env.example", "Makefile"}:
        kind = RepositoryFileKind.CONFIG
    elif language == SourceLanguage.MARKDOWN or path.name in {"README", "LICENSE", "NOTICE"}:
        kind = RepositoryFileKind.DOCUMENTATION
    else:
        kind = RepositoryFileKind.OTHER
    return Classification(language, kind, extension, generated, binary)
