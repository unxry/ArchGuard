"""Source-free, append-only human review protocol. No predictions enter these contracts."""

from collections import Counter
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from archguard.benchmark.models import Digest, relative_path
from archguard.benchmark.oss.models import (
    AnnotationPacket,
    AnnotationSample,
    Commit,
    Count,
    Sealed,
    Slug,
    seal,
)
from archguard.core.model.base import DomainModel

Label = Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]
BINARY: frozenset[Label] = frozenset({"POSITIVE", "NEGATIVE"})
TERMINAL = {"DOUBLE_REVIEW", "ADJUDICATED"}


class PinnedEvidence(DomainModel):
    repository_id: Slug
    commit_sha: Commit
    path: str
    sha256: Digest
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    purpose: Literal["SOURCE", "DEPENDENCY", "DOCUMENTATION"]

    _path = field_validator("path")(relative_path)

    @model_validator(mode="after")
    def ordered(self) -> Self:
        if self.end_line < self.start_line:
            raise ValueError("invalid evidence line range")
        return self


class PacketRevision(Sealed):
    annotation_case_id: Slug
    original_packet_fingerprint: Digest
    repository_id: Slug
    commit_sha: Commit
    review_question: str = Field(min_length=1)
    guide_fingerprint: Digest
    revision: int = Field(ge=1)
    previous_packet_fingerprint: Digest | None = None
    additional_evidence: tuple[PinnedEvidence, ...] = ()


class RevisionCatalog(Sealed):
    schema_version: Literal["oss-review-packets-v1"] = "oss-review-packets-v1"
    sample_fingerprint: Digest
    packets: tuple[PacketRevision, ...]


def original_evidence(
    packet: AnnotationPacket, revision: PacketRevision
) -> tuple[PinnedEvidence, ...]:
    return tuple(
        PinnedEvidence(
            repository_id=packet.repository_id,
            commit_sha=revision.commit_sha,
            path=e.path,
            sha256=e.sha256,
            start_line=e.start_line,
            end_line=e.end_line,
            purpose="SOURCE" if e.purpose == "DECLARATION" else e.purpose,
        )
        for e in packet.evidence
    )


def validate_catalog(sample: AnnotationSample, catalog: RevisionCatalog) -> None:
    if catalog.sample_fingerprint != sample.fingerprint:
        raise ValueError("packet catalog sample mismatch")
    originals = {p.annotation_case_id: p for p in sample.packets}
    latest: dict[str, PacketRevision] = {}
    for revision in catalog.packets:
        packet = originals.get(revision.annotation_case_id)
        if packet is None or (
            revision.original_packet_fingerprint != packet.fingerprint
            or revision.repository_id != packet.repository_id
        ):
            raise ValueError("packet revision outside frozen sample")
        previous = latest.get(revision.annotation_case_id)
        if previous is None:
            if (
                revision.revision != 1
                or revision.previous_packet_fingerprint is not None
                or revision.additional_evidence
            ):
                raise ValueError("original packet revision must be unchanged")
        elif (
            revision.revision != previous.revision + 1
            or revision.previous_packet_fingerprint != previous.fingerprint
            or revision.commit_sha != previous.commit_sha
            or revision.review_question != previous.review_question
            or revision.guide_fingerprint != previous.guide_fingerprint
            or revision.additional_evidence[: len(previous.additional_evidence)]
            != previous.additional_evidence
            or len(revision.additional_evidence) <= len(previous.additional_evidence)
        ):
            raise ValueError("supplemental packet must append context to previous revision")
        if len(set(revision.additional_evidence)) != len(revision.additional_evidence):
            raise ValueError("duplicate supplemental evidence")
        if any(
            e.repository_id != revision.repository_id or e.commit_sha != revision.commit_sha
            for e in revision.additional_evidence
        ):
            raise ValueError("supplemental evidence must name the pinned repository/commit")
        latest[revision.annotation_case_id] = revision
    if set(latest) != set(originals):
        raise ValueError("packet catalog must cover frozen sample")


