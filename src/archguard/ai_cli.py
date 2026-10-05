import argparse
from pathlib import Path

from pydantic import ValidationError

from archguard.application.analyze_architecture_semantics import AnalyzeArchitectureSemantics
from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.graph.enums import NeighbourhoodDirection
from archguard.architecture.intelligence.context import GraphGuidedContextBuilder
from archguard.architecture.intelligence.models import (
    RULES,
    AIAnalysisConfig,
    ContextDiagnostic,
    ContextStrategy,
    serialize_ai,
)
from archguard.architecture.intelligence.ports import LLMProviderError
from archguard.architecture.intelligence.selection import resolve_node
from archguard.core.model.enums import EdgeKind
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.ai_configuration import load_ai_configuration
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.llm_provider import AIProviderSettings, create_llm_provider
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy


def ai_arguments(parser: argparse.ArgumentParser, command: str) -> None:
    parser.add_argument("--config", type=Path)
    parser.add_argument("--spec", type=Path)
    parser.add_argument("--strategy", choices=[item.value for item in ContextStrategy])
    parser.add_argument("--hops", type=int)
    parser.add_argument("--direction", choices=[item.value for item in NeighbourhoodDirection])
    parser.add_argument("--relations", nargs="+", choices=[item.value for item in EdgeKind])
    for name in ("nodes", "files", "fragments", "total-chars"):
        parser.add_argument("--max-" + name, type=int)
    if command == "context":
        parser.add_argument("--node", required=True)
        parser.add_argument(
            "--show-source", action="store_true", help="Explicit local source inspection"
        )
    else:
        parser.add_argument("--target", action="append", default=[])
        parser.add_argument("--rule", action="append", choices=list(RULES), default=[])
        parser.add_argument("--provider", choices=["openai"])
        parser.add_argument("--model")
        parser.add_argument("--allow-remote-ai", action="store_true")
        parser.add_argument("--dry-run", action="store_true")


def execute_ai(arguments: argparse.Namespace) -> int:
    base = load_ai_configuration(arguments.config) if arguments.config else AIAnalysisConfig()
    context = base.context.model_dump()
    for argument, field in (
        ("strategy", "strategy"),
        ("hops", "hop_count"),
        ("direction", "direction"),
        ("max_nodes", "max_nodes"),
        ("max_files", "max_files"),
        ("max_fragments", "max_fragments"),
        ("max_total_chars", "max_total_chars"),
    ):
        value = getattr(arguments, argument)
        if value is not None:
            context[field] = value
    if arguments.relations is not None:
        context["included_relations"] = arguments.relations
    settings = base.model_dump()
    settings["context"] = context
    settings["allow_remote_source"] = bool(getattr(arguments, "allow_remote_ai", False))
    if arguments.command == "analyze":
        targets = base.targets.model_dump()
        if arguments.target:
            targets["explicit_targets"] = arguments.target
        if arguments.rule:
            targets["rules"] = arguments.rule
        settings["targets"] = targets
    config = AIAnalysisConfig.model_validate(settings)
    spec = load_architecture_file(arguments.spec) if arguments.spec else None
    source = RepositoryInput(
        source_type=RepositorySourceType(arguments.source.upper()),
        location=arguments.location,
        ref=arguments.ref,
    )
    policy = RepositoryScanPolicy(
        extra_exclusions=tuple(arguments.exclude), respect_gitignore=not arguments.no_gitignore
    )
    application = AnalyzeArchitectureSemantics(
        BuildIAM(
            ParseRepository(
                create_parser_registry(), ParserConfig(strict_syntax_errors=arguments.strict)
            ),
            create_extractor_registry(),
            ExtractionConfig(repository_namespace=arguments.namespace),
        )
    )
    with create_discovery(policy).open(source) as repository:
        if arguments.command == "context":
            inputs = application.prepare(repository.snapshot, repository.workspace, config)
            target = resolve_node(inputs.iam, arguments.node)
            pack = GraphGuidedContextBuilder().build(
                target,
                inputs.iam,
                inputs.graph,
                repository.workspace,
                config.context,
                spec,
                inputs.discovery,
            )
            rendered = serialize_ai(pack if arguments.show_source else pack.manifest)
            exit_code = 0
            summary = (
                f"Context {config.context.strategy}: {pack.manifest.context_chars} chars; "
                f"{len(pack.manifest.selected_nodes)} nodes; {pack.manifest.files} files; "
                f"{len(pack.manifest.fragments)} fragments; truncated={pack.manifest.truncated}"
            )
        else:
            provider = None
            diagnostic = None
            if not arguments.dry_run:
                try:
                    provider_settings = AIProviderSettings()
                    overrides = provider_settings.model_dump()
                    if arguments.provider:
                        overrides["provider"] = arguments.provider
                    if arguments.model:
                        overrides["model"] = arguments.model
                    provider = create_llm_provider(AIProviderSettings.model_validate(overrides))
                except (LLMProviderError, ValidationError) as error:
                    diagnostic = ContextDiagnostic(
                        code=error.code
                        if isinstance(error, LLMProviderError)
                        else "AI_PROVIDER_CONFIGURATION_REQUIRED",
                        message="provider configuration is unavailable",
                    )
            result = application.execute(
                repository.snapshot, repository.workspace, config, provider, spec, arguments.dry_run
            )
            if diagnostic is not None:
                result = result.model_copy(
                    update={"diagnostics": (*result.diagnostics, diagnostic)}
                )
            rendered = serialize_ai(result)
            exit_code = (
                0
                if result.status in {"DRY_RUN", "COMPLETE"}
                else 2
                if result.status == "INVALID"
                else 3
            )
            summary = (
                f"AI analysis: {result.status}; calls={result.calls}; "
                f"semantic candidates={len(result.candidates)}; skipped={result.skipped_targets}"
            )
    if arguments.output is not None:
        arguments.output.write_text(rendered, encoding="utf-8")
    print(
        rendered if arguments.json or getattr(arguments, "show_source", False) else summary,
        end="" if arguments.json or getattr(arguments, "show_source", False) else "\n",
    )
    return exit_code
