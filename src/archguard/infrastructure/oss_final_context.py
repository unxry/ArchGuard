"""Common pinned context freeze and independent preparation; no human decisions."""

import hashlib
import re
from pathlib import Path
from typing import Literal

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import AnnotationSample, Sealed, Slug, digest, seal
from archguard.benchmark.oss.review import (
    PacketRevision,
    PinnedEvidence,
    RevisionCatalog,
    original_evidence,
    validate_catalog,
)
from archguard.core.model.base import DomainModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_assistance import (
    AssistancePackage,
    _facts,
    build_assistance,
    masked_source,
    publish_assistance,
)
from archguard.infrastructure.oss_assistance_b import (
    build_b_assistance,
    publish_b_assistance,
    verify_b_freeze,
)
from archguard.infrastructure.oss_benchmark import FrozenOSSCorpus, write_new
from archguard.infrastructure.oss_context_comparison import ContextConsensus
from archguard.infrastructure.oss_review import (
    atomic_directory,
    prepare_bundles,
    render_packet,
    validate_context,
    verify_evidence,
)
from archguard.infrastructure.oss_review_wizard import bundle_fingerprint


class RevisionMapping(DomainModel):
    case_id: Slug
    previous_revision: int
    previous_fingerprint: Digest
    active_revision: int
    active_fingerprint: Digest
    supplements: tuple[PinnedEvidence, ...]


class FinalContextFreeze(Sealed):
    schema_version: Literal["oss-final-context-freeze-v1"] = "oss-final-context-freeze-v1"
    sample_fingerprint: Digest
    base_catalog_fingerprint: Digest
    final_catalog_fingerprint: Digest
    consensus_fingerprint: Digest
    audited_requests: int
    supplemented_cases: int
    unchanged_cases: int
    mapping: tuple[RevisionMapping, ...]


class CaseContextAudit(DomainModel):
    case_id: Slug
    active_revision: int
    packet_fingerprint: Digest
    state: Literal["SUFFICIENT", "LIMITED", "UNRESOLVED"]
    reasons: tuple[str, ...]
    ranges: tuple[PinnedEvidence, ...]
    files: int
    lines_shown: int
    context_bytes: int
    implementation_visible: bool
    subject_role_documented: bool
    subject_placement_documented: bool


class FinalContextAudit(Sealed):
    schema_version: Literal["oss-final-context-audit-v1"] = "oss-final-context-audit-v1"
    method: Literal["conservative-lexical-coverage-v1"] = "conservative-lexical-coverage-v1"
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    cases: tuple[CaseContextAudit, ...]


class HumanReviewReady(Sealed):
    schema_version: Literal["oss-human-review-ready-v1"] = "oss-human-review-ready-v1"
    status: Literal["READY_FOR_HUMAN_REVIEW"] = "READY_FOR_HUMAN_REVIEW"
    completed_annotation_freeze: Literal[False] = False
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    context_freeze_fingerprint: Digest
    context_audit_fingerprint: Digest
    a_assistance_fingerprint: Digest
    a_assistance_content_fingerprint: Digest
    b_assistance_fingerprint: Digest
    b_assistance_freeze_fingerprint: Digest
    a_bundle_fingerprint: Digest
    b_bundle_fingerprint: Digest
    common_content_fingerprint: Digest
    cases: int
    ready_packets: int
    human_reviews: Literal[0] = 0
    reviewer_ids: Literal[0] = 0
    prefilled_labels: Literal[0] = 0
    completed_attestations: Literal[0] = 0
    binary_eligible: Literal[0] = 0
    kappa: None = None


