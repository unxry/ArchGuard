"""Frozen human intake, output mapping and metrics; no benchmark truth or predictions."""

from collections import Counter
from enum import StrEnum
from typing import Any, Literal

from pydantic import Field, model_validator

from archguard.core.model.base import DomainModel

VERSION = "security-benchmark-v1"
RULES = tuple(f"SEC{i:03d}" for i in range(1, 11))


class TruthLabel(StrEnum):
    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    UNCERTAIN = "UNCERTAIN"
    OUT_OF_SCOPE = "OUT_OF_SCOPE"


class SourceFile(DomainModel):
    path: str = Field(pattern=r"^src/[A-Za-z0-9_/]+\.(java|ts)$")
    content: str = Field(min_length=1)


class ReviewEvidence(DomainModel):
    case_id: str = Field(pattern=r"^sc-[a-f0-9]{24}$")
    rule_id: str = Field(pattern=r"^SEC00[1-9]$|^SEC010$")
    rule_definition: str = Field(min_length=1)
    language: Literal["JAVA", "TYPESCRIPT"]
    framework_context: str = Field(min_length=1)
    review_scope: str = Field(min_length=1)
    source_files: tuple[SourceFile, ...] = Field(min_length=1)
    label_choices: tuple[TruthLabel, ...] = tuple(TruthLabel)

    @model_validator(mode="after")
    def complete(self) -> "ReviewEvidence":
        if len({s.path for s in self.source_files}) != len(self.source_files):
            raise ValueError("duplicate source path")
        if self.label_choices != tuple(TruthLabel):
            raise ValueError("frozen label choices required")
        return self


class ReviewPacket(DomainModel):
    reviewer_slot: Literal["A", "B"]
    evidence: ReviewEvidence
    evidence_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    response_destination: str = Field(pattern=r"^responses/[AB]/sc-[a-f0-9]{24}\.json$")

    @model_validator(mode="after")
    def bind(self) -> "ReviewPacket":
        from archguard.benchmark.oss.models import digest

        if self.evidence_fingerprint != digest(self.evidence.model_dump(mode="json")):
            raise ValueError("evidence fingerprint mismatch")
        if (
            self.response_destination
            != f"responses/{self.reviewer_slot}/{self.evidence.case_id}.json"
        ):
            raise ValueError("response destination mismatch")
        return self


class ReviewResponse(DomainModel):
    reviewer_slot: Literal["A", "B"]
    case_id: str = Field(pattern=r"^sc-[a-f0-9]{24}$")
    label: TruthLabel | None = None
    rationale: str | None = Field(default=None, max_length=8000)
    evidence_note: str | None = Field(default=None, max_length=8000)
    completed: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def completion(self) -> "ReviewResponse":
        if self.completed != (self.label is not None):
            raise ValueError("completed response requires exactly one human label")
        return self


def validate_submission(
    responses: tuple[ReviewResponse, ...], slot: Literal["A", "B"], case_ids: set[str]
) -> None:
    if len(responses) != len(case_ids) or {r.case_id for r in responses} != case_ids:
        raise ValueError("missing, duplicate or unexpected case")
    if any(r.reviewer_slot != slot or not r.completed for r in responses):
        raise ValueError("wrong slot or incomplete submission")


def reconcile(
    a: ReviewResponse, b: ReviewResponse, adjudicated: TruthLabel | None = None
) -> dict[str, Any]:
    if a.case_id != b.case_id or a.reviewer_slot != "A" or b.reviewer_slot != "B":
        raise ValueError("independent A/B responses for same case required")
    if not a.completed or not b.completed:
        raise ValueError("both initial human responses must be locked")
    conflict = a.label != b.label
    if adjudicated is not None and not isinstance(adjudicated, TruthLabel):
        raise ValueError("adjudicated label must use the frozen truth enum")
    if not conflict and adjudicated is not None:
        raise ValueError("agreement requires no adjudication")
    return dict(
        case_id=a.case_id,
        A=a.label,
        B=b.label,
        conflict=conflict,
        adjudicated_label=adjudicated if conflict else None,
        final_label=adjudicated if conflict else a.label,
        requires_human_adjudication=conflict and adjudicated is None,
    )


