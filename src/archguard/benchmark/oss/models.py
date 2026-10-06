"Source-free OSS lineage and blinded annotation contracts; no inference dependency."

import hashlib
import json
from datetime import datetime
from typing import Annotated, Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from archguard.benchmark.models import Digest, Locator, RuleId, relative_path
from archguard.core.model.base import DomainModel

Slug = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,100}$")]
Commit = Annotated[str, Field(pattern=r"^[a-f0-9]{40}$")]
Count = Annotated[int, Field(ge=0)]


def _json_default(value: object) -> object:
    if isinstance(value, DomainModel):
        return value.model_dump(mode="json")
    raise TypeError("unsupported canonical OSS value")


def canonical(value: object) -> str:
    if isinstance(value, DomainModel):
        value = value.model_dump(mode="json")
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=_json_default
    )


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class Sealed(DomainModel):
    fingerprint: Digest

    @model_validator(mode="after")
    def sealed(self) -> Self:
        if self.fingerprint != digest(self.model_dump(mode="json", exclude={"fingerprint"})):
            raise ValueError("OSS artifact fingerprint mismatch")
        return self


def seal[T: Sealed](contract: type[T], **values: Any) -> T:
    provisional = contract.model_construct(**values)
    payload = {n: getattr(provisional, n) for n in contract.model_fields if n != "fingerprint"}
    return contract.model_validate(payload | {"fingerprint": digest(payload)})


class SamplingProtocol(DomainModel):
    schema_version: Literal["oss-sampling-protocol-v1"]
    seed: int
    subjects_per_repository: int = Field(ge=3, le=20)
    questions: tuple[RuleId, ...]
    strata: tuple[Literal["LOW", "MEDIUM", "HIGH"], ...]
    ranking: str
    subject_kinds: tuple[str, ...]
    max_context_files: int = Field(gt=0, le=20)
    max_context_bytes: int = Field(gt=0, le=1048576)
    max_excerpt_lines: int = Field(gt=0, le=1000)
    controls: str

    @model_validator(mode="after")
    def questions_supported(self) -> Self:
        if set(self.questions) != {f"ARCH20{i}" for i in range(1, 6)} or len(self.questions) != 5:
            raise ValueError("sampling requires exactly ARCH201–205")
        if self.strata != ("LOW", "MEDIUM", "HIGH"):
            raise ValueError("include control, intermediate and high raw-degree strata")
        return self


class SelectionProtocol(DomainModel):
    schema_version: Literal["oss-selection-protocol-v1"]
    dataset_id: Literal["archguard-oss-benchmark-v1"]
    version: Literal["1.0.0"]
    status: Literal["OSS_ANNOTATION_SEED"]
    target_repositories: int = Field(ge=8, le=12)
    per_language: int = Field(ge=4, le=6)
    min_source_files: int = Field(gt=0)
    min_source_directories: int = Field(gt=0)
    min_primary_language_fraction: float = Field(gt=0, le=1)
    max_metadata_size_kib: int = Field(gt=0)
    max_demo_repositories: int = Field(ge=0)
    allowed_licenses: tuple[str, ...]
    selection_basis: str
    inclusion_criteria: tuple[str, ...]
    exclusion_reasons: tuple[str, ...]
    post_freeze_failure_policy: str
    limits: dict[str, int | float]
    max_corpus_source_bytes: int = Field(gt=0)
    sampling: SamplingProtocol
    no_model_scoring: Literal[True]
    no_live_ai: Literal[True]
    submodules: Literal["DO_NOT_INITIALIZE"]
    lfs: Literal["DO_NOT_DOWNLOAD"]
    parser_coverage_policy: str
    graph_configuration: str
    license_verification: str

    @property
    def fingerprint(self) -> str:
        return digest(self)


class EvidenceReference(DomainModel):
    path: str
    sha256: Digest
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    purpose: Literal["DECLARATION", "DEPENDENCY", "DOCUMENTATION"]

    _path = field_validator("path")(relative_path)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_line < self.start_line:
            raise ValueError("invalid evidence line range")
        return self