def freeze_context(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    consensus: ContextConsensus,
) -> tuple[RevisionCatalog, FinalContextFreeze]:
    validate_context(bound, sample, cache, catalog)
    identifiers = tuple(p.annotation_case_id for p in sample.packets)
    if (
        consensus.sample_fingerprint != sample.fingerprint
        or consensus.catalog_fingerprint != catalog.fingerprint
        or tuple(p.case_id for p in consensus.cases) != identifiers
    ):
        raise ValueError("supplemental consensus requires the frozen base sample/catalog/order")
    groups: list[list[str]] = [[], [], [], []]
    latest = {p.annotation_case_id: p for p in catalog.packets}
    updates, mapping = [], []
    budget = bound.protocol.sampling
    for packet, pair in zip(sample.packets, consensus.cases, strict=True):
        a, b = bool(pair.a_requested_ranges), bool(pair.b_requested_ranges)
        if a != pair.a_extra_context_recommended or b != pair.b_extra_context_recommended:
            raise ValueError("context flags do not match pinned requests")
        groups[0 if a and b else 1 if a else 2 if b else 3].append(pair.case_id)
        previous = latest[pair.case_id]
        existing = original_evidence(packet, previous) + previous.additional_evidence
        requests = tuple(dict.fromkeys((*pair.a_requested_ranges, *pair.b_requested_ranges)))
        for ref in requests:
            if ref.repository_id != previous.repository_id or ref.commit_sha != previous.commit_sha:
                raise ValueError("supplement repository/commit differs from frozen case")
            verify_evidence(bound, cache, ref)
            if any(
                r.path == ref.path and r.start_line <= ref.start_line and r.end_line >= ref.end_line
                for r in existing
            ):
                raise ValueError("supplement is already covered by the base packet")
            if ref.end_line - ref.start_line + 1 > budget.max_excerpt_lines:
                raise ValueError("supplement exceeds range budget; request a smaller pinned range")
        active = previous
        if requests:
            active = seal(
                PacketRevision,
                **(
                    previous.model_dump(exclude={"fingerprint"})
                    | {
                        "revision": previous.revision + 1,
                        "previous_packet_fingerprint": previous.fingerprint,
                        "additional_evidence": previous.additional_evidence + requests,
                    }
                ),
            )
            refs = original_evidence(packet, active) + active.additional_evidence
            _, quality = render_packet(bound, sample, cache, active)
            if (
                len({r.path for r in refs}) > budget.max_context_files
                or sum(r.end_line - r.start_line + 1 for r in refs)
                > budget.max_context_files * budget.max_excerpt_lines
                or quality["context_bytes"] > budget.max_context_bytes
            ):
                raise ValueError(
                    "supplement exceeds packet context budget; no truncation performed"
                )
            updates.append(active)
        mapping.append(
            RevisionMapping(
                case_id=pair.case_id,
                previous_revision=previous.revision,
                previous_fingerprint=previous.fingerprint,
                active_revision=active.revision,
                active_fingerprint=active.fingerprint,
                supplements=requests,
            )
        )
    if tuple(map(tuple, groups)) != (
        consensus.both_need_context,
        consensus.a_only,
        consensus.b_only,
        consensus.neither,
    ):
        raise ValueError("context consensus groups mismatch")
    final = seal(
        RevisionCatalog,
        sample_fingerprint=sample.fingerprint,
        packets=catalog.packets + tuple(updates),
    )
    validate_catalog(sample, final)
    receipt = seal(
        FinalContextFreeze,
        sample_fingerprint=sample.fingerprint,
        base_catalog_fingerprint=catalog.fingerprint,
        final_catalog_fingerprint=final.fingerprint,
        consensus_fingerprint=consensus.fingerprint,
        audited_requests=sum(len(m.supplements) for m in mapping),
        supplemented_cases=len(updates),
        unchanged_cases=len(sample.packets) - len(updates),
        mapping=tuple(mapping),
    )
    return final, receipt


def _body_visible(lines: list[str], start: int, end: int, covered: set[int]) -> bool:
    masked = masked_source(lines).splitlines()
    opening = next((i for i in range(start - 1, end) if "{" in masked[i]), None)
    if opening is None:
        return False
    balance, seen = 0, False
    for i in range(opening, len(masked)):
        for char in masked[i]:
            if char == "{":
                balance += 1
                seen = True
            elif char == "}":
                balance -= 1
                if seen and balance == 0:
                    return set(range(start, i + 2)) <= covered
    return False


