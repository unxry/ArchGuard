from hashlib import sha256
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID, uuid5

from pydantic import Field, model_validator

from archguard.benchmark.identity import digest
from archguard.benchmark.models import (
    AnnotationStatus,
    Digest,
    GroundTruthCase,
    Label,
    Locator,
    Origin,
    RuleId,
    Subjects,
    relative_path,
    rule_family,
)
from archguard.benchmark.resolver import LocatorResolver
from archguard.core.model.base import DomainModel
from archguard.core.model.enums import Language, NodeKind
from archguard.iam.model import ArchitectureModel


class MutationLimits(DomainModel):
    max_source_files: Annotated[int, Field(strict=True, gt=0, le=100)] = 100
    max_source_bytes: Annotated[int, Field(strict=True, gt=0, le=1048576)] = 1048576
    max_changed_files: Annotated[int, Field(strict=True, gt=0, le=100)] = 1
    max_output_bytes: Annotated[int, Field(strict=True, gt=0, le=1048576)] = 1048576


class MutationConfig(DomainModel):
    seed: str = "mutation-v1"
    limits: MutationLimits = Field(default_factory=MutationLimits)
    source: Locator
    target: Locator
    expected_subjects: Subjects
    cycle_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def endpoints(self) -> Self:
        if self.source.language != self.target.language or self.source.path == self.target.path:
            raise ValueError("mutation endpoints must be distinct and share a language")
        if self.source.kind != NodeKind.CLASS or self.target.kind != NodeKind.CLASS:
            raise ValueError("controlled mutations require class endpoints")
        for path in self.cycle_paths:
            relative_path(path)
        return self


class FileChange(DomainModel):
    path: str
    before_hash: Digest
    after_hash: Digest


class MutationResult(DomainModel):
    schema_version: Literal["1.0"] = "1.0"
    mutation_id: UUID
    operator_id: RuleId
    operator_version: Literal["1.0"] = "1.0"
    base_repository_id: str
    derived_repository_id: str
    config: MutationConfig
    base_fingerprint: Digest
    result_fingerprint: Digest
    changed_files: tuple[FileChange, ...]
    expected_cases: tuple[GroundTruthCase, ...]
    verification_status: Literal["VERIFIED", "INVALID"]
    diagnostics: tuple[str, ...] = ()


class MutationOperator(Protocol):
    operator_id: str
    version: str
    supported_languages: tuple[Language, ...]

    def apply(self, files: dict[str, str], config: MutationConfig) -> dict[str, str]: ...
    def verify(self, iam: ArchitectureModel, config: MutationConfig) -> bool: ...


def file_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def source_fingerprint(files: dict[str, str]) -> str:
    return digest(
        {
            p: file_hash(text)
            for p, text in sorted(files.items())
            if p.endswith((".java", ".ts", ".tsx", ".js"))
        }
    )


