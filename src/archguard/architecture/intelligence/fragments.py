import hashlib
from dataclasses import dataclass

from archguard.architecture.intelligence.models import (
    ContextSelectionConfig,
    FragmentReference,
    SelectedNode,
    SourceFragment,
)
from archguard.architecture.intelligence.ports import ContextRedactor, SourceReader
from archguard.core.identifiers import NodeId
from archguard.core.model.enums import Language
from archguard.iam.model import ArchitectureModel


@dataclass
class _Range:
    path: str
    start: int
    end: int
    node_ids: list[NodeId]
    language: Language
    purpose: str
    truncated: bool
    priority: int


def extract_fragments(
    iam: ArchitectureModel,
    selected: tuple[SelectedNode, ...],
    workspace: SourceReader,
    config: ContextSelectionConfig,
    redactor: ContextRedactor | None,
) -> tuple[tuple[SourceFragment, ...], int, int, tuple[str, ...]]:
    nodes = {node.id: node for node in iam.nodes}
    ranges: list[_Range] = []
    files: set[str] = set()
    rejected_files: set[str] = set()
    dropped = 0
    for priority, selection in enumerate(selected):
        node = nodes[selection.node_id]
        location = node.source_location
        if location is None:
            dropped += 1
            continue
        path = location.file_path
        if path not in files and len(files) >= config.max_files:
            rejected_files.add(path)
            dropped += 1
            continue
        files.add(path)
        start = max(1, location.start_line - config.before_lines)
        requested_end = (location.end_line or location.start_line) + config.after_lines
        end = min(requested_end, start + config.max_lines_per_fragment - 1)
        overlap = next(
            (
                item
                for item in ranges
                if item.path == path and item.start <= end and start <= item.end
            ),
            None,
        )
        if overlap is not None:
            # Preserve higher-priority coordinates instead of expanding them beyond the budget.
            overlap.node_ids.append(node.id)
            overlap.truncated |= start < overlap.start or end > overlap.end
            continue
        if len(ranges) >= config.max_fragments:
            dropped += 1
            continue
        ranges.append(
            _Range(
                path,
                start,
                end,
                [node.id],
                node.language,
                selection.reason,
                end < requested_end,
                priority,
            )
        )
    texts: dict[int, list[str]] = {item.priority: [] for item in ranges}
    errors: list[str] = []
    for path in sorted({item.path for item in ranges}):
        relevant = [item for item in ranges if item.path == path]
        final_line = max(item.end for item in relevant)
        scanned = 0
        try:
            with workspace.open_source_file(path) as stream:
                for line_number in range(1, final_line + 1):
                    remaining = config.max_scan_bytes_per_file - scanned
                    if remaining <= 0:
                        for item in relevant:
                            item.truncated = True
                        break
                    raw = stream.readline(min(config.max_line_bytes + 1, remaining))
                    if not raw:
                        for item in relevant:
                            item.end = min(item.end, line_number - 1)
                        break
                    scanned += len(raw)
                    too_long = len(raw) > config.max_line_bytes or (
                        scanned == config.max_scan_bytes_per_file and not raw.endswith(b"\n")
                    )
                    for item in relevant:
                        if item.start <= line_number <= item.end:
                            accumulated = sum(map(len, texts[item.priority]))
                            value = raw.decode("utf-8", errors="replace")
                            room = max(0, config.max_fragment_chars - accumulated)
                            texts[item.priority].append(value[:room])
                            item.truncated |= len(value) > room or too_long
                        elif too_long:
                            item.truncated = True
                    if too_long or all(
                        line_number >= item.end
                        or sum(map(len, texts[item.priority])) >= config.max_fragment_chars
                        for item in relevant
                    ):
                        break
        except Exception:
            # SourceReader may report race/path/intake failures; never expose its input or source.
            errors.append(path)
    result: list[SourceFragment] = []
    for item in ranges:
        text = "".join(texts[item.priority])
        if not text:
            dropped += 1
            continue
        if redactor is not None:
            try:
                redacted = redactor.redact(text)
                if redacted.count("\n") != text.count("\n"):
                    raise ValueError("redactor must preserve line alignment")
                text = redacted
            except Exception:
                errors.append(item.path)
                dropped += 1
                continue
        item.truncated |= len(text) > config.max_fragment_chars
        text = text[: config.max_fragment_chars]
        end = item.start + max(0, len(text.splitlines()) - 1)
        result.append(
            SourceFragment(
                reference=FragmentReference(
                    evidence_id=f"SRC{len(result) + 1:03}",
                    relative_path=item.path,
                    start_line=item.start,
                    end_line=end,
                    node_ids=tuple(sorted(set(item.node_ids), key=str)),
                    language=item.language,
                    purpose=item.purpose,
                    truncated=item.truncated or end < item.end,
                    content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    chars=len(text),
                ),
                text=text,
            )
        )
    return tuple(result), len(rejected_files), dropped, tuple(errors)
