"""Initial tested API packs; identity resolution and conditions are part of the contract."""

from typing import Literal

from archguard.core.model.base import DomainModel
from archguard.security.domain import SecurityLanguage, SecurityRuleId
from archguard.security.flow_v1 import VERSION

APIRole = Literal["SOURCE", "SINK", "SANITIZER", "SECURITY_SENSITIVE_API", "PROPAGATION"]


class APIEntry(DomainModel):
    id: str
    language: SecurityLanguage
    qualified_api: str
    role: APIRole
    rule_ids: tuple[SecurityRuleId, ...]
    argument_semantics: str
    receiver_semantics: str
    return_semantics: str
    conditions: str
    limitations: tuple[str, ...] = (
        "Explicit imports/types and local aliases only; no whole-program resolution",
        "No framework callbacks, wildcard imports, reflection or dynamic dispatch resolution",
    )
    version: str = VERSION
    engineering_test_binding: str = "tests/security/test_analysis_v1.py"


FLOW_RULES = tuple(SecurityRuleId(f"SEC{i:03}") for i in (2, 3, 4, 6, 7, 10))


def entries() -> tuple[APIEntry, ...]:
    rows: tuple[
        tuple[str, str, str, APIRole, tuple[SecurityRuleId, ...], str, str, str, str], ...
    ] = (
        (
            "j.request",
            "JAVA",
            "javax.servlet.http.HttpServletRequest|jakarta.servlet.http.HttpServletRequest.getParameter/getHeader/getQueryString/getPathInfo",
            "SOURCE",
            FLOW_RULES,
            "Selector does not sanitize",
            "Explicit imported servlet request parameter",
            "TAINTED",
            "Exact receiver type",
        ),
        (
            "t.request",
            "TYPESCRIPT",
            "express.Request.query/params/body/headers",
            "SOURCE",
            FLOW_RULES,
            "Static property projection",
            "Explicit imported Request parameter",
            "TAINTED",
            "No arbitrary req/object heuristic",
        ),
        (
            "j.sql",
            "JAVA",
            "java.sql.Statement.execute/executeQuery/executeUpdate",
            "SINK",
            (SecurityRuleId.SEC002,),
            "SQL text argument 0",
            "Explicit Statement type",
            "UNKNOWN",
            "PreparedStatement bind arguments are not SQL text",
        ),
        (
            "t.sql",
            "TYPESCRIPT",
            "pg.Client.query|pg.Pool.query",
            "SINK",
            (SecurityRuleId.SEC002,),
            "SQL text argument 0; parameters ignored",
            "Imported pg Client/Pool type",
            "UNKNOWN",
            "Only string query forms",
        ),
        (
            "j.exec",
            "JAVA",
            "java.lang.Runtime.exec|java.lang.ProcessBuilder.start",
            "SINK",
            (SecurityRuleId.SEC003,),
            "Runtime command 0 / ProcessBuilder executable element 0",
            "Resolved platform receiver",
            "UNKNOWN",
            "Argument-vector operands do not imply shell injection",
        ),
        (
            "t.exec",
            "TYPESCRIPT",
            "node:child_process.exec/execSync/spawn/spawnSync",
            "SINK",
            (SecurityRuleId.SEC003,),
            "Command 0; shell=true also evaluates argument vector",
            "Explicit import",
            "UNKNOWN",
            "Shell option must be literal; unknown options give partial analysis",
        ),
        (
            "j.path",
            "JAVA",
            "java.nio.file.Files.readAllBytes/readString/newInputStream",
            "SINK",
            (SecurityRuleId.SEC004,),
            "Path argument 0",
            "Explicit imported Files",
            "UNKNOWN",
            "No path confinement proof in initial pack",
        ),
        (
            "t.path",
            "TYPESCRIPT",
            "node:fs.readFile/readFileSync/createReadStream",
            "SINK",
            (SecurityRuleId.SEC004,),
            "Path argument 0",
            "Explicit import",
            "UNKNOWN",
            "No path confinement proof in initial pack",
        ),
        (
            "j.path-build",
            "JAVA",
            "java.nio.file.Paths.get|java.nio.file.Path.normalize/resolve",
            "PROPAGATION",
            (SecurityRuleId.SEC004,),
            "Merge path components",
            "Imported API / typed Path",
            "Propagate; never sanitize",
            "Normalization does not prove confinement",
        ),
        (
            "t.path-build",
            "TYPESCRIPT",
            "node:path.join/resolve/normalize",
            "PROPAGATION",
            (SecurityRuleId.SEC004,),
            "Merge path components",
            "Explicit import",
            "Propagate; never sanitize",
            "Normalization does not prove confinement",
        ),
        (
            "j.deserialize",
            "JAVA",
            "java.io.ObjectInputStream.readObject/readUnshared",
            "SINK",
            (SecurityRuleId.SEC005,),
            "No direct data argument",
            "Locally constructed ObjectInputStream without observed filter",
            "UNKNOWN",
            "Explicit unsafe serialization pattern; not JSON/Jackson",
        ),
        (
            "j.http",
            "JAVA",
            "java.net.URL.openConnection/openStream",
            "SINK",
            (SecurityRuleId.SEC006,),
            "URL constructor argument",
            "Locally constructed URL",
            "UNKNOWN",
            "No DNS/redirect/allowlist guarantee",
        ),
        (
            "t.http",
            "TYPESCRIPT",
            "node:http.get/request|node:https.get/request",
            "SINK",
            (SecurityRuleId.SEC006,),
            "URL argument 0",
            "Explicit server-side import",
            "UNKNOWN",
            "URL strings only; options objects unsupported",
        ),
        (
            "j.html",
            "JAVA",
            "javax.servlet.jsp.JspWriter.write/print|jakarta.servlet.jsp.JspWriter.write/print",
            "SINK",
            (SecurityRuleId.SEC007,),
            "HTML output argument 0",
            "Explicit typed JSP writer",
            "UNKNOWN",
            "Other rendering frameworks and generic Writer unsupported",
        ),
        (
            "t.html",
            "TYPESCRIPT",
            "HTMLElement.innerHTML/outerHTML",
            "SINK",
            (SecurityRuleId.SEC007,),
            "Assigned HTML value",
            "DOM typed parameter or document.getElementById/querySelector result",
            "UNKNOWN",
            "No framework render/DOM wrapper modeling",
        ),
        (
            "t.escape",
            "TYPESCRIPT",
            "dompurify.sanitize",
            "SANITIZER",
            (SecurityRuleId.SEC007,),
            "Input 0; default options only",
            "Explicit default/namespace DOMPurify import",
            "SANITIZED for SEC007 only",
            "No custom options, wrappers or downstream DOM mutation modeling",
        ),
        (
            "j.crypto",
            "JAVA",
            "java.security.MessageDigest.getInstance|javax.crypto.Cipher.getInstance",
            "SECURITY_SENSITIVE_API",
            (SecurityRuleId.SEC008,),
            "Algorithm literal 0",
            "Explicit platform import",
            "UNKNOWN",
            "MD5/SHA-1 and DES/RC4; security-purpose symbol needed; unclear purpose POTENTIAL",
        ),
        (
            "t.crypto",
            "TYPESCRIPT",
            "node:crypto.createHash/createCipheriv",
            "SECURITY_SENSITIVE_API",
            (SecurityRuleId.SEC008,),
            "Algorithm literal 0",
            "Explicit import",
            "UNKNOWN",
            "MD5/SHA-1 and DES/RC4; security-purpose symbol needed; unclear purpose POTENTIAL",
        ),
        (
            "j.random",
            "JAVA",
            "java.util.Random.nextInt/nextLong/nextDouble|java.lang.Math.random",
            "SECURITY_SENSITIVE_API",
            (SecurityRuleId.SEC009,),
            "No taint required",
            "Exact platform type",
            "UNTAINTED",
            "Security-purpose receiving symbol required; no filename heuristic",
        ),
        (
            "t.random",
            "TYPESCRIPT",
            "Math.random",
            "SECURITY_SENSITIVE_API",
            (SecurityRuleId.SEC009,),
            "No taint required",
            "Unshadowed built-in Math",
            "UNTAINTED",
            "Security-purpose receiving symbol required; no filename heuristic",
        ),
        (
            "j.eval",
            "JAVA",
            "javax.script.ScriptEngine.eval",
            "SINK",
            (SecurityRuleId.SEC010,),
            "Code argument 0",
            "Explicit imported ScriptEngine type",
            "UNKNOWN",
            "Reflection is not dynamic execution",
        ),
        (
            "t.eval",
            "TYPESCRIPT",
            "eval|Function|setTimeout|setInterval|node:vm.runInNewContext/runInThisContext/runInContext",
            "SINK",
            (SecurityRuleId.SEC010,),
            "Code 0; Function body is final argument",
            "Unshadowed built-in or explicit vm import",
            "UNKNOWN",
            "Only proven string code; callback timers are not sinks",
        ),
    )
    return tuple(
        APIEntry(
            id=row[0],
            language=SecurityLanguage(row[1]),
            qualified_api=row[2],
            role=row[3],
            rule_ids=row[4],
            argument_semantics=row[5],
            receiver_semantics=row[6],
            return_semantics=row[7],
            conditions=row[8],
        )
        for row in rows
    )


def supported_rules(language: SecurityLanguage) -> tuple[SecurityRuleId, ...]:
    return tuple(
        r for r in SecurityRuleId if language == SecurityLanguage.JAVA or r != SecurityRuleId.SEC005
    )