def audit_context(
    bound: FrozenOSSCorpus, sample: AnnotationSample, cache: Path, catalog: RevisionCatalog
) -> FinalContextAudit:
    validate_context(bound, sample, cache, catalog)
    latest = {r.annotation_case_id: r for r in catalog.packets}
    cases = []
    for packet in sample.packets:
        revision = latest[packet.annotation_case_id]
        refs = original_evidence(packet, revision) + revision.additional_evidence
        primary = next(r for r in refs if r.purpose == "SOURCE" and r.path == packet.subject.path)
        lines = verify_evidence(bound, cache, primary)
        covered = {
            i
            for r in refs
            if r.path == primary.path and r.purpose == "SOURCE"
            for i in range(r.start_line, r.end_line + 1)
        }
        implemented = _body_visible(lines, primary.start_line, primary.end_line, covered)
        name = packet.subject.qualified_name.rsplit("::", 1)[-1].split("(", 1)[0].rsplit(".", 1)[-1]
        if not implemented:
            for fact in _facts(lines):
                if (
                    fact.type == "declaration_signature"
                    and fact.name == name
                    and fact.line > primary.end_line
                ):
                    implemented = _body_visible(
                        lines, fact.line, min(fact.line + 39, len(lines)), covered
                    )
                    break
        # Only visible documentation/comments naming this subject count. Project-wide README
        # language and directory names cannot establish this subject's intended architecture.
        role, placement = False, False
        for ref in refs:
            text_lines = verify_evidence(bound, cache, ref)[ref.start_line - 1 : ref.end_line]
            for i, line in enumerate(text_lines):
                if ref.purpose != "DOCUMENTATION" and not re.match(r"\s*(/\*|\*|//)", line):
                    continue
                if not re.search(r"\b" + re.escape(name) + r"\b", line):
                    continue
                paragraph = " ".join(text_lines[max(0, i - 2) : i + 3])
                role |= bool(
                    re.search(
                        r"responsib|provides|implements|manages|handles|controller|service|adapter|repository",
                        paragraph,
                        re.I,
                    )
                )
                placement |= bool(
                    re.search(r"layer|belongs|package|module|directory|located", paragraph, re.I)
                )
        reasons = []
        if not implemented:
            reasons.append(
                "A complete balanced implementation body is not visible; "
                "lexical coverage cannot establish behavior."
            )
        if not role:
            reasons.append(
                "Visible subject-specific documentation does not establish intended role; "
                "names and project-wide descriptions are insufficient."
            )
        if packet.rule_id == "ARCH204" and not placement:
            reasons.append(
                "No subject-specific documented placement; directory names alone are weak evidence."
            )
        if packet.rule_id == "ARCH203":
            reasons.append(
                "Concrete versus abstract responsibility and dependency ownership "
                "still require human interpretation."
            )
        if packet.rule_id == "ARCH205":
            reasons.append(
                "Substantive responsibilities require human interpretation; "
                "import count cannot establish them."
            )
        state: Literal["SUFFICIENT", "LIMITED", "UNRESOLVED"] = (
            "UNRESOLVED" if not implemented else "LIMITED" if reasons else "SUFFICIENT"
        )
        _, quality = render_packet(bound, sample, cache, revision)
        cases.append(
            CaseContextAudit(
                case_id=packet.annotation_case_id,
                active_revision=revision.revision,
                packet_fingerprint=revision.fingerprint,
                state=state,
                reasons=tuple(reasons)
                or (
                    "Complete lexical body coverage and visible subject-specific "
                    "role documentation; "
                    "this is not a human architectural judgment.",
                ),
                ranges=refs,
                files=len({r.path for r in refs}),
                lines_shown=sum(r.end_line - r.start_line + 1 for r in refs),
                context_bytes=quality["context_bytes"],
                implementation_visible=implemented,
                subject_role_documented=role,
                subject_placement_documented=placement,
            )
        )
    return seal(
        FinalContextAudit,
        sample_fingerprint=sample.fingerprint,
        catalog_fingerprint=catalog.fingerprint,
        cases=tuple(cases),
    )


def prepare_final_context(
    bound: FrozenOSSCorpus,
    sample: AnnotationSample,
    cache: Path,
    catalog: RevisionCatalog,
    consensus: ContextConsensus,
    destination: Path,
) -> HumanReviewReady:
    final, context_freeze = freeze_context(bound, sample, cache, catalog, consensus)
    audit = audit_context(bound, sample, cache, final)
    receipts = []

    def build(stage: Path) -> None:
        # This source-free catalog/receipt is frozen before either independent source pass.
        write_new(stage / "packet-revisions.json", final)
        write_new(stage / "final-context-freeze.json", context_freeze)
        write_new(stage / "final-context-audit.json", audit)
        a = build_assistance(bound, sample, cache, final)
        publish_assistance(a, stage / "assistance-a")
        a_content = digest(
            tuple(
                (p.name, hashlib.sha256(p.read_bytes()).hexdigest())
                for p in sorted((stage / "assistance-a").iterdir())
            )
        )
        b = build_b_assistance(bound, sample, cache, final)
        b_freeze = publish_b_assistance(b, stage / "assistance-b")
        manifests = prepare_bundles(bound, sample, cache, final, stage / "bundles")
        for slot in ("a", "b"):
            (stage / "bundles" / ("reviewer-" + slot)).rename(stage / ("reviewer-" + slot))
        (stage / "bundles" / "packet-revisions.json").unlink()
        (stage / "bundles").rmdir()
        receipt = seal(
            HumanReviewReady,
            sample_fingerprint=sample.fingerprint,
            catalog_fingerprint=final.fingerprint,
            context_freeze_fingerprint=context_freeze.fingerprint,
            context_audit_fingerprint=audit.fingerprint,
            a_assistance_fingerprint=a.fingerprint,
            a_assistance_content_fingerprint=a_content,
            b_assistance_fingerprint=b.fingerprint,
            b_assistance_freeze_fingerprint=b_freeze.fingerprint,
            a_bundle_fingerprint=manifests["a"]["fingerprint"],
            b_bundle_fingerprint=manifests["b"]["fingerprint"],
            common_content_fingerprint=manifests["a"]["content_fingerprint"],
            cases=len(sample.packets),
            ready_packets=len(sample.packets),
        )
        write_new(stage / "human-review-ready.json", receipt)
        verify_ready(stage, sample, final)
        receipts.append(receipt)

    atomic_directory(destination, build)
    return receipts[0]


