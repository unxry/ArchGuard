"""Synthetic engineering behavior, never benchmark truth or effectiveness metrics."""

import json
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from archguard.core.identifiers import RepositoryId, SnapshotId, SourceFileId
from archguard.core.locations import SourceLocation
from archguard.repository.models import RepositoryFile
from archguard.security.analyzer_v1 import (
    SecurityAnalyzerV1,
    SecuritySourceInput,
    StaticFlowDetector,
)
from archguard.security.api_v1 import entries
from archguard.security.domain import (
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecuritySourceReference,
)
from archguard.security.engine_v1 import EngineOutput
from archguard.security.flow_v1 import FlowLimits, FlowState, FlowValue, merge

FIXTURES = Path("tests/fixtures/security/v1/cases.json")
CASES = json.loads(FIXTURES.read_text())["cases"]
REPO = RepositoryId(UUID(int=201))
SNAP = SnapshotId(UUID(int=202))
FILE = SourceFileId(UUID(int=203))


def analyze(code, language="TYPESCRIPT", rule=None, limits=None, detectors=None):
    data = code.encode()
    path = "src/check.java" if language == "JAVA" else "src/check.ts"
    context = SecurityAnalysisContext(
        repository_id=REPO,
        snapshot_id=SNAP,
        language=language,
        **({"requested_rules": (rule,)} if rule else {}),
    )
    source = SecuritySourceInput(
        RepositoryFile(
            relative_path=path,
            extension=Path(path).suffix,
            size_bytes=len(data),
            language=language,
            kind="SOURCE",
            analysis_eligible=True,
            hash_status="BUDGET_LIMIT",
        ),
        data,
        FILE,
    )
    return SecurityAnalyzerV1(limits).analyze(context, (source,), detectors=detectors)


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fixture(case):
    result = analyze(case["source"], case["language"], case["rule"])
    assert len(result.findings) == case["expected_count"]
    if case["expected_diagnostic"]:
        assert case["expected_diagnostic"] in {d.code for d in result.diagnostics}
    if case["expected_status"]:
        assert all(f.status.value == case["expected_status"] for f in result.findings)
    assert SecurityAnalysisResult.model_validate_json(result.model_dump_json()) == result
    assert (
        analyze(case["source"], case["language"], case["rule"]).model_dump_json()
        == result.model_dump_json()
    )
    assert result.analysis_metadata["provider_calls"] == 0
    assert result.zero_findings_is_security_guarantee is False
    for finding in result.findings:
        assert finding.namespace == "SEC"
        assert finding.language == case["language"]
        assert finding.primary_source.file_id == FILE
        assert finding.primary_source.location.start_line >= 1
        assert (
            finding.primary_source.location.end_line >= finding.primary_source.location.start_line
        )
        if finding.flow:
            assert finding.source_ref and finding.sink_ref
            assert finding.flow.steps[0].role.value == "SOURCE"
            assert finding.flow.steps[-1].role.value == "SINK"


@pytest.fixture
def flow_source():
    return SecuritySourceReference(
        file_id=FILE,
        language="TYPESCRIPT",
        location=SourceLocation(file_path="src/check.ts", start_line=2),
    )


@pytest.mark.parametrize("state", tuple(FlowState))
def test_unknown_never_safe(state):
    merged = merge((FlowValue(state), FlowValue.unknown("unknown")))
    assert merged.state == FlowState.UNKNOWN


def test_lattice_sanitization_and_recontamination(flow_source):
    from archguard.security.domain import SecurityRuleId

    source = FlowValue.source(flow_source, "t.request")
    clean = FlowValue(FlowState.UNTAINTED)
    safe = source.sanitize(SecurityRuleId.SEC007, flow_source, "t.escape", 32)
    assert safe.state == FlowState.SANITIZED
    assert merge((source, clean)).state == FlowState.TAINTED
    assert merge((safe, clean)).state == FlowState.SANITIZED
    assert merge((safe, source)).state == FlowState.TAINTED
    assert merge((source, safe)).state == FlowState.TAINTED
    assert merge((safe, FlowValue.unknown("unknown"))).sanitized_for == frozenset()
    assert source.step(flow_source, 3).step(flow_source, 3).state == FlowState.UNKNOWN


@pytest.mark.parametrize(
    "limit,value,diagnostic",
    [
        ("max_nodes_per_function", 1, "NODE_LIMIT_EXCEEDED"),
        ("max_tracked_values", 1, "TRACKED_VALUE_LIMIT_EXCEEDED"),
        ("max_flow_steps", 3, "FLOW_LIMIT_EXCEEDED"),
        ("max_branch_states", 1, "BRANCH_LIMIT_EXCEEDED"),
        ("max_file_nodes", 1, "FILE_NODE_LIMIT_EXCEEDED"),
        ("max_expression_depth", 1, "EXPRESSION_DEPTH_LIMIT_EXCEEDED"),
    ],
)
def test_limits_are_partial(limit, value, diagnostic):
    case = next(c for c in CASES if c["id"] == "ts-alias")
    code = case["source"].replace("exec(c);", "if(flag) { exec(c); }")
    result = analyze(code, limits=FlowLimits(**{limit: value}))
    assert diagnostic in {d.code for d in result.diagnostics}
    assert result.analysis_metadata["partial"]
    assert all(f.status.value != "SUPPORTED" for f in result.findings)


