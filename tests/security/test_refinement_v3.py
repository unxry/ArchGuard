"""Small generic engineering fixtures; no benchmark source copies or identities."""

import subprocess
from pathlib import Path

import pytest

from archguard.infrastructure import security_refinement as stage
from archguard.infrastructure.security_dev_worker import SourceFence
from archguard.security.analyzer_v2 import SecurityAnalyzerV2
from archguard.security.analyzer_v3 import SecurityAnalyzerV3
from archguard.security.completeness_v3 import CompletenessCertificate, map_v3_outcome
from archguard.security.summaries_v2 import V2Limits
from tests.security.test_analysis_v2 import analyze
from tests.security.test_dev_evaluation import manifest

TS = 'import {Request} from "express"; '
JAVA = "import jakarta.servlet.http.HttpServletRequest; "


def ts(body, imports=""):
    return TS + imports + " function endpoint(input:Request){" + body + "}"


def java(body, extra=""):
    return (
        JAVA
        + " class Example { void endpoint(HttpServletRequest input) throws Exception {"
        + body
        + "}"
        + extra
        + "}"
    )


CASES = [
    (
        "SEC001",
        "TYPESCRIPT",
        'const apiKey="ghp_' + "a2B3c4D5" * 5 + '";',
        'const apiKey="YOUR_API_KEY";',
        "const apiKey=unknown();",
    ),
    (
        "SEC002",
        "TYPESCRIPT",
        ts(
            'db.query("select * from books where title="+String(input.query.title));',
            'import {Client} from "pg"; const db=new Client();',
        ),
        ts(
            'db.query("select * from books where title=$1", [String(input.query.title)]);',
            'import {Client} from "pg"; const db=new Client();',
        ),
        ts(
            "db.query(opaque(String(input.query.title)));",
            'import {Client} from "pg"; const db=new Client();',
        ),
    ),
    (
        "SEC003",
        "TYPESCRIPT",
        ts(
            'spawn("sh", ["-c",String(input.query.command)]);',
            'import {spawn} from "node:child_process";',
        ),
        ts('spawn("/usr/bin/printf",["%s","hello"]);', 'import {spawn} from "node:child_process";'),
        ts(
            "exec(opaque(String(input.query.command)));", 'import {exec} from "node:child_process";'
        ),
    ),
    (
        "SEC004",
        "JAVA",
        java('java.nio.file.Files.readString(java.nio.file.Path.of(input.getParameter("name")));'),
        java('java.nio.file.Files.readString(java.nio.file.Path.of("/public/readme"));'),
        java(
            (
                "java.nio.file.Files.readString(java.nio.file.Path.of(opaque("
                'input.getParameter("name"))));'
            ),
            "String opaque(String value){return external(value);}",
        ),
    ),
    (
        "SEC005",
        "JAVA",
        java("new java.io.ObjectInputStream(input.getInputStream()).readObject();"),
        java('String value=input.getParameter("q");'),
        java(
            "java.io.InputStream stream=opaque(); new java.io.ObjectInput"
            "Stream(stream).readObject();"
        ),
    ),
    (
        "SEC006",
        "TYPESCRIPT",
        ts("http.get(String(input.query.url));", 'import http from "node:http";'),
        ts('http.get("https://docs.invalid/manual");', 'import http from "node:http";'),
        ts("http.get(opaque(String(input.query.url)));", 'import http from "node:http";'),
    ),
    (
        "SEC007",
        "TYPESCRIPT",
        ts("document.body.innerHTML=String(input.query.message);"),
        ts("document.body.textContent=String(input.query.message);"),
        ts("document.body.innerHTML=opaque(String(input.query.message));"),
    ),
    (
        "SEC008",
        "TYPESCRIPT",
        'import crypto from "node:crypto"; crypto.createCipheriv("des","key","iv");',
        'import crypto from "node:crypto"; crypto.createHash("sha256");',
        'import crypto from "node:crypto"; crypto.createCipheriv(opaque(),"key","iv");',
    ),
    (
        "SEC009",
        "TYPESCRIPT",
        "const sessionToken=String(Math.random());",
        "const simulation=String(Math.random());",
        "const sessionToken=opaque(String(Math.random()));",
    ),
    (
        "SEC010",
        "TYPESCRIPT",
        ts("eval(String(input.query.code));"),
        ts('eval("2+3");'),
        ts("eval(opaque(String(input.query.code)));"),
    ),
]


