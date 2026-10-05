import argparse
from pathlib import Path

from archguard.application.analyze_architecture_hybrid import AnalyzeArchitectureHybrid
from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig
from archguard.architecture.hybrid.models import HybridAnalysisResult
from archguard.architecture.hybrid.serialization import serialize_hybrid
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.hybrid_configuration import (
    load_hybrid_ai_result,
    load_hybrid_configuration,
)
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy


def hybrid_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", type=Path, help="Typed Hybrid configuration JSON")
    parser.add_argument("--spec", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--without-ai", action="store_true", help="Explicit offline analysis without AI"
    )
    mode.add_argument("--ai-result", type=Path, help="Saved source-free AI analysis JSON")


def human_summary(result: HybridAnalysisResult) -> str:
    stats = result.statistics
    lines = [
        f"Hybrid: {len(result.cases)} cases; "
        f"confirmed Findings={len(result.confirmed_finding_ids)}; "
        f"review={len(result.review_case_ids)}",
        "States: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.decisions_by_state.items())),
        "Channels: " + ", ".join(f"{k}={v}" for k, v in sorted(stats.channel_cases.items())),
        f"Agreement={stats.agreements}; conflict={stats.conflicts}; missing={stats.missing}; "
        f"omitted candidates={stats.omitted_candidate_cases}",
    ]
    lines.extend(
        f"{c.rule_id}: {d.state.value}; "
        f"severity={d.severity.value if d.severity else 'null'}; confidence=null"
        for c, d in zip(result.cases, result.decisions, strict=True)
    )
    lines.append(
        "Graph and AI signals are uncalibrated review candidates, not confirmed violations."
    )
    if result.diagnostics:
        lines.append("Diagnostics: " + ", ".join(result.diagnostics))
    return "\n".join(lines)


def execute_hybrid(arguments: argparse.Namespace) -> int:
    config = (
        load_hybrid_configuration(arguments.config) if arguments.config else HybridAnalysisConfig()
    )
    spec = load_architecture_file(arguments.spec) if arguments.spec else None
    ai = load_hybrid_ai_result(arguments.ai_result) if arguments.ai_result else None
    building = BuildIAM(
        ParseRepository(
            create_parser_registry(), ParserConfig(strict_syntax_errors=arguments.strict)
        ),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace=arguments.namespace),
    )
    source = RepositoryInput(
        source_type=RepositorySourceType(arguments.source.upper()),
        location=arguments.location,
        ref=arguments.ref,
    )
    policy = RepositoryScanPolicy(
        extra_exclusions=tuple(arguments.exclude), respect_gitignore=not arguments.no_gitignore
    )
    with create_discovery(policy).open(source) as repository:
        result = AnalyzeArchitectureHybrid(building).execute(
            repository.snapshot, repository.workspace, config, spec, saved_ai=ai
        )
    rendered = serialize_hybrid(result)
    if arguments.output:
        arguments.output.write_text(rendered, encoding="utf-8")
    print(rendered if arguments.json else human_summary(result), end="" if arguments.json else "\n")
    return 2 if "INVALID" in result.diagnostics or "AI_INVALID" in result.diagnostics else 0
