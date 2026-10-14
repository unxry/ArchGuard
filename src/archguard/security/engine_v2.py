"""Bounded local/imported call summaries, heap slots and narrowly proven safety boundaries."""

import re
from dataclasses import dataclass, field, replace
from uuid import uuid5

from tree_sitter import Node

from archguard.extraction.common import child, text, walk
from archguard.security.domain import (
    FlowRole,
    SecurityFindingStatus,
    SecurityRuleId,
    SecuritySourceReference,
)
from archguard.security.engine_v1 import (
    NON_SECURITY,
    BoundedFlowEngine,
    Candidate,
    security_purpose,
)
from archguard.security.flow_v1 import FlowState, FlowValue, TraceStep, merge
from archguard.security.index_v2 import CallResolution, DeclarationIndex, DeclaredSymbol, SourceUnit
from archguard.security.summaries_v2 import (
    VERSION,
    FieldEffect,
    FunctionSummary,
    ParameterFlow,
    ProofKind,
    ResolutionState,
    ReturnFlow,
    SafetyProof,
    SanitizerEffect,
    SinkEffect,
    SummaryCache,
    SummaryState,
    UnknownEffect,
    V2Limits,
    fingerprint,
)


@dataclass(frozen=True)
class ValueOrigin:
    kind: str
    trace: tuple[TraceStep, ...]
    explicit: bool = False


@dataclass(frozen=True)
class PathFact:
    root_key: str
    absolute_root: str = field(repr=False)
    normalized: bool
    root: bool = False


@dataclass(frozen=True)
class V2Value(FlowValue):
    object_id: str | None = None
    path_fact: PathFact | None = field(default=None, repr=False)
    url_id: str | None = None
    url_part: str | None = None
    origins: tuple[ValueOrigin, ...] = ()

    @classmethod
    def unknown(cls, reason: str) -> "V2Value":
        return cls(uncertainty=(reason,))


@dataclass(frozen=True)
class V2Candidate(Candidate):
    supporting_steps: tuple[TraceStep, ...] = ()


def v2(value: FlowValue) -> V2Value:
    if isinstance(value, V2Value):
        return value
    return V2Value(
        value.state,
        value.paths,
        value.sanitized_for,
        value.uncertainty,
        value.literal,
        value.api_type,
        value.fields,
    )


def join(values: tuple[FlowValue, ...], limit: int = 32) -> V2Value:
    base = merge(values, limit)
    extended = tuple(v2(v) for v in values)
    objects = {v.object_id for v in extended}
    facts = {v.path_fact for v in extended}
    urls = {(v.url_id, v.url_part) for v in extended}
    preferred: dict[tuple[str, tuple[tuple[str, str], ...]], tuple[TraceStep, ...]] = {}
    for path in base.paths:
        if not path:
            continue
        key = (
            path[0].source.model_dump_json(),
            tuple(
                (s.source.model_dump_json(), s.api_id)
                for s in path
                if s.role == FlowRole.INTERPROCEDURAL_BOUNDARY
            ),
        )
        previous = preferred.get(key)
        if previous is None or len(path) > len(previous):
            preferred[key] = path
    return replace(
        v2(base),
        paths=tuple(preferred[k] for k in sorted(preferred)),
        object_id=next(iter(objects)) if len(objects) == 1 else None,
        path_fact=next(iter(facts)) if len(facts) == 1 else None,
        url_id=next(iter(urls))[0] if len(urls) == 1 else None,
        url_part=next(iter(urls))[1] if len(urls) == 1 else None,
        origins=tuple(dict.fromkeys(f for v in extended for f in v.origins))[:limit],
    )


