"""Versioned refinements of bounded API identity and primitive value transport."""

import re
from dataclasses import replace

from tree_sitter import Node

from archguard.extraction.common import child, text
from archguard.security.domain import SecurityFindingStatus, SecurityRuleId, SecuritySourceReference
from archguard.security.engine_v1 import NON_SECURITY, PLACEHOLDER, security_purpose
from archguard.security.engine_v2 import InterproceduralEngine, PathFact, V2Value, join
from archguard.security.flow_v1 import FlowState, FlowValue


class RefinementEngine(InterproceduralEngine):
    def context(
        self, value: V2Value, name: str, reference: SecuritySourceReference | None = None
    ) -> None:
        super().context(value, "" if value.state == FlowState.UNKNOWN else name, reference)

    def expression(self, node: Node, purpose: str) -> FlowValue:
        if (
            self.language.value == "TYPESCRIPT"
            and node.type == "member_expression"
            and self.qualified(node) == "builtin.document.body"
        ):
            return V2Value(FlowState.UNTAINTED, api_type="dom.HTMLElement")
        return super().expression(node, purpose)

    def qualified(self, node: Node | None) -> str | None:
        if node is not None and self.language.value == "JAVA":
            raw = text(node)
            root = raw.split(".")[0]
            if (
                raw in {"String", "Double", "Long", "Integer", "Boolean"}
                and raw not in self.env
                and raw not in self.shadowed
                and raw not in self.imports
            ):
                return "java.lang." + raw
            if (
                re.fullmatch(r"(?:java|javax|jakarta)(?:\.[A-Za-z_$][\w$]*)+", raw)
                and root not in self.env
                and root not in self.shadowed
            ):
                return raw
        return super().qualified(node)

    def secret(self, node: Node) -> None:
        literal = child(node, "value")
        if literal is not None and literal.type in {"string", "string_literal"}:
            self.credential(text(child(node, "name")), text(literal)[1:-1], literal)

    def credential(self, name: str, value: str, node: Node) -> None:
        if PLACEHOLDER.search(value) or NON_SECURITY.search(name):
            return
        structured = bool(
            re.fullmatch(r"(?:sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{30,}|AKIA[A-Z0-9]{16})", value)
        ) or value.startswith(("-----BEGIN PRIVATE KEY-----", "-----BEGIN RSA PRIVATE KEY-----"))
        role_literal = (
            security_purpose(name)
            and len(value) >= 28
            and len(set(value)) >= 12
            and sum(bool(re.search(p, value)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^\w]"))
            >= 3
            and not re.fullmatch(r"[a-fA-F0-9-]+", value)
        )
        if structured or role_literal:
            self.pattern(
                SecurityRuleId.SEC001,
                node,
                "embedded-credential-redacted",
                SecurityFindingStatus.CONFIRMED_PATTERN,
            )

    def store(self, name: str, value: FlowValue, node: Node) -> None:
        super().store(name, value, node)
        if value.state == FlowState.UNTAINTED and value.literal is not None:
            self.credential(name, value.literal, node)

    def call(self, node: Node, purpose: str) -> FlowValue:
        java = self.language.value == "JAVA"
        construct = node.type in {"new_expression", "object_creation_expression"}
        func = (
            child(node, "type")
            if java and construct
            else child(node, "constructor")
            if construct
            else child(node, "function")
        )
        obj = child(node, "object") if java else child(func, "object") if func else None
        name = text(child(node, "name")) if java else text(child(func, "property")) if func else ""
        q = (
            self.resolve_type(func)
            if java and construct
            else self.qualified(func)
            if not java
            else f"{self.qualified(obj)}.{name}"
        )
        arglist = child(node, "arguments")
        argnodes = tuple(arglist.named_children) if arglist else ()
        if (
            java
            and len(argnodes) == 1
            and q
            in {
                "java.lang.String.valueOf",
                "java.lang.Double.toString",
                "java.lang.Long.toString",
                "java.lang.Integer.toString",
                "java.lang.Boolean.toString",
            }
        ):
            value = self.expr(argnodes[0], purpose)
            return self.step(replace(value, api_type="string"), node, "PRIMITIVE_STRING")
        if (
            not java
            and text(func) == "String"
            and "String" not in self.shadowed
            and "String" not in self.env
            and "String" not in self.imports
            and len(argnodes) == 1
        ):
            value = self.expr(argnodes[0], purpose)
            return self.step(replace(value, api_type="string"), node, "PRIMITIVE_STRING")
        if java and q in {
            "java.sql.Connection.createStatement",
            "javax.script.ScriptEngineManager.getEngineByName",
        }:
            for arg in argnodes:
                self.expr(arg, purpose)
            return V2Value(
                FlowState.UNTAINTED,
                api_type="java.sql.Statement"
                if name == "createStatement"
                else "javax.script.ScriptEngine",
            )
        if (
            java
            and name == "getEngineByName"
            and obj is not None
            and obj.type == "object_creation_expression"
            and self.resolve_type(child(obj, "type")) == "javax.script.ScriptEngineManager"
        ):
            receiver = self.expr(obj)
            for arg in argnodes:
                self.expr(arg, purpose)
            return replace(receiver, api_type="javax.script.ScriptEngine")
        if construct and q == "javax.script.ScriptEngineManager" and not argnodes:
            return V2Value(FlowState.UNTAINTED, api_type=q)
        if java and q == "java.nio.file.Path.of":
            values = tuple(self.expr(arg, purpose) for arg in argnodes)
            value = join(values)
            literal = values[0].literal if len(values) == 1 else None
            fact = None
            if (
                literal
                and literal.startswith("/")
                and ".." not in literal.split("/")
                and "\\" not in literal
                and value.state == FlowState.UNTAINTED
            ):
                fact = PathFact(
                    self.reference(node).model_dump_json(), literal.rstrip("/"), False, True
                )
            return self.step(
                replace(
                    value,
                    api_type="java.nio.file.Path",
                    path_fact=fact,
                    sanitized_for=value.sanitized_for - {SecurityRuleId.SEC004},
                    literal=literal if fact else None,
                ),
                node,
                "PATH_CONSTRUCTION",
            )
        if not java and q in {"child_process.spawn", "child_process.spawnSync"}:
            values = tuple(self.expr(arg, purpose) for arg in argnodes)
            if len(values) >= 2:
                executable, operands = values[:2]
                vector = self.fields(operands)
                option = self.fields(values[2]).get("shell") if len(values) > 2 else None
                if (
                    executable.literal in {"sh", "bash", "dash", "zsh"}
                    and vector.get("0", V2Value()).literal == "-c"
                    and (option is None or option.literal == "false")
                    and "1" in vector
                ):
                    self.sink(SecurityRuleId.SEC003, node, vector["1"], "shell-command-vector")
                    return V2Value.unknown("UNMODELED_PROCESS_RETURN")
            old = self.precomputed
            self.precomputed = old | {a.id: v for a, v in zip(argnodes, values, strict=True)}
            try:
                return super().call(node, purpose)
            finally:
                self.precomputed = old
        return super().call(node, purpose)
