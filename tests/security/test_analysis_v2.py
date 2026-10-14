"""Parsed inert engineering fixtures, never a Security benchmark or executable payloads."""

import json
from pathlib import Path
from uuid import UUID, uuid5

import pytest

from archguard.core.identifiers import RepositoryId, SnapshotId, SourceFileId
from archguard.parsing.config import ParserConfig
from archguard.parsing.tree_sitter_adapters import JavaParser, TypeScriptParser
from archguard.repository.models import RepositoryFile
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.analyzer_v2 import SecurityAnalyzerV2
from archguard.security.domain import (
    SecurityAnalysisContext,
    SecurityAnalysisResult,
    SecurityLanguage,
)
from archguard.security.engine_v2 import InterproceduralEngine
from archguard.security.frameworks_v2 import packs, proofs
from archguard.security.index_v2 import DeclarationIndex, SourceUnit
from archguard.security.summaries_v2 import FunctionSummary, SummaryCache, V2Limits

CASES = json.loads(Path("tests/fixtures/security/v2/cases.json").read_text())["cases"]
REPO = RepositoryId(UUID(int=301))
SNAP = SnapshotId(UUID(int=302))


def inputs(code, language="TYPESCRIPT", files=None):
    all_files = {"src/check.java" if language == "JAVA" else "src/check.ts": code} | (files or {})
    return tuple(
        SecuritySourceInput(
            RepositoryFile(
                relative_path=path,
                extension=Path(path).suffix,
                size_bytes=len(source.encode()),
                language=language,
                kind="SOURCE",
                analysis_eligible=True,
                hash_status="BUDGET_LIMIT",
            ),
            source.encode(),
            SourceFileId(uuid5(REPO, path)),
        )
        for path, source in all_files.items()
    )


def analyze(code, language="TYPESCRIPT", rule=None, limits=None, files=None, analyzer=None):
    context = SecurityAnalysisContext(
        repository_id=REPO,
        snapshot_id=SNAP,
        language=language,
        **({"requested_rules": (rule,)} if rule else {}),
    )
    return (analyzer or SecurityAnalyzerV2(limits)).analyze(context, inputs(code, language, files))


def debug_engine(case, limits=None):
    units = []
    for source in inputs(case["source"], case["language"], case["files"]):
        parser = JavaParser() if case["language"] == "JAVA" else TypeScriptParser()
        parsed = parser.parse(SNAP, source.file, source.source, ParserConfig())
        units.append(
            SourceUnit(
                source.file_id,
                source.file.relative_path,
                SecurityLanguage(case["language"]),
                parsed.tree.root_node,
                "test-version",
            )
        )
    engine = InterproceduralEngine(
        DeclarationIndex(tuple(units), limits or V2Limits()), limits or V2Limits(), SummaryCache()
    )
    engine.run_all()
    return engine


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_fixture(case):
    analyzer = SecurityAnalyzerV2()
    result = analyze(
        case["source"], case["language"], case["rule"], files=case["files"], analyzer=analyzer
    )
    if "ANALYSIS_ERROR" in {d.code for d in result.diagnostics}:
        debug_engine(case)
    assert len(result.findings) == case["expected_count"]
    if case["expected_proof"]:
        assert case["expected_proof"] in {p["kind"] for p in result.analysis_metadata["proofs"]}
    if case["expected_diagnostic"]:
        assert case["expected_diagnostic"] in {d.code for d in result.diagnostics}
    if case["expected_status"]:
        assert all(f.status.value == case["expected_status"] for f in result.findings)
    assert SecurityAnalysisResult.model_validate_json(result.model_dump_json()) == result
    again = analyze(
        case["source"], case["language"], case["rule"], files=case["files"], analyzer=analyzer
    )
    assert again.model_dump_json() == result.model_dump_json()
    for s in result.analysis_metadata["summaries"]:
        assert FunctionSummary.model_validate(s).fingerprint == s["fingerprint"]
    assert (
        result.analysis_metadata["provider_calls"]
        == result.analysis_metadata["credential_reads"]
        == 0
    )
    assert not result.zero_findings_is_security_guarantee
    for f in result.findings:
        assert f.primary_source.location.start_line > 0
        assert f.primary_source.location.end_line >= f.primary_source.location.start_line
        if f.flow:
            assert f.source_ref and f.sink_ref
            assert f.flow.steps[0].role.value == "SOURCE"
            assert f.flow.steps[-1].role.value == "SINK"


