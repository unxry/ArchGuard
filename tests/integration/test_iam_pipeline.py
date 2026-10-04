import json
import weakref
from collections.abc import Generator
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.core.model.enums import EdgeKind, Language, NodeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.enums import ReferenceKind, ResolutionMethod, ResolutionStatus
from archguard.extraction.errors import (
    DuplicateExtractorError,
    IAMValidationError,
    UnsupportedExtractorError,
)
from archguard.extraction.factory import create_extractor_registry
from archguard.extraction.models import ExtractedFileFacts
from archguard.extraction.registry import ExtractorRegistry
from archguard.extraction.resolution.index import SymbolIndex
from archguard.extraction.resolution.resolver import SymbolResolver
from archguard.iam.model import ArchitectureModel
from archguard.iam_building.builder import IAMBuilder
from archguard.iam_building.models import IAMBuildResult
from archguard.iam_building.serialization import serialize_iam
from archguard.iam_building.validation import validate_built_iam
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import ParserLanguage
from archguard.parsing.factory import create_parser_registry
from archguard.parsing.models import FileParseMetadata, ParsedSourceFile
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.ports import RepositoryWorkspace

FIXTURES = Path(__file__).parents[1] / "fixtures" / "extraction"


def build(
    path: Path,
    config: ExtractionConfig | None = None,
    strict: bool = False,
    registry: ExtractorRegistry | None = None,
) -> IAMBuildResult:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    ) as repository:
        return BuildIAM(
            ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=strict)),
            registry if registry is not None else create_extractor_registry(),
            config,
        ).execute(repository.snapshot, repository.workspace)


def source(tmp_path: Path, content: str, filename: str = "app.ts") -> IAMBuildResult:
    (tmp_path / filename).write_text(content, encoding="utf-8")
    return build(tmp_path)


@pytest.mark.parametrize(
    "fixture",
    [
        "java/simple",
        "java/packages",
        "java/inheritance",
        "java/nested",
        "java/resolution",
        "java/ambiguous",
        "typescript/simple",
        "typescript/modules",
        "typescript/inheritance",
        "typescript/resolution",
        "typescript/ambiguous",
        "javascript/es_modules",
        "javascript/commonjs",
        "javascript/dynamic_require",
        "tsx",
        "mixed",
    ],
)
def test_real_fixture_build_roundtrips(fixture: str) -> None:
    result = build(FIXTURES / fixture)
    assert result.is_valid
    assert result.statistics.files_extracted == result.statistics.files_seen
    assert result.statistics.declarations_total == len(result.iam.symbols)
    assert result.statistics.references_total == len(result.resolutions)
    assert ArchitectureModel.model_validate_json(serialize_iam(result.iam)) == result.iam
    assert IAMBuildResult.model_validate_json(result.model_dump_json()) == result
    assert all(
        ExtractedFileFacts.model_validate_json(file.model_dump_json()) == file
        for file in result.facts
    )


def test_java_declarations_modifiers_and_hierarchy() -> None:
    result = build(FIXTURES / "java/simple")
    declarations = {
        item.name: item
        for item in result.facts[0].declarations
        if item.kind != NodeKind.CONSTRUCTOR
    }
    assert declarations["submit"].kind == NodeKind.METHOD
    assert declarations["service"].kind == NodeKind.FIELD
    assert declarations["Status"].kind == NodeKind.ENUM
    assert declarations["helper"].visibility.value == "PRIVATE"
    assert declarations["submit"].container_key == declarations["OrderController"].key
    assert declarations["OrderController"].qualified_name == "shop.OrderController"
    assert any(item.kind == NodeKind.CONSTRUCTOR for item in result.facts[0].declarations)
    assert all(item.source_location.start_line >= 1 for item in declarations.values())
    assert {package.qualified_name for package in result.iam.packages} == {"shop"}
    assert result.statistics.references_external == 1
    assert result.statistics.references_unresolved >= 1