def test_path_count_bound(flow_source):
    from archguard.security.domain import FlowRole
    from archguard.security.flow_v1 import TraceStep

    paths = tuple((TraceStep(FlowRole.SOURCE, flow_source, f"source-{i}"),) for i in range(4))
    value = merge((FlowValue(FlowState.TAINTED, paths),), 2)
    assert value.state == FlowState.UNKNOWN
    assert len(value.paths) == 2
    assert "PATH_LIMIT_EXCEEDED" in value.uncertainty


def test_secret_redaction_by_construction(capsys, caplog):
    case = next(c for c in CASES if c["id"] == "typescript-secret")
    result = analyze(case["source"], rule="SEC001")
    literal = "TEST_ONLY_SYNTHETIC_SECRET_Ab4Cd5Ef6Gh7"
    assert result.findings
    assert literal not in result.model_dump_json()
    assert "[REDACTED]" in result.model_dump_json()
    assert literal not in capsys.readouterr().out + caplog.text


def test_failure_is_not_clean_and_exception_is_not_serialized():
    from archguard.security.domain import SecurityRuleId

    class Failed(StaticFlowDetector):
        def analyze(self, context, /):
            raise RuntimeError("TEST_ONLY_SYNTHETIC_SECRET_EXCEPTION")

    result = analyze(
        "const x=1;", rule="SEC001", detectors=(Failed(SecurityRuleId.SEC001, EngineOutput()),)
    )
    assert result.analyzed_rules == ()
    assert result.analysis_metadata["coverage"]["SEC001"]["status"] == "FAILED"
    assert "DETECTOR_ERROR" in {d.code for d in result.diagnostics}
    assert "TEST_ONLY_SYNTHETIC_SECRET_EXCEPTION" not in result.model_dump_json()


@pytest.mark.parametrize("code", ["function { broken", "\x00"])
def test_invalid_source_is_failed(code):
    result = analyze(code, rule="SEC002")
    assert not result.analyzed_rules
    assert result.analysis_metadata["coverage"]["SEC002"]["status"] == "FAILED"


def test_source_input_repr_hides_contents():
    data = b"TEST_ONLY_SYNTHETIC_SECRET_SOURCE"
    source = SecuritySourceInput(
        RepositoryFile(
            relative_path="src/check.ts",
            extension=".ts",
            size_bytes=len(data),
            language="TYPESCRIPT",
            kind="SOURCE",
            analysis_eligible=True,
            hash_status="BUDGET_LIMIT",
        ),
        data,
        FILE,
    )
    assert data.decode() not in repr(source)


def test_api_pack_typed_and_unique():
    pack = entries()
    assert len({e.id for e in pack}) == len(pack)
    assert all(e.engineering_test_binding == __file__.split("ArchGuard/")[-1] for e in pack)
    assert all(e.conditions and e.limitations and e.rule_ids for e in pack)


def test_unknown_library_cannot_preserve_sanitization():
    case = next(c for c in CASES if c["id"] == "ts-xss-sanitize")
    result = analyze(
        case["source"].replace("const alias=safe", "const alias=custom(safe)"), rule="SEC007"
    )
    assert result.findings[0].status.value == "POTENTIAL"
    assert not result.findings[0].flow.complete


def test_object_alias_write_is_unknown():
    case = next(c for c in CASES if c["id"] == "ts-object")
    code = case["source"].replace(
        "const box={item:req.query.q}; exec(box.item);",
        'const box={item:"constant"}; const alias=box; box.item=req.query.q; exec(alias.item);',
    )
    result = analyze(code, rule="SEC003")
    assert "OBJECT_ALIAS_WRITE" in {d.code for d in result.diagnostics}
    assert not result.findings


def test_snapshot_binding_changes_finding_identity():
    from archguard.security.analyzer_v1 import finding
    from archguard.security.domain import SecurityRuleId
    from archguard.security.engine_v1 import Candidate

    source = SecuritySourceReference(
        file_id=FILE, language="JAVA", location=SourceLocation(file_path="src/x.java", start_line=1)
    )
    candidate = Candidate(
        SecurityRuleId.SEC001, source, "embedded-credential-redacted", status="CONFIRMED_PATTERN"
    )
    context = SecurityAnalysisContext(repository_id=REPO, snapshot_id=SNAP, language="JAVA")
    first = finding(candidate, context)
    second = finding(
        replace(candidate), context.model_copy(update={"snapshot_id": SnapshotId(UUID(int=204))})
    )
    assert first.id != second.id