class HumanDecision(DomainModel):
    annotation_case_id: Slug
    packet_fingerprint: Digest
    packet_revision: int = Field(ge=1)
    label: Label
    rationale: str = Field(min_length=1)
    evidence: tuple[PinnedEvidence, ...] = ()
    uncertainty: Literal["CLEAR", "AMBIGUOUS"]
    attestation: Literal["HUMAN_REVIEW_COMPLETED"]

    @model_validator(mode="after")
    def justified(self) -> Self:
        if not self.rationale.strip() or (self.label in BINARY and not self.evidence):
            raise ValueError("human decisions require rationale; binary labels require evidence")
        return self


class ReviewInput(HumanDecision):
    reviewer_id: Slug
    supersedes_review_id: Digest | None = None


class AdjudicationInput(HumanDecision):
    adjudicator_id: Slug
    review_ids: tuple[Digest, Digest]
    supersedes_adjudication_id: Digest | None = None


class ReviewEvent(Sealed):
    review: ReviewInput


class AdjudicationEvent(Sealed):
    adjudication: AdjudicationInput


class ResolvedCase(DomainModel):
    annotation_case_id: Slug
    status: Literal[
        "UNREVIEWED", "SINGLE_REVIEW", "DOUBLE_REVIEW", "ADJUDICATION_REQUIRED", "ADJUDICATED"
    ]
    final_label: Label | Literal["NOT_ANNOTATED"] = "NOT_ANNOTATED"
    provisional_label: Label | None = None

    @property
    def binary_eligible(self) -> bool:
        return self.status in TERMINAL and self.final_label in BINARY


class ReviewStore(Sealed):
    schema_version: Literal["oss-human-review-store-v1"] = "oss-human-review-store-v1"
    corpus_fingerprint: Digest
    sample_fingerprint: Digest
    reviews: tuple[ReviewEvent, ...] = ()
    adjudications: tuple[AdjudicationEvent, ...] = ()
    cases: tuple[ResolvedCase, ...]


def _decision_scope(
    sample: AnnotationSample, catalog: RevisionCatalog, decision: HumanDecision
) -> None:
    revision = next(
        (p for p in catalog.packets if p.fingerprint == decision.packet_fingerprint), None
    )
    if revision is None or (revision.annotation_case_id, revision.revision) != (
        decision.annotation_case_id,
        decision.packet_revision,
    ):
        raise ValueError("unknown case/packet revision")
    packet = next(p for p in sample.packets if p.annotation_case_id == decision.annotation_case_id)
    available = original_evidence(packet, revision) + revision.additional_evidence
    for evidence in decision.evidence:
        if not any(
            (
                evidence.repository_id,
                evidence.commit_sha,
                evidence.path,
                evidence.sha256,
                evidence.purpose,
            )
            == (ref.repository_id, ref.commit_sha, ref.path, ref.sha256, ref.purpose)
            and ref.start_line <= evidence.start_line <= evidence.end_line <= ref.end_line
            for ref in available
        ):
            raise ValueError("evidence requires a matching source-verified packet revision")