def test_nested_generic_java_types_and_package_prefixes() -> None:
    result = build(FIXTURES / "java/nested")
    declarations = {
        item.name: item
        for item in result.facts[0].declarations
        if item.kind != NodeKind.CONSTRUCTOR
    }
    assert declarations["Inner"].qualified_name == "nested.Outer.Inner"
    assert declarations["Inner"].container_key == declarations["Outer"].key
    assert declarations["Outer"].type_parameters == ("T",)
    assert declarations["identity"].type_parameters == ("U",)
    assert declarations["Outer"].annotations == ("Deprecated",)
    packages = build(FIXTURES / "java/packages").iam.packages
    assert {item.qualified_name for item in packages} == {"shop", "shop.api", "shop.service"}


@pytest.mark.parametrize("fixture", ["java/inheritance", "typescript/inheritance"])
def test_heritage_has_exact_declaration_edges(fixture: str) -> None:
    result = build(FIXTURES / fixture)
    assert {EdgeKind.INHERITS, EdgeKind.IMPLEMENTS} <= {item.kind for item in result.iam.edges}
    nodes = {item.id: item for item in result.iam.nodes}
    for edge in result.iam.edges:
        if edge.kind in {EdgeKind.INHERITS, EdgeKind.IMPLEMENTS}:
            assert nodes[edge.source_id].symbol_id is not None
            assert nodes[edge.target_id].symbol_id is not None


def test_typescript_constructs_and_jsx_exclusion() -> None:
    result = build(FIXTURES / "typescript/simple")
    declarations = {
        item.name: item
        for item in result.facts[0].declarations
        if item.kind != NodeKind.CONSTRUCTOR
    }
    assert {
        NodeKind.INTERFACE,
        NodeKind.TYPE_ALIAS,
        NodeKind.ENUM,
        NodeKind.CLASS,
        NodeKind.CONSTRUCTOR,
        NodeKind.PROPERTY,
        NodeKind.METHOD,
        NodeKind.FUNCTION,
        NodeKind.MODULE,
    } <= {item.kind for item in result.facts[0].declarations}
    assert declarations["arrow"].is_exported and "async" in declarations["arrow"].modifiers
    assert declarations["task"].container_key == declarations["Internal"].key
    tsx = build(FIXTURES / "tsx")
    assert {item.name for item in tsx.facts[0].declarations} == {"Props", "title", "Card"}
    assert tsx.facts[0].language == Language.TYPESCRIPT
    assert tsx.facts[0].extractor.dialect == ParserLanguage.TSX
    assert not tsx.iam.packages


@pytest.mark.parametrize(
    "fixture", ["typescript/modules", "javascript/es_modules", "javascript/commonjs"]
)
def test_explicit_relative_import_alias_call_and_new(fixture: str) -> None:
    result = build(FIXTURES / fixture)
    assert {EdgeKind.IMPORTS, EdgeKind.CALLS, EdgeKind.CREATES} <= {
        item.kind for item in result.iam.edges
    }
    assert any(
        item.reference.name == "run" and item.status == ResolutionStatus.RESOLVED
        for item in result.resolutions
    )
    assert any(
        item.method in {ResolutionMethod.EXPLICIT_RELATIVE_MODULE, ResolutionMethod.EXACT_IMPORT}
        for item in result.resolutions
    )
    assert all(module.attributes["semantics"] == "es_file_module" for module in result.iam.modules)
    nodes = {item.id: item for item in result.iam.nodes}
    assert all(
        nodes[edge.source_id].kind == NodeKind.FILE
        for edge in result.iam.edges
        if edge.kind == EdgeKind.IMPORTS
    )


def test_java_static_import_and_class_qualified_call() -> None:
    result = build(FIXTURES / "java/resolution")
    calls = [
        item for item in result.resolutions if item.reference.reference_kind == ReferenceKind.CALL
    ]
    assert sum(item.status == ResolutionStatus.RESOLVED for item in calls) == 2
    assert {item.method for item in calls if item.status == ResolutionStatus.RESOLVED} == {
        ResolutionMethod.EXACT_IMPORT,
        ResolutionMethod.STATIC_QUALIFIED,
    }
    assert all(
        item.status == ResolutionStatus.UNRESOLVED
        for item in calls
        if item.reference.name in {"instance", "missing"}
    )