class TargetArchitectureProvenance(DomainModel):
    status: Literal["DOCUMENTED", "MANUALLY_DERIVED", "NONE"] = "NONE"
    references: tuple[EvidenceReference, ...] = ()
    rationale: str | None = None
    review_status: Literal["UNREVIEWED", "SINGLE_REVIEW", "DOUBLE_REVIEW", "ADJUDICATED"] = (
        "UNREVIEWED"
    )

    @model_validator(mode="after")
    def documented(self) -> Self:
        if self.status != "NONE" and (not self.references or not self.rationale):
            raise ValueError("target architecture needs evidence and rationale")
        if self.status == "NONE" and (
            self.references or self.rationale or self.review_status != "UNREVIEWED"
        ):
            raise ValueError("absent architecture has no reviewed constraints")
        return self


class OSSRepository(DomainModel):
    repository_id: Slug
    family_id: str = Field(min_length=1)
    project: str = Field(pattern=r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
    upstream_url: str
    language: Literal["JAVA", "TYPESCRIPT"]
    commit_sha: Commit
    git_tree_sha: Commit
    commit_date: str
    selection_reason: str = Field(min_length=1)
    license_spdx: str = Field(min_length=1)
    license_path: str
    license_sha256: Digest
    tag: str | None = None
    metadata_size_kib: Count
    estimated_source_files: Count
    estimated_source_bytes: Count
    architecture_provenance: TargetArchitectureProvenance
    acquisition_method: Literal["PINNED_GIT_OBJECTS; no checkout filters/submodules/LFS"]

    _license_path = field_validator("license_path")(relative_path)

    @model_validator(mode="after")
    def public_pin(self) -> Self:
        if self.upstream_url.casefold() != f"https://github.com/{self.project}.git".casefold():
            raise ValueError("primary corpus requires canonical public GitHub URL")
        if self.license_spdx in {"NOASSERTION", "NONE", "OTHER"}:
            raise ValueError("explicit OSS license required")
        if datetime.fromisoformat(self.commit_date.replace("Z", "+00:00")).tzinfo is None:
            raise ValueError("commit date requires timezone")
        return self


class OSSCorpus(Sealed):
    schema_version: Literal["oss-corpus-v1"]
    dataset_id: Literal["archguard-oss-benchmark-v1"]
    version: Literal["1.0.0"]
    status: Literal["OSS_ANNOTATION_SEED"]
    selection_protocol_fingerprint: Digest
    repositories: tuple[OSSRepository, ...]

    @model_validator(mode="after")
    def independent(self) -> Self:
        ids = tuple(r.repository_id for r in self.repositories)
        if ids != tuple(sorted(set(ids))) or len({r.family_id for r in self.repositories}) != len(
            ids
        ):
            raise ValueError("unique sorted repositories and independent families required")
        if len({r.upstream_url for r in self.repositories}) != len(ids):
            raise ValueError("duplicate upstream")
        return self


class CorpusFreeze(Sealed):
    schema_version: Literal["oss-corpus-freeze-v1"]
    corpus_fingerprint: Digest
    selection_protocol_fingerprint: Digest
    frozen_at: str
    repository_count: int
    family_count: int
    commits: tuple[tuple[str, Commit], ...]
    phase: Literal["BEFORE_FETCH_AND_ANALYSIS"]
    source_identities: str


class AcquisitionReceipt(Sealed):
    schema_version: Literal["oss-acquisition-v1"] = "oss-acquisition-v1"
    corpus_fingerprint: Digest
    repository_id: Slug
    commit_sha: Commit
    git_tree_sha: Commit
    acquired_at: str
    license_sha256: Digest
    content_fingerprint: Digest
    snapshot_fingerprint: Digest
    source_files: Count
    source_bytes: Count
    status: Literal["FETCHED_VERIFIED"] = "FETCHED_VERIFIED"
    omitted_nonregular_paths: tuple[str, ...] = ()


class AnnotationPacket(Sealed):
    schema_version: Literal["oss-annotation-packet-v1"] = "oss-annotation-packet-v1"
    annotation_case_id: Slug
    repository_id: Slug
    corpus_fingerprint: Digest
    rule_id: RuleId
    question: str
    task: Literal[
        "SEMANTIC_RESPONSIBILITY_REVIEW",
        "STRUCTURAL_SIGNAL",
        "ARCHITECTURAL_QUALITY_JUDGMENT",
        "DOCUMENTED_CONFORMANCE",
    ] = "SEMANTIC_RESPONSIBILITY_REVIEW"
    subject: Locator
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    license_spdx: str
    instructions: str
    allowed_labels: tuple[str, ...] = ("POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE")

    @model_validator(mode="after")
    def task_scope(self) -> Self:
        family = self.rule_id[4]
        expected = {
            "0": {"DOCUMENTED_CONFORMANCE"},
            "1": {"STRUCTURAL_SIGNAL", "ARCHITECTURAL_QUALITY_JUDGMENT"},
            "2": {"SEMANTIC_RESPONSIBILITY_REVIEW"},
        }[family]
        if self.task not in expected or self.allowed_labels != (
            "POSITIVE",
            "NEGATIVE",
            "UNCERTAIN",
            "OUT_OF_SCOPE",
        ):
            raise ValueError("annotation task/label scope mismatch")
        return self


class AnnotationSample(Sealed):
    schema_version: Literal["oss-annotation-sample-v1"] = "oss-annotation-sample-v1"
    corpus_fingerprint: Digest
    corpus_freeze_fingerprint: Digest
    sampling_protocol_fingerprint: Digest
    packets: tuple[AnnotationPacket, ...]
    strata: tuple[tuple[Slug, Literal["LOW", "MEDIUM", "HIGH"]], ...]
    review_status: Literal["UNREVIEWED"] = "UNREVIEWED"

    @model_validator(mode="after")
    def coherent(self) -> Self:
        ids = tuple(p.annotation_case_id for p in self.packets)
        if len(set(ids)) != len(ids) or tuple(x[0] for x in self.strata) != ids:
            raise ValueError("sample scope/order mismatch")
        if any(p.corpus_fingerprint != self.corpus_fingerprint for p in self.packets):
            raise ValueError("packet from wrong corpus")
        return self


class HumanAnnotation(DomainModel):
    annotation_case_id: Slug
    packet_fingerprint: Digest
    reviewer_id: Slug
    label: Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]
    rationale: str
    evidence: tuple[EvidenceReference, ...] = ()
    uncertainty: Literal["CLEAR", "AMBIGUOUS"]
    attestation: Literal["HUMAN_REVIEW_COMPLETED"]

    @model_validator(mode="after")
    def evidence_required(self) -> Self:
        if self.label in {"POSITIVE", "NEGATIVE"} and (
            not self.rationale.strip() or not self.evidence
        ):
            raise ValueError("binary human labels require rationale and concrete evidence")
        return self