def _replay(
    sample: AnnotationSample,
    catalog: RevisionCatalog,
    reviews: tuple[ReviewEvent, ...],
    adjudications: tuple[AdjudicationEvent, ...],
) -> ReviewStore:
    active: dict[str, dict[str, ReviewEvent]] = {p.annotation_case_id: {} for p in sample.packets}
    seen: set[str] = set()
    # Adjudications can refer to an earlier pair preserved by a later amendment.
    historical: dict[str, ReviewEvent] = {}
    for event in reviews:
        review = event.review
        _decision_scope(sample, catalog, review)
        if event.fingerprint in seen:
            raise ValueError("duplicate review event")
        seen.add(event.fingerprint)
        by_reviewer = active[review.annotation_case_id]
        previous = by_reviewer.get(review.reviewer_id)
        if previous:
            if review.supersedes_review_id != previous.fingerprint:
                raise ValueError("same reviewer requires explicit amendment of active review")
        elif review.supersedes_review_id is not None or len(by_reviewer) >= 2:
            raise ValueError("two distinct independent reviewers required; invalid amendment")
        by_reviewer[review.reviewer_id] = event
        historical[event.fingerprint] = event
    resolutions: dict[str, AdjudicationEvent] = {}
    for adjudication_event in adjudications:
        decision = adjudication_event.adjudication
        _decision_scope(sample, catalog, decision)
        if adjudication_event.fingerprint in seen:
            raise ValueError("duplicate adjudication event")
        seen.add(adjudication_event.fingerprint)
        pair = tuple(historical.get(identifier) for identifier in decision.review_ids)
        if any(r is None for r in pair):
            raise ValueError("adjudication refers to unknown reviews")
        left, right = pair
        assert left is not None and right is not None
        if (
            left.review.annotation_case_id != decision.annotation_case_id
            or right.review.annotation_case_id != decision.annotation_case_id
            or left.review.reviewer_id == right.review.reviewer_id
            or left.review.label == right.review.label
            or decision.adjudicator_id in {left.review.reviewer_id, right.review.reviewer_id}
        ):
            raise ValueError("adjudication requires a conflict and a distinct third human")
        previous_adj = resolutions.get(decision.annotation_case_id)
        if decision.supersedes_adjudication_id is not None:
            if previous_adj is None or (
                decision.supersedes_adjudication_id,
                decision.adjudicator_id,
                set(decision.review_ids),
            ) != (
                previous_adj.fingerprint,
                previous_adj.adjudication.adjudicator_id,
                set(previous_adj.adjudication.review_ids),
            ):
                raise ValueError("invalid adjudication amendment")
        elif previous_adj and set(previous_adj.adjudication.review_ids) == set(decision.review_ids):
            raise ValueError("adjudication correction requires explicit amendment")
        resolutions[decision.annotation_case_id] = adjudication_event
    cases = []
    for packet in sample.packets:
        case_id = packet.annotation_case_id
        current_pair = tuple(active[case_id].values())
        status: Literal[
            "UNREVIEWED", "SINGLE_REVIEW", "DOUBLE_REVIEW", "ADJUDICATION_REQUIRED", "ADJUDICATED"
        ] = "UNREVIEWED"
        label: Label | Literal["NOT_ANNOTATED"] = "NOT_ANNOTATED"
        provisional = None
        if len(current_pair) == 1:
            status, provisional = "SINGLE_REVIEW", current_pair[0].review.label
        elif len(current_pair) == 2:
            if current_pair[0].review.label == current_pair[1].review.label:
                status, label = "DOUBLE_REVIEW", current_pair[0].review.label
            else:
                status = "ADJUDICATION_REQUIRED"
                resolution = resolutions.get(case_id)
                if resolution and set(resolution.adjudication.review_ids) == {
                    r.fingerprint for r in current_pair
                }:
                    status, label = "ADJUDICATED", resolution.adjudication.label
        cases.append(
            ResolvedCase(
                annotation_case_id=case_id,
                status=status,
                final_label=label,
                provisional_label=provisional,
            )
        )
    return seal(
        ReviewStore,
        corpus_fingerprint=sample.corpus_fingerprint,
        sample_fingerprint=sample.fingerprint,
        reviews=reviews,
        adjudications=adjudications,
        cases=tuple(cases),
    )


def append_reviews(
    sample: AnnotationSample,
    catalog: RevisionCatalog,
    reviews: tuple[ReviewInput, ...] = (),
    adjudications: tuple[AdjudicationInput, ...] = (),
    previous: ReviewStore | None = None,
) -> ReviewStore:
    validate_catalog(sample, catalog)
    old_reviews: tuple[ReviewEvent, ...] = ()
    old_adjudications: tuple[AdjudicationEvent, ...] = ()
    if previous:
        if (previous.corpus_fingerprint, previous.sample_fingerprint) != (
            sample.corpus_fingerprint,
            sample.fingerprint,
        ):
            raise ValueError("review store sample/corpus mismatch")
        if _replay(sample, catalog, previous.reviews, previous.adjudications) != previous:
            raise ValueError("review history/state mismatch")
        old_reviews, old_adjudications = previous.reviews, previous.adjudications
    result = _replay(
        sample,
        catalog,
        old_reviews + tuple(seal(ReviewEvent, review=r) for r in reviews),
        old_adjudications + tuple(seal(AdjudicationEvent, adjudication=a) for a in adjudications),
    )
    # A newly submitted adjudication must settle the current pair, not a stale pair.
    active = active_reviews(result)
    for adjudication in adjudications:
        if set(adjudication.review_ids) != {
            r.fingerprint for r in active[adjudication.annotation_case_id]
        }:
            raise ValueError("adjudication must name the current independent review pair")
    return result


