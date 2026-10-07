"""Four source-only adjudication packets and future independent response validation."""

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import Sealed, digest
from archguard.benchmark.semantic_holdout import Language, SourceEvidence
from archguard.benchmark.semantic_review import HumanResponse
from archguard.core.model.base import DomainModel


class SafeConflictCase(DomainModel):
    conflict_id: str
    case_id: str
    rule_id: str = Field(pattern=r"^ARCH20[1-5]$")
    language: Language


class SafeConflictIndex(Sealed):
    schema_version: Literal["adjudicator-safe-conflict-index-v1"]
    source_lineage: dict[str, str]
    conflict_count: Literal[4]
    cases: tuple[SafeConflictCase, ...] = Field(min_length=4, max_length=4)
    full_handoff_created: Literal[False]

    @model_validator(mode="after")
    def unique_cases(self) -> Self:
        if any(
            len({getattr(c, field) for c in self.cases}) != 4
            for field in ("case_id", "conflict_id")
        ):
            raise ValueError("four unique frozen conflicts required")
        return self


class AdjudicatorPacket(Sealed):
    schema_version: Literal["blinded-semantic-adjudication-packet-v1"] = (
        "blinded-semantic-adjudication-packet-v1"
    )
    blinded_id: str = Field(pattern=r"^adj-[a-f0-9]{32}$")
    rule_id: str = Field(pattern=r"^ARCH20[1-5]$")
    language: Language
    target_path: str
    target_component: str
    architecture_contract: str
    evidence: tuple[SourceEvidence, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_complete(self) -> Self:
        if self.target_path not in {e.path for e in self.evidence} or len(
            {e.evidence_id for e in self.evidence}
        ) != len(self.evidence):
            raise ValueError("target evidence and unique evidence IDs required")
        return self


class AdjudicatorBundle(Sealed):
    schema_version: Literal["blank-independent-adjudicator-bundle-v1"]
    reviewer_slot: Literal["ADJUDICATOR"]
    status: Literal["WAITING_FOR_ADJUDICATOR"]
    packets: tuple[AdjudicatorPacket, ...] = Field(min_length=4, max_length=4)
    guidance: dict[str, Any]

    @model_validator(mode="after")
    def frozen_and_unique(self) -> Self:
        if len({p.blinded_id for p in self.packets}) != 4:
            raise ValueError("four unique adjudicator IDs required")
        if self.guidance.get("fingerprint") != digest(
            {k: v for k, v in self.guidance.items() if k != "fingerprint"}
        ):
            raise ValueError("frozen guidance seal mismatch")
        return self


class AdjudicatorSubmission(DomainModel):
    schema_version: Literal["semantic-holdout-adjudication-submission-v1"]
    reviewer_slot: Literal["ADJUDICATOR"]
    bundle_fingerprint: Digest
    reviewer_identity: str = Field(min_length=1, max_length=200)
    attestation: Literal["REAL_HUMAN_INDEPENDENT_ADJUDICATION"]
    responses: tuple[HumanResponse, ...] = Field(min_length=4, max_length=4)

    @model_validator(mode="after")
    def human_complete(self) -> Self:
        if not self.reviewer_identity.strip() or len({r.blinded_id for r in self.responses}) != 4:
            raise ValueError("self-declared third human and four unique responses required")
        return self


def validate_adjudication_response(
    bundle: AdjudicatorBundle, submission: AdjudicatorSubmission
) -> None:
    """Schema/evidence support only; no acceptance, persistence or truth materialization."""
    if submission.bundle_fingerprint != bundle.fingerprint:
        raise ValueError("response must bind to the frozen adjudicator bundle")
    packets = {p.blinded_id: p for p in bundle.packets}
    if {r.blinded_id for r in submission.responses} != set(packets):
        raise ValueError("responses must cover exactly the four frozen adjudicator IDs")
    for response in submission.responses:
        evidence = {e.evidence_id: e for e in packets[response.blinded_id].evidence}
        for ref in response.evidence:
            source = evidence.get(ref.evidence_id)
            if source is None or ref.end_line > len(source.text.splitlines()):
                raise ValueError("evidence reference outside its frozen case")
