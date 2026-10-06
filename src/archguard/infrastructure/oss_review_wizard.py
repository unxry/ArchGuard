"""Interactive human input into local drafts; explicit export, never canonical import."""

import hashlib
import os
from collections.abc import Callable
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

from archguard.benchmark.models import Digest
from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.oss.review import ReviewInput
from archguard.core.model.base import DomainModel
from archguard.infrastructure.hybrid_configuration import _read
from archguard.infrastructure.oss_assistance import AssistanceCase, AssistancePackage, render_case
from archguard.infrastructure.oss_benchmark import write_new


class ReviewDraft(DomainModel):
    schema_version: Literal["oss-local-human-draft-v1"] = "oss-local-human-draft-v1"
    sample_fingerprint: Digest
    catalog_fingerprint: Digest
    assistance_fingerprint: Digest
    bundle_fingerprint: Digest
    reviews: tuple[ReviewInput, ...] = ()


def bundle_fingerprint(bundle: Path, package: AssistancePackage) -> str:
    raw = _read(bundle / "bundle-manifest.json", 2097152)
    if not isinstance(raw, dict):
        raise ValueError("bundle manifest must be an object")
    payload = {k: v for k, v in raw.items() if k != "fingerprint"}
    if (
        raw.get("fingerprint") != digest(payload)
        or raw.get("sample_fingerprint") != package.sample_fingerprint
        or raw.get("catalog_fingerprint") != package.catalog_fingerprint
        or raw.get("slot") not in {"a", "b"}
    ):
        raise ValueError("bundle fingerprint/context mismatch")
    files = raw.get("files")
    if not isinstance(files, list) or raw.get("content_fingerprint") != digest(files):
        raise ValueError("bundle content manifest mismatch")
    for name, expected in files:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("bundle file path must be local")
        path = bundle / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("bundle file fingerprint mismatch")
    return str(raw["fingerprint"])


def _validate_draft(draft: ReviewDraft, package: AssistancePackage, fingerprint: str) -> None:
    if (
        draft.sample_fingerprint != package.sample_fingerprint
        or draft.catalog_fingerprint != package.catalog_fingerprint
        or draft.assistance_fingerprint != package.fingerprint
        or draft.bundle_fingerprint != fingerprint
    ):
        raise ValueError("draft bundle/sample/assistance mismatch")
    cases = {c.case_id: c for c in package.cases}
    seen: set[str] = set()
    identities: set[str] = set()
    for row in draft.reviews:
        case = cases.get(row.annotation_case_id)
        if (
            case is None
            or row.annotation_case_id in seen
            or (
                row.packet_fingerprint != case.packet_fingerprint
                or row.packet_revision != case.packet_revision
                or row.supersedes_review_id is not None
                or len(set(row.evidence)) != len(row.evidence)
            )
        ):
            raise ValueError("draft case/packet mismatch or duplicate")
        available = tuple(e.reference() for e in case.assistant_evidence_candidates)
        if any(e not in available for e in row.evidence):
            raise ValueError("draft evidence was not manually selected from this assistance")
        identities.add(row.reviewer_id)
        seen.add(row.annotation_case_id)
    if len(identities) > 1:
        raise ValueError("one independent human identity per draft")


def load_draft(path: Path, package: AssistancePackage, fingerprint: str) -> ReviewDraft:
    if path.is_symlink():
        raise ValueError("draft symlinks forbidden")
    draft = (
        ReviewDraft.model_validate(_read(path, 8388608))
        if path.exists()
        else ReviewDraft(
            sample_fingerprint=package.sample_fingerprint,
            catalog_fingerprint=package.catalog_fingerprint,
            assistance_fingerprint=package.fingerprint,
            bundle_fingerprint=fingerprint,
        )
    )
    _validate_draft(draft, package, fingerprint)
    return draft


