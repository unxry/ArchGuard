"""Independent human responses to frozen source-only holdout packets."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import Sealed, digest
from archguard.benchmark.semantic_holdout import BlindedPacket
from archguard.core.model.base import DomainModel

Outcome = Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]


class _ReviewBundle(Sealed):
    schema_version: Literal["blank-independent-human-bundle-v1"]
    reviewer_slot: Literal["A", "B"]
    status: Literal["WAITING_FOR_REAL_INDEPENDENT_HUMAN"]
    packets: tuple[BlindedPacket, ...] = Field(min_length=100, max_length=100)
    protocol: dict[str, Any]
    guidance: dict[str, Any]

    @model_validator(mode="after")
    def unique_and_sealed(self) -> Self:
        if len({p.blinded_id for p in self.packets}) != 100:
            raise ValueError("100 unique blinded IDs required")
        for item in (self.protocol, self.guidance):
            if item.get("fingerprint") != digest(
                {k: v for k, v in item.items() if k != "fingerprint"}
            ):
                raise ValueError("frozen protocol/guidance fingerprint mismatch")
        for packet in self.packets:
            if len({e.evidence_id for e in packet.evidence}) != len(packet.evidence):
                raise ValueError("duplicate source evidence IDs")
        return self


class ReviewerABundle(_ReviewBundle):
    reviewer_slot: Literal["A"]


class ReviewerBBundle(_ReviewBundle):
    reviewer_slot: Literal["B"]


class EvidenceReference(DomainModel):
    evidence_id: str = Field(min_length=1)
    start_line: int = Field(ge=1, strict=True)
    end_line: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_line < self.start_line:
            raise ValueError("evidence line range reversed")
        return self


class HumanResponse(DomainModel):
    blinded_id: str = Field(min_length=1)
    decision: Outcome
    rationale: str = Field(min_length=1, max_length=4000)
    evidence: tuple[EvidenceReference, ...] = Field(min_length=1)
    note: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def justified(self) -> Self:
        if not self.rationale.strip():
            raise ValueError("human rationale cannot be blank")
        if len(set(self.evidence)) != len(self.evidence):
            raise ValueError("duplicate evidence references")
        return self


class _HumanSubmission(DomainModel):
    schema_version: Literal["semantic-holdout-human-submission-v1"]
    reviewer_slot: Literal["A", "B"]
    bundle_fingerprint: Digest
    reviewer_identity: str = Field(min_length=1, max_length=200)
    attestation: Literal["REAL_HUMAN_INDEPENDENT_REVIEW"]
    responses: tuple[HumanResponse, ...] = Field(min_length=100, max_length=100)

    @model_validator(mode="after")
    def human_complete(self) -> Self:
        if not self.reviewer_identity.strip():
            raise ValueError("self-declared real reviewer identity required")
        if len({r.blinded_id for r in self.responses}) != 100:
            raise ValueError("100 unique human responses required")
        return self


class ReviewerASubmission(_HumanSubmission):
    reviewer_slot: Literal["A"]


class ReviewerBSubmission(_HumanSubmission):
    reviewer_slot: Literal["B"]


def validate_submission(
    bundle: ReviewerABundle | ReviewerBBundle,
    submission: ReviewerASubmission | ReviewerBSubmission,
) -> None:
    if (
        submission.bundle_fingerprint != bundle.fingerprint
        or submission.reviewer_slot != bundle.reviewer_slot
    ):
        raise ValueError("submission must reference its frozen reviewer slot and bundle")
    packets = {p.blinded_id: p for p in bundle.packets}
    if {r.blinded_id for r in submission.responses} != set(packets):
        raise ValueError("responses must cover exactly the frozen blinded IDs")
    for response in submission.responses:
        evidence = {e.evidence_id: e for e in packets[response.blinded_id].evidence}
        for ref in response.evidence:
            source = evidence.get(ref.evidence_id)
            if source is None or ref.end_line > len(source.text.splitlines()):
                raise ValueError("reference outside frozen case source evidence")