def active_reviews(store: ReviewStore) -> dict[str, tuple[ReviewEvent, ...]]:
    current: dict[str, dict[str, ReviewEvent]] = {c.annotation_case_id: {} for c in store.cases}
    for event in store.reviews:
        current[event.review.annotation_case_id][event.review.reviewer_id] = event
    return {case: tuple(reviews.values()) for case, reviews in current.items()}


class Agreement(DomainModel):
    paired_cases: Count
    binary_pairs: Count
    nonbinary_pairs: Count
    agreements: Count
    agreement_rate: float | None
    cohen_kappa: float | None


def paired_agreement(pairs: tuple[tuple[ReviewEvent, ...], ...]) -> Agreement:
    paired = tuple(p for p in pairs if len(p) == 2)
    binary = tuple(p for p in paired if all(r.review.label in BINARY for r in p))
    count = len(binary)
    agreed = sum(p[0].review.label == p[1].review.label for p in binary)
    rate = agreed / count if count else None
    # Orient by reviewer ID consistently; never pool different rater pairs for kappa.
    rater_pairs = {tuple(sorted(r.review.reviewer_id for r in p)) for p in binary}
    kappa = None
    if count and len(rater_pairs) == 1:
        ordered = tuple(tuple(sorted(p, key=lambda r: r.review.reviewer_id)) for p in binary)
        left = Counter(p[0].review.label for p in ordered)
        right = Counter(p[1].review.label for p in ordered)
        expected = sum(left[label] * right[label] for label in BINARY) / count**2
        if expected < 1:
            assert rate is not None
            kappa = (rate - expected) / (1 - expected)
    return Agreement(
        paired_cases=len(paired),
        binary_pairs=count,
        nonbinary_pairs=len(paired) - count,
        agreements=agreed,
        agreement_rate=rate,
        cohen_kappa=kappa,
    )


class ReviewCounts(DomainModel):
    total: Count
    unreviewed: Count
    single_review: Count
    double_review: Count
    conflicts: Count
    adjudicated: Count
    positive: Count
    negative: Count
    uncertain: Count
    out_of_scope: Count
    binary_eligible: Count


def counts(cases: tuple[ResolvedCase, ...]) -> ReviewCounts:
    statuses = Counter(c.status for c in cases)
    labels = Counter(c.final_label for c in cases if c.status in TERMINAL)
    return ReviewCounts(
        total=len(cases),
        unreviewed=statuses["UNREVIEWED"],
        single_review=statuses["SINGLE_REVIEW"],
        double_review=statuses["DOUBLE_REVIEW"],
        conflicts=statuses["ADJUDICATION_REQUIRED"],
        adjudicated=statuses["ADJUDICATED"],
        positive=labels["POSITIVE"],
        negative=labels["NEGATIVE"],
        uncertain=labels["UNCERTAIN"],
        out_of_scope=labels["OUT_OF_SCOPE"],
        binary_eligible=sum(c.binary_eligible for c in cases),
    )


class ReviewGroup(DomainModel):
    key: str
    counts: ReviewCounts
    agreement: Agreement


class AnnotationReviewReport(Sealed):
    schema_version: Literal["oss-annotation-review-report-v1"] = "oss-annotation-review-report-v1"
    sample_fingerprint: Digest
    store_fingerprint: Digest
    counts: ReviewCounts
    human_reviewers: Count
    review_events: Count
    adjudication_events: Count
    readiness: Literal[
        "WAITING_FOR_HUMAN_REVIEW",
        "FIRST_REVIEW_IN_PROGRESS",
        "FIRST_REVIEW_COMPLETE",
        "SECOND_REVIEW_IN_PROGRESS",
        "SECOND_REVIEW_COMPLETE",
        "ADJUDICATION_REQUIRED",
        "ANNOTATION_FROZEN",
    ]
    full_hybrid_readiness: Literal["NOT_READY"] = "NOT_READY"
    agreement: Agreement
    by_rule: tuple[ReviewGroup, ...]
    by_language: tuple[ReviewGroup, ...]
    by_repository: tuple[ReviewGroup, ...]


