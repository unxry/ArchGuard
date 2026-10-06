"""Post-freeze comparison of context flags and pinned ranges only; no semantic comparison."""

from pathlib import Path

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import Sealed, Slug, digest, seal
from archguard.benchmark.oss.review import PinnedEvidence
from archguard.core.model.base import DomainModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_assistance_b import verify_b_freeze
from archguard.infrastructure.oss_benchmark import write_new
from archguard.infrastructure.oss_review import atomic_directory


class ContextPair(DomainModel):
    case_id: Slug
    a_extra_context_recommended: bool
    b_extra_context_recommended: bool
    a_requested_ranges: tuple[PinnedEvidence, ...]
    b_requested_ranges: tuple[PinnedEvidence, ...]


class ContextConsensus(Sealed):
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    a_assistance_fingerprint: Digest
    b_assistance_fingerprint: Digest
    b_freeze_fingerprint: Digest
    both_need_context: tuple[Slug, ...]
    a_only: tuple[Slug, ...]
    b_only: tuple[Slug, ...]
    neither: tuple[Slug, ...]
    cases: tuple[ContextPair, ...]


def compare_context(a_assistance: Path, b_directory: Path) -> ContextConsensus:
    # No access to A occurs until the B receipt and all frozen files have been verified.
    b, receipt = verify_b_freeze(b_directory)
    raw = _read(a_assistance, 8388608)
    if not isinstance(raw, dict) or raw.get("fingerprint") != digest(
        {k: v for k, v in raw.items() if k != "fingerprint"}
    ):
        raise ValueError("A assistance must be sealed before context comparison")
    if (
        raw.get("sample_fingerprint") != b.sample_fingerprint
        or raw.get("catalog_fingerprint") != b.catalog_fingerprint
    ):
        raise ValueError("context comparison requires identical sample/catalog")
    # Only the permitted projection is retained. Summary, rationale and reason text is never used.
    a_projection = {}
    for case in raw["cases"]:
        identifier = case["case_id"]
        if identifier in a_projection:
            raise ValueError("duplicate A case in context comparison")
        ranges = tuple(
            PinnedEvidence.model_validate(request["evidence"])
            for request in case["extra_context_recommended"]
        )
        a_projection[identifier] = ranges
    if set(a_projection) != {c.case_id for c in b.cases}:
        raise ValueError("context comparison requires identical frozen case IDs")
    pairs = tuple(
        ContextPair(
            case_id=c.case_id,
            a_extra_context_recommended=bool(a_projection[c.case_id]),
            b_extra_context_recommended=bool(c.extra_context_recommended),
            a_requested_ranges=a_projection[c.case_id],
            b_requested_ranges=tuple(r.evidence for r in c.extra_context_recommended),
        )
        for c in b.cases
    )
    return seal(
        ContextConsensus,
        sample_fingerprint=b.sample_fingerprint,
        catalog_fingerprint=b.catalog_fingerprint,
        a_assistance_fingerprint=raw["fingerprint"],
        b_assistance_fingerprint=b.fingerprint,
        b_freeze_fingerprint=receipt.fingerprint,
        both_need_context=tuple(
            p.case_id
            for p in pairs
            if p.a_extra_context_recommended and p.b_extra_context_recommended
        ),
        a_only=tuple(
            p.case_id
            for p in pairs
            if p.a_extra_context_recommended and not p.b_extra_context_recommended
        ),
        b_only=tuple(
            p.case_id
            for p in pairs
            if not p.a_extra_context_recommended and p.b_extra_context_recommended
        ),
        neither=tuple(
            p.case_id
            for p in pairs
            if not p.a_extra_context_recommended and not p.b_extra_context_recommended
        ),
        cases=pairs,
    )


def publish_context_comparison(report: ContextConsensus, destination: Path) -> None:
    def build(stage: Path) -> None:
        write_new(stage / "context-consensus.json", report)
        lines = [
            "# Post-freeze context sufficiency",
            "",
            "Only case IDs, context flags and pinned range requests were compared. "
            "These are source-navigation passes; no human responses were read.",
            "",
            f"Sample: {report.sample_fingerprint}",
            "",
            f"B freeze: {report.b_freeze_fingerprint}",
            "",
            "| Group | Cases |",
            "| --- | --- |",
            f"| Both need context | {len(report.both_need_context)} |",
            f"| A only | {len(report.a_only)} |",
            f"| B only | {len(report.b_only)} |",
            f"| Neither | {len(report.neither)} |",
            f"| Union | "
            f"{len(report.both_need_context) + len(report.a_only) + len(report.b_only)} |",
            "",
            "| Case | A requests context | B requests context | A ranges | B ranges |",
            "| --- | --- | --- | --- | --- |",
        ]
        for pair in report.cases:

            def ranges(references: tuple[PinnedEvidence, ...]) -> str:
                return (
                    "; ".join(
                        f"{r.repository_id}@{r.commit_sha} "
                        f"{r.path}:{r.start_line}-{r.end_line} {r.purpose}"
                        for r in references
                    )
                    or "None"
                )

            lines.append(
                f"| {pair.case_id} | {pair.a_extra_context_recommended} | "
                f"{pair.b_extra_context_recommended} | {ranges(pair.a_requested_ranges)} | "
                f"{ranges(pair.b_requested_ranges)} |"
            )
        (stage / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    atomic_directory(destination, build)
