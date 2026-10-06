"Explicit acquisition and offline characterization, separated from blinded packets."

import hashlib
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.discovery.analyzer import ArchitectureDiscoveryAnalyzer
from archguard.architecture.discovery.config import ArchitectureDiscoveryConfig
from archguard.architecture.graph.analyzer import GraphAnalyzer
from archguard.architecture.graph.config import GraphAnalysisConfig
from archguard.benchmark.models import relative_path
from archguard.benchmark.oss.models import (
    AcquisitionReceipt,
    CorpusFreeze,
    OSSCorpus,
    OSSRepository,
    SelectionProtocol,
    canonical,
    digest,
    seal,
)
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.repository.factory import create_discovery
from archguard.infrastructure.repository.git_runner import GitRunner, SubprocessGitRunner
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy


@dataclass(frozen=True)
class FrozenOSSCorpus:
    corpus: OSSCorpus
    protocol: SelectionProtocol
    freeze: CorpusFreeze

    @property
    def policy(self) -> RepositoryScanPolicy:
        return RepositoryScanPolicy.model_validate(self.protocol.limits)


def load_corpus(corpus: Path, protocol: Path, freeze: Path) -> FrozenOSSCorpus:
    result = FrozenOSSCorpus(
        OSSCorpus.model_validate(_read(corpus, 1048576)),
        SelectionProtocol.model_validate(_read(protocol, 131072)),
        CorpusFreeze.model_validate(_read(freeze, 131072)),
    )
    repositories = result.corpus.repositories
    if (
        result.corpus.selection_protocol_fingerprint != result.protocol.fingerprint
        or result.freeze.corpus_fingerprint != result.corpus.fingerprint
        or result.freeze.selection_protocol_fingerprint != result.protocol.fingerprint
        or result.freeze.repository_count != len(repositories)
        or result.freeze.family_count != len({r.family_id for r in repositories})
        or result.freeze.commits != tuple((r.repository_id, r.commit_sha) for r in repositories)
        or len(repositories) != result.protocol.target_repositories
        or Counter(r.language for r in repositories)
        != {"JAVA": result.protocol.per_language, "TYPESCRIPT": result.protocol.per_language}
        or any(r.license_spdx not in result.protocol.allowed_licenses for r in repositories)
        or any(r.estimated_source_files < result.protocol.min_source_files for r in repositories)
        or sum(r.estimated_source_bytes for r in repositories)
        > result.protocol.max_corpus_source_bytes
    ):
        raise ValueError("frozen corpus/protocol/pins/licenses/budgets mismatch")
    return result


def write_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8") as stream:
        stream.write(canonical(value) + "\n")


def cache_root(path: Path | None) -> Path:
    raw = (
        path
        if path is not None
        else Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
        / "archguard"
        / "oss"
    )
    if raw.is_symlink():
        raise ValueError("cache symlinks forbidden")
    root = raw.resolve()
    if any((p / ".git").exists() for p in (root, *root.parents)):
        raise ValueError("OSS cache must be outside Git working trees")
    return root


def source_path(cache: Path, repository: OSSRepository) -> Path:
    cache = cache_root(cache)
    root = cache / repository.repository_id / repository.commit_sha / "source"
    if root.is_symlink() or any(p.is_symlink() for p in root.parents):
        raise ValueError("cache path escape/symlink forbidden")
    if not root.absolute().is_relative_to(cache.absolute()):
        raise ValueError("cache path escape")
    return root


def content_identity(root: Path, policy: RepositoryScanPolicy) -> tuple[str, int]:
    records: list[tuple[str, int, str]] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError("source symlink forbidden")
        if not path.is_file():
            continue
        size = path.stat().st_size
        total += size
        if (
            size > policy.max_single_file_bytes
            or total > policy.max_total_uncompressed_bytes
            or len(records) >= policy.max_entries
        ):
            raise ValueError("source identity budget exceeded")
        records.append(
            (path.relative_to(root).as_posix(), size, hashlib.sha256(path.read_bytes()).hexdigest())
        )
    return digest(records), total


def snapshot(root: Path, policy: RepositoryScanPolicy) -> RepositorySnapshot:
    with create_discovery(policy).open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as workspace:
        return workspace.snapshot


