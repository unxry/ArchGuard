from importlib.metadata import version
from pathlib import Path
from uuid import UUID

import pytest
from tree_sitter import LANGUAGE_VERSION, MIN_COMPATIBLE_LANGUAGE_VERSION

from archguard.core.identifiers import SnapshotId
from archguard.infrastructure.repository.classification import classify
from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import ParserDiagnosticCode, ParseStatus
from archguard.parsing.errors import (
    IneligibleSourceError,
    ParserExecutionError,
    ParserResourceLimitError,
    SourceDecodingError,
)
from archguard.parsing.models import FileParseMetadata, ParsedSourceFile
from archguard.parsing.tree_sitter_adapters import (
    JavaParser,
    JavaScriptParser,
    TSXParser,
    TypeScriptParser,
)
from archguard.repository.enums import HashStatus
from archguard.repository.models import RepositoryFile

FIXTURES = Path(__file__).parents[1] / "fixtures" / "parsing"
SNAPSHOT_ID = SnapshotId(UUID("00000000-0000-0000-0000-000000000001"))
ADAPTERS = [
    (JavaParser, "java", ".java"),
    (TypeScriptParser, "typescript", ".ts"),
    (JavaScriptParser, "javascript", ".js"),
    (TSXParser, "tsx", ".tsx"),
]


def descriptor(path: str, source: bytes) -> RepositoryFile:
    result = classify(path, source[:4096])
    return RepositoryFile(
        relative_path=path,
        extension=result.extension,
        size_bytes=len(source),
        language=result.language,
        kind=result.kind,
        is_binary=result.binary,
        is_generated=result.generated,
        analysis_eligible=not (result.binary or result.generated),
        hash_status=HashStatus.BINARY if result.binary else HashStatus.BUDGET_LIMIT,
    )


@pytest.mark.parametrize(("adapter_type", "directory", "extension"), ADAPTERS)
def test_valid_fixtures_build_real_trees(adapter_type, directory: str, extension: str) -> None:
    source = (FIXTURES / directory / f"valid_{directory}{extension}").read_bytes()
    file = descriptor(f"valid{extension}", source)
    adapter = adapter_type()
    parsed = adapter.parse(SNAPSHOT_ID, file, source, ParserConfig())
    assert parsed.root.type == "program"
    assert not parsed.root.has_error and not parsed.metadata.has_syntax_errors
    assert parsed.metadata.source_file == file
    assert parsed.metadata.status == ParseStatus.PARSED
    assert parsed.metadata.diagnostics == ()
    assert parsed.root.text == source
    runtime = parsed.metadata.parser
    assert runtime is not None
    assert runtime.runtime_version == version("tree-sitter")
    assert runtime.grammar_version == version(runtime.grammar_package)
    assert MIN_COMPATIBLE_LANGUAGE_VERSION <= runtime.grammar_abi_version <= LANGUAGE_VERSION
    assert (
        FileParseMetadata.model_validate_json(parsed.metadata.model_dump_json()) == parsed.metadata
    )
    assert source.decode() not in parsed.metadata.model_dump_json()


@pytest.mark.parametrize(("adapter_type", "directory", "extension"), ADAPTERS)
def test_invalid_fixtures_produce_tree_and_visible_diagnostics(
    adapter_type, directory: str, extension: str
) -> None:
    source = (FIXTURES / directory / f"invalid_{directory}{extension}").read_bytes()
    parsed = adapter_type().parse(
        SNAPSHOT_ID, descriptor(f"invalid{extension}", source), source, ParserConfig()
    )
    assert parsed.root.has_error
    assert parsed.metadata.status == ParseStatus.PARSED
    assert parsed.metadata.syntax_error_nodes + parsed.metadata.missing_nodes > 0
    assert parsed.metadata.diagnostics
    for diagnostic in parsed.metadata.diagnostics:
        assert diagnostic.line is not None and diagnostic.line >= 1
        assert diagnostic.column is not None and diagnostic.column >= 1
        assert diagnostic.start_byte is not None
        assert diagnostic.end_byte is not None
        assert 0 <= diagnostic.start_byte <= diagnostic.end_byte <= len(source)


