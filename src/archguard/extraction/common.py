import re
from collections.abc import Iterator

from tree_sitter import Node

from archguard.core.locations import SourceLocation


def walk(root: Node) -> Iterator[Node]:
    cursor = root.walk()
    while True:
        node = cursor.node
        assert node is not None
        if not (node.is_error or node.is_missing):
            yield node
            if cursor.goto_first_child():
                continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return


def child(node: Node, name: str) -> Node | None:
    return node.child_by_field_name(name)


def text(node: Node | None) -> str:
    if node is None:
        return ""
    data = node.text
    return data.decode("utf-8") if data is not None else ""


def dotted_name(node: Node | None) -> str | None:
    if node is None:
        return None
    value = text(node)
    return value if re.fullmatch(r"[#\w$]+(?:\.[#\w$]+)*", value) else None


def location(node: Node, path: str) -> SourceLocation:
    # py-tree-sitter 0.26.0 Point attribute getters return borrowed references.
    start_row, start_column = node.start_point
    end_row, end_column = node.end_point
    start = (start_row + 1, start_column + 1)
    if node.end_byte <= node.start_byte:
        return SourceLocation(file_path=path, start_line=start[0], start_column=start[1])
    if end_column:
        end = (end_row + 1, end_column)
    else:
        data = node.text or b""
        previous_newline = data.rfind(b"\n", 0, max(0, len(data) - 1))
        column = len(data) - previous_newline - 1
        if previous_newline < 0:
            column += start_column
        end = (end_row, max(1, column))
    return SourceLocation(
        file_path=path,
        start_line=start[0],
        start_column=start[1],
        end_line=end[0],
        end_column=end[1],
    )


def type_signature(node: Node | None) -> str | None:
    if node is None:
        return None
    tokens: list[str] = []
    pending = [node]
    while pending:
        current = pending.pop()
        if current.type in {"annotation", "marker_annotation"}:
            if name := dotted_name(child(current, "name")):
                tokens.append(name)
        elif current.type in {
            "string",
            "string_literal",
            "number",
            "literal_type",
            "template_literal_type",
        }:
            tokens.append("literal")
        elif current.children:
            pending.extend(reversed(current.children))
        else:
            value = text(current)
            if re.fullmatch(r"[\w$]+|[.<>,\[\]?|&]", value):
                tokens.append(value)
    return "".join(tokens)[:512] or None


def module_literal(node: Node | None) -> str | None:
    if node is None or node.type != "string":
        return None
    value = text(node)[1:-1]
    if re.fullmatch(
        r"(?:\.{1,2}/[\w./-]+|(?:@[\w.-]+/)?[\w.-]+(?:/[\w.-]+)*|node:[\w./-]+)", value
    ):
        return value
    return None
