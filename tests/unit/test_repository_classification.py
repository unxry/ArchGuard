import pytest

from archguard.infrastructure.repository.classification import classify
from archguard.repository.enums import RepositoryFileKind, SourceLanguage


@pytest.mark.parametrize(
    ("name", "language"),
    [
        ("App.java", SourceLanguage.JAVA),
        ("index.ts", SourceLanguage.TYPESCRIPT),
        ("App.tsx", SourceLanguage.TYPESCRIPT),
        ("index.js", SourceLanguage.JAVASCRIPT),
        ("App.jsx", SourceLanguage.JAVASCRIPT),
        ("config.json", SourceLanguage.JSON),
        ("config.yaml", SourceLanguage.YAML),
        ("config.yml", SourceLanguage.YAML),
        ("config.xml", SourceLanguage.XML),
        ("config.toml", SourceLanguage.TOML),
        ("run.sh", SourceLanguage.SHELL),
        ("README.md", SourceLanguage.MARKDOWN),
        ("Dockerfile", SourceLanguage.DOCKERFILE),
        ("unknown.xyz", SourceLanguage.UNKNOWN),
    ],
)
def test_language_detection(name: str, language: SourceLanguage) -> None:
    assert classify(name, b"").language == language


@pytest.mark.parametrize(
    "name",
    [
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
        "settings.gradle",
        "settings.gradle.kts",
        "package.json",
        "Dockerfile",
        "docker-compose.yml",
        "docker-compose.yaml",
    ],
)
def test_known_manifests(name: str) -> None:
    assert classify("nested/" + name, b"").kind == RepositoryFileKind.MANIFEST


@pytest.mark.parametrize("name", ["package-lock.json", "yarn.lock", "pnpm-lock.yaml"])
def test_lockfiles(name: str) -> None:
    assert classify(name, b"").kind == RepositoryFileKind.LOCKFILE


@pytest.mark.parametrize(
    ("path", "kind"),
    [
        ("src/App.java", RepositoryFileKind.SOURCE),
        ("src/test/java/App.java", RepositoryFileKind.TEST),
        ("src/AppTest.java", RepositoryFileKind.TEST),
        ("src/service.spec.ts", RepositoryFileKind.TEST),
        ("tests/service.ts", RepositoryFileKind.TEST),
        ("dist/bundle.js", RepositoryFileKind.GENERATED),
        ("bundle.min.js", RepositoryFileKind.GENERATED),
        ("generated/Model.java", RepositoryFileKind.GENERATED),
        ("src/contracts.d.ts", RepositoryFileKind.SOURCE),
        ("config.yml", RepositoryFileKind.CONFIG),
        ("README.md", RepositoryFileKind.DOCUMENTATION),
        ("image.png", RepositoryFileKind.BINARY),
        ("unknown", RepositoryFileKind.OTHER),
    ],
)
def test_file_classification(path: str, kind: RepositoryFileKind) -> None:
    assert classify(path, b"").kind == kind


def test_nul_sniff_overrides_source_extension() -> None:
    classification = classify("looks-like-source.ts", b"binary\x00payload")
    assert classification.binary
    assert classification.kind == RepositoryFileKind.BINARY
