"""Bounded worker invoking existing analyzers; never imports or executes project code."""

import json
import os
import resource
import sys
import threading
import time
from pathlib import Path
from typing import Any
from uuid import uuid5

from archguard.application.build_iam import BuildIAM
from archguard.application.check_architecture import CheckArchitecture
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.classification.classifier import ArchitectureClassifier
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig, GraphProjectionSpec
from archguard.architecture.graph.enums import GraphProjection
from archguard.core.identifiers import RepositoryId, SourceFileId
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from archguard.repository.policy import RepositoryScanPolicy
from archguard.security.analyzer_v1 import SecuritySourceInput
from archguard.security.analyzer_v2 import SecurityAnalyzerV2
from archguard.security.domain import SecurityAnalysisContext, SecurityLanguage


def stage(name: str) -> None:
    print(json.dumps({"stage": name}), flush=True)


def analyze(folder: Path, options: dict[str, Any]) -> dict[str, Any]:
    stage("READING")
    discovery = create_discovery(RepositoryScanPolicy(max_files=200, max_entries=5000))
    with discovery.open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(folder))
    ) as repo:
        stage("ANALYZING")
        building = BuildIAM(
            ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=True)),
            create_extractor_registry(),
            ExtractionConfig(repository_namespace="archguard:product:" + options["project_id"]),
        )
        built = building.execute(repo.snapshot, repo.workspace)
        iam = built.iam
        spec_path = folder / "architecture.yaml"
        spec = load_architecture_file(spec_path) if options["architecture"] else None
        graph = GraphAnalyzer().analyze(
            iam,
            GraphAnalysisConfig(projection=GraphProjectionSpec(projection=GraphProjection.FILE)),
            spec,
        )
        architecture = (
            CheckArchitecture(building).execute(repo.snapshot, repo.workspace, spec)
            if spec is not None
            else None
        )
        classification = ArchitectureClassifier().classify(iam, spec) if spec else None
        security = []
        if options["security"]:
            for language in (SecurityLanguage.JAVA, SecurityLanguage.TYPESCRIPT):
                sources = []
                for file in repo.snapshot.files:
                    if file.language.value != language.value or not file.analysis_eligible:
                        continue
                    match = next(
                        (f for f in iam.source_files if f.file_path == file.relative_path), None
                    )
                    with repo.workspace.open_source_file(file.relative_path) as stream:
                        sources.append(
                            SecuritySourceInput(
                                file,
                                stream.read(),
                                match.id
                                if match
                                else SourceFileId(
                                    uuid5(repo.snapshot.snapshot_id, file.relative_path)
                                ),
                            )
                        )
                if sources:
                    context = SecurityAnalysisContext(
                        repository_id=RepositoryId(iam.project.id),
                        snapshot_id=repo.snapshot.snapshot_id,
                        language=language,
                    )
                    security.append(
                        SecurityAnalyzerV2().analyze(context, sources).model_dump(mode="json")
                    )
        sources_map = {
            file.relative_path: (folder / file.relative_path)
            .read_text(encoding="utf-8")
            .splitlines()
            for file in repo.snapshot.files
            if file.analysis_eligible
        }
        # Secret detector evidence remains usable without echoing credential literals.
        for result in security:
            for finding in result["findings"]:
                if finding["rule_id"] == "SEC001":
                    loc = finding["primary_source"]["location"]
                    lines = sources_map.get(loc["file_path"], [])
                    for index in range(
                        loc["start_line"] - 1,
                        min(loc.get("end_line") or loc["start_line"], len(lines)),
                    ):
                        lines[index] = "[SEC001 source line redacted]"
        stage("SERIALIZING")
        return {
            "schema": "archguard-product-v1",
            "mode": "LOCAL_RESULT",
            "project": {"id": options["project_id"], "name": options["project_name"]},
            "provenance": {
                "snapshot_id": str(repo.snapshot.snapshot_id),
                "snapshot_fingerprint": repo.snapshot.fingerprint,
                "source_digest": options["source_digest"],
                "provider_calls": 0,
                "source_code_executed": False,
                "security_version": "security-interprocedural-v2",
                "intake_scope": "200 UTF-8 Java/TypeScript files; 4 MiB; "
                "no dependencies/configuration",
            },
            "iam": iam.model_dump(mode="json"),
            "graph": graph.model_dump(mode="json"),
            "architecture": architecture.model_dump(mode="json") if architecture else None,
            "classification": classification.model_dump(mode="json") if classification else None,
            "security": security,
            "sources": sources_map,
        }


def main(parent_pid: int | None = None) -> None:
    parent = parent_pid if parent_pid is not None else os.getppid()

    def watch_parent() -> None:
        while os.getppid() == parent:
            time.sleep(0.25)
        os._exit(3)

    threading.Thread(target=watch_parent, daemon=True).start()
    if sys.platform != "darwin":
        resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))
    resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (96, 96))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    job = Path(sys.argv[1])
    try:
        options = json.loads((job / "request.json").read_text())
        result = analyze(job / "source", options)
        (job / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        stage("READY")
    except Exception:
        # Raw exceptions may include a path or source text.
        stage("ANALYZER_FAILED")
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