@pytest.mark.parametrize("rule,language,unsafe,safe,ambiguous", CASES, ids=[c[0] for c in CASES])
def test_rule_safe_unsafe_ambiguous(rule, language, unsafe, safe, ambiguous):
    def outcome(source):
        result = analyze(source, language, rule, analyzer=SecurityAnalyzerV3())
        return map_v3_outcome(result.model_dump(mode="json"), rule, language)

    assert outcome(unsafe) == "DEFINITIVE_POSITIVE"
    assert outcome(safe) not in {"DEFINITIVE_POSITIVE", "FAILED"}
    assert outcome(ambiguous) not in {"DEFINITIVE_POSITIVE", "DEFINITIVE_NEGATIVE", "FAILED"}


def complete_result():
    return analyze(CASES[7][3], rule="SEC008", analyzer=SecurityAnalyzerV3()).model_dump(
        mode="json"
    )


def test_completeness_required_for_negative_and_version_separation():
    result = complete_result()
    assert map_v3_outcome(result, "SEC008", "TYPESCRIPT") == "DEFINITIVE_NEGATIVE"
    assert result["analyzer_version"] != SecurityAnalyzerV2.version
    result["analysis_metadata"].pop("completeness_certificates")
    assert map_v3_outcome(result, "SEC008", "TYPESCRIPT") == "PARTIAL"


@pytest.mark.parametrize(
    "field",
    [
        "applicable",
        "scope_complete",
        "source_coverage_complete",
        "sink_coverage_complete",
        "call_resolution_complete",
        "summary_resolution_complete",
        "dataflow_scope_complete",
        "framework_model_complete",
        "proofs_sufficient",
        "unsupported_constructs_present",
        "analysis_failures_present",
    ],
)
def test_certificate_invalidation_schema(field):
    cert = complete_result()["analysis_metadata"]["completeness_certificates"]["SEC008"]
    cert[field] = not cert[field]
    with pytest.raises(ValueError):
        CompletenessCertificate.model_validate(cert)


@pytest.mark.parametrize("code", ["CALL_UNRESOLVED", "UNSUPPORTED_FRAMEWORK", "ANALYSIS_ERROR"])
def test_unresolved_framework_failure_invalidates_negative(code):
    result = complete_result()
    result["diagnostics"].append(dict(code=code))
    with pytest.raises(ValueError):
        map_v3_outcome(result, "SEC008", "TYPESCRIPT")


@pytest.mark.parametrize(
    "tail",
    [
        "opaque();",
        "crypto.createHash(opaque());",
        "eval(opaque());",
        'if (opaque()) crypto.createHash("md5");',
        'crypto.createCipheriv("des","key","iv");',
    ],
)
def test_closed_grammar_rejects_unmodeled_constructs(tail):
    result = analyze(CASES[7][3] + tail, rule="SEC008", analyzer=SecurityAnalyzerV3())
    cert = result.analysis_metadata["completeness_certificates"]["SEC008"]
    assert cert["certificate_status"] == "NOT_PROVEN"


def test_positive_detection_does_not_require_complete_certificate():
    result = analyze(CASES[1][2], rule="SEC002", analyzer=SecurityAnalyzerV3()).model_dump(
        mode="json"
    )
    result["analysis_metadata"].pop("completeness_certificates")
    assert map_v3_outcome(result, "SEC002", "TYPESCRIPT") == "DEFINITIVE_POSITIVE"


