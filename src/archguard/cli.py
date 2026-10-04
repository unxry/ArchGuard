import argparse
import json
import logging
import sys
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from archguard.application.build_iam import BuildIAM
from archguard.application.check_architecture import CheckArchitecture
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.conformance.analyzer import serialize_conformance
from archguard.architecture.conformance.models import ConformanceStatus, StaticConformanceResult
from archguard.architecture.specification.errors import ArchitectureSpecificationError
from archguard.architecture.specification.models import ArchitectureSpecification
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.errors import IAMValidationError
from archguard.extraction.factory import create_extractor_registry
from archguard.iam_building.models import IAMBuildResult
from archguard.iam_building.serialization import serialize_iam
from archguard.infrastructure.architecture_specification import load_architecture_file
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
        (
            "architecture",
            [],
            "Check explicit target architecture against resolved IAM dependencies",
        ),
    ):
        group = groups.add_parser(name, aliases=aliases)
        commands = group.add_subparsers(dest="command", required=True)
        command = "build" if name == "iam" else "check" if name == "architecture" else "inspect"
        inspect = commands.add_parser(command, help=description)
        inspect.add_argument("location")
        inspect.add_argument("--source", choices=["local", "zip", "git"], default="local")
        inspect.add_argument("--ref", help="Public Git branch, tag or full commit SHA")
        inspect.add_argument("--exclude", action="append", default=[])
        inspect.add_argument("--no-gitignore", action="store_true")
        inspect.add_argument("--json", action="store_true")
        if name in {"parse", "iam", "architecture"}:
            inspect.add_argument("--strict", action="store_true", help="Mark syntax errors invalid")
        if name in {"iam", "architecture"}:
            inspect.add_argument("--output", type=Path, help="Write deterministic analysis JSON")
            inspect.add_argument(
                "--namespace",
                default="archguard:default-project",
                help="Stable project identity namespace",
            )
        if name == "architecture":
            inspect.add_argument("--spec", type=Path, required=True)
            validate = commands.add_parser("validate", help="Validate target architecture YAML")
            validate.add_argument("spec", type=Path)
            validate.add_argument("--json", action="store_true")
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


def _print_spec_summary(spec: ArchitectureSpecification) -> None:
    print(f"Specification: {spec.version}; fingerprint: {spec.fingerprint}")
    print("Valid: True")
    print("Layers: " + (", ".join(item.name for item in spec.architecture.layers) or "none"))
    print("Modules: " + (", ".join(item.name for item in spec.architecture.modules) or "none"))
    print("Rules: " + (", ".join(item.id for item in spec.rules) or "none"))
    print("Diagnostics: none")


def _print_conformance_summary(result: StaticConformanceResult) -> None:
    stats = result.statistics
    print(f"Project: {result.reproducibility.project_id}")
    print(f"Snapshot: {result.reproducibility.snapshot_id}")
    print(f"IAM nodes: {stats.iam_nodes_total}; edges: {stats.iam_edges_total}")
    print("Layer nodes: " + json.dumps(stats.nodes_by_layer, sort_keys=True))
    print("Module nodes: " + json.dumps(stats.nodes_by_module, sort_keys=True))
    print(f"Unclassified: {stats.nodes_unclassified}; ambiguous: {stats.ambiguous_nodes}")
    print(f"Rules evaluated: {stats.rules_evaluated}/{stats.rules_enabled}")
    print(f"Findings: {stats.findings_total}; status: {result.status.value}")
    print("Findings by rule: " + json.dumps(stats.findings_by_rule, sort_keys=True))
    print("Findings by severity: " + json.dumps(stats.findings_by_severity, sort_keys=True))
    for finding in result.findings:
        print(f"{finding.rule_id} {finding.severity.value}: {finding.description}")
    for diagnostic in result.diagnostics:
        print(f"{diagnostic.code}: {diagnostic.message}")


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
    conformance = None
    try:
        try:
            spec = None
            if arguments.group == "architecture":
                spec = load_architecture_file(arguments.spec)
                if arguments.command == "validate":
                    if arguments.json:
                        print(
                            json.dumps(
                                {
                                    "is_valid": True,
                                    "fingerprint": spec.fingerprint,
                                    "specification": spec.model_dump(mode="json", by_alias=True),
                                    "diagnostics": [],
                                },
                                sort_keys=True,
                                ensure_ascii=False,
                                indent=2,
                            )
                        )
                    else:
                        _print_spec_summary(spec)
                    return 0
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
            if arguments.group in {"parse", "iam", "architecture"}:
                config = ParserConfig(strict_syntax_errors=arguments.strict)
                with discovery.open(source) as repository:
                    parsing = ParseRepository(create_parser_registry(), config)
                    if arguments.group in {"iam", "architecture"}:
                        building = BuildIAM(
                            parsing,
                            create_extractor_registry(),
                            ExtractionConfig(repository_namespace=arguments.namespace),
                        )
                        if spec is not None:
                            conformance = CheckArchitecture(building).execute(
                                repository.snapshot, repository.workspace, spec
                            )
                            if arguments.output is not None:
                                arguments.output.write_text(
                                    serialize_conformance(conformance), encoding="utf-8"
                                )
                        else:
                            iam_result = building.execute(repository.snapshot, repository.workspace)
                        if iam_result is not None and arguments.output is not None:
                            arguments.output.write_text(
                                serialize_iam(iam_result.iam), encoding="utf-8"
                            )
                    else:
                        parse_result = parsing.execute(repository.snapshot, repository.workspace)
                snapshot = repository.snapshot
            else:
                snapshot = discovery.execute(source)
        except (
            RepositoryIntakeError,
            ArchitectureSpecificationError,
            ValidationError,
            IAMValidationError,
            OSError,
        ) as error:
            code = (
                error.code
                if isinstance(error, (RepositoryIntakeError, ArchitectureSpecificationError))
                else "iam_validation_error"
                if isinstance(error, IAMValidationError)
                else "output_write_error"
                if isinstance(error, OSError)
                else "invalid_repository_input"
            )
            message = (
                str(error)
                if isinstance(error, (RepositoryIntakeError, ArchitectureSpecificationError))
                else "IAM structure could not be validated"
                if isinstance(error, IAMValidationError)
                else "analysis output could not be written"
                if isinstance(error, OSError)
                else "repository input or scan policy is invalid"
            )
            if arguments.json:
                detail = {"code": code, "message": message}
                if isinstance(error, ArchitectureSpecificationError):
                    print(
                        json.dumps(
                            {
                                "error": {
                                    **detail,
                                    "line": error.line,
                                    "column": error.column,
                                }
                            }
                        ),
                        file=sys.stderr,
                    )
                else:
                    print(json.dumps({"error": detail}), file=sys.stderr)
            else:
                print(f"{code}: {message}", file=sys.stderr)
            return 2
        if conformance is not None:
            if arguments.json:
                print(serialize_conformance(conformance), end="")
            else:
                _print_conformance_summary(conformance)
            return {
                ConformanceStatus.CONFORMANT: 0,
                ConformanceStatus.NON_CONFORMANT: 1,
                ConformanceStatus.INVALID: 2,
                ConformanceStatus.INCOMPLETE: 3,
            }[conformance.status]
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
