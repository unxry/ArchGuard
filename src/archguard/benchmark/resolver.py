from enum import StrEnum

from archguard.benchmark.models import Locator, Subjects
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import NodeKind
from archguard.iam.model import ArchitectureModel
from archguard.iam.nodes import ArchitectureNode


class ResolutionStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING = "MISSING"


class LocatorResolver:
    def __init__(self, iam: ArchitectureModel) -> None:
        self.iam = iam
        self.nodes = {n.id: n for n in iam.nodes}
        self.symbols = {s.id: s for s in iam.symbols}

    def locator(self, node: ArchitectureNode) -> Locator:
        if node.source_location is None:
            raise ValueError("subject has no source locator")
        symbol = self.symbols.get(node.symbol_id) if node.symbol_id else None
        return Locator(
            path=node.source_location.file_path,
            language=node.language,
            qualified_name=node.qualified_name,
            kind=node.kind,
            signature=symbol.signature if symbol else None,
        )

    def resolve(self, locator: Locator) -> tuple[ResolutionStatus, tuple[NodeId, ...]]:
        found = tuple(
            sorted(
                (
                    n.id
                    for n in self.iam.nodes
                    if n.source_location
                    and n.source_location.file_path == locator.path
                    and n.language == locator.language
                    and n.kind == locator.kind
                    and n.qualified_name == locator.qualified_name
                    and (
                        locator.signature is None or self.locator(n).signature == locator.signature
                    )
                ),
                key=str,
            )
        )
        status = (
            ResolutionStatus.MISSING
            if not found
            else ResolutionStatus.RESOLVED
            if len(found) == 1
            else ResolutionStatus.AMBIGUOUS
        )
        return status, found

    def subjects(self, subjects: Subjects) -> tuple[NodeId, ...] | None:
        values = [self.resolve(x) for x in subjects.locators]
        if any(status != ResolutionStatus.RESOLVED for status, _ in values):
            return None
        return tuple(v[0] for _, v in values)

    def normalize(self, node_id: NodeId, kind: NodeKind) -> ArchitectureNode:
        current = self.nodes[node_id]
        if current.kind == NodeKind.FILE and kind == NodeKind.CLASS:
            children = [
                n
                for n in self.iam.nodes
                if n.file_id == current.file_id and n.kind == NodeKind.CLASS
            ]
            if len(children) != 1:
                raise ValueError("file has ambiguous class granularity")
            return children[0]
        visited: set[NodeId] = set()
        while current.kind != kind and current.id not in visited:
            visited.add(current.id)
            parent = current.attributes.get("parent_node_id")
            if not isinstance(parent, str):
                break
            from uuid import UUID

            current = self.nodes[NodeId(UUID(parent))]
        if current.kind != kind:
            raise ValueError("cannot normalize subject to requested granularity")
        return current

    def from_ids(
        self, ids: tuple[NodeId, ...], *, directed: bool = False, kind: NodeKind | None = None
    ) -> Subjects:
        nodes = [self.normalize(i, kind) if kind else self.nodes[i] for i in ids]
        locators = {self.locator(n).model_dump_json(): self.locator(n) for n in nodes}
        values = (
            tuple(self.locator(n) for n in nodes)
            if directed
            else tuple(locators[k] for k in sorted(locators))
        )
        return Subjects(locators=values, directed=directed)