@pytest.mark.parametrize("method", ["getParameter", "getHeader", "getQueryString", "getPathInfo"])
@pytest.mark.parametrize("prefix", ["javax", "jakarta"])
def test_servlet_source_pack(method, prefix):
    case = next(c for c in CASES if c["id"] == "java-command")
    code = (
        case["source"]
        .replace("javax", prefix)
        .replace(
            'getParameter("q")',
            method + ('("q")' if method in {"getParameter", "getHeader"} else "()"),
        )
    )
    assert len(analyze(code, "JAVA", "SEC003").findings) == 1


@pytest.mark.parametrize("field", ["query", "params", "body", "headers"])
def test_express_source_pack(field):
    case = next(c for c in CASES if c["id"] == "ts-command")
    assert analyze(case["source"].replace("req.query", f"req.{field}"), rule="SEC003").findings


@pytest.mark.parametrize("method", ["setTimeout", "setInterval"])
def test_string_timer_and_unknown_type(method):
    code = (
        'import {Request} from "express"; function f(req: Request) {'
        + method
        + "(`${req.query.code}`,10); }"
    )
    assert len(analyze(code, rule="SEC010").findings) == 1
    unknown = analyze(code.replace("`${req.query.code}`", "req.query.code"), rule="SEC010")
    assert not unknown.findings
    assert "DYNAMIC_CODE_TYPE_UNKNOWN" in {d.code for d in unknown.diagnostics}


@pytest.mark.parametrize("method", ["execute", "executeUpdate", "executeQuery"])
def test_statement_sinks(method):
    case = next(c for c in CASES if c["id"] == "java-sql")
    assert analyze(case["source"].replace("executeQuery", method), "JAVA", "SEC002").findings


@pytest.mark.parametrize("name", ["passwordHash", "sessionToken", "csrfToken", "resetKey", "nonce"])
def test_security_random_purpose(name):
    assert analyze(f"const {name}=Math.random();", rule="SEC009").findings


@pytest.mark.parametrize("name", ["monkey", "parserToken", "tokenLabel", "sample", "game"])
def test_nonsecurity_random_purpose(name):
    assert not analyze(f"const {name}=Math.random();", rule="SEC009").findings


def test_same_flow_deduplication():
    from archguard.security.domain import deduplicate_findings

    result = analyze(next(c for c in CASES if c["id"] == "ts-command")["source"], rule="SEC003")
    assert deduplicate_findings(result.findings * 2) == result.findings


def test_shadowed_import_is_not_api_identity():
    code = (
        'import {exec} from "node:child_process"; import {Request} from "express"; '
        "function f(req: Request, exec: (x:unknown) => unknown) { exec(req.query.q); }"
    )
    result = analyze(code, rule="SEC003")
    assert not result.findings
    assert "INTERPROCEDURAL_BOUNDARY" in {d.code for d in result.diagnostics}


def test_empty_input_not_evaluated():
    context = SecurityAnalysisContext(repository_id=REPO, snapshot_id=SNAP, language="JAVA")
    result = SecurityAnalyzerV1().analyze(context, ())
    assert not result.analyzed_rules
    assert all(v["status"] == "FAILED" for v in result.analysis_metadata["coverage"].values())


def test_java_argument_vector_and_array_projection():
    case = next(c for c in CASES if c["id"] == "java-command")
    code = case["source"].replace(
        '"inert-command " + req.getParameter("q")',
        'new String[]{"inert-command",req.getParameter("q")}',
    )
    assert not analyze(code, "JAVA", "SEC003").findings
    unsafe = code.replace(
        'new String[]{"inert-command",req.getParameter("q")}',
        'new String[]{req.getParameter("q"),"fixed"}',
    )
    assert analyze(unsafe, "JAVA", "SEC003").findings


def test_branch_sanitizer_invalidation_and_else_flow():
    case = next(c for c in CASES if c["id"] == "ts-xss-sanitize")
    code = case["source"].replace(
        "const alias=safe;",
        'let alias=safe; if(flag) { alias="fixed"; } else { alias=req.query.more; }',
    )
    assert analyze(code, rule="SEC007").findings
    changed = case["source"].replace("const alias=safe;", "let alias=safe; alias=req.query.more;")
    assert analyze(changed, rule="SEC007").findings


def test_multiline_locations_are_concrete_byte_columns():
    case = next(c for c in CASES if c["id"] == "ts-command")
    code = case["source"].replace(
        "exec(`inert-command ${req.query.q}`);",
        'const label="Пример";\nexec(`inert-command ${req.query.q}`);',
    )
    f = analyze(code, rule="SEC003").findings[0]
    assert f.primary_source.location.start_line == 4
    assert f.primary_source.location.start_column == 1
    assert f.primary_source.location.end_column > 1


def test_filtered_deserializer_alias_stays_unknown():
    case = next(c for c in CASES if c["id"] == "java-deserialization-filter")
    code = case["source"].replace(
        "stream.setObjectInputFilter(filter);",
        "ObjectInputStream alias=stream; alias.setObjectInputFilter(filter);",
    )
    result = analyze(code, "JAVA", "SEC005")
    assert not result.findings
    assert "DESERIALIZATION_FILTER_UNKNOWN" in {d.code for d in result.diagnostics}
