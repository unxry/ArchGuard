import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.errors import IAMValidationError
from archguard.extraction.factory import create_extractor_registry
from archguard.iam_building.models import IAMBuildResult
from archguard.iam_building.serialization import serialize_iam
from archguard.infrastructure.logging import JsonFormatter
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.parsing.models import ParseRepositoryResult
from archguard.repository.enums import RepositorySourceType
from archguard.repository.errors import RepositoryIntakeError
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="archguard")
    groups = parser.add_subparsers(dest="group", required=True)
    for name, aliases, description in (
        ("repo", ["repository"], "Discover files without parsing or executing code"),
        ("parse", [], "Parse eligible sources without extraction or code execution"),
        ("iam", [], "Build IAM from syntax facts and conservative reference resolution"),
    ):
        group = groups.add_parser(name, aliases=aliases)
        commands = group.add_subparsers(dest="command", required=True)
        inspect = commands.add_parser("build" if name == "iam" else "inspect", help=description)
        inspect.add_argument("location")
        inspect.add_argument("--source", choices=["local", "zip", "git"], default="local")
        inspect.add_argument("--ref", help="Public Git branch, tag or full commit SHA")
        inspect.add_argument("--exclude", action="append", default=[])
        inspect.add_argument("--no-gitignore", action="store_true")
        inspect.add_argument("--json", action="store_true")
        if name in {"parse", "iam"}:
            inspect.add_argument("--strict", action="store_true", help="Mark syntax errors invalid")
        if name == "iam":
            inspect.add_argument(
                "--output", type=Path, help="Write deterministic ArchitectureModel JSON"
            )
            inspect.add_argument(
                "--namespace",
                default="archguard:default-project",
                help="Stable project identity namespace",
            )
    return parser


def _print_summary(snapshot: RepositorySnapshot) -> None:
    print(f"Root: {snapshot.root} ({snapshot.source_type.value})")
    print(f"Revision: {snapshot.revision or 'not applicable'}")
    print("Languages: " + ", ".join(language.value for language in snapshot.detected_languages))
    stats = snapshot.statistics
    print(
        f"Files: {stats.total_files}; sources: {stats.source_files}; "
        f"tests: {stats.test_files}; eligible: {stats.eligible_files}"
    )
    print("Manifests: " + (", ".join(snapshot.manifests) or "none"))
    print("Lockfiles: " + (", ".join(snapshot.lockfiles) or "none"))
    print(f"Supported for analysis: {snapshot.supported_for_analysis}")
    print(f"Fingerprint: {snapshot.fingerprint}")


def _print_parse_summary(result: ParseRepositoryResult) -> None:
    stats = result.statistics
    print(f"Snapshot: {result.snapshot_id}")
    print(f"Fingerprint: {result.snapshot_fingerprint}")
    print(
        f"Candidates: {stats.total_candidates}; parsed: {stats.parsed_files}; "
        f"skipped: {stats.skipped_files}; unsupported: {stats.unsupported_files}; "
        f"failed: {stats.failed_files}"
    )
    print(
        f"Syntax error files: {stats.syntax_error_files}; ERROR nodes: {stats.syntax_error_nodes}; "
        f"missing nodes: {stats.missing_nodes}; valid: {result.is_valid}"
    )
    for parser in result.parser_versions:
        print(
            f"{parser.language.value}: {parser.parser_id} {parser.implementation_version}; "
            f"grammar {parser.grammar_version}; Tree-sitter {parser.runtime_version}"
        )