def agreement(a: tuple[TruthLabel, ...], b: tuple[TruthLabel, ...]) -> dict[str, Any]:
    if len(a) != len(b):
        raise ValueError("aligned labels required")
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    same = sum(x == y for x, y in zip(a, b, strict=True))
    raw = same / n if n else None
    chance = sum(ca[x] * cb[x] for x in TruthLabel) / n**2 if n else None
    return dict(
        raw_agreement=raw,
        cohens_kappa=(raw - chance) / (1 - chance)
        if raw is not None and chance is not None and chance != 1
        else None,
        conflict_count=n - same,
        A_distribution={x.value: ca[x] for x in TruthLabel},
        B_distribution={x.value: cb[x] for x in TruthLabel},
    )


class Outcome(StrEnum):
    DEFINITIVE_POSITIVE = "DEFINITIVE_POSITIVE"
    DEFINITIVE_NEGATIVE = "DEFINITIVE_NEGATIVE"
    POTENTIAL = "POTENTIAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNSUPPORTED = "UNSUPPORTED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


def map_outcome(statuses: tuple[str, ...], execution: str, applicable: bool) -> Outcome:
    """Consume a later frozen receipt; no analyzer import or execution."""
    allowed = {
        "CONFIRMED_PATTERN",
        "SUPPORTED",
        "POTENTIAL",
        "INSUFFICIENT_EVIDENCE",
        "NOT_APPLICABLE",
    }
    if set(statuses) - allowed or execution not in {"COMPLETE", "PARTIAL", "UNSUPPORTED", "FAILED"}:
        raise ValueError("unrecognized frozen output semantics")
    if execution in {"FAILED", "UNSUPPORTED"}:
        return Outcome(execution)
    if {"CONFIRMED_PATTERN", "SUPPORTED"} & set(statuses):
        return Outcome.DEFINITIVE_POSITIVE
    if "POTENTIAL" in statuses:
        return Outcome.POTENTIAL
    if "INSUFFICIENT_EVIDENCE" in statuses:
        return Outcome.INSUFFICIENT_EVIDENCE
    if not applicable or "NOT_APPLICABLE" in statuses:
        return Outcome.NOT_APPLICABLE
    if execution == "PARTIAL":
        return Outcome.PARTIAL
    return Outcome.DEFINITIVE_NEGATIVE


def map_p029_outcome(result: dict[str, Any], rule_id: str) -> Outcome:
    """Normalize actual frozen V2 receipts without importing/executing a detector.

    P029's applicable_rules is finding-derived, not a no-finding scope certificate.
    Its SUPPORTED_PARTIAL_V2_SCOPE never authorizes a definitive negative.
    """
    if rule_id not in result.get("requested_rules", ()):
        raise ValueError("target rule not requested")
    coverage = result.get("analysis_metadata", {}).get("coverage", {}).get(rule_id, {})
    status = coverage.get("status")
    if status == "FAILED":
        return Outcome.FAILED
    if status == "CONTRACT_ONLY" and not coverage.get("evaluated"):
        return Outcome.UNSUPPORTED
    if status != "SUPPORTED_PARTIAL_V2_SCOPE" or not coverage.get("evaluated"):
        raise ValueError("unknown P029 coverage receipt")
    findings = tuple(f["status"] for f in result.get("findings", ()) if f["rule_id"] == rule_id)
    return map_outcome(findings, "PARTIAL", True)