def test_java_path_component_guard_and_proof_invalidation():
    """DEV-derived minimal structural regression; identities and literals replaced."""
    prefix = (
        'java.nio.file.Path base=java.nio.file.Path.of("/opt/content")'
        ".toAbsolutePath().normalize();"
        'java.nio.file.Path file=base.resolve(input.getParameter("file")).normalize();'
        "if (!file.startsWith(base)) return;"
    )
    safe = analyze(
        java(prefix + "java.nio.file.Files.readString(file);"),
        "JAVA",
        "SEC004",
        analyzer=SecurityAnalyzerV3(),
    )
    assert not safe.findings
    assert "PATH_CONFINEMENT" in {p["kind"] for p in safe.analysis_metadata["proofs"]}
    unsafe = analyze(
        java(
            prefix + 'file=java.nio.file.Path.of(input.getParameter("other"));'
            "java.nio.file.Files.readString(file);"
        ),
        "JAVA",
        "SEC004",
        analyzer=SecurityAnalyzerV3(),
    )
    assert unsafe.findings


def test_primitive_java_randomness_conversion():
    code = java("String token=String.valueOf(Double.toString(Math.random()));")
    assert analyze(code, "JAVA", "SEC009", analyzer=SecurityAnalyzerV3()).findings


def test_certificate_rule_and_language_binding():
    for key, value in [("language", "JAVA"), ("rule_id", "SEC002")]:
        result = complete_result()
        result["analysis_metadata"]["completeness_certificates"]["SEC008"][key] = value
        with pytest.raises(ValueError):
            map_v3_outcome(result, "SEC008", "TYPESCRIPT")


def test_java_jdbc_script_api_types_and_fully_qualified_shadowing():
    sql = java(
        'Object db=connection(); db.createStatement().executeQuery(input.getParameter("query"));'
    )
    script = java(
        'new javax.script.ScriptEngineManager().getEngineByName("java'
        'script").eval(input.getParameter("code"));'
    )
    # An unknown database factory must not acquire a trusted receiver type.
    assert not analyze(sql, "JAVA", "SEC002", analyzer=SecurityAnalyzerV3()).findings
    assert analyze(script, "JAVA", "SEC010", analyzer=SecurityAnalyzerV3()).findings
    jdbc = JAVA + (
        "class Example { void f(HttpServletRequest input, java.sql.Co"
        "nnection db) throws Exception { db.createStatement().execute"
        '(input.getParameter("q")); }}'
    )
    assert analyze(jdbc, "JAVA", "SEC002", analyzer=SecurityAnalyzerV3()).findings


def test_interprocedural_objects_and_new_taint_after_sanitizer():
    source = (
        ts("const box={value:relay(String(input.query.q))}; eval(box.value);")
        + "function relay(value:string){return value;}"
    )
    result = analyze(source, rule="SEC010", analyzer=SecurityAnalyzerV3())
    assert result.findings
    source = ts(
        (
            "let html=DOMPurify.sanitize(String(input.query.q)); html=htm"
            "l+String(input.query.more); document.body.innerHTML=html;"
        ),
        'import DOMPurify from "dompurify";',
    )
    assert analyze(source, rule="SEC007", analyzer=SecurityAnalyzerV3()).findings


def test_recursion_bounds_and_ts_deserialization_honesty():
    source = (
        ts("eval(loop(String(input.query.q)));") + "function loop(x:string):string{return loop(x);}"
    )
    result = analyze(source, rule="SEC010", analyzer=SecurityAnalyzerV3())
    assert any("RECURSION" in d.code for d in result.diagnostics)
    limited = analyze(
        CASES[1][2],
        rule="SEC002",
        limits=V2Limits(max_total_nodes=1),
        analyzer=SecurityAnalyzerV3(V2Limits(max_total_nodes=1)),
    )
    assert any("LIMIT" in d.code for d in limited.diagnostics)
    result = analyze('JSON.parse("{}");', rule="SEC005", analyzer=SecurityAnalyzerV3())
    assert map_v3_outcome(result.model_dump(mode="json"), "SEC005", "TYPESCRIPT") == "UNSUPPORTED"