def verify_acquisition(
    bound: FrozenOSSCorpus, repository: OSSRepository, cache: Path
) -> AcquisitionReceipt:
    root = source_path(cache, repository)
    receipt = AcquisitionReceipt.model_validate(_read(root.parent / "acquisition.json", 131072))
    content, _ = content_identity(root, bound.policy)
    actual_snapshot = snapshot(root, bound.policy)
    if (
        receipt.corpus_fingerprint != bound.corpus.fingerprint
        or receipt.repository_id != repository.repository_id
        or receipt.commit_sha != repository.commit_sha
        or receipt.git_tree_sha != repository.git_tree_sha
        or receipt.license_sha256 != repository.license_sha256
        or hashlib.sha256((root / repository.license_path).read_bytes()).hexdigest()
        != repository.license_sha256
        or receipt.content_fingerprint != content
        or receipt.snapshot_fingerprint != actual_snapshot.fingerprint
    ):
        raise ValueError("cached content/license/revision/receipt mismatch")
    return receipt


def fetch_repository(
    bound: FrozenOSSCorpus, repository: OSSRepository, cache: Path, runner: GitRunner | None = None
) -> AcquisitionReceipt:
    root = source_path(cache, repository)
    if root.parent.exists():
        return verify_acquisition(bound, repository, cache)
    cache.mkdir(parents=True, exist_ok=True)
    transport = runner or SubprocessGitRunner()
    policy = bound.policy
    config = [
        "-c",
        "core.hooksPath=/dev/null",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "credential.helper=",
        "-c",
        "protocol.ext.allow=never",
        "-c",
        "protocol.file.allow=never",
        "-c",
        "http.followRedirects=false",
    ]
    with TemporaryDirectory(prefix="oss-fetch-", dir=cache) as temporary:
        staging = Path(temporary)
        bare = staging / "objects.git"
        template = staging / "empty-template"
        template.mkdir()
        transport.run(
            [*config, "init", "--quiet", "--bare", "--template=" + str(template), str(bare)],
            policy.git_timeout_seconds,
        )
        transport.run(
            [
                *config,
                "fetch",
                "--quiet",
                "--depth=1",
                "--no-tags",
                "--no-recurse-submodules",
                repository.upstream_url,
                repository.commit_sha,
            ],
            policy.git_timeout_seconds,
            bare,
        )
        fetched = transport.run(
            [*config, "rev-parse", "--verify", "FETCH_HEAD"], policy.git_timeout_seconds, bare
        ).strip()
        if fetched != repository.commit_sha:
            raise ValueError("requested commit differs from fetched revision")
        tree = transport.run(
            [*config, "rev-parse", fetched + "^{tree}"], policy.git_timeout_seconds, bare
        ).strip()
        if fetched != repository.commit_sha or tree != repository.git_tree_sha:
            raise ValueError("requested commit/tree differs from fetched revision")
        listing = transport.run(
            [*config, "ls-tree", "-rz", "--long", fetched], policy.git_timeout_seconds, bare
        )
        entries = [entry for entry in listing.split("\0") if entry]
        if len(entries) > policy.max_entries:
            raise ValueError("pinned Git tree exceeds entry budget")
        materialized = staging / "source"
        materialized.mkdir()
        total = 0
        omitted = []
        # Read raw objects without checkout filters, hooks or repository commands.
        with subprocess.Popen(
            ["git", *config, "cat-file", "--batch"],
            cwd=bare,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env={
                **os.environ,
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_LFS_SKIP_SMUDGE": "1",
            },
        ) as blobs:
            assert blobs.stdin is not None and blobs.stdout is not None
            try:
                for entry in entries:
                    header, path = entry.split("\t", 1)
                    mode, kind, oid, size_text = header.split()
                    relative_path(path)
                    if len(path.split("/")) > 64:
                        raise ValueError("source path depth exceeded")
                    if kind != "blob" or mode not in {"100644", "100755"}:
                        omitted.append(path)
                        continue
                    size = int(size_text)
                    total += size
                    if (
                        size > policy.max_single_file_bytes
                        or total > policy.max_total_uncompressed_bytes
                    ):
                        raise ValueError("pinned blob budget exceeded")
                    blobs.stdin.write((oid + "\n").encode("ascii"))
                    blobs.stdin.flush()
                    response = blobs.stdout.readline(200).decode("ascii").split()
                    if response != [oid, "blob", str(size)]:
                        raise ValueError("Git blob response mismatch")
                    data = blobs.stdout.read(size)
                    if len(data) != size or blobs.stdout.read(1) != b"\n":
                        raise ValueError("truncated Git blob")
                    destination = materialized / path
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
            finally:
                blobs.stdin.close()
                blobs.wait(timeout=policy.git_timeout_seconds)
        if (
            hashlib.sha256((materialized / repository.license_path).read_bytes()).hexdigest()
            != repository.license_sha256
        ):
            raise ValueError("pinned license hash mismatch")
        content, _ = content_identity(materialized, policy)
        observed = snapshot(materialized, policy)
        receipt = seal(
            AcquisitionReceipt,
            corpus_fingerprint=bound.corpus.fingerprint,
            repository_id=repository.repository_id,
            commit_sha=fetched,
            git_tree_sha=tree,
            acquired_at=datetime.now(UTC).isoformat(),
            license_sha256=repository.license_sha256,
            content_fingerprint=content,
            snapshot_fingerprint=observed.fingerprint,
            omitted_nonregular_paths=tuple(omitted),
            source_files=observed.statistics.eligible_files,
            source_bytes=sum(f.size_bytes for f in observed.files if f.analysis_eligible),
        )
        root.parent.mkdir(parents=True, exist_ok=False)
        materialized.rename(root)
        write_new(root.parent / "acquisition.json", receipt)
    return receipt


