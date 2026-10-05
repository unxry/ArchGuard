import ast
from pathlib import Path


def test_domain_dependency_direction() -> None:
    root = Path(__file__).parents[2] / "src" / "archguard"
    allowed = {
        "core": ("archguard.core",),
        "iam": ("archguard.core", "archguard.iam"),
        "architecture": ("archguard.core", "archguard.iam", "archguard.architecture"),
        "application": (
            "archguard.core",
            "archguard.iam",
            "archguard.application",
            "archguard.repository",
            "archguard.parsing",
            "archguard.extraction",
            "archguard.iam_building",
            "archguard.architecture",
        ),
        "repository": ("archguard.core", "archguard.repository"),
        "parsing": ("archguard.core", "archguard.repository", "archguard.parsing"),
        "extraction": (
            "archguard.core",
            "archguard.repository",
            "archguard.parsing",
            "archguard.extraction",
        ),
        "iam_building": (
            "archguard.core",
            "archguard.repository",
            "archguard.parsing",
            "archguard.extraction",
            "archguard.iam",
            "archguard.iam_building",
        ),
        "experiments": ("archguard.core", "archguard.experiments"),
    }
    forbidden = {
        "fastapi",
        "sqlalchemy",
        "alembic",
        "psycopg",
        "openai",
        "pydantic_settings",
        "subprocess",
        "zipfile",
        "pathspec",
        "os",
        "pathlib",
        "tempfile",
        "shutil",
        "socket",
    }
    for boundary, prefixes in allowed.items():
        for path in (root / boundary).rglob("*.py"):
            for node in ast.walk(ast.parse(path.read_text())):
                imports: list[str] = []
                if isinstance(node, ast.Import):
                    imports = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    assert node.level == 0, f"Use explicit absolute imports: {path}"
                    imports = [node.module or ""]
                    if node.module == "archguard":
                        imports.extend(
                            f"archguard.{alias.name}"
                            for alias in node.names
                            if alias.name != "__version__"
                        )
                for imported in imports:
                    assert imported.split(".")[0] not in forbidden, (path, imported)
                    native_extractor = boundary == "extraction" and (
                        path.name in {"common.py", "collector.py"}
                        or path.parent.name in {"java", "ecmascript"}
                    )
                    if boundary != "parsing" and not native_extractor:
                        assert not imported.startswith("tree_sitter"), (path, imported)
                    if boundary != "architecture" or "graph" not in path.parts:
                        assert not imported.startswith("networkx"), (path, imported)
                    if imported.startswith("archguard."):
                        assert any(
                            imported == prefix or imported.startswith(prefix + ".")
                            for prefix in prefixes
                        ), (path, imported)