def verify_ready(
    destination: Path, sample: AnnotationSample, catalog: RevisionCatalog
) -> HumanReviewReady:
    receipt = HumanReviewReady.model_validate(
        _read(destination / "human-review-ready.json", 2097152)
    )
    frozen = FinalContextFreeze.model_validate(
        _read(destination / "final-context-freeze.json", 2097152)
    )
    audit = FinalContextAudit.model_validate(
        _read(destination / "final-context-audit.json", 2097152)
    )
    stored = RevisionCatalog.model_validate(_read(destination / "packet-revisions.json", 2097152))
    a = AssistancePackage.model_validate(
        _read(destination / "assistance-a/assistance.json", 8388608)
    )
    b, b_freeze = verify_b_freeze(destination / "assistance-b")
    latest = {p.annotation_case_id: p for p in catalog.packets}
    identities = tuple(
        (
            p.annotation_case_id,
            latest[p.annotation_case_id].revision,
            latest[p.annotation_case_id].fingerprint,
        )
        for p in sample.packets
    )
    if (
        stored != catalog
        or receipt.sample_fingerprint != sample.fingerprint
        or receipt.catalog_fingerprint != catalog.fingerprint
        or frozen.sample_fingerprint != sample.fingerprint
        or frozen.final_catalog_fingerprint != catalog.fingerprint
        or receipt.context_freeze_fingerprint != frozen.fingerprint
        or receipt.context_audit_fingerprint != audit.fingerprint
        or audit.catalog_fingerprint != catalog.fingerprint
        or audit.sample_fingerprint != sample.fingerprint
        or tuple((c.case_id, c.active_revision, c.packet_fingerprint) for c in audit.cases)
        != identities
        or tuple((m.case_id, m.active_revision, m.active_fingerprint) for m in frozen.mapping)
        != identities
        or receipt.a_assistance_fingerprint != a.fingerprint
        or receipt.b_assistance_fingerprint != b.fingerprint
        or receipt.b_assistance_freeze_fingerprint != b_freeze.fingerprint
        or receipt.cases != len(identities)
        or receipt.ready_packets != len(identities)
    ):
        raise ValueError("human review ready context binding mismatch")
    for slot, package, expected in (
        ("a", a, receipt.a_bundle_fingerprint),
        ("b", b, receipt.b_bundle_fingerprint),
    ):
        if (
            package.sample_fingerprint != sample.fingerprint
            or package.catalog_fingerprint != catalog.fingerprint
            or tuple((c.case_id, c.packet_revision, c.packet_fingerprint) for c in package.cases)
            != identities
        ):
            raise ValueError("final assistance active revisions mismatch")
        bundle = destination / ("reviewer-" + slot)
        if bundle_fingerprint(bundle, package) != expected:
            raise ValueError("human review ready bundle mismatch")
        manifest = _read(bundle / "bundle-manifest.json", 2097152)
        if (
            not isinstance(manifest, dict)
            or manifest["content_fingerprint"] != receipt.common_content_fingerprint
        ):
            raise ValueError("common final bundle content mismatch")
    # Bind the complete A navigation package too, without making it a B input.
    a_files = tuple(
        (p.name, hashlib.sha256(p.read_bytes()).hexdigest())
        for p in sorted((destination / "assistance-a").iterdir())
        if p.is_file()
    )
    expected_names = {"assistance.json", "index.md", "ANNOTATION_CHEATSHEET.md"} | {
        c.case_id + ".md" for c in a.cases
    }
    if (
        set(n for n, _ in a_files) != expected_names
        or digest(a_files) != receipt.a_assistance_content_fingerprint
    ):
        raise ValueError("A assistance changed after final preparation")
    return receipt