def metrics(rows: tuple[tuple[TruthLabel, Outcome], ...]) -> dict[str, Any]:
    """Synthetic-tested future strict metrics; benchmark evaluation is not invoked in P030."""
    if any(t not in tuple(TruthLabel) or o not in tuple(Outcome) for t, o in rows):
        raise ValueError("unknown truth or outcome")
    binary = [(t, o) for t, o in rows if t in {TruthLabel.POSITIVE, TruthLabel.NEGATIVE}]
    tp = sum(t == TruthLabel.POSITIVE and o == Outcome.DEFINITIVE_POSITIVE for t, o in binary)
    fp = sum(t == TruthLabel.NEGATIVE and o == Outcome.DEFINITIVE_POSITIVE for t, o in binary)
    tn = sum(t == TruthLabel.NEGATIVE and o == Outcome.DEFINITIVE_NEGATIVE for t, o in binary)
    fn = sum(t == TruthLabel.POSITIVE and o == Outcome.DEFINITIVE_NEGATIVE for t, o in binary)
    positives = sum(t == TruthLabel.POSITIVE for t, _ in binary)
    negatives = len(binary) - positives
    nondef = len(binary) - tp - fp - tn - fn

    def ratio(x: int, y: int) -> float | None:
        return x / y if y else None

    return dict(
        TP=tp,
        FP=fp,
        TN=tn,
        FN=fn,
        precision=ratio(tp, tp + fp),
        recall=ratio(tp, tp + fn),
        F1=ratio(2 * tp, 2 * tp + fp + fn),
        specificity=ratio(tn, tn + fp),
        FPR=ratio(fp, tn + fp),
        FNR=ratio(fn, tp + fn),
        binary_eligible=len(binary),
        excluded_truth=len(rows) - len(binary),
        nondefinitive_binary=nondef,
        effective_correctness=ratio(tp + tn, len(binary)),
        unified_correctness=ratio(tp + tn, len(rows)),
        effective_positive_recovery=ratio(tp, positives),
        effective_negative_correctness=ratio(tn, negatives),
        definitive_coverage=ratio(tp + fp + tn + fn, len(binary)),
        unified_definitive_coverage=ratio(
            sum(o in {Outcome.DEFINITIVE_POSITIVE, Outcome.DEFINITIVE_NEGATIVE} for _, o in rows),
            len(rows),
        ),
        analysis_coverage=ratio(
            sum(o not in {Outcome.UNSUPPORTED, Outcome.FAILED} for _, o in rows), len(rows)
        ),
        applicability_coverage=ratio(
            sum(
                o not in {Outcome.UNSUPPORTED, Outcome.FAILED, Outcome.NOT_APPLICABLE}
                for _, o in rows
            ),
            len(rows),
        ),
        outcomes={o.value: sum(v == o for _, v in rows) for o in Outcome},
    )