class DependencyMutation:
    version = "1.0"
    supported_languages: tuple[Language, ...] = (Language.JAVA, Language.TYPESCRIPT)

    def __init__(self, rule: str) -> None:
        self.operator_id = rule

    def apply(self, files: dict[str, str], config: MutationConfig) -> dict[str, str]:
        if config.source.language not in self.supported_languages:
            raise ValueError("unsupported mutation language")
        if (
            len(files) > config.limits.max_source_files
            or sum(len(v.encode()) for v in files.values()) > config.limits.max_source_bytes
        ):
            raise ValueError("mutation source budget exceeded")
        for path in files:
            relative_path(path)
        if config.source.path not in files or config.target.path not in files:
            raise ValueError("mutation endpoints missing")
        source = files[config.source.path]
        if source.count("// BENCHMARK_DEPENDENCIES") != 1 or "\r" in source:
            raise ValueError("controlled LF mutation marker required")
        target_name = config.target.qualified_name.rsplit("::", 1)[-1].rsplit(".", 1)[-1]
        if not target_name.isidentifier():
            raise ValueError("invalid mutation target symbol")
        if config.source.language == Language.JAVA:
            qualified = config.target.qualified_name
            if not all(p.isidentifier() for p in qualified.split(".")):
                raise ValueError("invalid Java qualified target")
            source = source.replace(
                "// BENCHMARK_DEPENDENCIES", f"{qualified} benchmarkDependency;"
            )
        else:
            source_parts = config.source.path.split("/")[:-1]
            target_parts = config.target.path.removesuffix(".ts").split("/")
            while source_parts and target_parts and source_parts[0] == target_parts[0]:
                source_parts.pop(0)
                target_parts.pop(0)
            reference = "../" * len(source_parts) + "/".join(target_parts)
            if not reference.startswith("."):
                reference = "./" + reference
            source = f"import {{ {target_name} }} from '{reference}';\n" + source.replace(
                "// BENCHMARK_DEPENDENCIES", f"benchmarkDependency!: {target_name};"
            )
        result = {**files, config.source.path: source}
        if (
            sum(len(v.encode()) for v in result.values()) > config.limits.max_output_bytes
            or sum(files[p] != result[p] for p in files) > config.limits.max_changed_files
        ):
            raise ValueError("mutation output budget exceeded")
        return result

    def verify(self, iam: ArchitectureModel, config: MutationConfig) -> bool:
        if not iam.metadata.get("is_valid") or not iam.metadata.get("is_complete"):
            return False
        resolver = LocatorResolver(iam)
        if resolver.subjects(config.expected_subjects) is None:
            return False
        by_id = resolver.nodes
        pairs = set()
        for edge in iam.edges:
            left, right = (
                by_id[edge.source_id].source_location,
                by_id[edge.target_id].source_location,
            )
            if left and right and left.file_path != right.file_path:
                pairs.add((left.file_path, right.file_path))
        if (config.source.path, config.target.path) not in pairs:
            return False
        paths = tuple(x.path for x in config.expected_subjects.locators)
        if self.operator_id != "ARCH003":
            return config.expected_subjects.directed and paths == (
                config.source.path,
                config.target.path,
            )
        if config.expected_subjects.directed or set(paths) != set(config.cycle_paths):
            return False
        paths = config.cycle_paths
        return len(paths) >= 3 and all(
            (paths[i], paths[(i + 1) % len(paths)]) in pairs for i in range(len(paths))
        )


class MutationRegistry:
    def __init__(self) -> None:
        self.operators: dict[str, MutationOperator] = {
            f"ARCH00{i}": DependencyMutation(f"ARCH00{i}") for i in range(1, 6)
        }

    def get(self, rule: str) -> MutationOperator:
        if rule not in self.operators:
            raise ValueError("unknown mutation operator")
        return self.operators[rule]


def mutation_identity(
    namespace: UUID, base: str, operator: MutationOperator, config: MutationConfig, fingerprint: str
) -> UUID:
    return uuid5(
        namespace,
        digest(
            {
                "base": base,
                "operator": operator.operator_id,
                "version": operator.version,
                "config": config.model_dump(mode="json"),
                "source": fingerprint,
            }
        ),
    )


def expected_truth(
    namespace: UUID, repository: str, rule: str, config: MutationConfig, mutation_id: UUID
) -> GroundTruthCase:
    from archguard.benchmark.identity import case_id

    return GroundTruthCase(
        case_id=case_id(namespace, repository, rule, Label.POSITIVE, config.expected_subjects),
        repository_id=repository,
        rule_id=rule,
        rule_family=rule_family(rule),
        label=Label.POSITIVE,
        subjects=config.expected_subjects,
        rationale=(
            "Controlled dependency insertion violates the explicitly declared "
            "target rule; cycle operator closes the declared three-component d"
            "irected SCC."
        ),
        origin=Origin.MUTATION,
        annotation_status=AnnotationStatus.MUTATION_DERIVED,
        mutation_id=mutation_id,
        expected_evidence=("Resolved inserted dependency; strict parse and IAM verification",),
    )
