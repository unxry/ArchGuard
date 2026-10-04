from dataclasses import dataclass

from tree_sitter import Node

from archguard.parsing.config import ParserConfig
from archguard.parsing.enums import DiagnosticSeverity, ParserDiagnosticCode
from archguard.parsing.models import ParserDiagnostic


@dataclass(frozen=True)
class SyntaxDiagnostics:
    error_nodes: int
    missing_nodes: int
    diagnostics: tuple[ParserDiagnostic, ...]


def collect_syntax_diagnostics(
    root: Node, relative_path: str, config: ParserConfig
) -> SyntaxDiagnostics:
    errors = missing = 0
    diagnostics: list[ParserDiagnostic] = []
    cursor = root.walk()
    while True:
        node = cursor.node
        assert node is not None
        if node.is_error or node.is_missing:
            errors += node.is_error
            missing += node.is_missing
            if config.collect_error_nodes and len(diagnostics) < config.max_diagnostics_per_file:
                diagnostics.append(
                    ParserDiagnostic(
                        relative_path=relative_path,
                        code=(
                            ParserDiagnosticCode.MISSING_NODE
                            if node.is_missing
                            else ParserDiagnosticCode.SYNTAX_ERROR
                        ),
                        message=(
                            "required syntax token is missing"
                            if node.is_missing
                            else "syntax error detected"
                        ),
                        line=node.start_point.row + 1,
                        column=node.start_point.column + 1,
                        start_byte=node.start_byte,
                        end_byte=node.end_byte,
                    )
                )
        if cursor.goto_first_child():
            continue
        while not cursor.goto_next_sibling():
            if not cursor.goto_parent():
                return _finish(relative_path, config, errors, missing, diagnostics)


def _finish(
    relative_path: str,
    config: ParserConfig,
    errors: int,
    missing: int,
    diagnostics: list[ParserDiagnostic],
) -> SyntaxDiagnostics:
    if errors or missing:
        if not config.collect_error_nodes:
            diagnostics.append(
                ParserDiagnostic(
                    relative_path=relative_path,
                    code=ParserDiagnosticCode.SYNTAX_ERROR,
                    message="syntax errors detected; detailed node diagnostics are disabled",
                )
            )
        elif errors + missing > len(diagnostics):
            diagnostics.append(
                ParserDiagnostic(
                    relative_path=relative_path,
                    code=ParserDiagnosticCode.DIAGNOSTICS_TRUNCATED,
                    severity=DiagnosticSeverity.WARNING,
                    message="syntax diagnostic limit reached; node counts remain complete",
                )
            )
    return SyntaxDiagnostics(errors, missing, tuple(diagnostics))
