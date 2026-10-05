from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

import yaml
from pydantic import Field
from yaml.events import AliasEvent, CollectionEndEvent, CollectionStartEvent

from archguard.application.analyze_architecture_hybrid import (
    AnalyzeArchitectureHybrid,
    HybridAnalysisInputs,
)
from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.architecture.hybrid.analyzer import HybridAnalysisConfig
from archguard.architecture.hybrid.serialization import canonical
from archguard.benchmark.identity import case_id, digest, subject_key
from archguard.benchmark.models import BenchmarkDataset, GroundTruthCase, Label, relative_path
from archguard.benchmark.mutations import (
    FileChange,
    MutationConfig,
    MutationRegistry,
    MutationResult,
    expected_truth,
    file_hash,
    mutation_identity,
    source_fingerprint,
)
from archguard.benchmark.resolver import LocatorResolver
from archguard.benchmark.splits import plan_splits, validate_leakage
from archguard.core.model.base import DomainModel
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.architecture_specification import load_architecture_file
from archguard.infrastructure.graph_configuration import load_graph_configuration
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput


class BenchmarkLimits(DomainModel):
    max_manifest_bytes: Annotated[int, Field(strict=True, gt=0, le=2097152)] = 2097152
    max_dataset_manifest_bytes: Annotated[int, Field(strict=True, gt=0, le=16777216)] = 16777216
    max_depth: Annotated[int, Field(strict=True, gt=0, le=32)] = 32
    max_nodes: Annotated[int, Field(strict=True, gt=0, le=100000)] = 100000
    max_repositories: Annotated[int, Field(strict=True, gt=0, le=500)] = 500
    max_cases: Annotated[int, Field(strict=True, gt=0, le=20000)] = 20000
    max_source_files: Annotated[int, Field(strict=True, gt=0, le=100)] = 100
    max_source_bytes: Annotated[int, Field(strict=True, gt=0, le=1048576)] = 1048576
    max_dataset_source_bytes: Annotated[int, Field(strict=True, gt=0, le=16777216)] = 16777216


class BenchmarkError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    pass


def _mapping(loader: UniqueLoader, node: yaml.MappingNode) -> dict[str, object]:
    result = {}
    for k, v in node.value:
        key = loader.construct_object(k)
        if not isinstance(key, str) or key in result:
            raise BenchmarkError("duplicate/non-string manifest key")
        result[key] = loader.construct_object(v)
    return result


UniqueLoader.add_constructor("tag:yaml.org,2002:map", _mapping)


def read_manifest(path: Path, limits: BenchmarkLimits | None = None) -> object:
    config = limits or BenchmarkLimits()
    with path.open("rb") as stream:
        raw = stream.read(config.max_manifest_bytes + 1)
    if len(raw) > config.max_manifest_bytes:
        raise BenchmarkError("manifest byte budget exceeded")
    try:
        depth = 0
        for count, event in enumerate(
            yaml.parse(raw.decode("utf-8"), Loader=yaml.SafeLoader), start=1
        ):
            if isinstance(event, AliasEvent):
                raise BenchmarkError("manifest aliases forbidden")
            if isinstance(event, CollectionStartEvent):
                depth += 1
            elif isinstance(event, CollectionEndEvent):
                depth -= 1
            if depth > config.max_depth or count > config.max_nodes:
                raise BenchmarkError("manifest structure budget exceeded")
        return yaml.load(raw, Loader=UniqueLoader)
    except (yaml.YAMLError, UnicodeError, RecursionError) as exc:
        raise BenchmarkError("invalid safe manifest") from exc


def safe_path(root: Path, relative: str) -> Path:
    relative_path(relative)
    candidate = root / relative
    if any(p.is_symlink() for p in (candidate, *candidate.parents) if p != root.parent):
        raise BenchmarkError("symlink traversal forbidden")
    resolved = candidate.resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise BenchmarkError("path escapes dataset root")
    return candidate