def test_parameter_return_sink_and_call_trace():
    case = next(c for c in CASES if c["id"] == "ts-helper-return")
    result = analyze(case["source"], rule="SEC003")
    assert any(
        s["return_flow"]["parameter_indices"] == [0] for s in result.analysis_metadata["summaries"]
    )
    kinds = {e.metadata["step_kind"] for f in result.findings for e in f.evidence}
    assert {"CALL_ARGUMENT", "CALLEE_PARAMETER", "CALLEE_RETURN", "CALL_RETURN"} <= kinds
    sink = analyze(next(c for c in CASES if c["id"] == "ts-helper-sink")["source"], rule="SEC003")
    assert any(
        s["sinks"] and s["sinks"][0]["parameter_indices"] == [0]
        for s in sink.analysis_metadata["summaries"]
    )


def test_cache_is_bounded_invalidates_source_and_preserves_canonical_output():
    analyzer = SecurityAnalyzerV2(V2Limits(max_summary_cache_entries=1))
    case = next(c for c in CASES if c["id"] == "ts-helper-return")
    first = analyze(case["source"], rule="SEC003", analyzer=analyzer)
    assert len(analyzer.cache.entries) <= 1
    changed = analyze(
        case["source"].replace("return x;", 'return "safe";'), rule="SEC003", analyzer=analyzer
    )
    assert first.findings and not changed.findings
    assert len(analyzer.cache.entries) <= 1


@pytest.mark.parametrize(
    "limit,value,diagnostic",
    [
        ("max_call_depth", 1, "CALL_DEPTH_LIMIT"),
        ("max_summary_expansions", 1, "SUMMARY_INDEX_LIMIT"),
        ("max_summary_nodes", 1, "SUMMARY_NODE_LIMIT"),
        ("max_flow_steps", 3, "FLOW_LIMIT_EXCEEDED"),
        ("max_total_flow_steps", 3, "FLOW_LIMIT_EXCEEDED"),
    ],
)
def test_call_bounds_terminate_partial(limit, value, diagnostic):
    case = next(c for c in CASES if c["id"] == "ts-helper-return")
    result = analyze(case["source"], limits=V2Limits(**{limit: value}))
    assert diagnostic in {d.code for d in result.diagnostics} or any(
        diagnostic == e["code"]
        for s in result.analysis_metadata["summaries"]
        for e in s["unknown_effects"]
    )
    assert result.analysis_metadata["partial"]


def test_alias_bounds_and_field_bounds():
    case = next(c for c in CASES if c["id"] == "ts-alias-write")
    result = analyze(case["source"], limits=V2Limits(max_aliases_per_object=1))
    assert "ALIAS_LIMIT" in {d.code for d in result.diagnostics}
    result = analyze(case["source"], limits=V2Limits(max_fields_per_object=1, max_heap_objects=1))
    assert result.analysis_metadata["partial"]


def test_registry_real_packs_proofs_and_no_ts_deserialization():
    assert len({p.pack_id for p in packs()}) == len(packs())
    assert all(p.apis and p.tests and p.limitations for p in packs())
    assert all(p.preconditions and p.invalidators and p.limitations for p in proofs())
    assert not any(
        p.pack_id.startswith("TS_") and any("SEC005" in e.rule_ids for e in p.apis) for p in packs()
    )


def test_redaction_and_invalid_source_failure(capsys, caplog):
    case = next(c for c in CASES if c["id"] == "ts-secret-still-redacted")
    result = analyze(case["source"], rule="SEC001")
    assert (
        "TEST_ONLY_SYNTHETIC_SECRET_Ab4Cd5Ef6Gh7"
        not in result.model_dump_json() + caplog.text + capsys.readouterr().out
    )
    invalid = analyze("function {", rule="SEC003")
    assert invalid.analysis_metadata["coverage"]["SEC003"]["status"] == "FAILED"
    assert not invalid.analyzed_rules


@pytest.mark.parametrize(
    "limit,value,diagnostic",
    [
        ("max_total_nodes", 1, "TOTAL_NODE_LIMIT"),
        ("max_total_summary_nodes", 1, "SUMMARY_TOTAL_NODE_LIMIT"),
        ("max_candidates", 1, "CANDIDATE_LIMIT"),
        ("max_fields_per_object", 1, "FIELD_LIMIT"),
        ("max_total_heap_fields", 1, "FIELD_LIMIT"),
        ("max_heap_objects", 1, "HEAP_OBJECT_LIMIT"),
    ],
)
def test_global_stress_bounds(limit, value, diagnostic):
    code = 'import {Request} from "express"; import {exec} from "node:child_process"; '
    code += "function pass(x:string){return x;} function check(req:Request){"
    code += "const a={one:req.query.q,two:req.query.b}; const b={x:req.query.c}; "
    code += "exec(pass(a.one)); exec(b.x);}"
    analyzer = SecurityAnalyzerV2(V2Limits(**{limit: value}))
    first = analyze(code, analyzer=analyzer)
    codes = {d.code for d in first.diagnostics} | {
        e["code"] for s in first.analysis_metadata["summaries"] for e in s["unknown_effects"]
    }
    assert diagnostic in codes
    assert first.model_dump_json() == analyze(code, analyzer=analyzer).model_dump_json()