def review_report(
    sample: AnnotationSample, store: ReviewStore, *, frozen: bool = False
) -> AnnotationReviewReport:
    active = active_reviews(store)
    summary = counts(store.cases)
    readiness: Literal[
        "WAITING_FOR_HUMAN_REVIEW",
        "FIRST_REVIEW_IN_PROGRESS",
        "FIRST_REVIEW_COMPLETE",
        "SECOND_REVIEW_IN_PROGRESS",
        "SECOND_REVIEW_COMPLETE",
        "ADJUDICATION_REQUIRED",
        "ANNOTATION_FROZEN",
    ] = "WAITING_FOR_HUMAN_REVIEW"
    if frozen:
        if not store.cases or any(c.status not in TERMINAL for c in store.cases):
            raise ValueError("cannot report unresolved annotations as frozen")
        readiness = "ANNOTATION_FROZEN"
    elif summary.conflicts:
        readiness = "ADJUDICATION_REQUIRED"
    elif summary.total and summary.double_review + summary.adjudicated == summary.total:
        readiness = "SECOND_REVIEW_COMPLETE"
    elif summary.double_review + summary.adjudicated:
        readiness = "SECOND_REVIEW_IN_PROGRESS"
    elif summary.single_review == summary.total and summary.total:
        readiness = "FIRST_REVIEW_COMPLETE"
    elif summary.single_review:
        readiness = "FIRST_REVIEW_IN_PROGRESS"
    groups = []
    for dimension in ("rule", "language", "repository"):
        keys = {
            p.annotation_case_id: str(
                p.rule_id
                if dimension == "rule"
                else p.subject.language.value
                if dimension == "language"
                else p.repository_id
            )
            for p in sample.packets
        }
        groups.append(
            tuple(
                ReviewGroup(
                    key=key,
                    counts=counts(
                        tuple(c for c in store.cases if keys[c.annotation_case_id] == key)
                    ),
                    agreement=paired_agreement(
                        tuple(active[case] for case in keys if keys[case] == key)
                    ),
                )
                for key in sorted(set(keys.values()))
            )
        )
    return seal(
        AnnotationReviewReport,
        sample_fingerprint=sample.fingerprint,
        store_fingerprint=store.fingerprint,
        counts=summary,
        human_reviewers=len({e.review.reviewer_id for e in store.reviews}),
        review_events=len(store.reviews),
        adjudication_events=len(store.adjudications),
        readiness=readiness,
        agreement=paired_agreement(tuple(active.values())),
        by_rule=groups[0],
        by_language=groups[1],
        by_repository=groups[2],
    )


class ReviewedFreeze(Sealed):
    schema_version: Literal["oss-reviewed-annotation-freeze-v1"] = (
        "oss-reviewed-annotation-freeze-v1"
    )
    corpus_fingerprint: Digest
    corpus_freeze_fingerprint: Digest
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    store_fingerprint: Digest
    review_fingerprints: tuple[Digest, ...]
    adjudication_fingerprints: tuple[Digest, ...]
    resolved_cases: tuple[ResolvedCase, ...]
    status: Literal["ANNOTATION_FROZEN"] = "ANNOTATION_FROZEN"
    future_model_receipts: Literal["REQUIRED_FOR_EVALUATION; NONE_ATTACHED"] = (
        "REQUIRED_FOR_EVALUATION; NONE_ATTACHED"
    )


def freeze_reviews(
    sample: AnnotationSample, catalog: RevisionCatalog, store: ReviewStore
) -> ReviewedFreeze:
    append_reviews(sample, catalog, previous=store)
    if not store.cases or any(c.status not in TERMINAL for c in store.cases):
        raise ValueError(
            "final annotation freeze requires two independent reviews "
            "and resolved conflicts for every case"
        )
    return seal(
        ReviewedFreeze,
        corpus_fingerprint=sample.corpus_fingerprint,
        corpus_freeze_fingerprint=sample.corpus_freeze_fingerprint,
        sample_fingerprint=sample.fingerprint,
        catalog_fingerprint=catalog.fingerprint,
        store_fingerprint=store.fingerprint,
        review_fingerprints=tuple(r.fingerprint for r in store.reviews),
        adjudication_fingerprints=tuple(a.fingerprint for a in store.adjudications),
        resolved_cases=store.cases,
    )