def source_files(root: Path, limits: BenchmarkLimits | None = None) -> dict[str, str]:
    config = limits or BenchmarkLimits()
    files: dict[str, str] = {}
    size = 0
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise BenchmarkError("source symlinks forbidden")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        relative_path(relative)
        size += path.stat().st_size
        if len(files) >= config.max_source_files or size > config.max_source_bytes:
            raise BenchmarkError("repository source budget exceeded")
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8")
        except UnicodeError as exc:
            raise BenchmarkError("source must be UTF-8") from exc
        if "\r" in text:
            raise BenchmarkError("benchmark sources require LF")
        files[relative] = text
    return files


@dataclass(frozen=True)
class LoadedBenchmark:
    dataset: BenchmarkDataset
    truths: tuple[GroundTruthCase, ...]
    mutations: tuple[MutationResult, ...]
    root: Path
    fingerprint: str


def load_dataset(path: Path, limits: BenchmarkLimits | None = None) -> LoadedBenchmark:
    config = limits or BenchmarkLimits()
    dataset = BenchmarkDataset.model_validate(read_manifest(path, config))
    if len(dataset.repositories) > config.max_repositories:
        raise BenchmarkError("repository budget exceeded")
    validate_leakage(dataset)
    root = path.parent.resolve()
    planned = plan_splits(
        tuple(r.repository_family_id for r in dataset.repositories), dataset.split_seed
    )
    manifest_bytes = path.stat().st_size
    referenced_paths: set[str] = set()

    def bounded_reference(relative: str) -> Path:
        nonlocal manifest_bytes
        target = safe_path(root, relative)
        if relative not in referenced_paths:
            manifest_bytes += target.stat().st_size
            referenced_paths.add(relative)
            if manifest_bytes > config.max_dataset_manifest_bytes:
                raise BenchmarkError("dataset manifest budget exceeded")
        return target

    split_manifest = read_manifest(bounded_reference(dataset.split_manifest), config)
    if split_manifest != {
        "algorithm": dataset.split_algorithm,
        "seed": dataset.split_seed,
        "families": {k: v.value for k, v in planned.items()},
    } or any(planned[r.repository_family_id] != r.dataset_split for r in dataset.repositories):
        raise BenchmarkError("split manifest/planner mismatch")
    cases: list[GroundTruthCase] = []
    mutations = []
    referenced = {dataset.split_manifest: split_manifest}
    total_bytes = 0
    for repo in dataset.repositories:
        files = source_files(safe_path(root, repo.source_path), config)
        total_bytes += sum(len(text.encode()) for text in files.values())
        if total_bytes > config.max_dataset_source_bytes:
            raise BenchmarkError("dataset source budget exceeded")
        if source_fingerprint(files) != repo.source_fingerprint:
            raise BenchmarkError("source fingerprint mismatch")
        raw_truth = read_manifest(bounded_reference(repo.ground_truth), config)
        if (
            not isinstance(raw_truth, list)
            or len(raw_truth) > 10000
            or len(cases) + len(raw_truth) > config.max_cases
        ):
            raise BenchmarkError("truth case budget/type invalid")
        repository_cases = tuple(GroundTruthCase.model_validate(c) for c in raw_truth)
        for c in repository_cases:
            if (
                c.repository_id != repo.repository_id
                or c.rule_id not in repo.annotation_scope.rules
            ):
                raise BenchmarkError("truth repository/scope mismatch")
            if c.case_id != case_id(
                dataset.namespace, c.repository_id, c.rule_id, c.label, c.subjects
            ):
                raise BenchmarkError("noncanonical case identity")
            if any(x.language not in repo.languages for x in c.subjects.locators):
                raise BenchmarkError("truth language mismatch")
        cases.extend(repository_cases)
        if repo.mutation_manifest:
            mutation = MutationResult.model_validate(
                read_manifest(bounded_reference(repo.mutation_manifest), config)
            )
            if (
                mutation.derived_repository_id != repo.repository_id
                or mutation.base_repository_id != repo.base_repository_id
                or mutation.result_fingerprint != repo.source_fingerprint
                or mutation.verification_status != "VERIFIED"
                or mutation.expected_cases != repository_cases
            ):
                raise BenchmarkError("mutation manifest/truth mismatch")
            mutations.append(mutation)
        if repo.architecture_spec:
            referenced[repo.architecture_spec] = load_architecture_file(
                bounded_reference(repo.architecture_spec)
            ).model_dump(mode="json")
        if repo.graph_config:
            referenced[repo.graph_config] = load_graph_configuration(
                bounded_reference(repo.graph_config)
            ).model_dump(mode="json")
    if len(cases) > config.max_cases or len({c.case_id for c in cases}) != len(cases):
        raise BenchmarkError("truth case budget/uniqueness invalid")
    keys = {(c.repository_id, c.rule_id, subject_key(c.subjects)) for c in cases}
    if len(keys) != len(cases):
        raise BenchmarkError("conflicting logical truth")
    repos = {r.repository_id: r for r in dataset.repositories}
    for m in mutations:
        if m.base_fingerprint != repos[m.base_repository_id].source_fingerprint:
            raise BenchmarkError("mutation base fingerprint mismatch")
        operator = MutationRegistry().get(m.operator_id)
        if (
            mutation_identity(
                dataset.namespace, m.base_repository_id, operator, m.config, m.base_fingerprint
            )
            != m.mutation_id
        ):
            raise BenchmarkError("noncanonical mutation identity")
        base = source_files(safe_path(root, repos[m.base_repository_id].source_path))
        after = operator.apply(base, m.config)
        changes = tuple(
            FileChange(path=p, before_hash=file_hash(base[p]), after_hash=file_hash(after[p]))
            for p in sorted(base)
            if base[p] != after[p]
        )
        if changes != m.changed_files:
            raise BenchmarkError("mutation changed-file hashes mismatch")
        if source_fingerprint(after) != m.result_fingerprint:
            raise BenchmarkError("mutation output does not replay")
    fp = digest(
        {
            "dataset": dataset.model_dump(mode="json"),
            "truths": [
                c.model_dump(mode="json") for c in sorted(cases, key=lambda c: str(c.case_id))
            ],
            "mutations": [
                m.model_dump(mode="json")
                for m in sorted(mutations, key=lambda m: str(m.mutation_id))
            ],
            "references": referenced,
        }
    )
    return LoadedBenchmark(dataset, tuple(cases), tuple(mutations), root, fp)


