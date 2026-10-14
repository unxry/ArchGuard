"""Derived Security AST index over the existing parser; no Architecture semantics."""

import re
from dataclasses import dataclass, field, replace

from tree_sitter import Node

from archguard.core.identifiers import SourceFileId
from archguard.extraction.common import child, location, text, walk
from archguard.security.domain import (
    SecurityFindingStatus,
    SecurityLanguage,
    SecurityRuleId,
    SecuritySourceReference,
)
from archguard.security.flow_v1 import FlowLimits, FlowState, FlowValue, merge

PURPOSE = re.compile(
    r"(?:password|secret|session|nonce|csrf|auth|reset|(?:access|api)?token|key)", re.I
)
NON_SECURITY = re.compile(
    r"(?:checksum|cache|fingerprint|simulation|shuffle|sample|parser|label|game)", re.I
)
PLACEHOLDER = re.compile(r"(?:placeholder|example|changeme|your[_ -]|<|\$\{|process\.env)", re.I)


def security_purpose(name: str) -> bool:
    words = re.sub(r"([a-z])([A-Z])", r"\1_\2", name).lower()
    return bool(
        set(re.split(r"[^a-z]+", words))
        & {"password", "secret", "session", "nonce", "csrf", "auth", "reset", "token", "key"}
    )


@dataclass(frozen=True)
class Candidate:
    rule: SecurityRuleId
    source: SecuritySourceReference
    api_id: str
    value: FlowValue | None = field(default=None, repr=False)
    status: SecurityFindingStatus = SecurityFindingStatus.SUPPORTED


@dataclass
class EngineOutput:
    candidates: list[Candidate] = field(default_factory=list)
    diagnostics: set[str] = field(default_factory=set)
    partial: bool = False


