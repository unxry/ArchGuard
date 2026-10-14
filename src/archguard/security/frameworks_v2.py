"""Explicit, test-bound framework packs and rule-specific proof preconditions."""

from archguard.core.model.base import DomainModel
from archguard.security.api_v1 import APIEntry, entries
from archguard.security.domain import SecurityLanguage, SecurityRuleId
from archguard.security.summaries_v2 import VERSION, ProofKind


class FrameworkPack(DomainModel):
    pack_id: str
    language: SecurityLanguage
    framework: str
    scope: str = "Version-agnostic declared AST/API subset; not an ecosystem version guarantee"
    apis: tuple[APIEntry, ...]
    safe_boundaries: tuple[ProofKind, ...] = ()
    limitations: tuple[str, ...]
    implementation_paths: tuple[str, ...] = ("src/archguard/security/engine_v2.py",)
    tests: tuple[str, ...] = ("tests/security/test_analysis_v2.py",)
    version: str = VERSION


class ProofDefinition(DomainModel):
    kind: ProofKind
    rules: tuple[SecurityRuleId, ...]
    languages: tuple[SecurityLanguage, ...]
    preconditions: tuple[str, ...]
    invalidators: tuple[str, ...]
    limitations: tuple[str, ...]
    tests: str = "tests/security/test_analysis_v2.py"


def packs() -> tuple[FrameworkPack, ...]:
    old = {
        e.id: e.model_copy(
            update={
                "version": VERSION,
                "engineering_test_binding": "tests/security/test_analysis_v2.py",
            }
        )
        for e in entries()
    }
    specs = (
        ("JAVA_SERVLET_V2", "JAVA", "javax/jakarta Servlet", ("j.request",), ()),
        ("JAVA_JDBC_V2", "JAVA", "JDBC", ("j.sql",), (ProofKind.SQL_PARAMETERIZATION,)),
        ("JAVA_HTTP_V2", "JAVA", "java.net.URL", ("j.http",), (ProofKind.SSRF_ALLOWLIST,)),
        (
            "JAVA_FILESYSTEM_V2",
            "JAVA",
            "java.nio.file",
            ("j.path", "j.path-build"),
            (ProofKind.PATH_CONFINEMENT,),
        ),
        ("JAVA_CRYPTO_V2", "JAVA", "java.security/javax.crypto", ("j.crypto", "j.random"), ()),
        (
            "JAVA_PROCESS_V2",
            "JAVA",
            "java.lang process APIs",
            ("j.exec",),
            (ProofKind.COMMAND_ARGUMENT_BOUNDARY,),
        ),
        ("JAVA_SERIALIZATION_V2", "JAVA", "java.io.ObjectInputStream", ("j.deserialize",), ()),
        ("JAVA_RENDER_SCRIPT_V2", "JAVA", "JSP/ScriptEngine", ("j.html", "j.eval"), ()),
        ("TS_EXPRESS_V2", "TYPESCRIPT", "express.Request", ("t.request",), ()),
        ("TS_PG_V2", "TYPESCRIPT", "pg", ("t.sql",), (ProofKind.SQL_PARAMETERIZATION,)),
        (
            "TS_NODE_HTTP_V2",
            "TYPESCRIPT",
            "node:http/https + WHATWG URL",
            ("t.http",),
            (ProofKind.SSRF_ALLOWLIST,),
        ),
        (
            "TS_NODE_FS_V2",
            "TYPESCRIPT",
            "node:fs/path (POSIX lexical scope)",
            ("t.path", "t.path-build"),
            (ProofKind.PATH_CONFINEMENT,),
        ),
        (
            "TS_DOM_V2",
            "TYPESCRIPT",
            "DOM/DOMPurify",
            ("t.html", "t.escape"),
            (ProofKind.XSS_SANITIZATION,),
        ),
        ("TS_NODE_CRYPTO_V2", "TYPESCRIPT", "node:crypto + Math", ("t.crypto", "t.random"), ()),
        (
            "TS_PROCESS_SCRIPT_V2",
            "TYPESCRIPT",
            "node:child_process/vm + built-in code evaluation",
            ("t.exec", "t.eval"),
            (ProofKind.COMMAND_ARGUMENT_BOUNDARY,),
        ),
    )
    extra = (
        APIEntry(
            id="j.stream-source",
            language=SecurityLanguage.JAVA,
            qualified_api="javax/jakarta.servlet.http.HttpServletRequest.getInputStream",
            role="SOURCE",
            rule_ids=(SecurityRuleId.SEC005,),
            argument_semantics="None",
            receiver_semantics="Imported typed Servlet request",
            return_semantics="Tainted InputStream",
            conditions="Exact typed receiver",
            version=VERSION,
            engineering_test_binding="tests/security/test_analysis_v2.py",
        ),
        APIEntry(
            id="j.prepared",
            language=SecurityLanguage.JAVA,
            qualified_api=(
                "java.sql.Connection.prepareStatement / PreparedStatement.setString/executeQuery"
            ),
            role="SINK",
            rule_ids=(SecurityRuleId.SEC002,),
            argument_semantics="SQL text at construction; separate bind values",
            receiver_semantics="Imported JDBC types",
            return_semantics="Track constant template; no generic sanitation",
            conditions="Constant template plus separate bind transport for positive proof",
            version=VERSION,
            engineering_test_binding="tests/security/test_analysis_v2.py",
        ),
        APIEntry(
            id="t.prisma-unsafe",
            language=SecurityLanguage.TYPESCRIPT,
            qualified_api="@prisma/client.PrismaClient.$queryRawUnsafe/$executeRawUnsafe",
            role="SINK",
            rule_ids=(SecurityRuleId.SEC002,),
            argument_semantics="SQL text argument 0",
            receiver_semantics="Explicit imported PrismaClient type",
            return_semantics="UNKNOWN",
            conditions="Only explicitly unsafe string-query API subset",
            version=VERSION,
            engineering_test_binding="tests/security/test_analysis_v2.py",
        ),
        APIEntry(
            id="j.spring",
            language=SecurityLanguage.JAVA,
            qualified_api="org.springframework.web.bind.annotation.RequestParam/PathVariable/RequestHeader/RequestBody",
            role="SOURCE",
            rule_ids=tuple(SecurityRuleId(f"SEC{i:03}") for i in (2, 3, 4, 6, 7, 10)),
            argument_semantics="Annotated scalar method parameter",
            receiver_semantics="Exact annotation import",
            return_semantics="Tainted scalar binding",
            conditions="String/primitive scalar only; DTO/model binding UNKNOWN",
            version=VERSION,
            engineering_test_binding="tests/security/test_analysis_v2.py",
        ),
    )
    result = []
    for id, lang, framework, keys, proofs in specs:
        apis = tuple(old[k] for k in keys)
        if id == "JAVA_SERVLET_V2":
            apis += extra[:1]
        if id == "JAVA_JDBC_V2":
            apis += extra[1:2]
        result.append(
            FrameworkPack(
                pack_id=id,
                language=SecurityLanguage(lang),
                framework=framework,
                apis=apis,
                safe_boundaries=proofs,
                limitations=(
                    "Explicit imports/types; no wildcard, dynamic or compiler-complete resolution",
                    "Bounded summaries; no arbitrary framework, closure or heap semantics",
                ),
            )
        )
    result.append(
        FrameworkPack(
            pack_id="JAVA_SPRING_WEB_V2",
            language=SecurityLanguage.JAVA,
            framework="Spring Web scalar annotations",
            apis=extra[3:],
            limitations=(
                "Imported scalar annotations only; no DTO/model/controller lifecycle inference",
            ),
        )
    )
    result.append(
        FrameworkPack(
            pack_id="TS_PRISMA_RAW_UNSAFE_V2",
            language=SecurityLanguage.TYPESCRIPT,
            framework="PrismaClient explicit unsafe APIs",
            apis=extra[2:3],
            limitations=("No tagged-template/Prisma.sql/raw fragment proof claimed",),
        )
    )
    return tuple(sorted(result, key=lambda p: p.pack_id))