@pytest.mark.parametrize(("adapter_type", "directory", "extension"), ADAPTERS)
@pytest.mark.parametrize("source", [b"", b"// comment only\n/* another comment */\n"])
def test_empty_and_comments_only_sources(adapter_type, directory, extension, source: bytes) -> None:
    parsed = adapter_type().parse(
        SNAPSHOT_ID, descriptor(f"empty{extension}", source), source, ParserConfig()
    )
    assert not parsed.root.has_error
    assert parsed.metadata.diagnostics == ()


@pytest.mark.parametrize(
    ("adapter_type", "directory", "extension", "expected"),
    [
        (
            JavaParser,
            "java",
            ".java",
            {
                "package_declaration",
                "import_declaration",
                "class_declaration",
                "interface_declaration",
                "enum_declaration",
                "annotation_type_declaration",
                "marker_annotation",
                "constructor_declaration",
                "method_declaration",
                "field_declaration",
                "type_parameters",
            },
        ),
        (
            TypeScriptParser,
            "typescript",
            ".ts",
            {
                "interface_declaration",
                "type_alias_declaration",
                "class_declaration",
                "function_declaration",
                "method_definition",
                "enum_declaration",
                "import_statement",
                "export_statement",
                "arrow_function",
                "type_parameters",
                "await_expression",
            },
        ),
        (
            JavaScriptParser,
            "javascript",
            ".js",
            {
                "import_statement",
                "export_statement",
                "function_declaration",
                "class_declaration",
                "arrow_function",
                "await_expression",
            },
        ),
        (
            TSXParser,
            "tsx",
            ".tsx",
            {"interface_declaration", "jsx_element", "jsx_self_closing_element"},
        ),
    ],
)
def test_language_constructs_are_present_in_syntax_tree(
    adapter_type, directory, extension, expected: set[str]
) -> None:
    source = (FIXTURES / directory / f"valid_{directory}{extension}").read_bytes()
    parsed = adapter_type().parse(
        SNAPSHOT_ID, descriptor(f"valid{extension}", source), source, ParserConfig()
    )
    pending = [parsed.root]
    types = set()
    while pending:
        node = pending.pop()
        types.add(node.type)
        pending.extend(node.children)
    assert expected <= types


def test_missing_token_has_zero_width_diagnostic() -> None:
    source = b"class App { int value = 1 }"
    parsed = JavaParser().parse(SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig())
    assert parsed.metadata.missing_nodes > 0
    diagnostic = next(
        item
        for item in parsed.metadata.diagnostics
        if item.code == ParserDiagnosticCode.MISSING_NODE
    )
    assert diagnostic.start_byte == diagnostic.end_byte
    assert diagnostic.line == 1


def test_strict_mode_marks_invalid_and_keeps_tree() -> None:
    source = b"class App { int value = 1 }"
    parsed = JavaParser().parse(
        SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig(strict_syntax_errors=True)
    )
    assert parsed.metadata.status == ParseStatus.INVALID
    assert parsed.root.has_error


def test_disabled_details_still_count_errors_and_emit_summary() -> None:
    source = b"class App { int value = 1 }"
    parsed = JavaParser().parse(
        SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig(collect_error_nodes=False)
    )
    assert parsed.metadata.missing_nodes > 0
    assert len(parsed.metadata.diagnostics) == 1
    assert parsed.metadata.diagnostics[0].line is None


def test_diagnostic_limit_preserves_complete_counts() -> None:
    source = b"class App { int a = 1 int b = 2 int c = 3 }"
    parsed = JavaParser().parse(
        SNAPSHOT_ID,
        descriptor("App.java", source),
        source,
        ParserConfig(max_diagnostics_per_file=1),
    )
    assert parsed.metadata.syntax_error_nodes + parsed.metadata.missing_nodes > 1
    assert len(parsed.metadata.diagnostics) == 2
    assert parsed.metadata.diagnostics[-1].code == ParserDiagnosticCode.DIAGNOSTICS_TRUNCATED


