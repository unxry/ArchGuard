"""Independent B source pass and immutable receipt; accepts no generated assistance inputs."""

import hashlib
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import AnnotationSample, Sealed, Slug, digest, seal
from archguard.benchmark.oss.review import RevisionCatalog
from archguard.core.model.base import DomainModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_assistance import (
    CHEATSHEET,
    AssistancePackage,
    build_assistance,
    publish_assistance,
)
from archguard.infrastructure.oss_benchmark import FrozenOSSCorpus, write_new


class ContextSufficiency(DomainModel):
    case_id: Slug
    extra_context_recommended: bool


class ReviewerBAssistance(AssistancePackage):
    strategy: Literal["reviewer-b-assistance-v1"] = "reviewer-b-assistance-v1"
    context_sufficiency: tuple[ContextSufficiency, ...]

    @model_validator(mode="after")
    def consistent_context_flags(self) -> Self:
        expected = tuple(
            ContextSufficiency(
                case_id=c.case_id, extra_context_recommended=bool(c.extra_context_recommended)
            )
            for c in self.cases
        )
        if self.context_sufficiency != expected:
            raise ValueError("context flags must match independently derived requests")
        return self


class BAssistanceFreeze(Sealed):
    schema_version: Literal["oss-reviewer-b-assistance-freeze-v1"] = (
        "oss-reviewer-b-assistance-freeze-v1"
    )
    strategy: Literal["reviewer-b-assistance-v1"] = "reviewer-b-assistance-v1"
    assistance_fingerprint: Digest
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    content_fingerprint: Digest
    files: tuple[tuple[str, Digest], ...]


def build_b_assistance(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, catalog: RevisionCatalog
) -> ReviewerBAssistance:
    # A new read of original source inputs. No generated A data or human forms enter this API.
    source = build_assistance(bound, sample, cache, catalog)
    order = {"DEPENDENCY": 0, "SOURCE": 1, "DOCUMENTATION": 2}
    cases = tuple(
        case.model_copy(
            update={
                "assistant_evidence_candidates": tuple(
                    sorted(case.assistant_evidence_candidates, key=lambda e: order[e.purpose])
                )
            }
        )
        for case in source.cases
    )
    return seal(
        ReviewerBAssistance,
        **(
            source.model_dump(exclude={"fingerprint", "cases"})
            | {
                "cases": cases,
                "context_sufficiency": tuple(
                    ContextSufficiency(
                        case_id=c.case_id,
                        extra_context_recommended=bool(c.extra_context_recommended),
                    )
                    for c in cases
                ),
            }
        ),
    )


def publish_b_assistance(package: ReviewerBAssistance, destination: Path) -> BAssistanceFreeze:
    cheatsheet = CHEATSHEET.replace(
        "Both independent reviewers receive the same source context and must",
        "This independent B pass uses the same pinned original source inputs; reviewers must",
    )
    publish_assistance(package, destination, behavior_first=True, cheatsheet=cheatsheet)
    files = tuple(
        (p.name, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted(destination.iterdir())
        if p.is_file()
    )
    receipt = seal(
        BAssistanceFreeze,
        assistance_fingerprint=package.fingerprint,
        sample_fingerprint=package.sample_fingerprint,
        catalog_fingerprint=package.catalog_fingerprint,
        content_fingerprint=digest(files),
        files=files,
    )
    write_new(destination / "assistance-freeze.json", receipt)
    return receipt


def verify_b_freeze(destination: Path) -> tuple[ReviewerBAssistance, BAssistanceFreeze]:
    receipt = BAssistanceFreeze.model_validate(
        _read(destination / "assistance-freeze.json", 2097152)
    )
    if receipt.content_fingerprint != digest(receipt.files) or len(
        set(n for n, _ in receipt.files)
    ) != len(receipt.files):
        raise ValueError("B assistance freeze file manifest mismatch")
    for name, expected in receipt.files:
        if Path(name).name != name:
            raise ValueError("B freeze paths must be local filenames")
        path = destination / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("B assistance changed after freeze")
    package = ReviewerBAssistance.model_validate(_read(destination / "assistance.json", 8388608))
    expected_files = {"assistance.json", "index.md", "ANNOTATION_CHEATSHEET.md"} | {
        c.case_id + ".md" for c in package.cases
    }
    if (
        set(n for n, _ in receipt.files) != expected_files
        or receipt.assistance_fingerprint != package.fingerprint
        or receipt.sample_fingerprint != package.sample_fingerprint
        or receipt.catalog_fingerprint != package.catalog_fingerprint
    ):
        raise ValueError("B assistance freeze context mismatch")
    return package, receipt