def building(namespace: str) -> BuildIAM:
    return BuildIAM(
        ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=True)),
        create_extractor_registry(),
        ExtractionConfig(repository_namespace=namespace),
    )


def build_source(path: Path, namespace: str) -> ArchitectureModel:
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(path))
    ) as repository:
        return building(namespace).execute(repository.snapshot, repository.workspace).iam


def prepared(
    loaded: LoadedBenchmark, repo_id: str
) -> tuple[AnalyzeArchitectureHybrid, HybridAnalysisInputs]:
    repo = next(r for r in loaded.dataset.repositories if r.repository_id == repo_id)
    config = HybridAnalysisConfig()
    if repo.graph_config:
        graph = load_graph_configuration(safe_path(loaded.root, repo.graph_config))
        config = HybridAnalysisConfig(ai=config.ai.model_copy(update={"graph": graph}))
    spec = (
        load_architecture_file(safe_path(loaded.root, repo.architecture_spec))
        if repo.architecture_spec
        else None
    )
    pipeline = AnalyzeArchitectureHybrid(building("benchmark:" + repo_id))
    with create_discovery().open(
        RepositoryInput(
            source_type=RepositorySourceType.LOCAL,
            location=str(safe_path(loaded.root, repo.source_path)),
        )
    ) as repository:
        inputs = pipeline.prepare(repository.snapshot, repository.workspace, config, spec)
    return pipeline, inputs