def test_shadowed_string_does_not_preserve_known_taint():
    source = ts("const String=(v:unknown)=>opaque(v); eval(String(input.query.q));")
    result = analyze(source, rule="SEC010", analyzer=SecurityAnalyzerV3())
    assert (
        map_v3_outcome(result.model_dump(mode="json"), "SEC010", "TYPESCRIPT")
        != "DEFINITIVE_POSITIVE"
    )


@pytest.mark.parametrize(
    "path",
    [
        "FINAL/truth.json",
        "reviews/A.json",
        "adjudication.json",
        "coordinator/intent.json",
        "../truth.json",
    ],
)
def test_final_intent_and_review_fence(tmp_path, path):
    fence = SourceFence(tmp_path, manifest())
    with pytest.raises(ValueError):
        fence.source(path)
    with pytest.raises(PermissionError):
        fence.audit("open", (str(tmp_path / path), "r", 0))


def test_anti_memorization_and_private_exclusion():
    assert all(v == 0 for v in stage.anti_memorization().values())
    assert (
        subprocess.run(["git", "check-ignore", "-q", str(stage.PRIVATE / "probe")]).returncode == 0
    )
    assert not subprocess.check_output(["git", "ls-files", "--", str(stage.PRIVATE)])


@pytest.mark.parametrize(
    "source",
    [
        'if case_id == "sample": pass',
        'if filename == "Unit' + "0123" * 4 + '": pass',
        'if source_hash == "' + "a" * 64 + '": pass',
        'if split == "DEV": pass',
    ],
)
def test_memorization_guard_rejects_identity_branches(tmp_path, monkeypatch, source):
    path = tmp_path / "candidate.py"
    path.write_text(source)
    monkeypatch.setattr(stage, "DETECTOR_SOURCES", (str(path),))
    with pytest.raises(ValueError, match="MEMORIZATION"):
        stage.anti_memorization()


@pytest.mark.parametrize(
    "relative",
    [
        "experiments/security/security-human-review-v1/private/truth/FINAL/truth.json",
        "experiments/security/security-human-review-v1/private/reviews/A.json",
        "experiments/security/security-human-review-v1/private/adjudication.json",
        "experiments/security/security-benchmark-v1/private/coordinator/intent.json",
        ".env",
    ],
)
def test_parent_custody_guard_denies_before_open(relative):
    with pytest.raises(PermissionError):
        stage.access_guard("open", (str(Path.cwd() / relative), "r", 0))


def test_parent_guard_denies_connectivity():
    with pytest.raises(PermissionError):
        stage.access_guard("socket.connect", ())


def test_public_privacy():
    stage.safety.privacy(tuple(stage.PUBLIC.glob("*.json")))


def test_frozen_dev_full_cohort_and_replay_if_present():
    path = stage.PRIVATE / "selected-replay/registry.json"
    if not path.exists():
        pytest.skip("Selected DEV candidate not yet frozen")
    registry = stage.io.read_seal(path)
    raw = stage.io.read_seal(path.with_name("raw.json"))
    first = stage.evaluate(raw, registry)
    assert first == stage.evaluate(raw, registry)
    assert first["primary"]["N"] == 100 and first["primary"]["binary_eligible"] == 89
    assert len(first["rules"]["groups"]) == 10
    assert set(first["languages"]["groups"]) == {"JAVA", "TYPESCRIPT"}
    assert first["primary"]["truth_distribution"]["UNCERTAIN"] == 11
    assert first["primary"]["FP"] == 0


@pytest.mark.parametrize(
    "root,name",
    [
        (stage.v2.ROOT, "freeze-index.json"),
        (stage.baseline.PUBLIC, "freeze-index.json"),
    ],
)
def test_historical_byte_immutability(root, name):
    index = stage.io.read_seal(root / name)
    for path, expected in index["files"].items():
        assert stage.io.sha(root / path) == expected
    for path, expected in (index["source_bindings"] | index["documents"]).items():
        assert stage.io.sha(Path(path)) == expected