@pytest.mark.parametrize("fixture", ["java/ambiguous", "typescript/ambiguous"])
def test_ambiguity_never_produces_guessed_edges(fixture: str) -> None:
    result = build(FIXTURES / fixture)
    assert result.statistics.references_ambiguous > 0
    assert not any(edge.kind == EdgeKind.CALLS for edge in result.iam.edges)
    assert all(
        len(item.candidates) >= 2
        for item in result.resolutions
        if item.status == ResolutionStatus.AMBIGUOUS
    )


@pytest.mark.parametrize(
    "filename,content",
    [
        ("app.ts", "function hit() {} function run(hit: () => void) { hit(); }"),
        ("app.js", "function hit() {} function run() { const hit = other; hit(); }"),
        (
            "app.ts",
            "class Tools { static ping() {} } function run(Tools: unknown) { Tools.ping(); }",
        ),
        (
            "App.java",
            "class Tools { static void ping() {} } "
            "class App { Tools Tools; void run() { Tools.ping(); } }",
        ),
        ("app.ts", "function hit() {} function run() { function hit() {} hit(); }"),
        ("App.java", "class Target {} class App { void run() { class Target {} new Target(); } }"),
        ("app.js", "function run(require) { const loaded = require('pkg'); }"),
    ],
)
def test_local_bindings_block_false_resolution(tmp_path: Path, filename: str, content: str) -> None:
    result = source(tmp_path, content, filename)
    assert not any(edge.kind in {EdgeKind.CALLS, EdgeKind.CREATES} for edge in result.iam.edges)


def test_same_file_calls_and_static_this_resolution() -> None:
    result = build(FIXTURES / "typescript/resolution")
    assert any(edge.kind == EdgeKind.CALLS for edge in result.iam.edges)
    hit = [item for item in result.resolutions if item.reference.name == "hit"]
    assert {item.status for item in hit} == {ResolutionStatus.RESOLVED, ResolutionStatus.UNRESOLVED}
    assert any(
        item.status == ResolutionStatus.RESOLVED and item.reference.receiver == "this"
        for item in result.resolutions
    )


def test_dynamic_import_require_and_unknown_receiver() -> None:
    result = build(FIXTURES / "javascript/dynamic_require")
    assert result.statistics.references_unresolved >= 3
    assert not result.iam.edges
    assert any(item.reference.is_dynamic for item in result.resolutions)
    assert result.diagnostics


def test_external_namespace_package_roots_not_fictional_classes() -> None:
    result = build(FIXTURES / "mixed")
    external = [item for item in result.iam.nodes if item.kind == NodeKind.EXTERNAL_DEPENDENCY]
    assert {item.qualified_name for item in external} == {
        "external:java_namespace:java.util",
        "external:npm:@scope/ui",
        "external:npm:react",
    }
    assert all(item.symbol_id is None and item.file_id is None for item in external)
    assert all(
        item.kind == EdgeKind.IMPORTS
        for item in result.iam.edges
        if item.target_id in {node.id for node in external}
    )
    node_external = build(FIXTURES / "javascript/commonjs")
    assert any(item.qualified_name == "external:node:path" for item in node_external.iam.nodes)


def test_same_names_do_not_cross_java_and_es(tmp_path: Path) -> None:
    (tmp_path / "Target.java").write_text("class Target {}")
    result = source(tmp_path, "function run() { new Target(); }")
    assert (
        next(
            item
            for item in result.resolutions
            if item.reference.reference_kind == ReferenceKind.CREATE
        ).status
        == ResolutionStatus.UNRESOLVED
    )
    assert not any(item.kind == EdgeKind.CREATES for item in result.iam.edges)


def test_aggregation_and_bounded_provenance() -> None:
    result = build(FIXTURES / "mixed", ExtractionConfig(max_provenance_per_edge=1))
    repeated = [
        item
        for item in result.iam.edges
        if item.kind == EdgeKind.CALLS and item.attributes["occurrences"] == 2
    ]
    assert len(repeated) == 2
    assert all(
        len(item.attributes["provenance"]) == 1 and item.attributes["provenance_truncated"] == 1
        for item in repeated
    )
    assert sum(item.code.value == "IAM_PROVENANCE_LIMIT" for item in result.diagnostics) == 3
    full = build(FIXTURES / "mixed")
    assert {item.id for item in full.iam.edges} == {item.id for item in result.iam.edges}
    assert all(item.attributes["provenance_truncated"] == 0 for item in full.iam.edges)