def validate_dataset(
    loaded: LoadedBenchmark,
) -> tuple[dict[str, object], dict[str, ArchitectureModel]]:
    iams = {
        r.repository_id: build_source(
            safe_path(loaded.root, r.source_path), "benchmark:" + r.repository_id
        )
        for r in loaded.dataset.repositories
    }
    diagnostics = []
    for repo, iam in iams.items():
        if not iam.metadata.get("is_valid") or not iam.metadata.get("is_complete"):
            diagnostics.append("INCOMPLETE_IAM:" + repo)
    for truth in loaded.truths:
        if LocatorResolver(iams[truth.repository_id]).subjects(truth.subjects) is None:
            diagnostics.append("UNRESOLVED_TRUTH:" + str(truth.case_id))
    for mutation in loaded.mutations:
        if (
            not MutationRegistry()
            .get(mutation.operator_id)
            .verify(iams[mutation.derived_repository_id], mutation.config)
        ):
            diagnostics.append("INVALID_MUTATION:" + str(mutation.mutation_id))
    for rule in sorted({c.rule_id for c in loaded.truths}):
        labels = {c.label for c in loaded.truths if c.rule_id == rule}
        if not {Label.POSITIVE, Label.NEGATIVE} <= labels:
            diagnostics.append("WARNING_UNBALANCED:" + rule)
    summary: dict[str, object] = {
        "schema_version": "1.0",
        "dataset_id": loaded.dataset.dataset_id,
        "dataset_version": loaded.dataset.dataset_version,
        "purpose": loaded.dataset.purpose,
        "repositories": len(iams),
        "families": len({r.repository_family_id for r in loaded.dataset.repositories}),
        "labels": dict(Counter(c.label.value for c in loaded.truths)),
        "rules": dict(Counter(c.rule_id for c in loaded.truths)),
        "languages": dict(
            Counter(language.value for r in loaded.dataset.repositories for language in r.languages)
        ),
        "splits": {
            s.value: {
                "repositories": sum(r.dataset_split == s for r in loaded.dataset.repositories),
                "families": len(
                    {
                        r.repository_family_id
                        for r in loaded.dataset.repositories
                        if r.dataset_split == s
                    }
                ),
                "cases": sum(
                    c.repository_id
                    in {
                        r.repository_id for r in loaded.dataset.repositories if r.dataset_split == s
                    }
                    for c in loaded.truths
                ),
            }
            for s in plan_splits(
                tuple(r.repository_family_id for r in loaded.dataset.repositories),
                loaded.dataset.split_seed,
            ).values()
        },
        "annotation_scopes": {
            r.repository_id: r.annotation_scope.model_dump(mode="json")
            for r in loaded.dataset.repositories
        },
        "diagnostics": sorted(diagnostics),
        "status": "VALID"
        if not any(not d.startswith("WARNING") for d in diagnostics)
        else "PARTIAL",
        "fingerprint": loaded.fingerprint,
    }
    return summary, iams


def generate_mutation(
    loaded: LoadedBenchmark, base_id: str, rule: str, config: MutationConfig, output: Path
) -> MutationResult:
    base = next((r for r in loaded.dataset.repositories if r.repository_id == base_id), None)
    if base is None:
        raise BenchmarkError("unknown mutation base repository")
    base_path = safe_path(loaded.root, base.source_path)
    if output.exists() or output.resolve().is_relative_to(base_path.resolve()):
        raise BenchmarkError("mutation output must be a new directory outside the base")
    operator = MutationRegistry().get(rule)
    before = source_files(base_path)
    after = operator.apply(before, config)
    identity = mutation_identity(
        loaded.dataset.namespace, base_id, operator, config, source_fingerprint(before)
    )
    derived = base_id + "-" + rule.lower()
    truth = expected_truth(loaded.dataset.namespace, derived, rule, config, identity)
    with TemporaryDirectory(prefix="archguard-mutation-") as temp:
        workspace = Path(temp) / "repository"
        for path, text in after.items():
            target = workspace / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
        iam = build_source(workspace, "benchmark:" + derived)
        if not operator.verify(iam, config):
            raise BenchmarkError("mutation parse/IAM structural verification failed")
        result = MutationResult(
            mutation_id=identity,
            operator_id=rule,
            base_repository_id=base_id,
            derived_repository_id=derived,
            config=config,
            base_fingerprint=source_fingerprint(before),
            result_fingerprint=source_fingerprint(after),
            changed_files=tuple(
                FileChange(path=p, before_hash=file_hash(before[p]), after_hash=file_hash(after[p]))
                for p in sorted(before)
                if before[p] != after[p]
            ),
            expected_cases=(truth,),
            verification_status="VERIFIED",
        )
        output.mkdir(parents=True)
        for path, text in after.items():
            target = output / "repository" / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode())
        (output / "mutation.json").write_text(canonical(result) + "\n", encoding="utf-8")
    return result