def _save(path: Path, draft: ReviewDraft) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(canonical(draft) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def _human_row(
    case: AssistanceCase, ask: Callable[[str], str], tell: Callable[[str], None]
) -> ReviewInput | None:
    choices = {"P": "POSITIVE", "N": "NEGATIVE", "U": "UNCERTAIN", "O": "OUT_OF_SCOPE"}
    while True:
        choice = (
            ask(
                "Choose [P] Positive [N] Negative [U] Uncertain "
                "[O] Out of scope [S] Skip [Q] Quit: "
            )
            .strip()
            .upper()
        )
        if choice == "Q":
            raise EOFError
        if choice == "S":
            return None
        if choice not in choices:
            tell("Enter an explicit choice; no default is selected.")
            continue
        reviewer = ask("Reviewer ID (stable pseudonym): ").strip()
        rationale = ask("Your rationale: ").strip()
        uncertainty = ask("Uncertainty [C] Clear [A] Ambiguous: ").strip().upper()
        selection = ask(
            "Evidence numbers, comma-separated (select after reading; blank selects none): "
        ).strip()
        try:
            indexes = [] if not selection else [int(s.strip()) - 1 for s in selection.split(",")]
            if len(set(indexes)) != len(indexes) or any(
                i < 0 or i >= len(case.assistant_evidence_candidates) for i in indexes
            ):
                raise ValueError("invalid evidence selection")
            if uncertainty not in {"C", "A"}:
                raise ValueError("explicit uncertainty required")
            fields: dict[str, Any] = {
                "annotation_case_id": case.case_id,
                "packet_fingerprint": case.packet_fingerprint,
                "packet_revision": case.packet_revision,
                "reviewer_id": reviewer,
                "label": choices[choice],
                "rationale": rationale,
                "evidence": tuple(
                    case.assistant_evidence_candidates[i].reference() for i in indexes
                ),
                "uncertainty": "CLEAR" if uncertainty == "C" else "AMBIGUOUS",
            }
            if (
                ask(
                    "Confirm you personally reviewed this case and selected its evidence [yes/no]: "
                )
                .strip()
                .lower()
                != "yes"
            ):
                tell("No confirmed decision saved.")
                return None
            return ReviewInput.model_validate(fields | {"attestation": "HUMAN_REVIEW_COMPLETED"})
        except ValueError as error:
            tell(f"Invalid review: {error}")


def wizard(
    package: AssistancePackage,
    bundle: Path,
    draft_path: Path,
    *,
    ask: Callable[[str], str] = input,
    tell: Callable[[str], None] = print,
) -> ReviewDraft:
    if draft_path.resolve().is_relative_to(bundle.resolve()):
        raise ValueError("draft must be outside the original bundle")
    fingerprint = bundle_fingerprint(bundle, package)
    draft = load_draft(draft_path, package, fingerprint)
    done = {r.annotation_case_id for r in draft.reviews}
    try:
        for i, case in enumerate(package.cases, 1):
            if case.case_id in done:
                continue
            tell(f"Case {i}/{len(package.cases)} · {case.rule} · {case.subject}\n")
            tell(render_case(case))
            row = _human_row(case, ask, tell)
            if row is not None:
                updated = draft.model_copy(update={"reviews": draft.reviews + (row,)})
                try:
                    _validate_draft(updated, package, fingerprint)
                except ValueError as error:
                    tell(f"Invalid draft: {error}. Case remains unreviewed.")
                    continue
                _save(draft_path, updated)
                draft = updated
                tell(
                    "Confirmed human input saved to local draft; canonical import remains separate."
                )
    except (EOFError, KeyboardInterrupt):
        tell("Session ended; confirmed draft rows are preserved.")
    return draft


def export_draft(package: AssistancePackage, bundle: Path, draft_path: Path, output: Path) -> int:
    if output.resolve().is_relative_to(bundle.resolve()):
        raise ValueError("export must be outside the original bundle")
    if not draft_path.is_file():
        raise ValueError("explicit export requires an existing draft")
    draft = load_draft(draft_path, package, bundle_fingerprint(bundle, package))
    if not draft.reviews:
        raise ValueError("no confirmed human decisions to export")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_new(
        output,
        {
            "sample_fingerprint": draft.sample_fingerprint,
            "reviews": draft.reviews,
            "adjudications": [],
        },
    )
    return len(draft.reviews)