def test_deep_chain_and_wide_fanout_are_bounded():
    chain = " ".join(f"function f{i}(x:string){{return f{i + 1}(x);}}" for i in range(10))
    chain += " function f10(x:string){return x;}"
    code = (
        'import {Request} from "express"; import {exec} from "node:child_process"; '
        + chain
        + " function check(req:Request){exec(f0(req.query.q));}"
    )
    result = analyze(code, rule="SEC003")
    assert "CALL_DEPTH_LIMIT" in {d.code for d in result.diagnostics}
    assert all(f.status.value == "POTENTIAL" for f in result.findings)
    wide = 'import {Request} from "express"; '
    wide += " ".join(f"function f{i}(x:string){{return x;}}" for i in range(40))
    wide += (
        " function check(req:Request){" + "".join(f"f{i}(req.query.q);" for i in range(40)) + "}"
    )
    bounded = analyze(wide, limits=V2Limits(max_summary_expansions=8))
    assert "SUMMARY_INDEX_LIMIT" in {d.code for d in bounded.diagnostics}


def test_call_target_bound_reports_ambiguity():
    helpers = " ".join(f'String pass(T{i} x){{return "safe";}}' for i in range(6))
    code = (
        "import javax.servlet.http.HttpServletRequest; class C{"
        + helpers
        + " void run(HttpServletRequest req)throws Exception{"
        'Runtime.getRuntime().exec(pass(req.getParameter("q")));}}'
    )
    result = analyze(code, "JAVA", "SEC003", limits=V2Limits(max_call_targets=2))
    assert {"CALL_AMBIGUOUS", "CALL_TARGET_LIMIT"} <= {d.code for d in result.diagnostics}


def test_constructor_field_and_parameter_write_summaries():
    case = next(c for c in CASES if c["id"] == "ts-symbolic-field-summary")
    result = analyze(case["source"], rule="SEC003")
    assert any(
        f["destination"] == "FIELD_WRITE" and f["parameter_index"] == 1
        for s in result.analysis_metadata["summaries"]
        for f in s["parameter_flows"]
    )


def test_source_and_configuration_cache_invalidation():
    case = next(c for c in CASES if c["id"] == "ts-helper-return")
    analyzer = SecurityAnalyzerV2()
    first = analyze(case["source"], rule="SEC003", analyzer=analyzer)
    hits = analyzer.cache.hits
    assert analyze(case["source"], rule="SEC003", analyzer=analyzer) == first
    assert analyzer.cache.hits > hits
    analyzer.limits = V2Limits(max_call_depth=1)
    limited = analyze(case["source"], rule="SEC003", analyzer=analyzer)
    assert limited.findings[0].status.value == "POTENTIAL"


def test_source_file_limit_and_reversed_input_order():
    case = next(c for c in CASES if c["id"] == "ts-cross-file-import")
    context = SecurityAnalysisContext(repository_id=REPO, snapshot_id=SNAP, language="TYPESCRIPT")
    sources = inputs(case["source"], files=case["files"])
    analyzer = SecurityAnalyzerV2()
    assert (
        analyzer.analyze(context, sources).model_dump_json()
        == analyzer.analyze(context, reversed(sources)).model_dump_json()
    )
    failed = SecurityAnalyzerV2(V2Limits(max_source_files=1)).analyze(context, sources)
    assert "SOURCE_INTAKE_LIMIT" in {d.code for d in failed.diagnostics}
    assert not failed.analyzed_rules


@pytest.mark.parametrize("body", ["x", "{return x;}"])
def test_assigned_arrow_and_function_alias(body):
    code = 'import {Request} from "express"; import {exec} from "node:child_process"; '
    code += (
        f"const pass=(x:string)=>{body}; "
        "function check(req:Request){const alias=pass; exec(alias(req.query.q));}"
    )
    assert analyze(code, rule="SEC003").findings[0].status.value == "SUPPORTED"