class Adjudication(DomainModel):
    annotation_case_id: Slug
    adjudicator_id: Slug
    label: Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]
    rationale: str = Field(min_length=1)
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    attestation: Literal["HUMAN_REVIEW_COMPLETED"]


class CaseReview(DomainModel):
    annotation_case_id: Slug
    status: Literal[
        "UNREVIEWED", "SINGLE_REVIEW", "DOUBLE_REVIEW", "ADJUDICATION_REQUIRED", "ADJUDICATED"
    ]
    final_label: Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE", "NOT_ANNOTATED"]


class AnnotationResult(Sealed):
    schema_version: Literal["oss-annotation-result-v1"] = "oss-annotation-result-v1"
    corpus_fingerprint: Digest
    sample_fingerprint: Digest
    reviews: tuple[HumanAnnotation, ...] = ()
    adjudications: tuple[Adjudication, ...] = ()
    cases: tuple[CaseReview, ...]


class AnnotationFreeze(Sealed):
    schema_version: Literal["oss-annotation-freeze-v1"] = "oss-annotation-freeze-v1"
    corpus_freeze_fingerprint: Digest
    sample_fingerprint: Digest
    annotation_result_fingerprint: Digest
    status: Literal["AWAITING_HUMAN_REVIEW", "REVIEWED_SCOPE_FROZEN"]
    future_evaluation_policy: Literal[
        "SEPARATE_MODEL_RECEIPT_REQUIRED; NO_EVALUATION_IN_PROMPT_012"
    ] = "SEPARATE_MODEL_RECEIPT_REQUIRED; NO_EVALUATION_IN_PROMPT_012"


class SampleFreeze(Sealed):
    schema_version: Literal["oss-sample-freeze-v1"] = "oss-sample-freeze-v1"
    corpus_freeze_fingerprint: Digest
    sample_fingerprint: Digest
    frame_fingerprint: Digest
    sampling_protocol_fingerprint: Digest
    frozen_at: str
    phase: Literal["BEFORE_HUMAN_LABELS_OR_AI"] = "BEFORE_HUMAN_LABELS_OR_AI"
    cases: Count