class InterproceduralEngine(BoundedFlowEngine):
    def __init__(self, index: DeclarationIndex, limits: V2Limits, cache: SummaryCache) -> None:
        unit = index.units[0]
        super().__init__(unit.language, unit.file_id, unit.path, limits)
        self.index = index
        self.v2limits = limits
        self.cache = cache
        self.unit = unit
        self.current: DeclaredSymbol | None = None
        self.stack: list[tuple[DeclaredSymbol, SecuritySourceReference]] = []
        self.frames: list[dict[str, FlowValue]] = []
        self.return_values: list[V2Value] = []
        self.heap: dict[str, dict[str, V2Value] | None] = {}
        self.object_proofs: dict[str, SafetyProof] = {}
        self.expansions = 0
        self.total_nodes = 0
        self.summary_nodes = 0
        self.summary_mode = False
        self.summaries: dict[str, FunctionSummary] = {}
        self.resolutions: list[tuple[SecuritySourceReference, CallResolution]] = []
        self.proven: list[SafetyProof] = []
        self.field_effects: list[FieldEffect] = []
        self.precomputed: dict[int, V2Value] = {}
        self.static_contexts: dict[tuple[str, str], tuple[ValueOrigin, set[str]]] = {}
        self.inbound: set[str] = set()
        self.globals_by_file: dict[str, dict[str, FlowValue]] = {}
        self.output.diagnostics.update(index.diagnostics)

    def select_unit(self, unit: SourceUnit) -> None:
        self.unit = unit
        self.file_id, self.path, self.language = unit.file_id, unit.path, unit.language
        self.imports = unit.imports

    def resolve_type(self, node: Node | None) -> str | None:
        if node is None:
            return None
        name = text(node).lstrip(": ")
        project = self.index.resolve_class(self.unit, name)
        return project or super().resolve_type(node) or ("string" if name == "String" else None)

    def qualified(self, node: Node | None) -> str | None:
        if node is not None and node.type in {"member_expression", "field_access"}:
            obj = child(node, "object")
            owner = super().qualified(obj)
            if owner is None and obj is not None:
                owner = self.expr(obj).api_type
            prop = text(child(node, "property") or child(node, "field"))
            return f"{owner}.{prop}" if owner else None
        if (
            node is not None
            and node.type == "identifier"
            and text(node) == "URL"
            and self.language.value == "TYPESCRIPT"
            and "URL" not in self.shadowed
        ):
            return "builtin.URL"
        return super().qualified(node)

    def unknown(self, reason: str) -> V2Value:
        return v2(super().unknown(reason))

    def consume(self) -> bool:
        self.total_nodes += 1
        if self.total_nodes > self.v2limits.max_total_nodes:
            self.unknown("TOTAL_NODE_LIMIT")
            self.env = {k: self.unknown("TOTAL_NODE_LIMIT") for k in self.env}
            return False
        if self.summary_mode and self.nodes >= self.v2limits.max_summary_nodes:
            self.unknown("SUMMARY_NODE_LIMIT")
            self.env = {k: self.unknown("SUMMARY_NODE_LIMIT") for k in self.env}
            return False
        return super().consume()

    def step(
        self, value: FlowValue, node: Node, kind: str, role: FlowRole = FlowRole.PROPAGATION
    ) -> V2Value:
        value = v2(value)
        stepped = v2(value.step(self.reference(node), self.v2limits.flow_bound))
        if (
            stepped.state != FlowState.UNKNOWN
            or value.state == FlowState.UNKNOWN
            and stepped.paths != value.paths
        ):
            stepped = replace(
                stepped,
                paths=tuple(
                    (*p[:-1], TraceStep(role, self.reference(node), kind)) for p in stepped.paths
                ),
            )
        origins = tuple(
            replace(
                o,
                trace=(*o.trace, TraceStep(role, self.reference(node), kind))[
                    : self.v2limits.flow_bound
                ],
            )
            for o in stepped.origins
        )
        self.output.diagnostics.update(stepped.uncertainty)
        return replace(stepped, origins=origins)

    def allocate(self, node: Node, fields: dict[str, V2Value], base: V2Value) -> V2Value:
        call_frames = [
            (str(s.id), r.location.start_line, r.location.start_column) for s, r in self.stack
        ]
        key = str(
            uuid5(
                self.file_id,
                f"{VERSION}:{node.start_byte}:{call_frames}",
            )
        )
        if key not in self.heap and len(self.heap) >= self.v2limits.max_heap_objects:
            return self.unknown("HEAP_OBJECT_LIMIT")
        if (
            len(fields) > self.v2limits.max_fields_per_object
            or sum(len(v or {}) for v in self.heap.values()) + len(fields)
            > self.v2limits.max_total_heap_fields
        ):
            self.heap[key] = None
            self.unknown("FIELD_LIMIT")
        else:
            self.heap[key] = fields
        return replace(base, object_id=key, fields=())

    def object_value(self, value: FlowValue) -> V2Value:
        value = v2(value)
        if value.url_id:
            fields = self.heap.get(value.url_id)
            combined = join((value, *(fields or {}).values()), self.v2limits.max_branch_states)
            value = replace(
                value,
                paths=combined.paths,
                state=combined.state,
                sanitized_for=value.sanitized_for - {SecurityRuleId.SEC006},
            )
            proof = self.object_proofs.get(value.url_id or "")
            if proof and value.state != FlowState.UNKNOWN:
                value = replace(
                    value,
                    state=FlowState.SANITIZED,
                    sanitized_for=value.sanitized_for | {SecurityRuleId.SEC006},
                    paths=tuple(
                        (
                            *p,
                            TraceStep(
                                FlowRole.SANITIZER,
                                proof.evidence[-1],
                                ProofKind.SSRF_ALLOWLIST.value,
                            ),
                        )
                        if len(p) < self.v2limits.flow_bound - 1
                        else p
                        for p in value.paths
                    ),
                )
        return value

    def store(self, name: str, value: FlowValue, node: Node) -> None:
        value = v2(value)
        if value.object_id:
            alias_count = sum(
                v2(v).object_id == value.object_id
                for env in (*self.frames, self.env)
                for v in env.values()
            )
            if name not in self.env and alias_count >= self.v2limits.max_aliases_per_object:
                self.heap[value.object_id] = None
                self.unknown("ALIAS_LIMIT")
        super().store(name, value, node)
        if name in self.env:
            self.env[name] = self.step(value, node, "ASSIGNMENT")
        self.context(value, name, self.reference(node))

    def context(
        self, value: V2Value, name: str, reference: SecuritySourceReference | None = None
    ) -> None:
        if self.summary_mode:
            return
        for origin in value.origins:
            if reference:
                origin = replace(
                    origin,
                    trace=(*origin.trace, TraceStep(FlowRole.PROPAGATION, reference, "VALUE_USE")),
                )
            key = (origin.kind, origin.trace[0].source.model_dump_json())
            if (
                key not in self.static_contexts
                and len(self.static_contexts) >= self.v2limits.max_candidates
            ):
                self.unknown("CANDIDATE_LIMIT")
                continue
            tag = (
                "SECURITY"
                if security_purpose(name) and not NON_SECURITY.search(name)
                else "NONSECURITY"
                if NON_SECURITY.search(name)
                else "UNKNOWN"
            )
            old = self.static_contexts.get(key)
            tags = set() if old is None else set(old[1])
            tags.add(tag)
            selected = (
                origin
                if old is None
                or tag == "SECURITY"
                and "SECURITY" not in old[1]
                or "SECURITY" not in tags
                and len(origin.trace) > len(old[0].trace)
                else old[0]
            )
            self.static_contexts[key] = (selected, tags)

    def run_all(self) -> None:
        # Top-level TypeScript globals are analyzed once, before declaration roots.
        globals_by_file: dict[str, dict[str, FlowValue]] = {}
        for unit in self.index.units:
            self.select_unit(unit)
            self.env = {}
            self.shadowed = set(unit.global_names)
            self.current = None
            self.returned = False
            self.nodes = self.branches = 0
            for position, n in enumerate(walk(unit.root)):
                if position >= self.v2limits.max_file_nodes:
                    self.unknown("FILE_NODE_LIMIT_EXCEEDED")
                    break
                if n.type == "variable_declarator":
                    self.secret(n)
            if unit.language.value == "TYPESCRIPT":
                for n in unit.root.named_children:
                    if n.type not in {
                        "import_statement",
                        "function_declaration",
                        "class_declaration",
                        "interface_declaration",
                    }:
                        self.statement(n)
                        self.globals_by_file[unit.path] = dict(self.env)
            globals_by_file[unit.path] = dict(self.env)
        self.globals_by_file = globals_by_file
        for symbol in self.index.symbols:
            self.make_summary(symbol)
        # Symbolic summaries are not production findings. Actual roots use only real source packs.
        for symbol in self.index.symbols:
            if symbol.constructor or str(symbol.id) in self.inbound:
                continue
            if self.summaries[str(symbol.id)].state == SummaryState.UNKNOWN:
                self.unknown("SUMMARY_PARTIAL")
                continue
            self.select_unit(symbol.unit)
            self.env = dict(globals_by_file.get(symbol.unit.path, {}))
            self.current = None
            self.nodes = self.branches = 0
            arguments = tuple(self.root_parameter(symbol, p) for p in symbol.parameters)
            self.invoke(symbol, arguments, symbol.declaration, root=True)
        self.finalize_static()

    def parameter_name(self, node: Node) -> str:
        return text(child(node, "name") or child(node, "pattern"))

    def root_parameter(self, symbol: DeclaredSymbol, param: Node) -> V2Value:
        old = self.unit
        self.select_unit(symbol.unit)
        typ = self.resolve_type(child(param, "type"))
        for node in walk(param):
            if node.type in {"annotation", "marker_annotation"}:
                raw = text(child(node, "name"))
                q = self.imports.get(raw, raw)
                if q in {
                    f"org.springframework.web.bind.annotation.{n}"
                    for n in ("RequestParam", "PathVariable", "RequestHeader", "RequestBody")
                }:
                    type_text = text(child(param, "type"))
                    if type_text in {"String", "int", "long", "boolean", "double"}:
                        result = replace(
                            v2(FlowValue.source(self.reference(param), "j.spring")),
                            api_type="string" if type_text == "String" else None,
                        )
                        self.select_unit(old)
                        return result
                    self.unknown("FRAMEWORK_BINDING_UNKNOWN")
        self.select_unit(old)
        return V2Value(api_type=typ)

    def make_summary(self, symbol: DeclaredSymbol) -> FunctionSummary:
        if str(symbol.id) in self.summaries:
            return self.summaries[str(symbol.id)]
        remaining = self.v2limits.max_total_summary_nodes - self.summary_nodes
        key = (
            str(symbol.id),
            self.index.graph_version,
            fingerprint(
                self.v2limits.model_dump(mode="json") | {"remaining_summary_budget": remaining}
            ),
        )
        summary = self.cache.get(key)
        if remaining <= 0:
            payload = dict(
                version=VERSION,
                symbol_id=str(symbol.id),
                declaration=symbol.reference.model_dump(mode="json"),
                arity=len(symbol.parameters),
                state=SummaryState.UNKNOWN,
                parameter_flows=[],
                return_flow=ReturnFlow(state=FlowState.UNKNOWN).model_dump(mode="json"),
                sinks=[],
                sanitizers=[],
                call_targets=[],
                analysis_nodes=0,
                field_effects=[],
                unknown_effects=[dict(code="SUMMARY_TOTAL_NODE_LIMIT")],
            )
            summary = FunctionSummary.model_validate(
                payload | {"fingerprint": fingerprint(payload)}
            )
            self.summaries[str(symbol.id)] = summary
            self.unknown("SUMMARY_TOTAL_NODE_LIMIT")
            return summary
        if summary is not None:
            self.summary_nodes += summary.analysis_nodes
            self.summaries[str(symbol.id)] = summary
            self.inbound.update(str(s) for s in summary.call_targets if s != symbol.id)
            return summary
        probe = InterproceduralEngine(
            self.index,
            self.v2limits.model_copy(update={"max_total_nodes": remaining}),
            SummaryCache(),
        )
        probe.summary_mode = True
        probe.globals_by_file = self.globals_by_file
        probe.heap = {k: dict(v) if v is not None else None for k, v in self.heap.items()}
        probe.select_unit(symbol.unit)
        args = tuple(
            replace(
                v2(FlowValue.source(probe.reference(p), f"PARAMETER[{i}]")),
                api_type=probe.resolve_type(child(p, "type")),
            )
            for i, p in enumerate(symbol.parameters)
        )
        value = probe.invoke(symbol, args, symbol.declaration, root=True)
        self.summary_nodes += probe.total_nodes

        def indices(v: FlowValue) -> tuple[int, ...]:
            return tuple(
                sorted(
                    {
                        int(p[0].api_id[10:-1])
                        for p in v.paths
                        if p and re.fullmatch(r"PARAMETER\[[0-9]+\]", p[0].api_id)
                    }
                )
            )

        flows = []
        for i in indices(value):
            flows.append(
                ParameterFlow(
                    parameter_index=i,
                    destination="RETURN",
                    evidence=tuple(s.source for p in value.paths for s in p),
                )
            )
        for effect in probe.field_effects:
            if effect.action == "WRITE":
                flows.extend(
                    ParameterFlow(
                        parameter_index=i, destination="FIELD_WRITE", evidence=(effect.location,)
                    )
                    for i in effect.parameter_indices
                )
        sinks = []
        for c in probe.output.candidates:
            if c.value:
                ids = indices(c.value)
                sinks.append(
                    SinkEffect(
                        rule_id=c.rule,
                        sink=c.source,
                        parameter_indices=ids,
                        source_locations=tuple(dict.fromkeys(p[0].source for p in c.value.paths)),
                    )
                )
                flows.extend(
                    ParameterFlow(
                        parameter_index=i,
                        destination="SINK",
                        evidence=(c.source,),
                        rule_ids=(c.rule,),
                    )
                    for i in ids
                )
        sanitizers = tuple(
            SanitizerEffect(
                rule_ids=tuple(sorted(value.sanitized_for)),
                evidence=tuple(
                    dict.fromkeys(
                        s.source for p in value.paths for s in p if s.role == FlowRole.SANITIZER
                    )
                ),
            )
            for _ in (0,)
            if value.sanitized_for
        )
        refs = tuple(
            dict.fromkeys(
                [*(p[0].source for p in value.paths), *(o.trace[0].source for o in value.origins)]
            )
        )
        payload = dict(
            version=VERSION,
            symbol_id=str(symbol.id),
            declaration=symbol.reference.model_dump(mode="json"),
            arity=len(symbol.parameters),
            state=SummaryState.PARTIAL if probe.output.diagnostics else SummaryState.SUPPORTED,
            parameter_flows=[f.model_dump(mode="json") for f in flows],
            return_flow=ReturnFlow(
                state=value.state,
                parameter_indices=indices(value),
                sources=refs,
                sanitized_for=tuple(sorted(value.sanitized_for)),
            ).model_dump(mode="json"),
            sinks=[s.model_dump(mode="json") for s in sinks],
            sanitizers=[s.model_dump(mode="json") for s in sanitizers],
            call_targets=sorted({str(s.id) for _, r in probe.resolutions for s in r.targets}),
            analysis_nodes=probe.total_nodes,
            field_effects=[f.model_dump(mode="json") for f in probe.field_effects],
            unknown_effects=[
                UnknownEffect(code=c).model_dump(mode="json")
                for c in sorted(probe.output.diagnostics)
            ],
        )
        summary = FunctionSummary.model_validate(payload | {"fingerprint": fingerprint(payload)})
        self.cache.put(key, summary, self.v2limits.max_summary_cache_entries)
        self.summaries[str(symbol.id)] = summary
        self.inbound.update(
            str(s.id) for _, r in probe.resolutions for s in r.targets if s.id != symbol.id
        )
        return summary

    def invoke(
        self,
        symbol: DeclaredSymbol,
        args: tuple[V2Value, ...],
        call: Node,
        *,
        root: bool = False,
        receiver: V2Value | None = None,
    ) -> V2Value:
        if not root and len(self.stack) >= self.v2limits.max_call_depth:
            self.unknown("CALL_DEPTH_LIMIT")
            return replace(
                join(args),
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=("CALL_DEPTH_LIMIT",),
            )
        if any(s.id == symbol.id for s, _ in self.stack):
            self.unknown("SUMMARY_RECURSION_BOUND")
            return replace(
                join(args),
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=("SUMMARY_RECURSION_BOUND",),
            )
        self.expansions += 1
        if self.expansions > self.v2limits.max_summary_expansions:
            self.unknown("SUMMARY_EXPANSION_LIMIT")
            return replace(
                join(args),
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=("SUMMARY_EXPANSION_LIMIT",),
            )
        caller_ref = self.reference(call)
        saved = (
            self.unit,
            self.current,
            self.env,
            self.shadowed,
            self.return_values,
            self.returned,
            self.nodes,
            self.branches,
            self.precomputed,
        )
        self.frames.append(self.env)
        self.select_unit(symbol.unit)
        self.current = symbol
        self.env = dict(self.globals_by_file.get(symbol.unit.path, {}))
        self.shadowed = set(symbol.unit.global_names) | self.local_names(symbol.declaration)
        self.return_values = []
        self.returned = False
        self.nodes = self.branches = 0
        self.precomputed = {}
        self.stack.append((symbol, caller_ref))
        if root and symbol.class_name and receiver is None:
            receiver = self.allocate(
                symbol.declaration,
                {},
                V2Value(
                    FlowState.UNTAINTED,
                    api_type=self.index.class_key(symbol.unit, symbol.class_name),
                ),
            )
        if receiver is not None:
            self.env["this"] = receiver
            self.initialize_fields(receiver, symbol)
        for p, arg in zip(symbol.parameters, args, strict=True):
            value = arg
            if not root:
                value = replace(
                    value,
                    paths=tuple(
                        (
                            *path,
                            TraceStep(
                                FlowRole.INTERPROCEDURAL_BOUNDARY, caller_ref, "CALL_ARGUMENT"
                            ),
                        )
                        for path in value.paths
                    ),
                )
                value = self.step(value, p, "CALLEE_PARAMETER", FlowRole.INTERPROCEDURAL_BOUNDARY)
            self.env[self.parameter_name(p)] = value
            if self.summary_mode and text(child(p, "type")).lstrip(": ") in {"object", "Object"}:
                self.env[self.parameter_name(p)] = self.allocate(p, {}, v2(value))
        if symbol.declaration.type == "arrow_function" and symbol.body.type not in {
            "statement_block",
            "block",
        }:
            self.return_values.append(
                self.step(
                    self.expr(symbol.body),
                    symbol.body,
                    "CALLEE_RETURN",
                    FlowRole.INTERPROCEDURAL_BOUNDARY,
                )
            )
            self.returned = True
        else:
            self.statement(symbol.body)
        returned = (
            join(tuple(self.return_values), self.v2limits.max_branch_states)
            if self.return_values
            else V2Value(FlowState.UNTAINTED)
        )
        if not self.returned and self.return_values:
            returned = join((returned, V2Value.unknown("RETURN_PATH_UNPROVEN")))
        self.stack.pop()
        self.frames.pop()
        self.select_unit(saved[0])
        (
            self.current,
            self.env,
            self.shadowed,
            self.return_values,
            self.returned,
            self.nodes,
            self.branches,
            self.precomputed,
        ) = saved[1:]
        if not root:
            returned = self.step(returned, call, "CALL_RETURN", FlowRole.INTERPROCEDURAL_BOUNDARY)
        return returned

    def initialize_fields(self, receiver: V2Value, symbol: DeclaredSymbol) -> None:
        if not receiver.object_id or not symbol.class_name:
            return
        info = self.index.class_locations.get(self.index.class_key(symbol.unit, symbol.class_name))
        body = child(info[1], "body") if info else None
        fields = self.heap.get(receiver.object_id)
        if fields is None or body is None:
            return
        for declaration in body.named_children:
            if declaration.type == "field_declaration":
                for var in declaration.named_children:
                    if var.type == "variable_declarator":
                        name = text(child(var, "name"))
                        if name not in fields:
                            fields[name] = replace(
                                self.expr(child(var, "value")),
                                api_type=self.resolve_type(child(declaration, "type")),
                            )
                        self.env.setdefault(name, fields[name])

    def statement(self, node: Node) -> None:
        if self.returned:
            return
        if node.type == "return_statement":
            value = (
                self.expr(node.named_children[0])
                if node.named_children
                else V2Value(FlowState.UNTAINTED)
            )
            self.return_values.append(
                self.step(value, node, "CALLEE_RETURN", FlowRole.INTERPROCEDURAL_BOUNDARY)
            )
            self.returned = True
            return
        if node.type == "throw_statement":
            self.returned = True
            return
        if node.type == "if_statement":
            self.branch(node)
            return
        super().statement(node)

    def branch(self, node: Node) -> None:
        self.branches += 2
        if self.branches > self.v2limits.max_branch_states:
            self.env = {k: self.unknown("BRANCH_LIMIT_EXCEEDED") for k in self.env}
            return
        guard = self.guard(child(node, "condition"))
        condition = None if guard else self.expr(child(node, "condition"))
        if condition and condition.literal in {"true", "false"}:
            selected = (
                child(node, "consequence")
                if condition.literal == "true"
                else child(node, "alternative")
            )
            if selected:
                self.statement(selected)
            return
        then = child(node, "consequence")
        otherwise = child(node, "alternative")
        before = dict(self.env)
        heap_before = {k: dict(v) if v is not None else None for k, v in self.heap.items()}
        proofs_before = dict(self.object_proofs)
        if guard and not guard[2]:
            self.apply_guard(*guard[:2])
        if then:
            self.statement(then)
        left, left_return, left_heap, left_proofs = (
            dict(self.env),
            self.returned,
            self.heap,
            self.object_proofs,
        )
        self.env = dict(before)
        self.heap = {k: dict(v) if v is not None else None for k, v in heap_before.items()}
        self.object_proofs = dict(proofs_before)
        self.returned = False
        if guard and guard[2]:
            self.apply_guard(*guard[:2])
        if otherwise:
            self.statement(otherwise)
        right, right_return = dict(self.env), self.returned
        if left_return and not right_return:
            self.env = right
        elif right_return and not left_return:
            self.env, self.heap, self.object_proofs = left, left_heap, left_proofs
        else:
            self.env = {
                k: join(
                    (
                        left.get(k, V2Value.unknown("BRANCH_BINDING_UNKNOWN")),
                        right.get(k, V2Value.unknown("BRANCH_BINDING_UNKNOWN")),
                    ),
                    self.v2limits.max_branch_states,
                )
                for k in sorted(left.keys() | right.keys())
            }
            merged_heap = {}
            for key in sorted(left_heap.keys() | self.heap.keys()):
                a, b = left_heap.get(key), self.heap.get(key)
                merged_heap[key] = (
                    None
                    if a is None or b is None
                    else {
                        p: join(
                            (
                                a.get(p, V2Value.unknown("FIELD_FLOW_UNKNOWN")),
                                b.get(p, V2Value.unknown("FIELD_FLOW_UNKNOWN")),
                            ),
                            self.v2limits.max_branch_states,
                        )
                        for p in sorted(a.keys() | b.keys())
                    }
                )
            self.heap = merged_heap
            self.object_proofs = {
                k: v for k, v in left_proofs.items() if self.object_proofs.get(k) == v
            }
        self.returned = left_return and right_return

    def unwrap(self, node: Node | None) -> Node | None:
        while node is not None and node.type == "parenthesized_expression":
            node = node.named_children[0] if node.named_children else None
        return node

    def guard(self, node: Node | None) -> tuple[Node, SafetyProof, bool] | None:
        node = self.unwrap(node)
        if node is None:
            return None
        negated = False
        if node.type == "unary_expression" and text(child(node, "operator")) == "!":
            negated = True
            node = self.unwrap(child(node, "argument") or child(node, "operand"))
            if node is None:
                return None
        if node.type in {"call_expression", "method_invocation"}:
            func = child(node, "function")
            obj = (
                child(node, "object")
                if self.language.value == "JAVA"
                else child(func, "object")
                if func
                else None
            )
            name = (
                text(child(node, "name"))
                if self.language.value == "JAVA"
                else text(child(func, "property"))
                if func
                else ""
            )
            args = child(node, "arguments")
            argnodes = tuple(args.named_children) if args else ()
            if name == "startsWith" and obj and len(argnodes) == 1:
                target = self.expr(obj)
                prefix = self.expr(argnodes[0])
                fact = target.path_fact
                valid = fact is not None and fact.normalized
                if self.language.value == "JAVA":
                    valid = (
                        valid
                        and prefix.path_fact is not None
                        and prefix.path_fact.root
                        and fact is not None
                        and prefix.path_fact.root_key == fact.root_key
                    )
                else:
                    valid = (
                        valid
                        and fact is not None
                        and prefix.literal == fact.absolute_root.rstrip("/") + "/"
                    )
                if valid:
                    proof = SafetyProof(
                        kind=ProofKind.PATH_CONFINEMENT,
                        rule_ids=(SecurityRuleId.SEC004,),
                        evidence=(self.reference(obj), self.reference(node)),
                        scope="Lexical canonical containment only; no symlink/race guarantee",
                    )
                    return obj, proof, negated
                self.unknown("CONFINEMENT_UNPROVEN")
            if name in {"equals", "includes"} and obj and len(argnodes) == 1:
                host = self.expr(obj) if name == "equals" else self.expr(argnodes[0])
                allowed = (
                    (self.expr(argnodes[0]),)
                    if name == "equals"
                    else tuple(self.fields(self.expr(obj)).values())
                )
                if (
                    host.url_id
                    and host.url_part == "host"
                    and allowed
                    and all(
                        v.literal is not None
                        and re.fullmatch(r"[a-zA-Z0-9.-]+\.[a-zA-Z0-9-]+", v.literal)
                        for v in allowed
                    )
                ):
                    guard_target = obj if name == "equals" else argnodes[0]
                    proof = SafetyProof(
                        kind=ProofKind.SSRF_ALLOWLIST,
                        rule_ids=(SecurityRuleId.SEC006,),
                        evidence=(self.reference(guard_target), self.reference(node)),
                        scope="Exact static host allowlist only; no DNS/redirect guarantee",
                    )
                    return guard_target, proof, negated
                if host.url_id:
                    self.unknown("ALLOWLIST_UNPROVEN")
        if node.type == "binary_expression" and text(child(node, "operator")) in {
            "===",
            "!==",
            "==",
            "!=",
        }:
            a, b = child(node, "left"), child(node, "right")
            va, vb = self.expr(a), self.expr(b)
            binary_target = a if va.url_part == "host" else b
            host = va if va.url_part == "host" else vb
            constant = vb if va.url_part == "host" else va
            if (
                binary_target
                and host.url_id
                and constant.literal
                and re.fullmatch(r"[a-zA-Z0-9.-]+\.[a-zA-Z0-9-]+", constant.literal)
            ):
                proof = SafetyProof(
                    kind=ProofKind.SSRF_ALLOWLIST,
                    rule_ids=(SecurityRuleId.SEC006,),
                    evidence=(self.reference(binary_target), self.reference(node)),
                    scope="Exact static host equality; no DNS/redirect guarantee",
                )
                return (
                    binary_target,
                    proof,
                    negated ^ (text(child(node, "operator")) in {"!==", "!="}),
                )
        return None

    def apply_guard(self, target: Node, proof: SafetyProof) -> None:
        value = self.expr(target)
        self.proven.append(proof)
        if proof.kind == ProofKind.SSRF_ALLOWLIST and value.url_id:
            self.object_proofs[value.url_id] = proof
        elif proof.kind == ProofKind.PATH_CONFINEMENT:
            for name, old in tuple(self.env.items()):
                old = v2(old)
                if (
                    old.path_fact == value.path_fact
                    and old.paths == value.paths
                    and old.state != FlowState.UNKNOWN
                ):
                    self.env[name] = replace(
                        v2(
                            old.sanitize(
                                SecurityRuleId.SEC004,
                                proof.evidence[-1],
                                proof.kind.value,
                                self.v2limits.flow_bound,
                            )
                        ),
                        path_fact=old.path_fact,
                    )

    def fields(self, value: FlowValue) -> dict[str, V2Value]:
        value = v2(value)
        if value.object_id:
            result = self.heap.get(value.object_id)
            if result is None:
                self.unknown("FIELD_FLOW_UNKNOWN")
            return result or {}
        return {k: v2(v) for k, v in value.fields}

    def expr(self, node: Node | None, purpose: str = "") -> V2Value:
        if node is not None and node.id in self.precomputed:
            return self.precomputed[node.id]
        return v2(super().expr(node, purpose))

    def expression(self, node: Node, purpose: str) -> FlowValue:
        kind = node.type
        if kind in {"arrow_function", "function_expression"}:
            symbol = next(
                (
                    s
                    for s in self.index.symbols
                    if s.unit == self.unit and s.declaration.start_byte == node.start_byte
                ),
                None,
            )
            if symbol:
                return V2Value(FlowState.UNTAINTED, api_type="function:" + str(symbol.id))
        if kind in {"string", "string_literal"}:
            return replace(v2(super().expression(node, purpose)), api_type="string")
        if kind in {"identifier", "this"}:
            name = text(node)
            if name in self.env:
                return self.object_value(self.env[name])
            funcs = [
                s
                for s in self.index.symbols
                if s.unit == self.unit
                and s.name == name
                and s.class_name is None
                and s.lexical_owner in {None, self.current.id if self.current else None}
            ]
            if len(funcs) == 1:
                return V2Value(FlowState.UNTAINTED, api_type=f"function:{funcs[0].id}")
        if kind in {"object", "array", "array_initializer"}:
            fields = {}
            for i, c in enumerate(node.named_children):
                if kind == "object":
                    if c.type == "pair":
                        key_node = child(c, "key")
                        if key_node is None or key_node.type not in {
                            "property_identifier",
                            "string",
                        }:
                            return self.unknown("FIELD_FLOW_UNKNOWN")
                        fields[text(key_node).strip("\"'")] = self.expr(child(c, "value"), purpose)
                    elif c.type == "shorthand_property_identifier":
                        fields[text(c)] = self.expr(c, purpose)
                    else:
                        return self.unknown("FIELD_FLOW_UNKNOWN")
                else:
                    fields[str(i)] = self.expr(c, purpose)
            return self.allocate(
                node, fields, join(tuple(fields.values()), self.v2limits.max_branch_states)
            )
        if kind in {"member_expression", "field_access", "subscript_expression"}:
            obj = child(node, "object")
            prop = child(node, "property") or child(node, "field") or child(node, "index")
            if prop is None or prop.type not in {
                "identifier",
                "property_identifier",
                "string",
                "number",
            }:
                return self.unknown("FIELD_FLOW_UNKNOWN")
            key = text(prop).strip("\"'")
            owner = self.expr(obj)
            if kind == "subscript_expression" and prop.type == "identifier":
                index_value = self.expr(prop)
                if index_value.literal is None:
                    self.unknown("FIELD_FLOW_UNKNOWN")
                    known = join(
                        (owner, *self.fields(owner).values()), self.v2limits.max_branch_states
                    )
                    return self.step(
                        replace(
                            known,
                            state=FlowState.UNKNOWN,
                            sanitized_for=frozenset(),
                            object_id=None,
                            uncertainty=("FIELD_FLOW_UNKNOWN",),
                        ),
                        node,
                        "FIELD_FLOW_UNKNOWN",
                    )
                key = index_value.literal
            if owner.url_id and key in {"hostname", "host", "href"}:
                return replace(
                    owner,
                    api_type="string",
                    url_part="host" if key in {"hostname", "host"} else "url",
                    object_id=None,
                )
            if owner.object_id or owner.fields:
                value = self.fields(owner).get(key)
                self.field_effects.append(
                    FieldEffect(action="READ", location=self.reference(node), projection_depth=1)
                )
                return (
                    self.step(value, node, "FIELD_READ")
                    if value is not None
                    else self.unknown("FIELD_FLOW_UNKNOWN")
                )
            if self.qualified(node) == "path.sep":
                return V2Value(FlowState.UNTAINTED, literal="/")
            value = v2(super().expression(node, purpose))
            return value
        if kind in {"assignment_expression", "augmented_assignment_expression"}:
            lhs = child(node, "left")
            rhs = child(node, "right")
            if lhs and lhs.type in {"member_expression", "field_access", "subscript_expression"}:
                obj = child(lhs, "object")
                prop = child(lhs, "property") or child(lhs, "field") or child(lhs, "index")
                owner = self.expr(obj)
                rhs_value = self.expr(rhs, text(prop))
                if (
                    owner.object_id
                    and prop
                    and prop.type in {"identifier", "property_identifier", "string", "number"}
                ):
                    written_fields = self.heap.get(owner.object_id)
                    if written_fields is not None:
                        if (
                            len(written_fields) >= self.v2limits.max_fields_per_object
                            and text(prop) not in written_fields
                        ):
                            self.heap[owner.object_id] = None
                            self.unknown("FIELD_LIMIT")
                        else:
                            written_fields[text(prop).strip("\"'")] = rhs_value
                    self.object_proofs.pop(owner.object_id, None)
                    self.field_effects.append(
                        FieldEffect(
                            action="WRITE",
                            location=self.reference(lhs),
                            projection_depth=1,
                            parameter_indices=tuple(
                                sorted(
                                    {
                                        int(p[0].api_id[10:-1])
                                        for p in rhs_value.paths
                                        if p and re.fullmatch(r"PARAMETER\[[0-9]+\]", p[0].api_id)
                                    }
                                )
                            ),
                        )
                    )
                    self.context(rhs_value, text(prop), self.reference(lhs))
                    return rhs_value
                # Typed DOM assignment is still handled by the frozen V1 sink matcher.
                if owner.sanitized_for or owner.url_id:
                    self.unknown("FIELD_WRITE_UNKNOWN")
                    known = join((owner, rhs_value), self.v2limits.max_branch_states)
                    if obj is not None and obj.type == "identifier":
                        self.env[text(obj)] = replace(
                            known,
                            state=FlowState.UNKNOWN,
                            sanitized_for=frozenset(),
                            api_type=owner.api_type,
                            path_fact=None,
                            url_id=None,
                            object_id=None,
                            uncertainty=("FIELD_WRITE_UNKNOWN",),
                        )
                    return rhs_value
            old = self.precomputed
            if rhs:
                self.precomputed = old | {
                    rhs.id: rhs_value
                    if lhs
                    and lhs.type in {"member_expression", "field_access", "subscript_expression"}
                    else self.expr(rhs, text(lhs))
                }
            result = super().expression(node, purpose)
            self.precomputed = old
            return result
        if kind in {
            "binary_expression",
            "template_string",
            "ternary_expression",
            "conditional_expression",
        }:
            values = tuple(
                self.expr(c, purpose)
                for c in node.named_children
                if c.type not in {"string_fragment", "escape_sequence"}
            )
            value = join(values, self.v2limits.max_branch_states)
            if kind in {"binary_expression", "template_string"}:
                value = replace(
                    value,
                    sanitized_for=value.sanitized_for
                    - {SecurityRuleId.SEC004, SecurityRuleId.SEC006},
                    path_fact=None,
                    url_id=None,
                    object_id=None,
                )
            if (
                kind == "binary_expression"
                and text(child(node, "operator")) == "+"
                and len(values) == 2
                and all(v.literal is not None for v in values)
            ):
                value = replace(
                    value, literal=(values[0].literal or "") + (values[1].literal or "")
                )
            if (
                kind == "template_string"
                or kind == "binary_expression"
                and text(child(node, "operator")) == "+"
            ):
                value = replace(value, api_type="string")
            return self.step(value, node, "EXPRESSION")
        return super().expression(node, purpose)

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
        name = (
            text(child(node, "name"))
            if java and not construct
            else text(child(func, "property"))
            if func and func.type == "member_expression"
            else text(func)
        )
        args_node = child(node, "arguments")
        argnodes = tuple(args_node.named_children) if args_node else ()
        args = tuple(self.expr(c, purpose) for c in argnodes)
        receiver = (
            self.expr(obj)
            if obj is not None
            and (text(obj) in self.env or obj.type not in {"identifier", "type_identifier"})
            else None
        )
        q = (
            self.resolve_type(func)
            if java and construct
            else self.qualified(func)
            if not java
            else f"{receiver.api_type if receiver else self.qualified(obj)}.{name}"
        )
        first = args[0] if args else V2Value(FlowState.UNTAINTED)
        if construct:
            project = self.index.resolve_class(self.unit, text(func))
            if project:
                result = self.allocate(node, {}, V2Value(FlowState.UNTAINTED, api_type=project))
                constructors = [
                    s
                    for s in self.index.symbols
                    if s.constructor
                    and self.index.class_key(s.unit, s.class_name or "") == project
                    and len(s.parameters) == len(args)
                ]
                if len(constructors) == 1:
                    self.invoke(constructors[0], args, node, receiver=result)
                elif constructors or args:
                    self.unknown("CALL_AMBIGUOUS" if constructors else "CALL_UNRESOLVED")
                return result
            if q in {"pg.Client", "pg.Pool", "@prisma/client.PrismaClient"}:
                return V2Value(FlowState.UNTAINTED, api_type=q)
            if q == "builtin.URL" or q == "java.net.URL":
                value = self.allocate(node, {"__url_input": first}, replace(first, api_type=q))
                return replace(value, url_id=value.object_id)
            if q == "java.io.ByteArrayInputStream":
                return replace(first, api_type=q)
            if q == "java.lang.ProcessBuilder":
                vector = (
                    self.fields(first)
                    if first.object_id
                    else {str(i): v for i, v in enumerate(args)}
                )
                executable = vector.get("0", first)
                operands = join(tuple(v for k, v in vector.items() if k != "0"))
                return replace(
                    join((executable, operands)),
                    api_type=q,
                    fields=(("__executable", executable), ("__operands", operands)),
                )
        receiver_type = receiver.api_type if receiver else None
        if obj is not None and receiver_type is None:
            receiver_type = self.index.resolve_class(self.unit, text(obj))
            imported = self.imports.get(text(obj), "")
            if imported.startswith("."):
                import posixpath
                from pathlib import PurePosixPath

                path = posixpath.normpath(str(PurePosixPath(self.unit.path).parent / imported))
                unit = next(
                    (
                        u
                        for u in self.index.units
                        if u.path in {path, path + ".ts", path + "/index.ts"}
                    ),
                    None,
                )
                if unit:
                    receiver_type = "module:" + unit.path
        if not construct:
            if (
                func
                and func.type == "identifier"
                and text(func) in self.env
                and (self.env[text(func)].api_type or "").startswith("function:")
            ):
                target_id = (self.env[text(func)].api_type or "").removeprefix("function:")
                targets = tuple(
                    s
                    for s in self.index.symbols
                    if str(s.id) == target_id and len(s.parameters) == len(args)
                )
                resolution = CallResolution(
                    ResolutionState.EXACT if targets else ResolutionState.UNRESOLVED, targets
                )
            else:
                resolution = self.index.resolve(
                    self.unit,
                    self.current,
                    name,
                    len(args),
                    receiver_type,
                    local_shadow=obj is not None
                    and receiver_type is None
                    or obj is None
                    and name in self.env,
                )
            if resolution.targets:
                if (
                    receiver
                    and (receiver.api_type or "").startswith("project:")
                    and receiver.object_id is None
                    and not all(s.static for s in resolution.targets)
                ) or (
                    obj is not None
                    and receiver is None
                    and (receiver_type or "").startswith("project:")
                    and not all(s.static for s in resolution.targets)
                ):
                    resolution = CallResolution(ResolutionState.PARTIAL, resolution.targets)
                self.resolutions.append((self.reference(node), resolution))
                if resolution.state in {ResolutionState.AMBIGUOUS, ResolutionState.PARTIAL}:
                    code = (
                        "CALL_AMBIGUOUS"
                        if resolution.state == ResolutionState.AMBIGUOUS
                        else "INSTANCE_DISPATCH_UNKNOWN"
                    )
                    self.unknown(code)
                    return replace(
                        join(args),
                        state=FlowState.UNKNOWN,
                        sanitized_for=frozenset(),
                        uncertainty=(code,),
                    )
                target = resolution.targets[0]
                if not self.summary_mode:
                    summary = self.make_summary(target)
                    if summary.state == SummaryState.UNKNOWN:
                        self.unknown("SUMMARY_PARTIAL")
                        return replace(
                            join(args),
                            state=FlowState.UNKNOWN,
                            sanitized_for=frozenset(),
                            uncertainty=("SUMMARY_PARTIAL",),
                        )
                self.inbound.add(str(target.id))
                return self.invoke(target, args, node, receiver=receiver)
        if q in {
            "java.lang.Math.random",
            "java.util.Random.nextInt",
            "java.util.Random.nextLong",
            "java.util.Random.nextDouble",
            "builtin.Math.random",
        }:
            value = V2Value(
                FlowState.UNTAINTED,
                origins=(
                    ValueOrigin(
                        "RANDOMNESS",
                        (TraceStep(FlowRole.PROPAGATION, self.reference(node), "PRNG"),),
                    ),
                ),
            )
            self.context(value, "", self.reference(node))
            return value
        if q in {
            "java.security.MessageDigest.getInstance",
            "javax.crypto.Cipher.getInstance",
            "crypto.createHash",
            "crypto.createCipheriv",
        }:
            algorithm = (first.literal or "").lower().replace("-", "")
            weak = (
                algorithm in {"md5", "sha1", "des", "rc4", "descbc"}
                or algorithm.startswith("des/")
                or "/ecb/" in algorithm
            )
            origin = (
                (
                    ValueOrigin(
                        "WEAK_CRYPTO",
                        (TraceStep(FlowRole.PROPAGATION, self.reference(node), "WEAK_CRYPTO"),),
                        explicit=q in {"javax.crypto.Cipher.getInstance", "crypto.createCipheriv"},
                    ),
                )
                if weak
                else ()
            )
            value = V2Value(
                FlowState.UNTAINTED,
                api_type="crypto.Hash"
                if q == "crypto.createHash"
                else "java.security.MessageDigest"
                if q.endswith("MessageDigest.getInstance")
                else "crypto.Cipher",
                origins=origin,
            )
            self.context(value, "", self.reference(node))
            return value
        if receiver and q in {
            "crypto.Hash.update",
            "crypto.Hash.digest",
            "java.security.MessageDigest.digest",
        }:
            return self.step(
                replace(receiver, api_type="crypto.Hash" if q.endswith("update") else "string"),
                node,
                "CRYPTO_RESULT",
            )
        if q in {"java.sql.Connection.prepareStatement", "pg.Client.query", "pg.Pool.query"}:
            if q.endswith("prepareStatement"):
                if first.paths:
                    self.sink(SecurityRuleId.SEC002, node, first, "j.prepared")
                return replace(
                    first,
                    api_type="java.sql.PreparedStatement",
                    fields=(
                        (
                            "__constant_template",
                            V2Value(
                                FlowState.UNTAINTED,
                                literal="true"
                                if first.literal is not None and first.state == FlowState.UNTAINTED
                                else "false",
                            ),
                        ),
                    ),
                )
            if first.object_id:
                self.unknown("QUERY_OPTIONS_UNSUPPORTED")
                return V2Value.unknown("QUERY_OPTIONS_UNSUPPORTED")
            if first.literal is not None and first.state == FlowState.UNTAINTED and len(args) > 1:
                self.proven.append(
                    SafetyProof(
                        kind=ProofKind.SQL_PARAMETERIZATION,
                        rule_ids=(SecurityRuleId.SEC002,),
                        evidence=(self.reference(node),),
                        scope="Constant pg template and separate bind transport",
                    )
                )
                return V2Value.unknown("UNMODELED_DB_RETURN")
        if (
            receiver
            and receiver.api_type == "java.sql.PreparedStatement"
            and name in {"setString", "executeQuery", "execute", "executeUpdate"}
        ):
            if self.fields(receiver).get("__constant_template", V2Value()).literal == "true":
                self.proven.append(
                    SafetyProof(
                        kind=ProofKind.SQL_PARAMETERIZATION,
                        rule_ids=(SecurityRuleId.SEC002,),
                        evidence=(self.reference(node),),
                        scope="Constant JDBC template; bind transport distinct from SQL text",
                    )
                )
            else:
                self.unknown("SQL_TEMPLATE_UNKNOWN")
            return V2Value(FlowState.UNTAINTED)
        if q in {
            "@prisma/client.PrismaClient.$queryRawUnsafe",
            "@prisma/client.PrismaClient.$executeRawUnsafe",
        }:
            if first.object_id:
                self.unknown("SQL_ARGUMENT_UNSUPPORTED")
                return V2Value.unknown("SQL_ARGUMENT_UNSUPPORTED")
            self.sink(SecurityRuleId.SEC002, node, first, "t.prisma-unsafe")
            return V2Value.unknown("UNMODELED_DB_RETURN")
        if q in {
            "java.nio.file.Paths.get",
            "java.nio.file.Path.resolve",
            "java.nio.file.Path.normalize",
            "java.nio.file.Path.toAbsolutePath",
            "path.resolve",
            "path.join",
            "path.normalize",
        }:
            inputs = args + ((receiver,) if receiver else ())
            value = join(inputs, self.v2limits.max_branch_states)
            root = (
                receiver.path_fact
                if receiver and receiver.path_fact and receiver.path_fact.root
                else first.path_fact
                if first.path_fact and first.path_fact.root
                else None
            )
            literal = first.literal
            fact = None
            if (
                receiver
                and receiver.path_fact
                and q in {"java.nio.file.Path.normalize", "java.nio.file.Path.toAbsolutePath"}
            ):
                fact = replace(receiver.path_fact, normalized=True)
            elif root:
                fact = replace(
                    root,
                    root=False,
                    normalized=q in {"path.resolve", "java.nio.file.Path.normalize"},
                )
            elif receiver and receiver.path_fact:
                fact = replace(
                    receiver.path_fact,
                    normalized=q
                    in {"java.nio.file.Path.normalize", "java.nio.file.Path.toAbsolutePath"},
                )
            elif (
                literal
                and literal.startswith("/")
                and ".." not in literal.split("/")
                and "\\" not in literal
                and value.state == FlowState.UNTAINTED
            ):
                fact = PathFact(
                    self.reference(node).model_dump_json(),
                    literal.rstrip("/"),
                    q in {"path.resolve", "java.nio.file.Paths.get"},
                    True,
                )
            return self.step(
                replace(
                    value,
                    api_type="java.nio.file.Path" if java else "string",
                    path_fact=fact,
                    sanitized_for=value.sanitized_for - {SecurityRuleId.SEC004},
                    literal=literal if fact and fact.root else None,
                ),
                node,
                "PATH_TRANSFORM",
            )
        if receiver and receiver.url_id and name in {"getHost", "toString"}:
            return replace(
                self.object_value(receiver),
                api_type="string",
                url_part="host" if name == "getHost" else "url",
                object_id=None,
            )
        if q in {
            "javax.servlet.http.HttpServletRequest.getInputStream",
            "jakarta.servlet.http.HttpServletRequest.getInputStream",
        }:
            return replace(
                v2(FlowValue.source(self.reference(node), "j.stream-source")),
                api_type="java.io.InputStream",
            )
        if (
            q in {"java.io.ObjectInputStream.readObject", "java.io.ObjectInputStream.readUnshared"}
            and receiver
        ):
            if receiver.paths and "DESERIALIZATION_FILTER_UNKNOWN" not in receiver.uncertainty:
                self.sink(SecurityRuleId.SEC005, node, receiver, "j.deserialize")
            elif receiver.state == FlowState.UNKNOWN:
                self.unknown("DESERIALIZATION_ORIGIN_UNKNOWN")
            return V2Value.unknown("UNMODELED_DESERIALIZATION_RETURN")
        if receiver and receiver.api_type == "string" and name == "getBytes":
            return replace(receiver, api_type="bytes")
        if q == "dompurify.sanitize" and len(args) != 1:
            self.unknown("SANITIZER_CONTEXT_UNKNOWN")
            return replace(
                first,
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                uncertainty=("SANITIZER_CONTEXT_UNKNOWN",),
            )
        if (
            q in {f"{m}.{n}" for m in ("http", "https") for n in ("get", "request")}
            and first.object_id
            and not first.url_id
        ):
            self.unknown("HTTP_OPTIONS_UNSUPPORTED")
            return V2Value.unknown("HTTP_OPTIONS_UNSUPPORTED")
        if q in {"child_process.exec", "child_process.execSync"} and first.object_id:
            self.unknown("COMMAND_ARGUMENT_UNSUPPORTED")
            return V2Value.unknown("COMMAND_ARGUMENT_UNSUPPORTED")
        if q == "java.lang.Runtime.exec" and first.object_id:
            vector = self.fields(first)
            executable = vector.get("0", V2Value.unknown("COMMAND_ARGUMENT_UNSUPPORTED"))
            operands = join(tuple(v for k, v in vector.items() if k != "0"))
            if executable.paths:
                self.sink(SecurityRuleId.SEC003, node, executable, "j.exec-executable")
            elif operands.paths:
                self.sink(
                    SecurityRuleId.SEC003,
                    node,
                    replace(
                        operands,
                        state=FlowState.UNKNOWN,
                        uncertainty=("ARGUMENT_INJECTION_CONTEXT_UNKNOWN",),
                    ),
                    "j.exec-argv",
                )
            return V2Value.unknown("UNMODELED_PROCESS_RETURN")
        if (
            q in {f"child_process.{n}" for n in ("spawn", "spawnSync")}
            or q == "java.lang.ProcessBuilder.start"
        ):
            if q.startswith("child_process"):
                operands = args[1] if len(args) > 1 else V2Value(FlowState.UNTAINTED)
                options = args[2] if len(args) > 2 else V2Value(FlowState.UNTAINTED)
                shell = self.fields(options).get("shell")
                if shell and shell.literal == "true":
                    self.sink(SecurityRuleId.SEC003, node, join(args[:2]), "t.exec-shell")
                elif (
                    shell
                    and shell.literal not in {"false", None}
                    or options.state == FlowState.UNKNOWN
                ):
                    self.unknown("COMMAND_BOUNDARY_UNKNOWN")
                elif first.paths:
                    self.sink(SecurityRuleId.SEC003, node, first, "t.exec-executable")
                elif operands.paths:
                    self.proven.append(
                        SafetyProof(
                            kind=ProofKind.COMMAND_ARGUMENT_BOUNDARY,
                            rule_ids=(SecurityRuleId.SEC003,),
                            evidence=(self.reference(node),),
                            scope="No modeled shell; argument injection is not proven safe",
                        )
                    )
                    self.sink(
                        SecurityRuleId.SEC003,
                        node,
                        replace(
                            operands,
                            state=FlowState.UNKNOWN,
                            uncertainty=("ARGUMENT_INJECTION_CONTEXT_UNKNOWN",),
                        ),
                        "t.exec-argv",
                    )
            elif receiver:
                executable = self.fields(receiver).get("__executable", receiver)
                operands = self.fields(receiver).get("__operands", V2Value(FlowState.UNTAINTED))
                if executable.paths:
                    self.sink(SecurityRuleId.SEC003, node, executable, "j.exec-executable")
                elif operands.paths:
                    explicit_shell = executable.literal in {"sh", "bash", "cmd", "powershell"}
                    self.sink(
                        SecurityRuleId.SEC003,
                        node,
                        operands
                        if explicit_shell
                        else replace(
                            operands,
                            state=FlowState.UNKNOWN,
                            uncertainty=("ARGUMENT_INJECTION_CONTEXT_UNKNOWN",),
                        ),
                        "j.exec-shell" if explicit_shell else "j.exec-argv",
                    )
            return V2Value.unknown("UNMODELED_PROCESS_RETURN")
        old = self.precomputed
        self.precomputed = (
            old
            | {c.id: v for c, v in zip(argnodes, args, strict=True)}
            | ({obj.id: receiver} if obj is not None and receiver is not None else {})
        )
        result = v2(super().call(node, purpose))
        self.precomputed = old
        if (
            "INTERPROCEDURAL_BOUNDARY" in self.output.diagnostics
            and result.state == FlowState.UNKNOWN
            and "INTERPROCEDURAL_BOUNDARY" in result.uncertainty
        ):
            self.unknown("CALL_UNRESOLVED")
            joined = join((*args, *((receiver,) if receiver else ())))
            return replace(
                joined,
                state=FlowState.UNKNOWN,
                sanitized_for=frozenset(),
                path_fact=None,
                url_id=None,
                uncertainty=tuple(sorted({*joined.uncertainty, "CALL_UNRESOLVED"})),
            )
        if q == "dompurify.sanitize" and len(args) == 1:
            self.proven.append(
                SafetyProof(
                    kind=ProofKind.XSS_SANITIZATION,
                    rule_ids=(SecurityRuleId.SEC007,),
                    evidence=(self.reference(node),),
                    scope="Default DOMPurify for HTML only",
                )
            )
        return result

    def sink(self, rule: SecurityRuleId, node: Node, value: FlowValue, api_id: str) -> None:
        if len(self.output.candidates) >= self.v2limits.max_candidates:
            self.unknown("CANDIDATE_LIMIT")
            return
        value = self.object_value(value)
        if rule in value.sanitized_for:
            return
        if value.state == FlowState.UNKNOWN:
            self.unknown("UNKNOWN_FLOW")
        if not value.paths:
            return
        if any(len(p) >= self.v2limits.flow_bound for p in value.paths):
            value = replace(
                value,
                state=FlowState.UNKNOWN,
                uncertainty=tuple(sorted({*value.uncertainty, "TOTAL_FLOW_LIMIT"})),
                paths=tuple(p[: self.v2limits.flow_bound - 1] for p in value.paths),
            )
            self.unknown("TOTAL_FLOW_LIMIT")
        self.output.candidates.append(
            V2Candidate(
                rule,
                self.reference(node),
                api_id,
                value,
                SecurityFindingStatus.POTENTIAL
                if value.state == FlowState.UNKNOWN
                else SecurityFindingStatus.SUPPORTED,
            )
        )

    def finalize_static(self) -> None:
        for (kind, _), (origin, tags) in sorted(self.static_contexts.items()):
            if len(self.output.candidates) >= self.v2limits.max_candidates:
                self.unknown("CANDIDATE_LIMIT")
                break
            if kind == "RANDOMNESS" and "SECURITY" not in tags:
                continue
            if (
                kind == "WEAK_CRYPTO"
                and not origin.explicit
                and "NONSECURITY" in tags
                and "SECURITY" not in tags
            ):
                continue
            rule = SecurityRuleId.SEC009 if kind == "RANDOMNESS" else SecurityRuleId.SEC008
            status = (
                SecurityFindingStatus.CONFIRMED_PATTERN
                if origin.explicit or "SECURITY" in tags
                else SecurityFindingStatus.POTENTIAL
            )
            self.output.candidates.append(
                V2Candidate(
                    rule, origin.trace[0].source, kind, status=status, supporting_steps=origin.trace
                )
            )

    def pattern(
        self, rule: SecurityRuleId, node: Node, api_id: str, status: SecurityFindingStatus
    ) -> None:
        if len(self.output.candidates) >= self.v2limits.max_candidates:
            self.unknown("CANDIDATE_LIMIT")
            return
        super().pattern(rule, node, api_id, status)