def test_stable_ids_across_lines_unrelated_edits_root_and_rename(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    original = "function work() {} function run() { work(); }"
    first = source(a, original)
    copied = source(b, original)
    assert serialize_iam(first.iam) == serialize_iam(copied.iam)
    moved = source(a, "\n\n" + original)
    assert {item.id for item in first.iam.nodes} == {item.id for item in moved.iam.nodes}
    assert {item.id for item in first.iam.edges} == {item.id for item in moved.iam.edges}
    (a / "unrelated.ts").write_text("export class Unrelated {}")
    edited = build(a)
    assert {item.id for item in first.iam.symbols} <= {item.id for item in edited.iam.symbols}
    (a / "app.ts").rename(a / "renamed.ts")
    renamed = build(a)
    assert not {item.id for item in first.iam.symbols} & {item.id for item in renamed.iam.symbols}
    different = build(b, ExtractionConfig(repository_namespace="other-project"))
    assert not {item.id for item in first.iam.nodes} & {item.id for item in different.iam.nodes}


def test_new_callsite_preserves_edge_identity(tmp_path: Path) -> None:
    first = source(tmp_path, "function work() {} function run() { work(); }")
    second = source(tmp_path, "function work() {} function run() { work(); work(); }")
    assert first.iam.edges[0].id == second.iam.edges[0].id
    assert second.iam.edges[0].attributes["occurrences"] == 2


def test_utf8_crlf_inclusive_source_coordinates(tmp_path: Path) -> None:
    result = source(tmp_path, "// Привет\r\nexport function работа() {}\r\n", "unicode.ts")
    declaration = result.facts[0].declarations[0]
    location = declaration.source_location
    assert location.start_line == location.end_line == 2
    assert location.start_column == 8
    assert location.end_column == len("export function работа() {}".encode())


def test_tolerant_strict_limits_and_missing_registry(tmp_path: Path) -> None:
    (tmp_path / "App.java").write_text("class App { int value = 1 }")
    tolerant = build(tmp_path)
    assert tolerant.facts[0].source_had_syntax_errors and not tolerant.is_complete
    strict = build(tmp_path, strict=True)
    assert not strict.facts and not strict.is_valid
    retained = build(tmp_path, ExtractionConfig(skip_invalid_files=False), strict=True)
    assert retained.facts and not retained.is_valid
    (tmp_path / "App.java").write_text("class App { void a() {} void b() {} }")
    limited = build(tmp_path, ExtractionConfig(max_declarations_per_file=1))
    assert not limited.is_valid and not limited.facts
    missing = build(tmp_path, registry=ExtractorRegistry())
    assert not missing.is_valid and not missing.facts
    assert any(item.code.value == "EXTRACT_MISSING_EXTRACTOR" for item in missing.diagnostics)


def test_registry_isolation_duplicate_and_absent() -> None:
    registry = create_extractor_registry()
    assert len(registry.supported_languages()) == 4
    with pytest.raises(DuplicateExtractorError):
        registry.register(registry.get(ParserLanguage.JAVA))
    with pytest.raises(UnsupportedExtractorError):
        ExtractorRegistry().get(ParserLanguage.JAVA)
    assert not ExtractorRegistry().supports(ParserLanguage.JAVA)


def test_compact_facts_and_iam_exclude_source_and_native_objects(tmp_path: Path) -> None:
    marker = "PRIVATE_SOURCE_CREDENTIAL_MARKER"
    result = source(
        tmp_path,
        f'export function work(value: string = "{marker}") {{ '
        f'const password = "{marker}"; return password; }} // {marker}',
    )
    output = result.model_dump_json() + serialize_iam(result.iam)
    assert marker not in output
    assert str(tmp_path) not in output
    assert '"source_text"' not in output and '"tree"' not in output
    invalid = result.iam.model_dump()
    invalid["metadata"]["native"] = object()
    with pytest.raises(ValidationError):
        ArchitectureModel.model_validate(invalid)
    invalid_fact = result.facts[0].model_dump()
    invalid_fact["source_bytes"] = b"private"
    with pytest.raises(ValidationError):
        ExtractedFileFacts.model_validate(invalid_fact)


@pytest.mark.parametrize(
    "defect",
    [
        "dangling_parent",
        "cycle",
        "duplicate_node",
        "dangling_edge",
        "wrong_file",
        "uncertain_provenance",
        "missing_provenance",
        "count_mismatch",
    ],
)
def test_builder_validator_rejects_broken_graphs(defect: str) -> None:
    result = build(FIXTURES / "mixed")
    data = result.iam.model_dump(mode="json")
    node = next(item for item in data["nodes"] if item["symbol_id"] is not None)
    if defect == "dangling_parent":
        node["attributes"]["parent_node_id"] = "missing"
    elif defect == "cycle":
        node["attributes"]["parent_node_id"] = node["id"]
    elif defect == "duplicate_node":
        data["nodes"].append(node)
    elif defect == "dangling_edge":
        data["edges"][0]["target_id"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    elif defect == "wrong_file":
        node["source_location"]["file_path"] = "wrong.ts"
    elif defect == "uncertain_provenance":
        data["edges"][0]["attributes"]["provenance"][0]["resolution_status"] = "AMBIGUOUS"
    elif defect == "missing_provenance":
        data["edges"][0]["attributes"]["provenance"] = []
    elif defect == "count_mismatch":
        data["edges"][0]["attributes"]["occurrences"] = 100
    with pytest.raises((ValidationError, IAMValidationError)):
        validate_built_iam(ArchitectureModel.model_validate(data))


def test_facts_validate_containers_languages_and_paths() -> None:
    file = build(FIXTURES / "java/simple").facts[0]
    for defect in ("container", "language", "location", "duplicate"):
        data = file.model_dump(mode="json")
        if defect == "container":
            data["declarations"][0]["container_key"] = "absent"
        elif defect == "language":
            data["language"] = "TYPESCRIPT"
        elif defect == "location":
            data["declarations"][0]["source_location"]["file_path"] = "wrong.java"
        else:
            data["declarations"].append(data["declarations"][0])
        with pytest.raises(ValidationError):
            ExtractedFileFacts.model_validate(data)
    with pytest.raises(IAMValidationError):
        SymbolIndex((file, file))


def test_builder_rejects_fake_resolution_and_snapshot_mismatch() -> None:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(FIXTURES / "mixed"))
    ) as repository:
        result = BuildIAM(
            ParseRepository(create_parser_registry()), create_extractor_registry()
        ).execute(repository.snapshot, repository.workspace)
        builder = IAMBuilder()
        with pytest.raises(IAMValidationError):
            builder.build(
                repository.snapshot,
                result.facts,
                result.resolutions[:-1],
                result.config,
                result.parsing,
                SymbolResolver.version,
            )
        fake = result.resolutions[0].model_copy(
            update={
                "target_file": "absent.ts",
                "status": ResolutionStatus.RESOLVED,
                "external": None,
            }
        )
        with pytest.raises(IAMValidationError):
            builder.build(
                repository.snapshot,
                result.facts,
                (fake, *result.resolutions[1:]),
                result.config,
                result.parsing,
                SymbolResolver.version,
            )


