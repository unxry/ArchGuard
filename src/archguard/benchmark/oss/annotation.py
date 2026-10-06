"""Independent hash sampling, explicit scope and human review transitions."""

from collections import Counter
from collections.abc import Mapping
from typing import Literal

from archguard.benchmark.oss.models import (
    Adjudication,
    AnnotationPacket,
    AnnotationResult,
    AnnotationSample,
    CaseReview,
    CorpusFreeze,
    HumanAnnotation,
    OSSCorpus,
    SamplingProtocol,
    digest,
    seal,
)
from archguard.core.model.base import DomainModel

QUESTIONS = {
    "ARCH201": (
        "Does the component implement responsibilities inconsistent with its "
        "documented role? Cite the intended role and source behavior; use "
        "UNCERTAIN when no role is documented."
    ),
    "ARCH202": (
        "Does this component contain substantial business decisions, "
        "calculations or workflow beyond mapping, validation and delegation? "
        "Use OUT_OF_SCOPE when the presentation/controller question is "
        "inapplicable."
    ),
    "ARCH203": (
        "Does domain/application behavior depend directly on infrastructure "
        "details such as persistence or transport? Explain the documented "
        "boundary; infrastructure components alone are not automatically "
        "positive."
    ),
    "ARCH204": (
        "Is this component placed outside the module/layer that its documented "
        "responsibility belongs to? Without evidence for the intended "
        "placement, use UNCERTAIN."
    ),
    "ARCH205": (
        "Does this component combine responsibilities across documented "
        "architectural boundaries in a way that violates their separation? "
        "Distinguish orchestration from a boundary violation."
    ),
}


class SamplingSubject(DomainModel):
    repository_id: str
    packet_template: AnnotationPacket
    raw_degree: int