def _print_iam_summary(result: IAMBuildResult) -> None:
    print(f"Repository: {result.iam.project.name}")
    print(f"Fingerprint: {result.parsing.snapshot_fingerprint}")
    print("Languages: " + ", ".join(sorted({file.parser.language.value for file in result.facts})))
    stats = result.statistics
    print(
        f"Files extracted: {stats.files_extracted}/{stats.files_seen}; "
        f"declarations: {stats.declarations_total}; imports: {stats.imports_total}; "
        f"references: {stats.references_total}"
    )
    print(
        f"Resolved: {stats.references_resolved}; ambiguous: {stats.references_ambiguous}; "
        f"unresolved: {stats.references_unresolved}; external: {stats.references_external}"
    )
    print(
        f"Nodes: {stats.nodes_created}; edges: {stats.edges_created}; "
        f"external nodes: {stats.external_nodes}"
    )
    print(
        f"IAM schema: {result.iam.iam_schema_version}; builder: {result.builder_version}; "
        f"resolver: {result.resolver_version}"
    )
    print(f"Valid: {result.is_valid}; complete: {result.is_complete}")
    for extractor in sorted(
        {file.extractor for file in result.facts}, key=lambda item: item.extractor_id
    ):
        print(f"Extractor: {extractor.extractor_id} {extractor.extractor_version}")


def main(argv: Sequence[str] | None = None) -> int:
    arguments = _parser().parse_args(argv)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter())
    loggers = [
        logging.getLogger(name)
        for name in ("archguard.repository", "archguard.parsing", "archguard.extraction")
    ]
    logger_states = [(logger.level, logger.propagate) for logger in loggers]
    for logger in loggers:
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    parse_result = None
    iam_result = None
    try:
        try:
            policy = RepositoryScanPolicy(
                extra_exclusions=tuple(arguments.exclude),
                respect_gitignore=not arguments.no_gitignore,
            )
            source = RepositoryInput(
                source_type=RepositorySourceType(arguments.source.upper()),
                location=arguments.location,
                ref=arguments.ref,
            )
            discovery = create_discovery(policy)
            if arguments.group in {"parse", "iam"}:
                config = ParserConfig(strict_syntax_errors=arguments.strict)
                with discovery.open(source) as repository:
                    parsing = ParseRepository(create_parser_registry(), config)
                    if arguments.group == "iam":
                        iam_result = BuildIAM(
                            parsing,
                            create_extractor_registry(),
                            ExtractionConfig(repository_namespace=arguments.namespace),
                        ).execute(repository.snapshot, repository.workspace)
                        if arguments.output is not None:
                            arguments.output.write_text(
                                serialize_iam(iam_result.iam), encoding="utf-8"
                            )
                    else:
                        parse_result = parsing.execute(repository.snapshot, repository.workspace)
                snapshot = repository.snapshot
            else:
                snapshot = discovery.execute(source)
        except (RepositoryIntakeError, ValidationError, IAMValidationError, OSError) as error:
            code = (
                error.code
                if isinstance(error, RepositoryIntakeError)
                else "iam_validation_error"
                if isinstance(error, IAMValidationError)
                else "output_write_error"
                if isinstance(error, OSError)
                else "invalid_repository_input"
            )
            message = (
                str(error)
                if isinstance(error, RepositoryIntakeError)
                else "IAM structure could not be validated"
                if isinstance(error, IAMValidationError)
                else "IAM output could not be written"
                if isinstance(error, OSError)
                else "repository input or scan policy is invalid"
            )
            if arguments.json:
                print(json.dumps({"error": {"code": code, "message": message}}), file=sys.stderr)
            else:
                print(f"{code}: {message}", file=sys.stderr)
            return 2
        if arguments.json:
            result = (
                iam_result
                if iam_result is not None
                else parse_result
                if parse_result is not None
                else snapshot
            )
            print(result.model_dump_json(indent=2))
        elif iam_result is not None:
            _print_iam_summary(iam_result)
        elif parse_result is not None:
            _print_parse_summary(parse_result)
        else:
            _print_summary(snapshot)
        return (
            3
            if (
                (parse_result is not None and not parse_result.is_valid)
                or (iam_result is not None and not iam_result.is_valid)
            )
            else 0
        )
    finally:
        for logger, (old_level, old_propagate) in zip(loggers, logger_states, strict=True):
            logger.removeHandler(handler)
            logger.setLevel(old_level)
            logger.propagate = old_propagate
        handler.close()


if __name__ == "__main__":
    raise SystemExit(main())