class BoundedFlowEngine:
    def __init__(
        self, language: SecurityLanguage, file_id: SourceFileId, path: str, limits: FlowLimits
    ) -> None:
        self.language, self.file_id, self.path, self.limits = language, file_id, path, limits
        self.output = EngineOutput()
        self.imports: dict[str, str] = {}
        self.shadowed: set[str] = set()
        self.env: dict[str, FlowValue] = {}
        self.nodes = 0
        self.branches = 0
        self.depth = 0
        self.returned = False

    def reference(self, node: Node) -> SecuritySourceReference:
        return SecuritySourceReference(
            file_id=self.file_id, location=location(node, self.path), language=self.language
        )

    def unknown(self, reason: str) -> FlowValue:
        self.output.diagnostics.add(reason)
        self.output.partial = True
        return FlowValue.unknown(reason)

    def consume(self) -> bool:
        self.nodes += 1
        if self.nodes > self.limits.max_nodes_per_function:
            self.unknown("NODE_LIMIT_EXCEEDED")
            self.env = {k: FlowValue.unknown("NODE_LIMIT_EXCEEDED") for k in self.env}
            return False
        return True

    def run(self, root: Node) -> EngineOutput:
        nodes: list[Node] = []
        for n in walk(root):
            if len(nodes) >= self.limits.max_file_nodes:
                self.unknown("FILE_NODE_LIMIT_EXCEEDED")
                return self.output
            nodes.append(n)
        self.index_imports(root)
        global_shadow = {
            text(child(n, "name"))
            for n in nodes
            if n.type in {"class_declaration", "interface_declaration", "function_declaration"}
        }
        # SEC001 is a literal-in-declaration pattern, independent of executable reachability.
        for n in nodes:
            if n.type == "variable_declarator":
                self.secret(n)
        functions = [
            n
            for n in nodes
            if n.type
            in {
                "method_declaration",
                "function_declaration",
                "arrow_function",
                "function_expression",
            }
        ]
        for fn in functions:
            # Nested function/callback execution is a boundary, never implicitly inline it.
            self.env = {}
            self.shadowed = global_shadow | self.local_names(fn)
            self.nodes = self.branches = 0
            self.returned = False
            params = child(fn, "parameters")
            if params:
                for p in params.named_children:
                    name = child(p, "name") or child(p, "pattern")
                    if name is not None and name.type == "identifier":
                        api_type = self.resolve_type(child(p, "type"))
                        self.env[text(name)] = FlowValue(api_type=api_type)
            body = child(fn, "body")
            if body:
                self.statement(body)
        if self.language == SecurityLanguage.TYPESCRIPT:
            self.env = {}
            self.shadowed = global_shadow | self.local_names(root, descend_functions=False)
            self.nodes = self.branches = 0
            self.returned = False
            for n in root.named_children:
                if n.type not in {
                    "import_statement",
                    "function_declaration",
                    "class_declaration",
                    "interface_declaration",
                }:
                    self.statement(n)
        return self.output

    def index_imports(self, root: Node) -> None:
        for n in root.named_children:
            if n.type == "import_declaration":
                identifiers = [
                    c for c in n.named_children if c.type in {"scoped_identifier", "identifier"}
                ]
                if identifiers and not any(c.type in {"asterisk", "static"} for c in n.children):
                    q = text(identifiers[0])
                    self.imports[q.rsplit(".", 1)[-1]] = q
            elif n.type == "import_statement":
                module = text(child(n, "source"))[1:-1]
                module = module.removeprefix("node:")
                for c in walk(n):
                    if c.type == "import_specifier":
                        name = text(child(c, "name"))
                        self.imports[text(child(c, "alias")) or name] = f"{module}.{name}"
                    elif c.type == "namespace_import":
                        self.imports[text(c.named_children[-1])] = module
                    elif c.type == "import_clause":
                        for item in c.named_children:
                            if item.type == "identifier":
                                self.imports[text(item)] = module

    def local_names(self, root: Node, *, descend_functions: bool = True) -> set[str]:
        names: set[str] = set()
        pending = list(root.named_children)
        while pending:
            n = pending.pop()
            if n.type in {
                "variable_declarator",
                "formal_parameter",
                "required_parameter",
                "optional_parameter",
            }:
                target = child(n, "name") or child(n, "pattern")
                if target and target.type == "identifier":
                    names.add(text(target))
            if n.type in {
                "function_declaration",
                "function_expression",
                "arrow_function",
                "method_declaration",
            } and (not descend_functions or n != root):
                if child(n, "name"):
                    names.add(text(child(n, "name")))
                continue
            pending.extend(n.named_children)
        return names

    def resolve_type(self, node: Node | None) -> str | None:
        if node is None:
            return None
        name = text(node).lstrip(": ")
        if name in self.shadowed or "<" in name or "[" in name or "|" in name:
            return None
        return self.imports.get(name, name if "." in name else None) or (
            f"dom.{name}"
            if name in {"HTMLElement", "HTMLDivElement", "Element"}
            else f"java.lang.{name}"
            if self.language == SecurityLanguage.JAVA and name in {"Runtime", "ProcessBuilder"}
            else None
        )

    def qualified(self, node: Node | None) -> str | None:
        if node is None:
            return None
        if node.type in {"identifier", "type_identifier"}:
            name = text(node)
            if name in self.env:
                return self.env[name].api_type
            if name in self.shadowed:
                return None
            if name in self.imports:
                return self.imports[name]
            if (
                name in {"Math", "Runtime", "ProcessBuilder"}
                and self.language == SecurityLanguage.JAVA
            ):
                return f"java.lang.{name}"
            if (
                name in {"Math", "document", "eval", "Function", "setTimeout", "setInterval"}
                and self.language == SecurityLanguage.TYPESCRIPT
            ):
                return f"builtin.{name}"
        if node.type in {"member_expression", "field_access"}:
            owner = self.qualified(child(node, "object"))
            prop = text(child(node, "property") or child(node, "field"))
            return f"{owner}.{prop}" if owner else None
        return None

    def store(self, name: str, value: FlowValue, node: Node) -> None:
        if name not in self.env and len(self.env) >= self.limits.max_tracked_values:
            self.unknown("TRACKED_VALUE_LIMIT_EXCEEDED")
            return
        stepped = value.step(self.reference(node), self.limits.max_flow_steps)
        for reason in stepped.uncertainty:
            self.output.diagnostics.add(reason)
        self.env[name] = stepped

    def statement(self, node: Node) -> None:
        if not self.consume() or self.returned:
            return
        kind = node.type
        if kind in {"block", "statement_block", "program"}:
            previous = dict(self.env)
            declarations: set[str] = set()
            for c in node.named_children:
                if c.type in {
                    "local_variable_declaration",
                    "lexical_declaration",
                    "variable_declaration",
                }:
                    declarations.update(
                        text(child(v, "name"))
                        for v in c.named_children
                        if v.type == "variable_declarator"
                    )
                self.statement(c)
            for name in declarations:
                if name in previous:
                    self.env[name] = previous[name]
                else:
                    self.env.pop(name, None)
        elif kind in {"local_variable_declaration", "lexical_declaration", "variable_declaration"}:
            for c in node.named_children:
                if c.type == "variable_declarator":
                    self.declare(c, child(node, "type"))
        elif kind == "variable_declarator":
            self.declare(node, None)
        elif kind == "if_statement":
            self.expr(child(node, "condition"))
            self.branches += 2
            if self.branches > self.limits.max_branch_states:
                self.env = {k: self.unknown("BRANCH_LIMIT_EXCEEDED") for k in self.env}
                return
            before = dict(self.env)
            then = child(node, "consequence")
            otherwise = child(node, "alternative")
            if then:
                self.statement(then)
            left, left_return = dict(self.env), self.returned
            self.env, self.returned = dict(before), False
            if otherwise:
                self.statement(otherwise)
            right, right_return = dict(self.env), self.returned
            if left_return and not right_return:
                self.env = right
            elif right_return and not left_return:
                self.env = left
            else:
                self.env = {
                    k: merge(
                        (
                            left.get(k, FlowValue.unknown("BRANCH_BINDING_UNKNOWN")),
                            right.get(k, FlowValue.unknown("BRANCH_BINDING_UNKNOWN")),
                        ),
                        self.limits.max_branch_states,
                    )
                    for k in sorted(left.keys() | right.keys())
                }
            self.returned = left_return and right_return
        elif kind == "return_statement":
            for c in node.named_children:
                self.expr(c)
            self.returned = True
        elif kind in {
            "for_statement",
            "for_in_statement",
            "enhanced_for_statement",
            "while_statement",
            "do_statement",
            "switch_statement",
            "try_statement",
        }:
            # Do not execute a loop once and falsely claim complete propagation.
            for k in self.env:
                self.env[k] = self.unknown("UNSUPPORTED_CONTROL_FLOW")
            self.unknown("UNSUPPORTED_CONTROL_FLOW")
        elif kind in {
            "function_declaration",
            "method_declaration",
            "arrow_function",
            "class_declaration",
            "comment",
            "import_statement",
        }:
            return
        elif kind == "else_clause":
            for c in node.named_children:
                self.statement(c)
        elif kind in {"expression_statement", "export_statement"}:
            for c in node.named_children:
                self.statement(c) if c.type.endswith("declaration") else self.expr(c)
        else:
            self.expr(node)

    def declare(self, node: Node, declared_type: Node | None) -> None:
        name_node = child(node, "name")
        if name_node is None or name_node.type != "identifier":
            self.unknown("UNSUPPORTED_DESTRUCTURING")
            return
        name = text(name_node)
        value = self.expr(child(node, "value"), name)
        api_type = self.resolve_type(child(node, "type") or declared_type)
        if api_type:
            value = replace(value, api_type=api_type)
        self.store(name, value, node)

    def expr(self, node: Node | None, purpose: str = "") -> FlowValue:
        if node is None:
            return FlowValue.unknown("UNINITIALIZED_VALUE")
        if not self.consume():
            return FlowValue.unknown("NODE_LIMIT_EXCEEDED")
        if self.depth >= self.limits.max_expression_depth:
            return self.unknown("EXPRESSION_DEPTH_LIMIT_EXCEEDED")
        self.depth += 1
        try:
            return self.expression(node, purpose)
        finally:
            self.depth -= 1

    def expression(self, node: Node, purpose: str) -> FlowValue:
        kind = node.type
        if kind in {"string", "string_literal", "character_literal"}:
            return FlowValue(FlowState.UNTAINTED, literal=text(node)[1:-1])
        if kind in {
            "number",
            "decimal_integer_literal",
            "decimal_floating_point_literal",
            "true",
            "false",
            "null",
            "null_literal",
        }:
            return FlowValue(FlowState.UNTAINTED, literal=text(node))
        if kind in {"identifier", "shorthand_property_identifier"}:
            name = text(node)
            return self.env.get(name) or self.unknown("UNRESOLVED_SYMBOL")
        if kind == "array_creation_expression":
            initializer = child(node, "value")
            return (
                self.expr(initializer, purpose)
                if initializer
                else self.unknown("UNSUPPORTED_ARRAY_DIMENSIONS")
            )
        if kind in {
            "parenthesized_expression",
            "as_expression",
            "non_null_expression",
            "cast_expression",
            "await_expression",
        }:
            target = child(node, "value") or next(
                (c for c in node.named_children if "type" not in c.type), None
            )
            return self.expr(target, purpose)
        if kind in {
            "binary_expression",
            "ternary_expression",
            "conditional_expression",
            "template_string",
            "template_substitution",
            "array",
            "array_initializer",
        }:
            children = node.named_children
            if kind in {"ternary_expression", "conditional_expression"}:
                self.expr(child(node, "condition"))
                children = [c for c in children if c != child(node, "condition")]
            values = tuple(
                self.expr(c, purpose)
                for c in children
                if c.type not in {"string_fragment", "escape_sequence"}
            )
            value = merge(values, self.limits.max_branch_states)
            if kind == "template_string" and not values:
                value = FlowValue(FlowState.UNTAINTED, literal=text(node)[1:-1])
            if kind == "template_string" or (
                kind == "binary_expression"
                and text(child(node, "operator")) == "+"
                and any(v.api_type == "string" or v.literal is not None for v in values)
            ):
                value = replace(value, api_type="string")
            if kind in {"array", "array_initializer"}:
                value = replace(value, fields=tuple((str(i), v) for i, v in enumerate(values)))
            return value.step(self.reference(node), self.limits.max_flow_steps)
        if kind == "object":
            fields = []
            for c in node.named_children:
                if c.type == "pair":
                    key_node = child(c, "key")
                    if key_node is None or key_node.type not in {"property_identifier", "string"}:
                        return self.unknown("DYNAMIC_PROPERTY")
                    fields.append(
                        (text(key_node).strip("\"'"), self.expr(child(c, "value"), purpose))
                    )
                elif c.type == "shorthand_property_identifier":
                    fields.append((text(c), self.expr(c, purpose)))
                else:
                    return self.unknown("UNSUPPORTED_OBJECT_EXPRESSION")
            value = merge(tuple(v for _, v in fields), self.limits.max_branch_states)
            return replace(value, fields=tuple(fields))
        if kind in {"member_expression", "field_access", "subscript_expression"}:
            obj = child(node, "object")
            prop_node = child(node, "property") or child(node, "field") or child(node, "index")
            if prop_node is None or prop_node.type not in {
                "property_identifier",
                "identifier",
                "string",
                "number",
            }:
                return self.unknown("DYNAMIC_PROPERTY")
            key = text(prop_node).strip("\"'")
            owner = self.expr(obj, purpose)
            if owner.api_type == "express.Request" and key in {
                "query",
                "params",
                "body",
                "headers",
            }:
                return replace(
                    FlowValue.source(self.reference(node), "t.request"), api_type="request-field"
                )
            if owner.api_type == "request-field":
                return owner.step(self.reference(node), self.limits.max_flow_steps)
            projected = dict(owner.fields).get(key)
            if projected is not None:
                return projected.step(self.reference(node), self.limits.max_flow_steps)
            return self.unknown("UNRESOLVED_PROPERTY")
        if kind in {"assignment_expression", "augmented_assignment_expression"}:
            lhs, rhs = child(node, "left"), child(node, "right")
            value = self.expr(rhs, text(lhs) if lhs and lhs.type == "identifier" else purpose)
            if lhs and lhs.type == "identifier":
                if text(child(node, "operator")) not in {"", "="}:
                    value = merge(
                        (self.env.get(text(lhs), FlowValue.unknown("UNRESOLVED_SYMBOL")), value),
                        self.limits.max_branch_states,
                    )
                self.store(text(lhs), value, node)
            elif lhs and lhs.type in {"member_expression", "field_access"}:
                obj = child(lhs, "object")
                prop = text(child(lhs, "property") or child(lhs, "field"))
                owner = self.expr(obj)
                if owner.api_type in {
                    "dom.HTMLElement",
                    "dom.HTMLDivElement",
                    "dom.Element",
                } and prop in {"innerHTML", "outerHTML"}:
                    self.sink(SecurityRuleId.SEC007, node, value, "t.html")
                elif obj is not None and obj.type == "identifier" and owner.fields:
                    updated_fields = dict(owner.fields)
                    updated_fields[prop] = value
                    self.store(
                        text(obj),
                        replace(
                            merge(tuple(updated_fields.values())),
                            fields=tuple(sorted(updated_fields.items())),
                        ),
                        node,
                    )
                    for alias in tuple(self.env):
                        if alias != text(obj) and self.env[alias].fields == owner.fields:
                            self.env[alias] = self.unknown("OBJECT_ALIAS_WRITE")
                else:
                    self.unknown("UNSUPPORTED_PROPERTY_WRITE")
            else:
                self.unknown("UNSUPPORTED_ASSIGNMENT")
            return value
        if kind in {
            "call_expression",
            "method_invocation",
            "new_expression",
            "object_creation_expression",
        }:
            return self.call(node, purpose)
        if kind in {"arrow_function", "function_expression"}:
            return FlowValue(FlowState.UNTAINTED, api_type="callback")
        return self.unknown("UNSUPPORTED_EXPRESSION")

    def call(self, node: Node, purpose: str) -> FlowValue:
        java = self.language == SecurityLanguage.JAVA
        construct = node.type in {"new_expression", "object_creation_expression"}
        obj = child(node, "object") if java else None
        func = (
            child(node, "type")
            if java and construct
            else child(node, "constructor")
            if construct
            else child(node, "function")
        )
        name = text(child(node, "name")) if java else ""
        receiver: FlowValue | None = None
        if java and not construct:
            owner = self.qualified(obj)
            if owner is None and obj is not None:
                receiver = self.expr(obj)
                owner = receiver.api_type
            q = f"{owner}.{name}" if owner else None
        else:
            q = self.resolve_type(func) if java else self.qualified(func)
        args_node = child(node, "arguments")
        args = tuple(self.expr(c, purpose) for c in args_node.named_children) if args_node else ()
        first = args[0] if args else FlowValue(FlowState.UNTAINTED)
        joined = merge(args, self.limits.max_branch_states)
        if construct and java:
            if q == "java.lang.ProcessBuilder":
                executable = dict(first.fields).get("0", first)
                if first.literal in {"sh", "bash", "cmd", "powershell"} and joined.paths:
                    self.unknown("EXPLICIT_SHELL_ARGV_UNMODELED")
                    return replace(
                        joined,
                        state=FlowState.UNKNOWN,
                        api_type=q,
                        uncertainty=("EXPLICIT_SHELL_ARGV_UNMODELED",),
                    )
                return replace(executable, api_type=q)
            if q in {
                "java.net.URL",
                "java.io.ObjectInputStream",
                "java.util.Random",
                "java.security.SecureRandom",
            }:
                return replace(
                    joined,
                    api_type=q,
                    fields=(("__constructed__", FlowValue(FlowState.UNTAINTED)),),
                )
        if q in {
            "javax.servlet.http.HttpServletRequest." + m
            for m in ("getParameter", "getHeader", "getQueryString", "getPathInfo")
        } | {
            "jakarta.servlet.http.HttpServletRequest." + m
            for m in ("getParameter", "getHeader", "getQueryString", "getPathInfo")
        }:
            return replace(FlowValue.source(self.reference(node), "j.request"), api_type="string")
        if q in {
            "java.sql.Statement.execute",
            "java.sql.Statement.executeQuery",
            "java.sql.Statement.executeUpdate",
            "pg.Client.query",
            "pg.Pool.query",
        }:
            if first.fields:
                return self.unknown("UNSUPPORTED_QUERY_OPTIONS")
            self.sink(SecurityRuleId.SEC002, node, first, "j.sql" if java else "t.sql")
        elif q == "java.lang.Runtime.getRuntime":
            return FlowValue(FlowState.UNTAINTED, api_type="java.lang.Runtime")
        elif q in {"java.lang.Runtime.exec", "java.lang.ProcessBuilder.start"}:
            value = (
                first
                if q.endswith(".exec")
                else receiver or self.env.get(text(obj), FlowValue.unknown("UNRESOLVED_SYMBOL"))
            )
            self.sink(SecurityRuleId.SEC003, node, dict(value.fields).get("0", value), "j.exec")
        elif q in {f"child_process.{n}" for n in ("exec", "execSync", "spawn", "spawnSync")}:
            value = first
            if q.endswith(("spawn", "spawnSync")) and len(args) >= 2:
                options = args[2] if len(args) >= 3 else FlowValue(FlowState.UNTAINTED)
                shell = dict(options.fields).get("shell")
                if shell and shell.literal == "true":
                    value = merge(args[:2], self.limits.max_branch_states)
                elif shell and shell.literal != "false" or options.state == FlowState.UNKNOWN:
                    self.unknown("UNRESOLVED_SHELL_OPTION")
                    return FlowValue.unknown("UNRESOLVED_SHELL_OPTION")
            self.sink(SecurityRuleId.SEC003, node, value, "t.exec")
        elif q in {
            f"java.nio.file.Files.{n}" for n in ("readAllBytes", "readString", "newInputStream")
        } | {f"fs.{n}" for n in ("readFile", "readFileSync", "createReadStream")}:
            self.sink(SecurityRuleId.SEC004, node, first, "j.path" if java else "t.path")
        elif q in {
            "java.nio.file.Paths.get",
            "java.nio.file.Path.normalize",
            "java.nio.file.Path.resolve",
        } | {f"path.{n}" for n in ("normalize", "join", "resolve")}:
            value = merge(
                (
                    *(args),
                    *(
                        (receiver or self.env.get(text(obj)),)
                        if java and obj is not None and q != "java.nio.file.Paths.get"
                        else ()
                    ),
                )
            )
            return replace(value, api_type="java.nio.file.Path" if java else None).step(
                self.reference(node), self.limits.max_flow_steps
            )
        elif q in {
            "java.io.ObjectInputStream.readObject",
            "java.io.ObjectInputStream.readUnshared",
        }:
            value = receiver or self.env.get(text(obj), FlowValue.unknown("UNRESOLVED_SYMBOL"))
            if (
                value.api_type == "java.io.ObjectInputStream"
                and "__constructed__" in dict(value.fields)
                and "DESERIALIZATION_FILTER_UNKNOWN" not in value.uncertainty
            ):
                self.pattern(
                    SecurityRuleId.SEC005,
                    node,
                    "j.deserialize",
                    SecurityFindingStatus.CONFIRMED_PATTERN,
                )
            else:
                self.unknown("DESERIALIZATION_FILTER_UNKNOWN")
        elif q == "java.io.ObjectInputStream.setObjectInputFilter":
            for binding in tuple(self.env):
                if self.env[binding].api_type == "java.io.ObjectInputStream":
                    self.env[binding] = replace(
                        self.env[binding], uncertainty=("DESERIALIZATION_FILTER_UNKNOWN",)
                    )
            self.unknown("DESERIALIZATION_FILTER_UNKNOWN")
        elif q in {"java.net.URL.openConnection", "java.net.URL.openStream"}:
            self.sink(
                SecurityRuleId.SEC006,
                node,
                receiver or self.env.get(text(obj), FlowValue.unknown("UNRESOLVED_SYMBOL")),
                "j.http",
            )
        elif q in {
            f"{module}.{method}" for module in ("http", "https") for method in ("get", "request")
        }:
            if first.fields:
                return self.unknown("UNSUPPORTED_HTTP_OPTIONS")
            self.sink(SecurityRuleId.SEC006, node, first, "t.http")
        elif q in {
            f"{prefix}.JspWriter.{method}"
            for prefix in ("javax.servlet.jsp", "jakarta.servlet.jsp")
            for method in ("print", "write")
        }:
            self.sink(SecurityRuleId.SEC007, node, first, "j.html")
        elif q in {"builtin.document.getElementById", "builtin.document.querySelector"}:
            return FlowValue(FlowState.UNTAINTED, api_type="dom.HTMLElement")
        elif q == "dompurify.sanitize":
            if len(args) != 1:
                return self.unknown("SANITIZER_UNRESOLVED")
            return first.sanitize(
                SecurityRuleId.SEC007, self.reference(node), "t.escape", self.limits.max_flow_steps
            )
        elif q in {
            "java.security.MessageDigest.getInstance",
            "javax.crypto.Cipher.getInstance",
            "crypto.createHash",
            "crypto.createCipheriv",
        }:
            algorithm = (first.literal or "").lower().replace("-", "")
            if algorithm in {
                "md5",
                "sha1",
                "des",
                "des/ecb/pkcs5padding",
                "rc4",
                "descbc",
            } and not NON_SECURITY.search(purpose):
                self.pattern(
                    SecurityRuleId.SEC008,
                    node,
                    "j.crypto" if java else "t.crypto",
                    SecurityFindingStatus.CONFIRMED_PATTERN
                    if security_purpose(purpose)
                    else SecurityFindingStatus.POTENTIAL,
                )
        elif q in {
            "java.lang.Math.random",
            "java.util.Random.nextInt",
            "java.util.Random.nextLong",
            "java.util.Random.nextDouble",
            "builtin.Math.random",
        }:
            if security_purpose(purpose) and not NON_SECURITY.search(purpose):
                self.pattern(
                    SecurityRuleId.SEC009,
                    node,
                    "j.random" if java else "t.random",
                    SecurityFindingStatus.CONFIRMED_PATTERN,
                )
            return FlowValue(FlowState.UNTAINTED)
        elif q == "javax.script.ScriptEngine.eval" or q in {
            "builtin.eval",
            "builtin.Function",
            "builtin.setTimeout",
            "builtin.setInterval",
            "vm.runInNewContext",
            "vm.runInThisContext",
            "vm.runInContext",
        }:
            code = args[-1] if q == "builtin.Function" and args else first
            if (
                q in {"builtin.setTimeout", "builtin.setInterval"}
                and code.api_type != "string"
                and code.literal is None
            ):
                self.unknown("DYNAMIC_CODE_TYPE_UNKNOWN")
                return FlowValue.unknown("DYNAMIC_CODE_TYPE_UNKNOWN")
            if code.api_type != "callback":
                self.sink(SecurityRuleId.SEC010, node, code, "j.eval" if java else "t.eval")
        elif q in {
            "java.sql.PreparedStatement.setString",
            "java.sql.PreparedStatement.execute",
            "java.sql.PreparedStatement.executeQuery",
            "java.sql.PreparedStatement.executeUpdate",
            "java.lang.Class.forName",
        }:
            return FlowValue(FlowState.UNTAINTED)
        else:
            # Calls may transform values arbitrarily; no identity-function guess.
            self.unknown("INTERPROCEDURAL_BOUNDARY")
            return replace(
                joined,
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=tuple(sorted({*joined.uncertainty, "INTERPROCEDURAL_BOUNDARY"})),
            )
        return FlowValue.unknown("UNMODELED_RETURN")

    def sink(self, rule: SecurityRuleId, node: Node, value: FlowValue, api_id: str) -> None:
        if rule in value.sanitized_for:
            return
        if value.state == FlowState.UNKNOWN:
            self.unknown("UNKNOWN_FLOW")
        if not value.paths:
            return
        self.output.candidates.append(
            Candidate(
                rule,
                self.reference(node),
                api_id,
                value,
                SecurityFindingStatus.POTENTIAL
                if value.state == FlowState.UNKNOWN
                else SecurityFindingStatus.SUPPORTED,
            )
        )

    def pattern(
        self, rule: SecurityRuleId, node: Node, api_id: str, status: SecurityFindingStatus
    ) -> None:
        self.output.candidates.append(Candidate(rule, self.reference(node), api_id, status=status))

    def secret(self, node: Node) -> None:
        value_node = child(node, "value")
        if value_node is None or value_node.type not in {
            "string",
            "string_literal",
            "template_string",
        }:
            return
        if any(c.type == "template_substitution" for c in value_node.named_children):
            return
        value = text(value_node)[1:-1]
        name = text(child(node, "name"))
        if PLACEHOLDER.search(value) or NON_SECURITY.search(name):
            return
        credential = (
            "-----BEGIN PRIVATE KEY-----" in value
            or "-----BEGIN RSA PRIVATE KEY-----" in value
            or bool(
                re.fullmatch(
                    r"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})", value
                )
            )
            or security_purpose(name)
            and len(value) >= 20
            and value.startswith("TEST_ONLY_SYNTHETIC_SECRET_")
            or security_purpose(name)
            and len(value) >= 28
            and len(set(value)) >= 12
            and sum(
                bool(re.search(p, value)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]")
            )
            >= 3
            and not re.fullmatch(r"[a-fA-F0-9-]+", value)
        )
        if credential:
            self.pattern(
                SecurityRuleId.SEC001,
                value_node,
                "embedded-credential-redacted",
                SecurityFindingStatus.CONFIRMED_PATTERN,
            )