def metric_protocol() -> dict[str, Any]:
    return dict(
        version=VERSION,
        P029_receipt_mapping={
            "SUPPORTED_PARTIAL_V2_SCOPE": (
                "PARTIAL; confirmed/supported findings can be definitive positive"
            ),
            "CONTRACT_ONLY": "UNSUPPORTED when not evaluated",
            "FAILED": "FAILED before unsupported partition",
            "applicable_rules": "finding-derived; never infer NOT_APPLICABLE/negative from absence",
            "no_findings": "PARTIAL for evaluated P029 V2; no P029 COMPLETE outcome exists",
        },
        truth_labels=list(TruthLabel),
        binary_eligible=["POSITIVE", "NEGATIVE"],
        status_mapping=dict(
            CONFIRMED_PATTERN="DEFINITIVE_POSITIVE",
            SUPPORTED="DEFINITIVE_POSITIVE",
            POTENTIAL="CANDIDATE_NONDEFINITIVE",
            INSUFFICIENT_EVIDENCE="NONDEFINITIVE",
            NOT_APPLICABLE="APPLICABILITY_NONDEFINITIVE",
        ),
        execution_mapping=(
            "FAILED/UNSUPPORTED override; supported finding remains positive "
            "despite partial traversal; no-finding PARTIAL is nondefinitive; "
            "no-finding COMPLETE and applicable is definitive negative"
        ),
        domain_binding=(
            "P027 SecurityFindingStatus; P029 "
            "analyzed/applicable/unsupported_rules, diagnostics and per-rule "
            "coverage/partial metadata. Implementation PARTIAL_V2 is capability, "
            "not an execution outcome."
        ),
        strict_confusion=(
            "TP/FP/TN/FN only definitive outcomes with POSITIVE/NEGATIVE truth. FN "
            "excludes abstention; report effective positive recovery and "
            "nondefinitive counts beside Recall."
        ),
        formulas=dict(
            precision="TP/(TP+FP)",
            recall="TP/(TP+FN)",
            F1="2TP/(2TP+FP+FN)",
            specificity="TN/(TN+FP)",
            FPR="FP/(TN+FP)",
            FNR="FN/(TP+FN)",
            effective_correctness="(TP+TN)/N_binary",
            unified_correctness="(TP+TN)/N_all",
            effective_positive_recovery="TP/N_human_positive",
            effective_negative_correctness="TN/N_human_negative",
        ),
        coverage=dict(
            definitive="definitive/N_binary and definitive/N_all",
            analysis="nonFAILED_nonUNSUPPORTED/N_all; partial counts as attempted",
            applicability="attempted_nonNOT_APPLICABLE/N_all; not a proof of applicability",
            truth="N_binary/N_all; UNCERTAIN/OOS separately",
        ),
        zero_denominator=None,
        primary_view="ALL_CASES_UNIFIED_WITH_COMPLETENESS_PENALTY",
        primary_binary_view="POSITIVE_NEGATIVE_ONLY_WITH_NONDEFINITIVE_REPORTED",
        supplemental_views=[
            "supported language-rule scope",
            "candidate-inclusive CONFIRMED_PATTERN+SUPPORTED+POTENTIAL",
        ],
        candidate_inclusive=(
            "Apply same formulas after mapping POTENTIAL to definitive positive; "
            "never replace strict primary view."
        ),
        strata=["split", "rule", "language", "rule-language"],
        aggregation=(
            "case micro pooled; macro per-rule over defined denominators with "
            "included stratum count; no DEV/FINAL pooling in final claims"
        ),
        unsupported_TS_SEC005=(
            "retain in unified view; exclude only in named supported-scope supplement"
        ),
        post_truth_remapping_allowed=False,
        results="NOT_EVALUATED",
    )


def human_protocol() -> dict[str, Any]:
    return dict(
        version=VERSION,
        slots=["A", "B"],
        cases_per_reviewer=300,
        labels={
            "POSITIVE": "sufficient source evidence supports frozen SEC finding",
            "NEGATIVE": "applicable scope and evidence supports absence of target finding",
            "UNCERTAIN": "insufficient evidence for reliable binary judgment",
            "OUT_OF_SCOPE": "cannot validly judge under frozen language/framework/rule scope",
        },
        independence=(
            "no discussion, response exchange or label/rationale sharing before "
            "both initial submissions lock"
        ),
        intake=(
            "exact frozen case set, independent A/B destination, completed flag; "
            "no PII or confidence required"
        ),
        adjudication=(
            "equal labels become truth including UNCERTAIN/OOS; conflicts require "
            "separate real human coordinator with case evidence and both locked "
            "rationales, preserving A/B/conflict/adjudicated label"
        ),
        prohibited=[
            "construction intent",
            "detector output",
            "support expectation",
            "other reviewer response before lock",
            "AI/LLM-generated label or adjudication",
        ],
        agreement=[
            "raw agreement",
            "Cohen kappa when defined",
            "conflict count",
            "per-reviewer label distribution",
            "adjudication count",
        ],
        agreement_caveat="artificial class construction limits kappa interpretation",
        truth_status="NOT_YET_AVAILABLE",
        reviewer_responses=0,
        adjudications=0,
        AI_labels_permitted=False,
        pii_required=False,
    )
