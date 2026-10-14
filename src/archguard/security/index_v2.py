"""Bounded declaration/import index. Arity resolution is not compiler overload resolution."""

import hashlib
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from uuid import UUID, uuid5

from tree_sitter import Node

from archguard.core.identifiers import SourceFileId
from archguard.extraction.common import child, location, text
from archguard.security.domain import SecurityLanguage, SecuritySourceReference
from archguard.security.engine_v1 import BoundedFlowEngine
from archguard.security.summaries_v2 import VERSION, ResolutionState, V2Limits


@dataclass
class SourceUnit:
    file_id: SourceFileId
    path: str
    language: SecurityLanguage
    root: Node = field(repr=False)
    source_version: str = field(repr=False)
    imports: dict[str, str] = field(default_factory=dict)
    package: str = ""
    global_names: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class DeclaredSymbol:
    id: UUID
    unit: SourceUnit = field(repr=False)
    name: str
    class_name: str | None
    lexical_owner: UUID | None
    parameters: tuple[Node, ...] = field(repr=False)
    body: Node = field(repr=False)
    declaration: Node = field(repr=False)
    static: bool = False
    exported: bool = False
    constructor: bool = False

    @property
    def reference(self) -> SecuritySourceReference:
        return SecuritySourceReference(
            file_id=self.unit.file_id,
            language=self.unit.language,
            location=location(self.declaration, self.unit.path),
        )


@dataclass(frozen=True)
class CallResolution:
    state: ResolutionState
    targets: tuple[DeclaredSymbol, ...] = ()