def test_streaming_releases_previous_parsed_file(tmp_path: Path) -> None:
    for i in range(48):
        (tmp_path / f"file{i:03}.ts").write_text(f"export function work{i}() {{}}")
    observed: list[weakref.ReferenceType[ParsedSourceFile]] = []

    class TrackingParse(ParseRepository):
        def iter_parse(
            self, snapshot: RepositorySnapshot, workspace: RepositoryWorkspace
        ) -> Generator[ParsedSourceFile | FileParseMetadata]:
            for item in super().iter_parse(snapshot, workspace):
                assert not observed or observed[-1]() is None
                assert isinstance(item, ParsedSourceFile)
                observed.append(weakref.ref(item))
                yield item
                del item

    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    ) as repository:
        result = BuildIAM(
            TrackingParse(create_parser_registry()), create_extractor_registry()
        ).execute(repository.snapshot, repository.workspace)
    assert result.statistics.files_extracted == 48
    assert all(reference() is None for reference in observed)
    assert len(json.loads(serialize_iam(result.iam))["symbols"]) == 48


@pytest.mark.parametrize(
    "construct", ["new ns()", "class Child extends ns {}", "type T = typeof ns"]
)
def test_namespace_binding_cannot_become_symbol_target(tmp_path: Path, construct: str) -> None:
    (tmp_path / "lib.ts").write_text("export class Base {}")
    result = source(tmp_path, f'import * as ns from "./lib"; {construct};')
    assert result.is_valid
    assert not any(edge.kind in {EdgeKind.CREATES, EdgeKind.INHERITS} for edge in result.iam.edges)