def proofs() -> tuple[ProofDefinition, ...]:
    rows = (
        (
            ProofKind.SQL_PARAMETERIZATION,
            SecurityRuleId.SEC002,
            (
                "Constant query template",
                "Bind values transported separately by declared JDBC/pg API",
            ),
            (
                "Query text gains taint",
                "Unknown wrapper or query object",
                "Different prepared statement",
            ),
            ("Not generic escaping; no dynamic ORM/query-builder safety proof",),
        ),
        (
            ProofKind.PATH_CONFINEMENT,
            SecurityRuleId.SEC004,
            (
                "Trusted absolute canonical root",
                "Canonical path derived from that root",
                "Dominating boundary-aware rejecting containment guard",
                "Same immutable path reaches sink",
            ),
            (
                "Path mutation/concat",
                "Different variable/root",
                "Unknown transformation",
                "Dynamic field mutation",
            ),
            ("Lexical POSIX/Java Path containment; no symlink, race or realpath guarantee",),
        ),
        (
            ProofKind.SSRF_ALLOWLIST,
            SecurityRuleId.SEC006,
            (
                "Parsed URL identity",
                "Exact static host equality/membership",
                "Reject nonmatching host",
                "Same unmodified URL reaches sink",
            ),
            (
                "URL mutation",
                "Different URL",
                "Unknown transformation",
                "Substring/suffix/regex/scheme-only test",
            ),
            ("No DNS/IP rebinding, redirects or comprehensive port/scheme policy guarantee",),
        ),
        (
            ProofKind.XSS_SANITIZATION,
            SecurityRuleId.SEC007,
            (
                "Imported DOMPurify.sanitize with default options",
                "Proven return relation and HTML sink context",
            ),
            ("New taint", "Unknown transformation/options", "Different output context"),
            ("DOM HTML subset only; no script/attribute/template-engine guarantee",),
        ),
        (
            ProofKind.COMMAND_ARGUMENT_BOUNDARY,
            SecurityRuleId.SEC003,
            ("Constant executable", "Separate argument vector", "Known shell=false/default"),
            ("shell=true/unknown", "Tainted executable", "Unknown process wrapper"),
            ("No modeled shell interpolation; operands remain POTENTIAL argument injection",),
        ),
    )
    return tuple(
        ProofDefinition(
            kind=k,
            rules=(rule,),
            languages=tuple(SecurityLanguage),
            preconditions=pre,
            invalidators=inv,
            limitations=lim,
        )
        for k, rule, pre, inv, lim in rows
    )