def sample_subjects(
    corpus: OSSCorpus,
    freeze: CorpusFreeze,
    protocol: SamplingProtocol,
    subjects: tuple[SamplingSubject, ...],
) -> AnnotationSample:
    if freeze.corpus_fingerprint != corpus.fingerprint:
        raise ValueError("sample requires exact frozen corpus")
    packets = []
    strata = []
    seen = set()
    for repository in corpus.repositories:
        universe = sorted(
            (s for s in subjects if s.repository_id == repository.repository_id),
            key=lambda s: (s.raw_degree, digest(s.packet_template.subject)),
        )
        groups: dict[str, list[SamplingSubject]] = {"LOW": [], "MEDIUM": [], "HIGH": []}
        for index, subject in enumerate(universe):
            key = digest((repository.repository_id, subject.packet_template.subject))
            if key in seen:
                raise ValueError("duplicate annotation subject")
            seen.add(key)
            groups[protocol.strata[min(2, index * 3 // len(universe))]].append(subject)
        for group in groups.values():
            group.sort(
                key=lambda s: digest(
                    (protocol.seed, repository.repository_id, s.packet_template.subject)
                )
            )
        chosen: list[tuple[SamplingSubject, Literal["LOW", "MEDIUM", "HIGH"]]] = []
        while len(chosen) < protocol.subjects_per_repository and any(groups.values()):
            for stratum in protocol.strata:
                if groups[stratum] and len(chosen) < protocol.subjects_per_repository:
                    chosen.append((groups[stratum].pop(0), stratum))
        for index, (subject, stratum) in enumerate(chosen):
            template = subject.packet_template
            rule = protocol.questions[index % len(protocol.questions)]
            case_id = (
                "oss-"
                + digest((corpus.fingerprint, template.repository_id, rule, template.subject))[:24]
            )
            packet = seal(
                AnnotationPacket,
                **(
                    template.model_dump(mode="python", exclude={"fingerprint"})
                    | {
                        "annotation_case_id": case_id,
                        "rule_id": rule,
                        "question": QUESTIONS[rule],
                    }
                ),
            )
            packets.append(packet)
            strata.append((case_id, stratum))
    if any(s.repository_id not in {r.repository_id for r in corpus.repositories} for s in subjects):
        raise ValueError("sampling subject from unknown repository")
    return seal(
        AnnotationSample,
        corpus_fingerprint=corpus.fingerprint,
        corpus_freeze_fingerprint=freeze.fingerprint,
        sampling_protocol_fingerprint=digest(protocol),
        packets=tuple(packets),
        strata=tuple(strata),
    )


def review_annotations(
    sample: AnnotationSample,
    reviews: tuple[HumanAnnotation, ...],
    adjudications: tuple[Adjudication, ...] = (),
    previous: AnnotationResult | None = None,
) -> AnnotationResult:
    if previous is not None:
        replayed = review_annotations(sample, previous.reviews, previous.adjudications)
        if replayed != previous:
            raise ValueError("previous review status does not match actual reviewer history")
        if previous.sample_fingerprint != sample.fingerprint:
            raise ValueError("previous annotations belong to a different frozen sample")
        reviews = previous.reviews + reviews
        adjudications = previous.adjudications + adjudications
    packets = {p.annotation_case_id: p for p in sample.packets}
    seen = set()
    for review in reviews:
        packet = packets.get(review.annotation_case_id)
        if packet is None or review.packet_fingerprint != packet.fingerprint:
            raise ValueError("unknown case or packet/corpus mismatch")
        identity = (review.annotation_case_id, review.reviewer_id)
        if identity in seen:
            raise ValueError("human review cannot be overwritten")
        seen.add(identity)
        if not set(review.evidence) <= set(packet.evidence):
            raise ValueError("evidence/source hash must belong to frozen packet")
    decisions = {a.annotation_case_id: a for a in adjudications}
    if len(decisions) != len(adjudications) or not set(decisions) <= set(packets):
        raise ValueError("duplicate/unknown adjudication")
    cases = []
    for case_id, packet in packets.items():
        case_reviews = [r for r in reviews if r.annotation_case_id == case_id]
        if len(case_reviews) > 2:
            raise ValueError("v1 allows two independent reviews; third must be adjudication")
        status: Literal[
            "UNREVIEWED", "SINGLE_REVIEW", "DOUBLE_REVIEW", "ADJUDICATION_REQUIRED", "ADJUDICATED"
        ]
        label: Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE", "NOT_ANNOTATED"]
        status, label = "UNREVIEWED", "NOT_ANNOTATED"
        if len(case_reviews) == 1:
            status, label = "SINGLE_REVIEW", case_reviews[0].label
        elif len(case_reviews) == 2:
            if case_reviews[0].label == case_reviews[1].label:
                status, label = "DOUBLE_REVIEW", case_reviews[0].label
            else:
                status = "ADJUDICATION_REQUIRED"
        if case_id in decisions:
            adjudication = decisions[case_id]
            if status != "ADJUDICATION_REQUIRED" or not set(adjudication.evidence) <= set(
                packet.evidence
            ):
                raise ValueError("adjudication requires actual conflict and frozen evidence")
            if adjudication.adjudicator_id in {r.reviewer_id for r in case_reviews}:
                raise ValueError("adjudicator must be independent of initial reviewers")
            status, label = "ADJUDICATED", adjudication.label
        cases.append(CaseReview(annotation_case_id=case_id, status=status, final_label=label))
    return seal(
        AnnotationResult,
        corpus_fingerprint=sample.corpus_fingerprint,
        sample_fingerprint=sample.fingerprint,
        reviews=reviews,
        adjudications=adjudications,
        cases=tuple(cases),
    )


def annotation_scope(
    sample: AnnotationSample, repository_id: str, rule: str, subject: object
) -> str:
    return (
        "IN_SCOPE"
        if any(
            p.repository_id == repository_id
            and p.rule_id == rule
            and digest(p.subject) == digest(subject)
            for p in sample.packets
        )
        else "OUT_OF_SCOPE"
    )


def agreement(
    result: AnnotationResult, reviewers: tuple[str, str]
) -> Mapping[str, int | float | None]:
    if len(set(reviewers)) != 2:
        raise ValueError("two distinct actual reviewers required")
    left = {r.annotation_case_id: r.label for r in result.reviews if r.reviewer_id == reviewers[0]}
    right = {r.annotation_case_id: r.label for r in result.reviews if r.reviewer_id == reviewers[1]}
    common = sorted(set(left) & set(right))
    if not common:
        return {"pairs": 0, "agreements": 0, "agreement_rate": None, "kappa": None}
    count = sum(left[k] == right[k] for k in common)
    n = len(common)
    lcounts, rcounts = Counter(left[k] for k in common), Counter(right[k] for k in common)
    expected = sum(lcounts[label] * rcounts[label] for label in set(lcounts) | set(rcounts)) / n**2
    observed = count / n
    return {
        "pairs": n,
        "agreements": count,
        "agreement_rate": observed,
        "kappa": (observed - expected) / (1 - expected) if expected != 1 else None,
    }


class SamplingFrame(DomainModel):
    schema_version: Literal["oss-sampling-frame-v1"] = "oss-sampling-frame-v1"
    corpus_fingerprint: str
    corpus_freeze_fingerprint: str
    subjects: tuple[SamplingSubject, ...]