def test_imported_arrow_is_not_a_constructor(tmp_path: Path) -> None:
    (tmp_path / "lib.ts").write_text("export const work = () => {};")
    result = source(tmp_path, 'import { work } from "./lib"; new work();')
    assert result.is_valid and not any(edge.kind == EdgeKind.CREATES for edge in result.iam.edges)


def test_reexport_chains_and_wildcards_are_conservative(tmp_path: Path) -> None:
    (tmp_path / "lib.ts").write_text("export function work() {}")
    (tmp_path / "barrel.ts").write_text('export { work } from "./lib";')
    result = source(tmp_path, 'import { work } from "./barrel"; work();')
    assert any(edge.kind == EdgeKind.IMPORTS for edge in result.iam.edges)
    assert not any(edge.kind == EdgeKind.CALLS for edge in result.iam.edges)
    (tmp_path / "Target.java").write_text("package p; class Target {}")
    (tmp_path / "Use.java").write_text("package q; import p.*; class Use { Target value; }")
    java = build(tmp_path)
    assert not any(edge.kind == EdgeKind.USES for edge in java.iam.edges)


def test_unreadable_source_and_unsupported_language_are_visible(tmp_path: Path) -> None:
    (tmp_path / "bad.ts").write_bytes(b"\xff")
    (tmp_path / "script.py").write_text("raise RuntimeError('must-never-execute')")
    result = build(tmp_path)
    assert not result.is_valid and not result.is_complete
    assert result.parsing.statistics.failed_files == 1
    assert result.parsing.statistics.unsupported_files == 1
    assert not result.iam.symbols


def test_extraction_is_offline_and_does_not_execute_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import socket
    import subprocess

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("unexpected network or process execution")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    marker = tmp_path / "executed"
    result = source(
        tmp_path,
        f'const fs = require("node:fs"); fs.writeFileSync("{marker}", "bad");',
        "script.js",
    )
    assert result.is_valid and not marker.exists()
    assert str(marker) not in result.model_dump_json()


def test_extractor_failure_never_logs_source_exception_arguments(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    actual = create_extractor_registry().get(ParserLanguage.TYPESCRIPT)

    class FailedExtractor:
        language = actual.language
        metadata = actual.metadata

        def extract(
            self, parsed_file: ParsedSourceFile, config: ExtractionConfig
        ) -> ExtractedFileFacts:
            raise RuntimeError("PRIVATE_EXCEPTION_SOURCE_MARKER")

    (tmp_path / "app.ts").write_text("export function work() {}")
    result = build(tmp_path, registry=ExtractorRegistry((FailedExtractor(),)))
    assert not result.is_valid
    assert "PRIVATE_EXCEPTION_SOURCE_MARKER" not in result.model_dump_json() + caplog.text


@pytest.mark.parametrize(
    "body",
    [
        "const run = work => work();",
        "function run({work}) { work(); }",
        "function run(work = other) { work(); }",
        "function run() { try {} catch (work) { work(); } }",
        "work = other; work();",
    ],
)
def test_arrow_patterns_catch_and_reassignment_block_guesses(tmp_path: Path, body: str) -> None:
    result = source(tmp_path, "function work() {} " + body, "app.js")
    assert not any(edge.kind == EdgeKind.CALLS for edge in result.iam.edges)


def test_commonjs_mutated_binding_and_namespace_shadowed_require(tmp_path: Path) -> None:
    (tmp_path / "lib.js").write_text("function work() {} exports.work = work;")
    mutated = source(
        tmp_path, 'let library = require("./lib.js"); library = other; library.work();', "app.js"
    )
    assert not any(edge.kind == EdgeKind.CALLS for edge in mutated.iam.edges)
    shadowed = source(
        tmp_path,
        'namespace N { const require = other; export function run() { require("external"); } }',
    )
    assert not any(node.kind == NodeKind.EXTERNAL_DEPENDENCY for node in shadowed.iam.nodes)


def test_build_result_validates_statistics() -> None:
    result = build(FIXTURES / "mixed")
    data = result.model_dump(mode="json")
    data["statistics"]["edges_created"] += 1
    with pytest.raises(ValidationError):
        IAMBuildResult.model_validate(data)


def test_explicit_repository_id_has_priority_over_default_namespace(tmp_path: Path) -> None:
    from uuid import UUID

    from archguard.core.identifiers import RepositoryId
    from archguard.extraction.identity import project_id

    identity = RepositoryId(UUID("11111111-1111-1111-1111-111111111111"))
    (tmp_path / "app.ts").write_text("export class Item {}")
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL, location=str(tmp_path), repository_id=identity
        )
    ) as repository:
        result = BuildIAM(
            ParseRepository(create_parser_registry()),
            create_extractor_registry(),
            ExtractionConfig(repository_namespace="ignored-default"),
        ).execute(repository.snapshot, repository.workspace)
    assert result.iam.project.id == project_id(str(identity))
    assert result.iam.metadata["repository_namespace"] == str(identity)