@pytest.mark.parametrize("path", ["generated/App.java", "App.generated.java", "App.ts", "App.tsx"])
def test_adapter_rejects_ineligible_or_wrong_dialect(path: str) -> None:
    source = b"class App {}"
    with pytest.raises(IneligibleSourceError):
        JavaParser().parse(SNAPSHOT_ID, descriptor(path, source), source, ParserConfig())


@pytest.mark.parametrize("flag", ["is_large", "is_binary", "is_generated"])
def test_adapter_guards_even_bypassed_validation(flag: str) -> None:
    source = b"class App {}"
    file = descriptor("App.java", source).model_copy(update={flag: True})
    with pytest.raises(IneligibleSourceError):
        JavaParser().parse(SNAPSHOT_ID, file, source, ParserConfig())


def test_adapter_size_guard_metadata_mismatch_disabled_and_binary_payload() -> None:
    source = b"class App {}"
    file = descriptor("App.java", source)
    with pytest.raises(ParserResourceLimitError):
        JavaParser().parse(SNAPSHOT_ID, file, source, ParserConfig(max_source_file_bytes=4))
    with pytest.raises(IneligibleSourceError):
        JavaParser().parse(SNAPSHOT_ID, file, b"", ParserConfig())
    with pytest.raises(IneligibleSourceError):
        JavaParser().parse(SNAPSHOT_ID, file, source, ParserConfig(enabled_languages=()))
    binary = b"class App {}\x00"
    with pytest.raises(IneligibleSourceError):
        JavaParser().parse(SNAPSHOT_ID, descriptor("App.java", binary), binary, ParserConfig())


def test_invalid_utf8_is_typed_and_byte_position_is_exact() -> None:
    source = b"// unicode: \xc3\xa9\nclass \xff {}"
    with pytest.raises(SourceDecodingError) as captured:
        JavaParser().parse(SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig())
    error = captured.value
    assert (error.line, error.column) == (2, 7)
    assert source[error.byte_offset] == 255
    assert isinstance(error.__cause__, UnicodeDecodeError)
    assert "class" not in str(error)


def test_unicode_and_bom_remain_original_bytes() -> None:
    source = '\ufeffclass Café { String value = "Привет 🌍"; }'.encode()
    parsed = JavaParser().parse(
        SNAPSHOT_ID, descriptor("Café.java", source), source, ParserConfig()
    )
    assert not parsed.root.has_error
    assert parsed.root.start_byte == 3
    assert parsed.root.text == source[parsed.root.start_byte : parsed.root.end_byte]


def test_jsx_uses_javascript_grammar() -> None:
    source = b"export const View = () => <main/>;"
    parsed = JavaScriptParser().parse(
        SNAPSHOT_ID, descriptor("View.jsx", source), source, ParserConfig()
    )
    assert not parsed.root.has_error


def test_tree_sitter_runtime_failure_is_typed(monkeypatch: pytest.MonkeyPatch) -> None:
    def failing_parser(grammar):
        raise RuntimeError("synthetic secret source contents")

    monkeypatch.setattr("archguard.parsing.tree_sitter_adapters.Parser", failing_parser)
    source = b"class App {}"
    with pytest.raises(ParserExecutionError) as captured:
        JavaParser().parse(SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig())
    assert isinstance(captured.value.__cause__, RuntimeError)
    assert "secret" not in str(captured.value)


def test_tree_handle_rejects_nonparsed_metadata() -> None:
    source = b"class App {}"
    parsed = JavaParser().parse(SNAPSHOT_ID, descriptor("App.java", source), source, ParserConfig())
    with pytest.raises(ValueError, match="parsed outcome"):
        ParsedSourceFile(
            parsed.metadata.model_copy(update={"status": ParseStatus.FAILED}), parsed.tree
        )
