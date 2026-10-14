"""Controlled source construction. Intent is private design metadata, never human truth.

No detector import, execution, filtering, external code or source execution.
"""

import hashlib
import re
from typing import Any

from archguard.benchmark.oss.models import digest

VERSION = "security-controlled-generator-v1"

# Every numbered shape is a separate family; first five are DEV, remaining ten FINAL.
SHAPES = (
    "direct-local",
    "return-helper",
    "local-record",
    "conditional-source",
    "opaque-wrapper",
    "constructor-field",
    "two-return-helpers",
    "separate-module",
    "field-alias",
    "indexed-container",
    "caller-to-sink-helper",
    "branch-merge",
    "nested-field",
    "callback-boundary",
    "parameter-copy",
)


def java_bodies(rule: int, intent: bool, n: int) -> tuple[str, str]:
    """Syntax-valid inert snippets; unresolved custom wrappers are explicitly supplied."""
    secret = "sk-proj-" + digest(dict(namespace=VERSION, slot=n, literal="fabricated"))
    bodies: dict[int, tuple[list[str], list[str], str]] = {
        1: (
            [
                f'String apiKey = "{secret}"; res.getWriter().print(apiKey);',
                'String privateKey = "-----BEGIN PRIVATE KEY-----\\nM'
                + digest([VERSION, n])
                + '\\n-----END PRIVATE KEY-----"; res.getWriter().print(privateKey);',
                'String password = "'
                + digest([VERSION, "password", n])[:32]
                + '"; res.getWriter().print(password);',
            ],
            [
                (
                    'String publicId = "d9428888-122b-4dad-a927-862cabef09e8"; '
                    "res.getWriter().print(publicId);"
                ),
                'String apiKey = "YOUR_API_KEY"; res.getWriter().print(apiKey);',
                'String checksum = "'
                + digest([VERSION, "checksum", n])
                + '"; res.getWriter().print(checksum);',
            ],
            "Servlet source/config",
        ),
        2: (
            [
                'db.createStatement().executeQuery("SELECT title FROM records WHERE id=" + x);',
                (
                    'String q = "DELETE FROM records WHERE key=" + x; '
                    "db.createStatement().executeUpdate(q);"
                ),
                'db.createStatement().execute("SELECT " + x + " FROM records");',
            ],
            [
                (
                    'java.sql.PreparedStatement p = db.prepareStatement("SELECT title FROM '
                    'records WHERE id=?"); p.setString(1,x); p.executeQuery();'
                ),
                'db.createStatement().executeQuery("SELECT title FROM records WHERE id=3");',
                (
                    'java.sql.PreparedStatement p = db.prepareStatement("UPDATE records '
                    'SET title=? WHERE id=3"); p.setString(1,x); p.executeUpdate();'
                ),
            ],
            "Servlet/JDBC",
        ),
        3: (
            [
                'Runtime.getRuntime().exec("sh -c " + x);',
                'new ProcessBuilder("sh", "-c", x).start();',
                "new ProcessBuilder(x).start();",
                'new ProcessBuilder("sh", "-c", "printf " + x).start();',
            ],
            [
                'new ProcessBuilder("printf", "%s", "ready").start();',
                'new ProcessBuilder("/usr/bin/printf", "%s", x).start();',
                'Runtime.getRuntime().exec("/usr/bin/true");',
            ],
            "Servlet/Java process",
        ),
        4: (
            [
                "java.nio.file.Files.readString(java.nio.file.Path.of(x));",
                (
                    "java.nio.file.Path p = "
                    'java.nio.file.Path.of("/srv/files").resolve(x).normalize(); '
                    "java.nio.file.Files.readAllBytes(p);"
                ),
                (
                    "java.nio.file.Path a = "
                    'java.nio.file.Path.of("/srv/files").toAbsolutePath().normalize(); '
                    "java.nio.file.Path p = a.resolve(x).normalize(); if "
                    "(!p.startsWith(a)) return; "
                    "java.nio.file.Files.readString(java.nio.file.Path.of(req.getParameter("
                    '"other")));'
                ),
            ],
            [
                (
                    "java.nio.file.Path root = "
                    'java.nio.file.Path.of("/srv/files").toAbsolutePath().normalize(); '
                    "java.nio.file.Path p = root.resolve(x).normalize(); if "
                    "(!p.startsWith(root)) return; java.nio.file.Files.readString(p);"
                ),
                'java.nio.file.Files.readString(java.nio.file.Path.of("/srv/files/catalog.txt"));',
                (
                    "java.nio.file.Path p = "
                    'java.nio.file.Path.of("/srv/files/catalog.txt"); '
                    "java.nio.file.Files.readAllBytes(p);"
                ),
            ],
            "Servlet/java.nio.file",
        ),
        5: (
            [
                (
                    "java.io.ObjectInputStream p = new "
                    "java.io.ObjectInputStream(req.getInputStream()); p.readObject();"
                ),
                (
                    "byte[] bytes = x.getBytes(java.nio.charset.StandardCharsets.UTF_8); "
                    "java.io.ObjectInputStream p = new java.io.ObjectInputStream(new "
                    "java.io.ByteArrayInputStream(bytes)); p.readObject();"
                ),
                "java.io.InputStream s = req.getInputStream(); read(s);",
            ],
            [
                (
                    "new java.io.ObjectInputStream(new java.io.ByteArrayInputStream(new "
                    "byte[]{1,2,3})).readObject();"
                ),
                (
                    "com.fasterxml.jackson.databind.ObjectMapper mapper = new "
                    "com.fasterxml.jackson.databind.ObjectMapper(); mapper.readTree(x);"
                ),
                (
                    "String value = new String(new byte[]{1,2,3}, "
                    "java.nio.charset.StandardCharsets.UTF_8); "
                    "res.getWriter().print(value.length());"
                ),
            ],
            "Servlet/Java serialization or Jackson tree",
        ),
        6: (
            [
                (
                    "java.net.http.HttpRequest p = "
                    "java.net.http.HttpRequest.newBuilder(java.net.URI.create(x)).build(); "
                    "java.net.http.HttpClient.newHttpClient().send(p, "
                    "java.net.http.HttpResponse.BodyHandlers.ofString());"
                ),
                "java.net.URL u = new java.net.URL(x); u.openConnection();",
                (
                    "java.net.URI u = java.net.URI.create(x); if "
                    '(!u.getHost().endsWith("example.invalid")) return; new '
                    "java.net.URL(x).openConnection();"
                ),
                (
                    "java.net.URI a = java.net.URI.create(x); if "
                    '(!"files.example.invalid".equals(a.getHost())) return; new '
                    'java.net.URL(req.getParameter("other")).openConnection();'
                ),
            ],
            [
                'new java.net.URL("https://files.example.invalid/catalog").openConnection();',
                (
                    "java.net.URI u = java.net.URI.create(x); if "
                    '(!"files.example.invalid".equals(u.getHost())) return; '
                    "u.toURL().openConnection();"
                ),
                (
                    'java.net.URL u = new java.net.URL("https://status.example.invalid/"); '
                    "u.openStream();"
                ),
            ],
            "Servlet/Java HTTP/URL",
        ),
        7: (
            [
                'res.setContentType("text/html"); res.getWriter().write(x);',
                'String page = "<article>" + x + "</article>"; res.getWriter().print(page);',
                "res.getWriter().write(render(x));",
            ],
            [
                'res.setContentType("text/plain"); res.getWriter().write(x);',
                (
                    'res.setContentType("text/html"); '
                    'res.getWriter().write("<article>Welcome</article>");'
                ),
                (
                    'res.setContentType("text/html"); '
                    "res.getWriter().write(org.owasp.encoder.Encode.forHtml(x));"
                ),
            ],
            "Servlet HTML / OWASP Encoder or custom render",
        ),
        8: (
            [
                (
                    'javax.crypto.Cipher c = javax.crypto.Cipher.getInstance("DES"); '
                    "res.getWriter().print(c.getAlgorithm());"
                ),
                (
                    "javax.crypto.Cipher c = "
                    'javax.crypto.Cipher.getInstance("AES/ECB/PKCS5Padding"); '
                    "res.getWriter().print(c.getAlgorithm());"
                ),
                (
                    "java.security.MessageDigest d = "
                    'java.security.MessageDigest.getInstance("MD5"); byte[] passwordHash = '
                    "d.digest(x.getBytes()); res.getWriter().print(passwordHash.length);"
                ),
                (
                    'javax.crypto.Cipher c = javax.crypto.Cipher.getInstance("RC4"); '
                    "res.getWriter().print(c.getAlgorithm());"
                ),
            ],
            [
                (
                    "javax.crypto.Cipher c = "
                    'javax.crypto.Cipher.getInstance("AES/GCM/NoPadding"); '
                    "res.getWriter().print(c.getAlgorithm());"
                ),
                (
                    "java.security.MessageDigest d = "
                    'java.security.MessageDigest.getInstance("MD5"); byte[] checksum = '
                    'd.digest("catalog".getBytes()); '
                    "res.getWriter().print(checksum.length);"
                ),
                (
                    "java.security.MessageDigest d = "
                    'java.security.MessageDigest.getInstance("SHA-256"); byte[] signature '
                    "= d.digest(x.getBytes()); res.getWriter().print(signature.length);"
                ),
            ],
            "Java JCA: security selection vs checksum",
        ),
        9: (
            [
                (
                    "String resetToken = Double.toString(Math.random()); "
                    "res.getWriter().print(resetToken);"
                ),
                (
                    "String sessionToken = Long.toString(new "
                    "java.util.Random().nextLong()); res.getWriter().print(sessionToken);"
                ),
                "double nonce = Math.random(); res.getWriter().print(nonce);",
            ],
            [
                (
                    "java.security.SecureRandom random = new java.security.SecureRandom(); "
                    "byte[] token = new byte[32]; random.nextBytes(token); "
                    "res.getWriter().print(token.length);"
                ),
                "double simulation = Math.random(); res.getWriter().print(simulation);",
                "int sample = new java.util.Random().nextInt(10); res.getWriter().print(sample);",
            ],
            "Java Random / SecureRandom, declared usage names",
        ),
        10: (
            [
                'new javax.script.ScriptEngineManager().getEngineByName("javascript").eval(x);',
                (
                    "javax.script.ScriptEngine engine = new "
                    'javax.script.ScriptEngineManager().getEngineByName("javascript"); '
                    'engine.eval("print(" + x + ")");'
                ),
                "execute(x);",
            ],
            [
                (
                    "new "
                    'javax.script.ScriptEngineManager().getEngineByName("javascript").eval('
                    '"1 + 2");'
                ),
                "Class.forName(x);",
                "res.getWriter().print(x.length());",
            ],
            "Servlet/JSR223 or reflection",
        ),
    }
    risks, controls, framework = bodies[rule]
    pool = risks if intent else controls
    return pool[(n // 2) % len(pool)], framework


def ts_bodies(rule: int, intent: bool, n: int) -> tuple[str, str, str]:
    secret = "sk-proj-" + digest(
        dict(namespace=VERSION, slot=n, language="TS", literal="fabricated")
    )
    bodies: dict[int, tuple[list[str], list[str], str, str]] = {
        1: (
            [
                f'const apiKey = "{secret}"; res.send(apiKey);',
                'const signingKey = "-----BEGIN PRIVATE KEY-----\\nM'
                + digest([VERSION, n, "TS"])
                + '\\n-----END PRIVATE KEY-----"; res.send(signingKey);',
                'const password = "'
                + digest([VERSION, n, "pass", "TS"])[:32]
                + '"; res.send(password);',
            ],
            [
                'const id = "d9428888-122b-4dad-a927-862cabef09e8"; res.send(id);',
                'const apiKey = "YOUR_API_KEY"; res.send(apiKey);',
                'const label = "Account settings"; res.send(label);',
            ],
            "",
            "Express/config literal",
        ),
        2: (
            [
                'client.query("SELECT title FROM records WHERE id=" + x);',
                "client.query(`DELETE FROM records WHERE key=${x}`);",
                'prisma.$queryRawUnsafe("SELECT " + x + " FROM records");',
                'client.query({text: "SELECT title FROM records WHERE id=" + x});',
            ],
            [
                'client.query("SELECT title FROM records WHERE id=$1", [x]);',
                'client.query("SELECT title FROM records WHERE id=3");',
                'client.query({text:"SELECT title FROM records WHERE id=$1", values:[x]});',
            ],
            (
                'import {Client} from "pg"; import {PrismaClient} from '
                '"@prisma/client"; const client = new Client(); const prisma = new '
                "PrismaClient();"
            ),
            "Express/pg/Prisma raw boundary",
        ),
        3: (
            [
                'exec("printf " + x);',
                'spawn("sh", ["-c", x]);',
                'spawn(x, ["--version"], {shell:false});',
                'execFile("sh", ["-c", x]);',
            ],
            [
                'exec("printf ready");',
                'spawn("/usr/bin/printf", ["%s",x], {shell:false});',
                'execFile("/usr/bin/true", [], {shell:false});',
            ],
            'import {exec, spawn, execFile} from "node:child_process";',
            "Express/Node child_process",
        ),
        4: (
            [
                "fs.readFileSync(x);",
                "fs.readFileSync(path.normalize(x));",
                (
                    'const root = path.resolve("/srv/files"); const p = path.resolve(root, '
                    "x); if (!p.startsWith(root + path.sep)) return; "
                    "fs.readFileSync(String(req.query.other));"
                ),
                (
                    'const p = path.resolve("/srv/files",x); if '
                    '(!p.startsWith("/srv/files")) return; fs.readFileSync(p);'
                ),
            ],
            [
                (
                    'const root = path.resolve("/srv/files"); const p = '
                    "path.resolve(root,x); if (!p.startsWith(root + path.sep)) return; "
                    "fs.readFileSync(p);"
                ),
                'fs.readFileSync("/srv/files/catalog.txt");',
                'const p = path.resolve("/srv/files/catalog.txt"); fs.readFileSync(p);',
            ],
            'import fs from "node:fs"; import path from "node:path";',
            "Express/Node fs POSIX path",
        ),
        5: (
            [
                "const obj = decode(x); res.json(obj);",
                "const item = hydrate(JSON.parse(x)); res.json(item);",
                (
                    'const item = Object.assign(Object.create({role:"visitor"}), '
                    "JSON.parse(x)); res.json(item);"
                ),
            ],
            [
                "const item = JSON.parse(x); res.json(item);",
                'const item = JSON.parse("{\\"name\\":\\"visitor\\"}"); res.json(item);',
                "const item = {value:String(x)}; res.json(item);",
            ],
            (
                "declare function decode(value:string):unknown; declare function "
                "hydrate(value:unknown):unknown;"
            ),
            (
                "TypeScript JSON/object construction / opaque custom decoder; "
                "implementation unavailable"
            ),
        ),
        6: (
            [
                "http.get(x);",
                "fetch(x);",
                (
                    'const u = new URL(x); if (!u.hostname.endsWith("example.invalid")) '
                    "return; fetch(u);"
                ),
                (
                    'const u = new URL(x); if (u.hostname !== "files.example.invalid") '
                    "return; fetch(String(req.query.other));"
                ),
            ],
            [
                'fetch("https://files.example.invalid/catalog");',
                (
                    'const u = new URL(x); if (u.hostname !== "files.example.invalid") '
                    "return; fetch(u);"
                ),
                (
                    "const u = new URL(x); if "
                    '(!["files.example.invalid","status.example.invalid"].includes(u.hostna'
                    "me)) return; http.get(u);"
                ),
            ],
            'import http from "node:http";',
            "Express/Node HTTP or Fetch; URL parse",
        ),
        7: (
            [
                "document.body.innerHTML = x;",
                'res.send("<article>" + x + "</article>");',
                "document.body.innerHTML = DOMPurify.sanitize(x) + String(req.query.other);",
                "document.body.innerHTML = render(x);",
            ],
            [
                "document.body.innerHTML = DOMPurify.sanitize(x);",
                "document.body.textContent = x;",
                'document.body.innerHTML = "<article>Welcome</article>";',
            ],
            'import DOMPurify from "dompurify"; declare function render(value:string):string;',
            "Express/DOM/DOMPurify; supplied browser bridge evidence only",
        ),
        8: (
            [
                (
                    'const cipher = crypto.createCipheriv("des", new Uint8Array(8), new '
                    "Uint8Array(8)); res.send(cipher);"
                ),
                (
                    "const passwordHash = "
                    'crypto.createHash("md5").update(x).digest("hex"); '
                    "res.send(passwordHash);"
                ),
                (
                    'const cipher = crypto.createCipheriv("aes-128-ecb", new '
                    "Uint8Array(16), null); res.send(cipher);"
                ),
                (
                    'const signature = crypto.createHash("sha1").update(x).digest("hex"); '
                    "res.send(signature);"
                ),
            ],
            [
                (
                    'const cipher = crypto.createCipheriv("aes-256-gcm", new '
                    "Uint8Array(32), new Uint8Array(12)); res.send(cipher);"
                ),
                (
                    "const checksum = "
                    'crypto.createHash("md5").update("catalog").digest("hex"); '
                    "res.send(checksum);"
                ),
                (
                    "const signature = "
                    'crypto.createHash("sha256").update(x).digest("hex"); '
                    "res.send(signature);"
                ),
            ],
            'import crypto from "node:crypto";',
            "Node crypto; security vs checksum usage",
        ),
        9: (
            [
                "const resetToken = String(Math.random()); res.send(resetToken);",
                "const sessionToken = `${Math.random()}`; res.send(sessionToken);",
                "const nonce = Math.random(); res.send(nonce);",
            ],
            [
                'const token = crypto.randomBytes(32).toString("hex"); res.send(token);',
                "const simulation = Math.random(); res.send(simulation);",
                "const sample = Math.floor(Math.random()*10); res.send(sample);",
            ],
            'import crypto from "node:crypto";',
            "Node crypto / Math.random usage",
        ),
        10: (
            ["eval(x);", "new Function(x)();", "vm.runInNewContext(x);", "execute(x);"],
            ['eval("1 + 2");', 'Reflect.get({title:"visitor"}, x);', "res.send(x.length);"],
            'import vm from "node:vm"; declare function execute(value:string):unknown;',
            "ECMAScript eval/Function/VM or opaque wrapper",
        ),
    }
    risks, controls, imports, framework = bodies[rule]
    pool = risks if intent else controls
    return pool[(n // 2) % len(pool)], imports, framework


def semantic_input(rule: int, language: str, action: str, default: str) -> tuple[str, str]:
    """Place the rule-relevant value, rather than unrelated filler, into each flow family."""
    if rule == 1:
        pattern = r'(String|const) ([A-Za-z]+) = ("(?:[^"\\]|\\.)*");'
        if match := re.search(pattern, action):
            return match[3], action.replace(match[0], f"{match[1]} {match[2]} = x;", 1)
    if rule == 8:
        pattern = r'(getInstance|createHash|createCipheriv)\(("[^"\n]+"|selectAlgorithm\(\))'
        if match := re.search(pattern, action):
            body = action.replace(match[0], match[1] + "(x", 1)
            body = body.replace("digest(x.getBytes())", 'digest(req.getParameter("q").getBytes())')
            body = body.replace("update(x)", "update(String(req.query.q))")
            return match[2], body
    if rule == 9:
        if language == "TYPESCRIPT":
            pattern = r"const ([A-Za-z]+) = ([^;]+);"
            if match := re.search(pattern, action):
                return f"String({match[2]})", action.replace(match[0], f"const {match[1]} = x;", 1)
        else:
            pattern = r"(String|double|int) ([A-Za-z]+) = ([^;]+);"
            if match := re.search(pattern, action):
                expression = (
                    "x"
                    if match[1] == "String"
                    else "Double.parseDouble(x)"
                    if match[1] == "double"
                    else "Integer.parseInt(x)"
                )
                return (f"String.valueOf({match[3]})"), action.replace(
                    match[0], (f"{match[1]} {match[2]} = {expression};"), 1
                )
    return default, action


def source_template(rule: int, language: str, n: int, intent: bool) -> tuple[dict[str, str], str]:
    """__ID__ is an opaque, nonsemantic identifier substituted after template fingerprinting."""
    if language == "JAVA":
        action, framework = java_bodies(rule, intent, n)
        selection_helper = ""
        if n == 6 and rule == 8:
            selection = '"RC4"' if intent else '"AES/GCM/NoPadding"'
            if selection in action:
                action = action.replace(selection, "selectAlgorithm()")
                selection_helper = f"static String selectAlgorithm() {{ return {selection}; }}"
        if n == 6 and rule == 9 and "Math.random()" in action:
            action = action.replace("Math.random()", "generateValue()")
            selection_helper = "static double generateValue() { return Math.random(); }"
        source = ['req.getParameter("q")', 'req.getHeader("X-Value")', 'req.getParameter("item")'][
            n % 3
        ]
        source, action = semantic_input(rule, language, action, source)
        shapes = (
            f"String x = {source}; {action}",
            f"String x = relay({source}); {action}",
            f"Box box = new Box({source}); String x = box.value; {action}",
            (
                'String x; if (req.getParameter("mode") != null) x = '
                f"{source}"
                '; else x = "catalog"; '
                f"{action}"
            ),
            f"String x = transform({source}); {action}",
            f"Holder h = new Holder({source}); String x = h.get(); {action}",
            f"String x = relay2(relay({source})); {action}",
            f"String x = Link__ID__.pass({source}); {action}",
            f"Box box = new Box({source}); Box alias = box; String x = alias.value; {action}",
            f"String[] entries = new String[]{{{source}}}; String x = entries[0]; {action}",
            f"consume({source}, req, res, db);",
            f'String x = "catalog"; if (req.getHeader("X-Mode") != null) x = {source}; {action}',
            (
                "Box box = new Box("
                f"{source}"
                "); Nest nest = new Nest(box); String x = nest.box.value; "
                f"{action}"
            ),
            (
                "java.util.function.Supplier<String> supplier = () -> "
                f"{source}"
                "; String x = supplier.get(); "
                f"{action}"
            ),
            f"String input = {source}; String copy = input; String x = copy.substring(0); {action}",
        )
        helpers = {
            1: "static String relay(String value) { return value; }",
            2: "static class Box { String value; Box(String value) { this.value=value; } }",
            4: "abstract String transform(String value);",
            5: (
                "static class Holder { String value; Holder(String value) { "
                "this.value=value; } String get() { return value; } }"
            ),
            6: (
                "static String relay(String value) { return value; } static String "
                "relay2(String value) { return value; }"
            ),
            8: "static class Box { String value; Box(String value) { this.value=value; } }",
            10: (
                "static void consume(String x, HttpServletRequest req, "
                "HttpServletResponse res, java.sql.Connection db) throws Exception { "
                f"{action}"
                " }"
            ),
            12: (
                "static class Box { String value; Box(String value) { "
                "this.value=value; } } static class Nest { Box box; Nest(Box b) "
                "{box=b;} }"
            ),
        }
        if rule == 5 and "read(s)" in action:
            helpers[n] = helpers.get(n, "") + (
                " static Object read(java.io.InputStream s) throws Exception { return "
                "new java.io.ObjectInputStream(s).readObject(); }"
            )
        if rule == 7 and "render(x)" in action:
            helpers[n] = (
                helpers.get(n, "") + " static String render(String value) { return value; }"
            )
        if rule == 10 and "execute(x)" in action:
            helpers[n] = helpers.get(n, "") + (
                " static Object execute(String value) throws Exception { return new "
                'javax.script.ScriptEngineManager().getEngineByName("javascript").eval('
                "value); }"
            )
        helpers[n] = helpers.get(n, "") + selection_helper
        text = (
            "import jakarta.servlet.http.HttpServletRequest; "
            "import jakarta.servlet.http.HttpServletResponse;\n"
            "class Unit__ID__ {\n void handle(HttpServletRequest req, "
            "HttpServletResponse res, java.sql.Connection db) throws Exception { "
            + shapes[n]
            + " }\n"
            + helpers.get(n, "")
            + "\n}\n"
        )
        if n == 4:
            text = text.replace("class Unit__ID__", "abstract class Unit__ID__", 1)
        files = {"src/Unit__ID__.java": text}
        if n == 7:
            files["src/Link__ID__.java"] = (
                "class Link__ID__ { static String pass(String value) { return value; } }\n"
            )
        return files, framework
    action, imports, framework = ts_bodies(rule, intent, n)
    selection_helper = ""
    if n == 6 and rule == 8:
        selection = '"sha1"' if intent else '"aes-256-gcm"'
        if selection in action:
            action = action.replace(selection, "selectAlgorithm()")
            selection_helper = f"function selectAlgorithm():string {{ return {selection}; }}"
    if n == 6 and rule == 9 and "Math.random()" in action:
        action = action.replace("Math.random()", "generateValue()")
        selection_helper = "function generateValue():number { return Math.random(); }"
    source = ["String(req.query.q)", 'String(req.headers["x-value"])', "String(req.body.item)"][
        n % 3
    ]
    source, action = semantic_input(rule, language, action, source)
    shapes = (
        f"const x = {source}; {action}",
        f"const x = relay({source}); {action}",
        f"const box = {{value:{source}}}; const x = box.value; {action}",
        f'const x = req.query.mode ? {source} : "catalog"; {action}',
        f"const x = transform({source}); {action}",
        f"const holder = new Holder({source}); const x = holder.get(); {action}",
        f"const x = relay2(relay({source})); {action}",
        f"const x = pass({source}); {action}",
        f"const box = {{value:{source}}}; const alias = box; const x = alias.value; {action}",
        f"const entries = [{source}]; const x = entries[0]; {action}",
        f"consume({source}, req, res);",
        f'let x = "catalog"; if (req.headers["x-mode"]) x = {source}; {action}',
        f"const nest = {{inner:{{value:{source}}}}}; const x = nest.inner.value; {action}",
        f"const supplier = () => {source}; const x = supplier(); {action}",
        f"const input = {source}; const copy = input; const x = copy.slice(0); {action}",
    )
    helpers = {
        1: "function relay(value:string):string { return value; }",
        4: "declare function transform(value:string):string;",
        5: (
            "class Holder { constructor(public value:string) {} get():string { "
            "return this.value; } }"
        ),
        6: (
            "function relay(value:string):string { return value; } function "
            "relay2(value:string):string { return value; }"
        ),
        10: f"function consume(x:string, req:Request, res:Response):void {{ {action} }}",
    }
    helpers[n] = helpers.get(n, "") + selection_helper
    text = (
        'import {Request, Response} from "express";\n'
        + imports
        + "\n"
        + ('import {pass} from "./Link__ID__";\n' if n == 7 else "")
        + f"export function handle__ID__(req:Request, res:Response):void {{ {shapes[n]} }}\n"
        + helpers.get(n, "")
        + "\n"
    )
    files = {"src/Unit__ID__.ts": text}
    if n == 7:
        files["src/Link__ID__.ts"] = "export function pass(value:string):string { return value; }\n"
    return files, framework


def generate() -> tuple[dict[str, Any], ...]:
    rows = []
    for rule in range(1, 11):
        for language in ("JAVA", "TYPESCRIPT"):
            for n in range(15):
                split = "DEV" if n < 5 else "FINAL"
                intent = n % 2 == (0 if language == "JAVA" or split == "FINAL" else 1)
                design = dict(generator=VERSION, rule=rule, language=language, variant=n)
                identity = digest(design)
                template, framework = source_template(rule, language, n, intent)
                files = {
                    p.replace("__ID__", identity[:16]): s.replace("__ID__", identity[:16])
                    for p, s in template.items()
                }
                evidence = dict(
                    case_id="sc-" + identity[:24],
                    rule_id=f"SEC{rule:03d}",
                    language=language,
                    framework_context=framework,
                    review_scope=(
                        "Judge only the target SEC rule in the supplied complete static source "
                        "bundle, including declared API context. No source is executed. Opaque "
                        "wrappers/ambient declarations have no supplied implementation; record "
                        "uncertainty or scope limits without assuming semantics. POSIX "
                        "filesystem semantics are assumed; remote resolution/redirects, "
                        "runtime configuration and exploitability are not evidenced."
                    ),
                    source_files=[dict(path=p, content=s) for p, s in sorted(files.items())],
                )
                rows.append(
                    dict(
                        **evidence,
                        split=split,
                        project_id="sp-" + digest([VERSION, "project", design])[:24],
                        template_id="st-" + digest([VERSION, "template", design])[:24],
                        template_fingerprint=digest(template),
                        flow_shape=SHAPES[n],
                        construction_intent="MUTATION_INTENT" if intent else "CONTROL_INTENT",
                        generator_version=VERSION,
                        generator_path="archguard.security_benchmark.templates.source_template",
                        construction_intent_capability=["MUTATION_INTENT", "CONTROL_INTENT"],
                        parameterization_dimensions=[
                            "request query/header/body",
                            "sink API",
                            "literal",
                            "flow shape",
                        ],
                        RULE_LANGUAGE_SCOPE_EXPECTATION="UNSUPPORTED_BY_CURRENT_DETECTOR"
                        if rule == 5 and language == "TYPESCRIPT"
                        else "WITHIN_DECLARED_PARTIAL_V2_SCOPE",
                        synthetic_only=True,
                        external_code=False,
                        source_bundle_fingerprint=digest(files),
                        source_file_fingerprints={
                            p: hashlib.sha256(s.encode()).hexdigest() for p, s in files.items()
                        },
                        case_fingerprint=digest(evidence),
                    )
                )
    return tuple(sorted(rows, key=lambda r: r["case_id"]))