def test_class_identity_survives_comments_and_unrelated_edit_then_changes_on_rename(
    tmp_path: Path,
) -> None:
    first = source(tmp_path, "export class Original {}", "model.ts")
    original = next(node.id for node in first.iam.nodes if node.kind == NodeKind.CLASS)
    shifted = source(tmp_path, "// preceding comment\n\nexport class Original {}", "model.ts")
    assert next(node.id for node in shifted.iam.nodes if node.kind == NodeKind.CLASS) == original
    (tmp_path / "other.ts").write_text("export function other() {}")
    unrelated = build(tmp_path)
    assert next(node.id for node in unrelated.iam.nodes if node.kind == NodeKind.CLASS) == original
    renamed = source(tmp_path, "export class Renamed {}", "model.ts")
    assert next(node.id for node in renamed.iam.nodes if node.kind == NodeKind.CLASS) != original


def test_three_call_sites_preserve_all_locations_in_order(tmp_path: Path) -> None:
    result = source(
        tmp_path, "function work() {}\nfunction run() {\n work();\n work();\n work();\n}"
    )
    calls = [edge for edge in result.iam.edges if edge.kind == EdgeKind.CALLS]
    assert len(calls) == 1
    assert calls[0].attributes["occurrences"] == 3
    locations = [item["source_location"] for item in calls[0].attributes["provenance"]]
    assert [item["start_line"] for item in locations] == [3, 4, 5]
    repeated = build(tmp_path)
    assert serialize_iam(repeated.iam) == serialize_iam(result.iam)


def test_java_generic_annotation_arguments_are_not_serialized(tmp_path: Path) -> None:
    marker = "PRIVATE_GENERIC_ANNOTATION_MARKER"
    result = source(
        tmp_path,
        f'class App<@Ann("{marker}") T> {{ '
        f'<@Ann("{marker}") U> U identity(U value) {{ return value; }} }} '
        "@interface Ann { String value(); }",
        "App.java",
    )
    assert result.is_valid
    assert marker not in result.model_dump_json() + serialize_iam(result.iam)
    declarations = {item.name: item for item in result.facts[0].declarations}
    assert declarations["App"].type_parameters == ("T",)
    assert declarations["identity"].type_parameters == ("U",)


def test_java_type_annotation_values_are_not_part_of_signatures(tmp_path: Path) -> None:
    marker = "7349276138927461"
    result = source(
        tmp_path,
        f"class App {{ java.util.List<@Ann({marker}L) String> values; "
        f"void use(java.util.List<@Ann({marker}L) String> input) {{}} }} "
        "@interface Ann { long value(); }",
        "App.java",
    )
    assert result.is_valid
    assert marker not in result.model_dump_json() + serialize_iam(result.iam)