class DeclarationIndex:
    def __init__(self, units: tuple[SourceUnit, ...], limits: V2Limits) -> None:
        self.units = units
        self.limits = limits
        self.symbols: list[DeclaredSymbol] = []
        self.diagnostics: set[str] = set()
        self.class_locations: dict[str, tuple[SourceUnit, Node]] = {}
        for unit in units:
            self.visited = 0
            helper = BoundedFlowEngine(unit.language, unit.file_id, unit.path, limits)
            helper.index_imports(unit.root)
            unit.imports = helper.imports
            for n in unit.root.named_children:
                if n.type == "package_declaration":
                    unit.package = text(n).removeprefix("package ").removesuffix(";").strip()
            self.collect(unit, unit.root, None, None)
        self.symbols.sort(key=lambda s: (s.unit.path, s.declaration.start_byte, str(s.id)))
        self.graph_version = hashlib.sha256(
            "|".join(
                f"{u.file_id}:{u.source_version}" for u in sorted(units, key=lambda u: u.path)
            ).encode()
        ).hexdigest()

    def class_key(self, unit: SourceUnit, name: str) -> str:
        return f"project:{unit.path}:{name}"

    def collect(
        self, unit: SourceUnit, node: Node, owner: UUID | None, class_name: str | None
    ) -> None:
        self.visited += 1
        if self.visited > self.limits.max_file_nodes:
            self.diagnostics.add("FILE_NODE_LIMIT_EXCEEDED")
            return
        if len(self.symbols) >= self.limits.max_summary_expansions:
            self.diagnostics.add("SUMMARY_INDEX_LIMIT")
            return
        if node.type in {"class_declaration", "interface_declaration"}:
            class_name = text(child(node, "name"))
            self.class_locations[self.class_key(unit, class_name)] = (unit, node)
            unit.global_names.add(class_name)
        if node.type in {
            "function_declaration",
            "function_expression",
            "arrow_function",
            "method_declaration",
            "method_definition",
            "constructor_declaration",
        }:
            body = child(node, "body")
            name_node = child(node, "name")
            if name_node is None and node.parent and node.parent.type == "variable_declarator":
                name_node = child(node.parent, "name")
            name = text(name_node)
            if owner is None and name:
                unit.global_names.add(name)
            params = child(node, "parameters")
            if body is None or not name:
                self.diagnostics.add("DECLARATION_UNSUPPORTED")
                return
            parameters = tuple(params.named_children) if params else ()
            if any(
                p.type
                in {"rest_pattern", "rest_parameter", "spread_parameter", "optional_parameter"}
                or (parameter_target := child(p, "name") or child(p, "pattern")) is None
                or parameter_target.type != "identifier"
                for p in parameters
            ):
                self.diagnostics.add("DECLARATION_UNSUPPORTED")
                return
            identity = (
                f"{VERSION}:{unit.language.value}:{unit.path}:{class_name}:{owner}:"
                f"{name}:{len(parameters)}:{node.start_byte}"
            )
            symbol = DeclaredSymbol(
                uuid5(unit.file_id, identity),
                unit,
                name,
                class_name,
                owner,
                parameters,
                body,
                node,
                static=any(
                    c.type == "static" or c.type == "modifiers" and "static" in text(c).split()
                    for c in node.named_children
                ),
                exported=node.parent is not None and node.parent.type == "export_statement",
                constructor=node.type == "constructor_declaration" or name == "constructor",
            )
            self.symbols.append(symbol)
            if owner is None:
                unit.global_names.add(name)
            owner = symbol.id
        for c in node.named_children:
            self.collect(unit, c, owner, class_name)

    def resolve_class(self, unit: SourceUnit, name: str) -> str | None:
        local = self.class_key(unit, name)
        if local in self.class_locations:
            return local
        imported = unit.imports.get(name, name if "." in name else "")
        matches = [
            key
            for key, (u, n) in self.class_locations.items()
            if f"{u.package}.{text(child(n, 'name'))}".lstrip(".") == imported
        ]
        return matches[0] if len(matches) == 1 else None

    def imported_function(self, unit: SourceUnit, q: str) -> list[DeclaredSymbol]:
        if not q.startswith("."):
            return []
        module, _, name = q.rpartition(".")
        # Index_imports stores './helpers.exportName'; match only explicit relative modules.
        target = str(PurePosixPath(unit.path).parent / module)
        candidates = {target, target + ".ts", target + "/index.ts"}
        return [
            s
            for s in self.symbols
            if s.unit.path in candidates
            and s.name == name
            and s.exported
            and s.class_name is None
            and s.lexical_owner is None
        ]

    def resolve(
        self,
        unit: SourceUnit,
        caller: DeclaredSymbol | None,
        name: str,
        arity: int,
        receiver_type: str | None = None,
        *,
        local_shadow: bool = False,
    ) -> CallResolution:
        targets: list[DeclaredSymbol] = []
        if receiver_type and receiver_type.startswith("project:"):
            targets = [
                s
                for s in self.symbols
                if s.class_name
                and self.class_key(s.unit, s.class_name) == receiver_type
                and s.name == name
                and not s.constructor
            ]
        elif receiver_type and receiver_type.startswith("module:"):
            target = receiver_type.removeprefix("module:")
            targets = [
                s
                for s in self.symbols
                if s.unit.path == target
                and s.name == name
                and s.exported
                and s.lexical_owner is None
            ]
        elif not receiver_type and not local_shadow:
            if caller:
                targets = [
                    s
                    for s in self.symbols
                    if s.unit == unit and s.name == name and s.lexical_owner == caller.id
                ]
                if not targets and caller.class_name:
                    targets = [
                        s
                        for s in self.symbols
                        if s.unit == unit
                        and s.class_name == caller.class_name
                        and s.name == name
                        and s.lexical_owner is None
                        and not s.constructor
                    ]
            if not targets:
                targets = [
                    s
                    for s in self.symbols
                    if s.unit == unit
                    and s.class_name is None
                    and s.name == name
                    and s.lexical_owner is None
                ]
            if not targets and name in unit.imports:
                targets = self.imported_function(unit, unit.imports[name])
        targets = sorted(
            (s for s in targets if len(s.parameters) == arity),
            key=lambda s: (s.unit.path, s.declaration.start_byte, str(s.id)),
        )
        if len(targets) > self.limits.max_call_targets:
            self.diagnostics.add("CALL_TARGET_LIMIT")
            return CallResolution(
                ResolutionState.AMBIGUOUS, tuple(targets[: self.limits.max_call_targets])
            )
        if len(targets) > 1:
            return CallResolution(ResolutionState.AMBIGUOUS, tuple(targets))
        if not targets:
            return CallResolution(ResolutionState.UNRESOLVED)
        return CallResolution(
            ResolutionState.EXACT if receiver_type else ResolutionState.UNAMBIGUOUS_LOCAL,
            tuple(targets),
        )