def characterize_repository(
    bound: FrozenOSSCorpus, repository: OSSRepository, cache: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt = verify_acquisition(bound, repository, cache)
    root = source_path(cache, repository)
    graph_config = GraphAnalysisConfig()
    building = BuildIAM(
        ParseRepository(create_parser_registry(), ParserConfig()),
        create_extractor_registry(),
        ExtractionConfig(),
    )
    with create_discovery(bound.policy).open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
    ) as workspace:
        built = building.execute(workspace.snapshot, workspace.workspace)
        graph = GraphAnalyzer().analyze(built.iam, graph_config)
        discovery = ArchitectureDiscoveryAnalyzer().analyze(
            built.iam, graph, ArchitectureDiscoveryConfig(graph=graph_config)
        )
        parse = built.parsing.statistics
        stats = built.statistics
        report = {
            "repository_id": repository.repository_id,
            "language": repository.language,
            "status": "COMPLETE"
            if built.is_complete and graph.is_complete and not receipt.omitted_nonregular_paths
            else "PARTIAL",
            "files_discovered": len(workspace.snapshot.files),
            "source_files": receipt.source_files,
            "omitted_nonregular_paths": receipt.omitted_nonregular_paths,
            "parsed": parse.parsed_files,
            "parse_errors": parse.syntax_error_files,
            "parse_failed": parse.failed_files,
            "parse_skipped": parse.skipped_files,
            "iam_nodes": len(built.iam.nodes),
            "iam_edges": len(built.iam.edges),
            "resolved": stats.references_resolved,
            "unresolved": stats.references_unresolved,
            "ambiguous": stats.references_ambiguous,
            "external": stats.references_external,
            "graph_nodes": len(graph.graph.nodes),
            "graph_edges": len(graph.graph.edges),
            "cyclic_sccs": graph.statistics.cyclic_scc_count,
            "graph_diagnostics": sorted({d.code for d in graph.diagnostics}),
            "snapshot_fingerprint": receipt.snapshot_fingerprint,
        }
        # Private structural context stays separate from the annotation view.
        context = {
            "corpus_fingerprint": bound.corpus.fingerprint,
            "corpus_freeze_fingerprint": bound.freeze.fingerprint,
            "repository_id": repository.repository_id,
            "iam": built.iam.model_dump(mode="json"),
            "graph": graph.model_dump(mode="json"),
            "discovery": discovery.model_dump(mode="json"),
        }
    return report, context
