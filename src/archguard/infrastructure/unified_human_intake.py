"""P021.B.1 raw return staging, independent human freezes and category-only agreement."""

import hashlib
import json
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_agreement import (
    BINARY,
    CATEGORIES,
    CaseAlignment,
    PairedDecision,
    align_decisions,
    analyze_agreement,
)
from archguard.infrastructure import unified_human_review as review
from archguard.infrastructure.oss_review import atomic_directory

INTAKE = review.PRIVATE / "human-intake"
INCOMING = INTAKE / "incoming"
ACCEPTED = INTAKE / "accepted"
RESULTS = INTAKE / "agreement-v1"
COORDINATOR = review.PRIVATE / "coordinator/review-map"
SOURCE_FILES = (
    "src/archguard/infrastructure/unified_human_intake.py",
    "scripts/prompt021b_human_intake.py",
    "tests/benchmark/test_unified_human_intake.py",
)
PUBLIC_FILES = (
    *SOURCE_FILES,
    "docs/verification/PROMPT_021_B.md",
    (review.BASE / "p021-b-human-agreement-v1.json").as_posix(),
    (review.BASE / "p021-b-verification-v1.json").as_posix(),
)
P021_A = "e82de9d0efc8e7e4dda444626aae86ce7f851628"


def raw_sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def intake_capability(repository: Path) -> Iterator[None]:
    """No construction, method prediction or credential inputs to this process."""
    token = review._CAPABILITY.set(
        (
            (repository / review.PRIVATE).resolve(),
            tuple((repository / p).resolve() for p in (*review.PINS, review.REVIEW, COORDINATOR)),
            ((repository / review.HANDOFF).resolve(), (repository / INTAKE).resolve()),
        )
    )
    try:
        yield
    finally:
        review._CAPABILITY.reset(token)


def handoff_expected(authority: review.Authority, role: review.Role) -> tuple[Path, dict[str, str]]:
    repository = authority.repository
    ready = review.read_seal(repository / review.BASE / "p021-a-handoff-readiness-v1.json")
    original = review.read_seal(repository / review.BASE / "p021-a-verification-v1.json")
    if original["readiness_fingerprint"] != ready["fingerprint"]:
        raise review.ReviewBlocked("P021_B_1_BLOCKED_AUTHORITATIVE_HANDOFF_DRIFT")
    folder = repository / review.HANDOFF / f"reviewer-{role.lower()}"
    receipt = review.read_seal(
        folder / "handoff-receipt.json", ready["handoffs"][role]["receipt_fingerprint"]
    )
    expected = receipt["files"] | {
        "handoff-receipt.json": review.sha(folder / "handoff-receipt.json")
    }
    for name, h in expected.items():
        path = folder / name
        if not path.is_file() or review.sha(path) != h:
            raise review.ReviewBlocked("P021_B_1_BLOCKED_AUTHORITATIVE_HANDOFF_DRIFT")
    actual = {p.relative_to(folder).as_posix() for p in folder.rglob("*")}
    if actual - set(expected) - {"completed-response.json", ".DS_Store"}:
        raise review.ReviewBlocked("P021_B_1_BLOCKED_UNEXPECTED_ENTRY")
    if any(p.is_symlink() or not p.is_file() for p in folder.rglob("*")):
        raise review.ReviewBlocked("P021_B_1_BLOCKED_UNEXPECTED_ENTRY")
    return folder, expected


def verify_incoming(repository: Path, role: review.Role) -> tuple[bytes, dict[str, Any]]:
    folder = repository / INCOMING / role
    receipt = review.read_seal(folder / "staging-receipt.json")
    if (
        receipt["role"] != role
        or receipt["scientifically_accepted"] is not False
        or receipt["decisions_parsed"] is not False
        or receipt["copy_verification"] != "PASS"
        or receipt["source_removal_authorization"] != "SAFE_AFTER_COPY_VERIFY"
        or receipt["source_path"]
        != (review.HANDOFF / f"reviewer-{role.lower()}" / "completed-response.json").as_posix()
        or receipt["staged_path"] != (INCOMING / role / "completed-response.json").as_posix()
    ):
        raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
    expected = {
        "completed-response.json": receipt["raw_sha256"],
        "staging-receipt.json": review.sha(folder / "staging-receipt.json"),
    }
    review.verify_files(folder, expected)
    raw = (folder / "completed-response.json").read_bytes()
    if len(raw) != receipt["byte_size"] or raw_sha(raw) != receipt["raw_sha256"]:
        raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
    binding_path = repository / INTAKE / "incoming-source-binding.json"
    if binding_path.exists():
        binding = review.read_seal(binding_path)
        if binding["roles"][role] != dict(
            path=receipt["staged_path"],
            raw_sha256=receipt["raw_sha256"],
            staging_receipt_fingerprint=receipt["fingerprint"],
        ):
            raise review.ReviewBlocked("P021_B_INCOMING_SOURCE_BINDING_DRIFT")
    return raw, receipt


def stage_returns(authority: review.Authority) -> dict[str, Any]:
    """COPY + raw SHA + frozen receipt before any unlink or human JSON parse."""
    repository = authority.repository
    expected = {role: handoff_expected(authority, role) for role in review.ROLES}
    staging: dict[str, dict[str, Any]] = {}
    # Both raw snapshots and receipts must exist before either handoff is cleaned.
    for role in review.ROLES:
        source = expected[role][0] / "completed-response.json"
        destination = repository / INCOMING / role
        review._safe_path(source)
        if destination.exists():
            raw, receipt = verify_incoming(repository, role)
            if source.exists() and source.read_bytes() != raw:
                raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
        else:
            if not source.is_file():
                raise review.ReviewBlocked("P021_B_1_RETURN_MISSING")
            raw = source.read_bytes()
            h = raw_sha(raw)

            def build(
                stage: Path,
                *,
                raw: bytes = raw,
                h: str = h,
                role: review.Role = role,
                source_name: str = source.name,
            ) -> None:
                stage.chmod(0o700)
                target = stage / "completed-response.json"
                with target.open("xb") as stream:
                    stream.write(raw)
                target.chmod(0o600)
                if target.read_bytes() != raw or review.sha(target) != h:
                    raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
                review.append_seal(
                    stage / "staging-receipt.json",
                    dict(
                        version="p021-b-1-raw-staging-v1",
                        role=role,
                        source_path=(
                            review.HANDOFF / f"reviewer-{role.lower()}" / source_name
                        ).as_posix(),
                        staged_path=(INCOMING / role / source_name).as_posix(),
                        raw_sha256=h,
                        byte_size=len(raw),
                        staged_at=datetime.now(UTC).isoformat(),
                        copy_verification="PASS",
                        scientifically_accepted=False,
                        decisions_parsed=False,
                        source_removal_authorization="SAFE_AFTER_COPY_VERIFY",
                    ),
                )

            atomic_directory(destination, build)
            _, receipt = verify_incoming(repository, role)
            if source.read_bytes() != raw:
                raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
        staging[role] = receipt
    binding_path = repository / INTAKE / "incoming-source-binding.json"
    binding = dict(
        version="p021-b-1-incoming-source-binding-v1",
        roles={
            r: dict(
                path=staging[r]["staged_path"],
                raw_sha256=staging[r]["raw_sha256"],
                staging_receipt_fingerprint=staging[r]["fingerprint"],
            )
            for r in review.ROLES
        },
        decisions_parsed=False,
        handoff_response_paths_for_intake=False,
    )
    freeze_exact(binding_path, binding)
    audit(repository, "INCOMING_SOURCE_BINDING_FROZEN", digest(binding))
    removed: dict[str, bool] = {}
    for role in review.ROLES:
        folder, inventory = handoff_expected(authority, role)
        raw, receipt = verify_incoming(repository, role)
        source = folder / "completed-response.json"
        if source.exists():
            if source.read_bytes() != raw or raw_sha(raw) != receipt["raw_sha256"]:
                raise review.ReviewBlocked("P021_B_1_BLOCKED_STAGING_COPY_MISMATCH")
            source.unlink()
        cleanup_path = repository / INTAKE / f"cleanup-{role}.json"
        metadata_existed = (folder / ".DS_Store").exists()
        removed_now = review.verify_files(folder, inventory, recover_ds_store=True)
        review.verify_handoff(authority, role, folder)
        if cleanup_path.exists():
            cleanup = review.read_seal(cleanup_path)
        else:
            cleanup = review.append_seal(
                cleanup_path,
                dict(
                    role=role,
                    duplicate_response_removed_after_copy=True,
                    staged_raw_sha256=receipt["raw_sha256"],
                    ds_store_narrow_conditions_satisfied=metadata_existed,
                    ds_store_removed=removed_now,
                    arbitrary_extra_ignored=False,
                    authoritative_handoff_restored=True,
                ),
            )
        removed[role] = cleanup["ds_store_removed"]
        audit(repository, f"HANDOFF_{role}_RESTORED", cleanup["fingerprint"])
    return dict(
        roles=staging,
        ds_store_removed=removed,
        parsed_before_staging=False,
        authoritative_handoffs_restored=True,
        source_binding_fingerprint=digest(binding),
    )


def freeze_exact(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        value = review.read_seal(path)
        if value != payload | {"fingerprint": digest(payload)}:
            raise review.ReviewBlocked("P021_B_IMMUTABLE_ARTIFACT_DRIFT")
        return value
    return review.append_seal(path, payload)


def audit(repository: Path, event: str, binding: str) -> None:
    path = repository / INTAKE / "audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    review._safe_path(path)
    rows = [json.loads(line) for line in path.read_bytes().splitlines()] if path.exists() else []
    previous = "0" * 64
    for i, row in enumerate(rows):
        if (
            row["previous"] != previous
            or row["sequence"] != i
            or row["fingerprint"] != digest({k: v for k, v in row.items() if k != "fingerprint"})
        ):
            raise review.ReviewBlocked("P021_B_AUDIT_CHAIN_DRIFT")
        previous = row["fingerprint"]
    if any(row["event"] == event and row["binding"] == binding for row in rows):
        return
    value = dict(
        event=event,
        binding=binding,
        previous=previous,
        sequence=len(rows),
        timestamp=datetime.now(UTC).isoformat(),
    )
    with path.open("ab") as stream:
        stream.write((canonical(value | {"fingerprint": digest(value)}) + "\n").encode())
    path.chmod(0o600)


def validate_current(
    authority: review.Authority, role: review.Role, raw: bytes
) -> review.Submission:
    """Current local blank/schema/bundle first; no category or rationale repair."""
    folder = authority.repository / review.HANDOFF / f"reviewer-{role.lower()}"
    review.verify_handoff(authority, role, folder)
    template = review._json((folder / "submission-template.json").read_bytes())
    data = review._json(raw)
    if data.get("schema_version") != template["schema_version"]:
        raise review.ReviewBlocked("P021_B_BLOCKED_CURRENT_SCHEMA_MISMATCH")
    if data.get("bundle_fingerprint") != template["bundle_fingerprint"]:
        raise review.ReviewBlocked("P021_B_BLOCKED_BUNDLE_MISMATCH")
    if {r["blinded_id"] for r in template["responses"]} != {
        p.blinded_id for p in authority.bundles[role].packets
    }:
        raise review.ReviewBlocked("P021_B_BLOCKED_CURRENT_ASSIGNMENT_DRIFT")
    return review.validate_intake(authority.bundles[role], raw)


def accept(authority: review.Authority, role: review.Role) -> dict[str, Any]:
    repository = authority.repository
    review.read_seal(repository / INTAKE / "incoming-source-binding.json")
    for required_role in review.ROLES:
        verify_incoming(repository, required_role)
    raw, staged = verify_incoming(repository, role)
    audit(repository, f"{role}_INTAKE_RAW_HASH", staged["raw_sha256"])
    submission = validate_current(authority, role, raw)
    audit(repository, f"{role}_VALIDATION_PASS", digest(submission))
    destination = repository / ACCEPTED / role / "v0001"
    if destination.exists():
        receipt, accepted = load_accepted(authority, role)
        if accepted != raw:
            raise review.ReviewBlocked("P021_B_ACCEPTED_V0001_DIFFERENT_BYTES")
        audit(repository, f"{role}_FROZEN", receipt["fingerprint"])
        return receipt
    other: review.Role = "B" if role == "A" else "A"
    if (repository / ACCEPTED / other / "v0001").exists():
        _, other_raw = load_accepted(authority, other)
        other_submission = validate_current(authority, other, other_raw)
        if other_submission.reviewer_identity == submission.reviewer_identity:
            raise review.ReviewBlocked("P021_B_DISTINCT_REAL_HUMAN_IDENTITIES_REQUIRED")
    result: dict[str, Any] = {}

    def build(stage: Path) -> None:
        nonlocal result
        stage.chmod(0o700)
        (stage / "completed-response.json").write_bytes(raw)
        (stage / "completed-response.json").chmod(0o600)
        normalized = (canonical(submission) + "\n").encode()
        (stage / "canonical-response.json").write_bytes(normalized)
        (stage / "canonical-response.json").chmod(0o600)
        result = review.append_seal(
            stage / "acceptance-receipt.json",
            dict(
                role=role,
                version="v0001",
                schema_version=submission.schema_version,
                bundle_fingerprint=submission.bundle_fingerprint,
                raw_sha256=raw_sha(raw),
                canonical_fingerprint=digest(submission),
                canonical_sha256=raw_sha(normalized),
                response_count=100,
                unique_case_count=100,
                validation="PASS",
                accepted=True,
                opaque_reviewer_identity_fingerprint=digest(submission.reviewer_identity),
                accepted_at=datetime.now(UTC).isoformat(),
                staging_receipt_fingerprint=staged["fingerprint"],
                human_bytes_modified=False,
                semantic_correction=False,
                provenance="COORDINATOR_ATTESTED_REAL_HUMANS; SELF_ATTESTATION",
            ),
        )
        review.verify_files(
            stage,
            {
                "completed-response.json": result["raw_sha256"],
                "canonical-response.json": result["canonical_sha256"],
                "acceptance-receipt.json": review.sha(stage / "acceptance-receipt.json"),
            },
        )

    atomic_directory(destination, build)
    load_accepted(authority, role)
    audit(repository, f"{role}_FROZEN", result["fingerprint"])
    return result


def load_accepted(authority: review.Authority, role: review.Role) -> tuple[dict[str, Any], bytes]:
    folder = authority.repository / ACCEPTED / role / "v0001"
    if not folder.is_dir():
        raise review.ReviewBlocked("P021_B_BOTH_ACCEPTED_FREEZES_REQUIRED")
    receipt = review.read_seal(folder / "acceptance-receipt.json")
    review.verify_files(
        folder,
        {
            "completed-response.json": receipt["raw_sha256"],
            "canonical-response.json": receipt["canonical_sha256"],
            "acceptance-receipt.json": review.sha(folder / "acceptance-receipt.json"),
        },
    )
    raw = (folder / "completed-response.json").read_bytes()
    submission = validate_current(authority, role, raw)
    _, staged = verify_incoming(authority.repository, role)
    normalized = (canonical(submission) + "\n").encode()
    if (
        receipt["role"] != role
        or receipt["version"] != "v0001"
        or receipt["accepted"] is not True
        or receipt["raw_sha256"] != staged["raw_sha256"]
        or receipt["staging_receipt_fingerprint"] != staged["fingerprint"]
        or receipt["canonical_fingerprint"] != digest(submission)
        or receipt["bundle_fingerprint"] != submission.bundle_fingerprint
        or receipt["schema_version"] != submission.schema_version
        or receipt["response_count"] != 100
        or receipt["unique_case_count"] != 100
        or receipt["opaque_reviewer_identity_fingerprint"] != digest(submission.reviewer_identity)
        or (folder / "canonical-response.json").read_bytes() != normalized
    ):
        raise review.ReviewBlocked("P021_B_ACCEPTED_STORE_DRIFT")
    return receipt, raw


def load_alignment(authority: review.Authority) -> tuple[tuple[CaseAlignment, ...], dict[str, str]]:
    """Read only the closed three-field identity map, never construction or predictions."""
    root = authority.repository / COORDINATOR
    a = {p.blinded_id: p for p in authority.bundles["A"].packets}
    b = {p.blinded_id: p for p in authority.bundles["B"].packets}
    if set(a) != set(b) or {p.name for p in root.iterdir()} != {f"{i}.json" for i in a}:
        raise review.ReviewBlocked("P021_B_STABLE_MAPPING_DRIFT")
    cases = []
    inventory = {}
    for blind in sorted(a):
        path = root / f"{blind}.json"
        mapping = review.read_seal(path)
        if set(mapping) != {"scientific_case_id", "execution_id", "fingerprint"}:
            raise review.ReviewBlocked("P021_B_FORBIDDEN_MAPPING_METADATA")
        if a[blind].fingerprint != b[blind].fingerprint:
            raise review.ReviewBlocked("P021_B_STABLE_MAPPING_DRIFT")
        cases.append(
            CaseAlignment(
                case_id=mapping["scientific_case_id"],
                a_blinded_id=blind,
                b_blinded_id=blind,
                rule_id=a[blind].rule_id,
                language=a[blind].language,
            )
        )
        inventory[path.name] = review.sha(path)
    return tuple(cases), inventory


@dataclass(frozen=True)
class FrozenPair:
    cases: tuple[PairedDecision, ...]
    receipts: dict[str, dict[str, Any]]
    mapping_fingerprint: str


def frozen_pair(authority: review.Authority, *, verify: bool = False) -> FrozenPair:
    # Gate BOTH stores before parsing either for an agreement decision map.
    for role in review.ROLES:
        if not (authority.repository / ACCEPTED / role / "v0001").is_dir():
            raise review.ReviewBlocked("P021_B_BOTH_ACCEPTED_FREEZES_REQUIRED")
    accepted = {role: load_accepted(authority, role) for role in review.ROLES}
    submissions = {
        role: validate_current(authority, role, accepted[role][1]) for role in review.ROLES
    }
    if submissions["A"].reviewer_identity == submissions["B"].reviewer_identity:
        raise review.ReviewBlocked("P021_B_DISTINCT_REAL_HUMAN_IDENTITIES_REQUIRED")
    cases, inventory = load_alignment(authority)
    verify_or_freeze(
        authority.repository / INTAKE / "stable-mapping-freeze.json", dict(files=inventory), verify
    )
    paired = align_decisions(
        cases,
        {r.blinded_id: r.decision for r in submissions["A"].responses},
        {r.blinded_id: r.decision for r in submissions["B"].responses},
    )
    return FrozenPair(
        paired, {role: accepted[role][0] for role in review.ROLES}, digest(dict(files=inventory))
    )


def agreement_payload(pair: FrozenPair) -> dict[str, Any]:
    analysis = analyze_agreement(pair.cases)
    # The prospective P021.A plan froze only rates/counts for descriptive strata.
    strata = {
        field: {
            name: dict(
                N=v["n"],
                agreements=v["exact_agreement"],
                conflicts=v["disagreement"],
                agreement_rate=v["observed_agreement"],
            )
            for name, v in groups.items()
        }
        for field, groups in analysis["strata"].items()
    }
    return dict(
        version="p021-human-categorical-agreement-v1",
        joined_cases=len(pair.cases),
        primary=analysis["primary"],
        binary=analysis["binary"]
        | {
            "excluded_due_A_nonbinary": sum(c.a_decision not in BINARY for c in pair.cases),
            "excluded_due_B_nonbinary": sum(c.b_decision not in BINARY for c in pair.cases),
        },
        strata=strata,
        A_acceptance_fingerprint=pair.receipts["A"]["fingerprint"],
        B_acceptance_fingerprint=pair.receipts["B"]["fingerprint"],
        stable_mapping_fingerprint=pair.mapping_fingerprint,
        semantic_correction=False,
        significance_tests=False,
    )


def conflict_payload(pair: FrozenPair) -> dict[str, Any]:
    return dict(
        version="p021-categorical-conflicts-v1",
        stable_mapping_fingerprint=pair.mapping_fingerprint,
        rows=[
            dict(
                scientific_case_id=c.case_id,
                A_blinded_id=c.a_blinded_id,
                B_blinded_id=c.b_blinded_id,
                rule_id=c.rule_id,
                language=c.language,
                A_category=c.a_decision,
                B_category=c.b_decision,
                adjudication_packet_reference="adj-" + digest(("p021-adjudication-v1", c.case_id)),
            )
            for c in pair.cases
            if c.a_decision != c.b_decision
        ],
        construction_intent_included=False,
        model_results_included=False,
    )


def branch_payload(pair: FrozenPair) -> tuple[str, dict[str, Any]]:
    if any(c.a_decision != c.b_decision for c in pair.cases):
        return "ADJUDICATION_REQUIRED", {}
    return "NO_ADJUDICATION_REQUIRED", dict(
        schema_version="unified-semantic-final-human-truth-v1",
        merge_rule="EXACT_A_B_CONSENSUS_ONLY; FOUR_CATEGORIES_PRESERVED",
        cases=[
            dict(
                scientific_case_id=c.case_id,
                target_rule=c.rule_id,
                language=c.language,
                final_category=c.a_decision,
                binary_eligible=c.a_decision in BINARY,
                resolution_provenance="EXACT_A_B_CONSENSUS",
            )
            for c in pair.cases
        ],
    )


def prepare_adjudication(
    authority: review.Authority, pair: FrozenPair, conflicts: dict[str, Any], destination: Path
) -> dict[str, Any]:
    """Third-human source-only package; no A/B judgments in any deliverable."""
    original = {p.blinded_id: p for p in authority.bundles["A"].packets}
    packets = []
    mappings = []
    for row in conflicts["rows"]:
        source = original[row["A_blinded_id"]]
        payload = source.model_dump(mode="json", exclude={"fingerprint"})
        payload["blinded_id"] = row["adjudication_packet_reference"]
        packets.append(payload | {"fingerprint": digest(payload)})
        mappings.append(
            dict(
                scientific_case_id=row["scientific_case_id"],
                adjudication_id=payload["blinded_id"],
                original_packet_fingerprint=source.fingerprint,
            )
        )
    if not packets:
        raise review.ReviewBlocked("P021_B_ADJUDICATION_CONFLICTS_REQUIRED")
    packets.sort(key=lambda p: digest(("p021-third-human-order-v1", p["blinded_id"])))
    manifest = dict(
        version="p021-adjudication-packet-manifest-v1",
        rows=[
            dict(adjudication_id=p["blinded_id"], packet_fingerprint=p["fingerprint"])
            for p in packets
        ],
    )
    assignment = dict(
        version="p021-adjudication-assignment-v1",
        rows=sorted(mappings, key=lambda r: r["adjudication_id"]),
    )
    guidance = authority.bundles["A"].guidance
    bundle = dict(
        schema_version="unified-independent-adjudicator-bundle-v1",
        reviewer_slot="ADJUDICATOR",
        packets=packets,
        guidance=guidance,
        categories=list(CATEGORIES),
        independence="THIRD_DISTINCT_REAL_HUMAN; SOURCE_ONLY; NO_A_B_ANSWERS; NO_AI",
    )
    bundle = bundle | {"fingerprint": digest(bundle)}
    folder = authority.repository / review.HANDOFF / "reviewer-a"
    schema = json.loads((folder / "submission-schema.json").read_bytes())["schema"]
    schema["title"] = "IndependentThirdHumanSubmission"
    props = schema["properties"]
    props["schema_version"]["const"] = "unified-semantic-adjudication-submission-v1"
    props["reviewer_slot"]["const"] = "ADJUDICATOR"
    props["attestation"]["const"] = "REAL_HUMAN_INDEPENDENT_ADJUDICATION"
    props["responses"]["minItems"] = props["responses"]["maxItems"] = len(packets)
    props["reviewer_identity"]["pattern"] = "^human-[a-f0-9]{32}$"
    template = dict(
        schema_version=props["schema_version"]["const"],
        reviewer_slot="ADJUDICATOR",
        bundle_fingerprint=bundle["fingerprint"],
        reviewer_identity="",
        attestation="",
        responses=[
            dict(blinded_id=p["blinded_id"], decision=None, rationale="", evidence=[], note="")
            for p in packets
        ],
    )
    readme = (
        b"Third distinct REAL HUMAN: independent adjudication. Use only this package and each "
        b"frozen target question/contract/source. Make your own four-category judgment and write "
        b"your own rationale with supplied evidence_id and inclusive existing source lines. "
        b"POSITIVE, NEGATIVE, UNCERTAIN and OUT_OF_SCOPE remain distinct. No AI/LLM/classifier "
        b"assistance, internet or repository browsing. Do not consult the previous reviewers. "
        b"Ordinary editors/viewers are allowed. Copy the blank template "
        b"to completed-response.json. "
        b"Use a new opaque human-32-lowercase-hex identity and attest "
        b"REAL_HUMAN_INDEPENDENT_ADJUDICATION only after your own review. Return privately to "
        b"the coordinator. Keep the frozen bundle and blank unchanged.\n"
    )
    result: dict[str, Any] = {}

    def build(stage: Path) -> None:
        nonlocal result
        stage.chmod(0o700)
        packet_manifest = review.append_seal(stage / "packet-manifest.json", manifest)
        assigned = review.append_seal(stage / "assignment.json", assignment)
        handoff = stage / "handoff"
        handoff.mkdir(mode=0o700)
        files = {}
        for name, value in (
            ("bundle.json", bundle),
            ("submission-schema.json", schema),
            ("submission-template.json", template),
        ):
            raw = (canonical(value) + "\n").encode()
            (handoff / name).write_bytes(raw)
            (handoff / name).chmod(0o600)
            files[name] = raw_sha(raw)
        (handoff / "README.txt").write_bytes(readme)
        (handoff / "README.txt").chmod(0o600)
        files["README.txt"] = raw_sha(readme)
        result = review.append_seal(
            stage / "handoff-receipt.json",
            dict(
                version="p021-third-human-handoff-v1",
                packets=len(packets),
                nonconflict_packets=0,
                packet_manifest_fingerprint=packet_manifest["fingerprint"],
                assignment_fingerprint=assigned["fingerprint"],
                bundle_fingerprint=bundle["fingerprint"],
                files=files,
                a_b_answers_exposed=False,
                construction_leakage=0,
                model_leakage=0,
                final_semantic_truth_created=False,
            ),
        )
        verify_adjudication(stage, conflicts)

    if destination.exists():
        result = verify_adjudication(destination, conflicts)
        if result["bundle_fingerprint"] != bundle["fingerprint"]:
            raise review.ReviewBlocked("P021_B_ADJUDICATION_DRIFT")
        return result
    atomic_directory(destination, build)
    return result


def verify_adjudication(destination: Path, conflicts: dict[str, Any]) -> dict[str, Any]:
    receipt = review.read_seal(destination / "handoff-receipt.json")
    manifest = review.read_seal(
        destination / "packet-manifest.json", receipt["packet_manifest_fingerprint"]
    )
    assignment = review.read_seal(
        destination / "assignment.json", receipt["assignment_fingerprint"]
    )
    expected = {
        **{f"handoff/{n}": h for n, h in receipt["files"].items()},
        **{
            n: review.sha(destination / n)
            for n in ("packet-manifest.json", "assignment.json", "handoff-receipt.json")
        },
    }
    review.verify_files(destination, expected)
    bundle = review.read_seal(destination / "handoff/bundle.json", receipt["bundle_fingerprint"])
    ids = {r["adjudication_packet_reference"] for r in conflicts["rows"]}
    if (
        receipt["packets"] != len(ids)
        or receipt["nonconflict_packets"] != 0
        or {p["blinded_id"] for p in bundle["packets"]} != ids
        or {r["adjudication_id"] for r in assignment["rows"]} != ids
        or {r["adjudication_id"] for r in manifest["rows"]} != ids
        or len(bundle["packets"]) != len(ids)
        or receipt["a_b_answers_exposed"] is not False
    ):
        raise review.ReviewBlocked("P021_B_ADJUDICATION_DRIFT")
    template = review._json((destination / "handoff/submission-template.json").read_bytes())
    if (
        template["reviewer_identity"]
        or template["attestation"]
        or any(
            r["decision"] is not None or r["rationale"] or r["evidence"]
            for r in template["responses"]
        )
    ):
        raise review.ReviewBlocked("P021_B_ADJUDICATION_NOT_BLANK")
    return receipt


def public_conflicts(pair: FrozenPair, conflicts: dict[str, Any]) -> dict[str, Any]:
    rows = conflicts["rows"]
    payload = dict(
        version="p021-public-conflict-summary-v1",
        conflict_count=len(rows),
        conflict_manifest_fingerprint=conflicts["fingerprint"],
        by_rule={
            rule: sum(c["rule_id"] == rule for c in rows)
            for rule in (f"ARCH20{i}" for i in range(1, 6))
        },
        by_language={
            lang: sum(c["language"] == lang for c in rows) for lang in ("JAVA", "TYPESCRIPT")
        },
        joined_cases=len(pair.cases),
        construction_intent_included=False,
        model_results_included=False,
    )
    return payload | {"fingerprint": digest(payload)}


def execute(authority: review.Authority, *, verify_only: bool = False) -> dict[str, Any]:
    repository = authority.repository
    if not verify_only:
        audit(repository, "P021_B_START", digest(dict(p021_a=P021_A)))
        stage_returns(authority)
        for role in review.ROLES:
            accept(authority, role)
    pair = frozen_pair(authority, verify=verify_only)
    result_root = repository / RESULTS
    joined = dict(
        version="p021-stable-frozen-join-v1", rows=[c.model_dump(mode="json") for c in pair.cases]
    )
    if not verify_only:
        audit(repository, "STABLE_JOIN", digest(joined))
    agreement = agreement_payload(pair)
    conflicts = conflict_payload(pair)
    branch, truth = branch_payload(pair)
    # Verification reproduces exclusively from accepted freezes; no human re-review.
    artifacts = {
        "stable-join.json": joined,
        "agreement.json": agreement,
        "conflicts.json": conflicts,
    }
    for name, payload in artifacts.items():
        path = result_root / name
        if verify_only:
            if review.read_seal(path) != payload | {"fingerprint": digest(payload)}:
                raise review.ReviewBlocked("P021_B_FROZEN_AGREEMENT_DRIFT")
        else:
            freeze_exact(path, payload)
    agreement = agreement | {"fingerprint": digest(agreement)}
    conflicts = conflicts | {"fingerprint": digest(conflicts)}
    if not verify_only:
        audit(repository, "AGREEMENT_COMPUTED", agreement["fingerprint"])
        audit(repository, "CONFLICT_MANIFEST_FROZEN", conflicts["fingerprint"])
        audit(repository, "BRANCH_SELECTED", digest(branch))
    protocol = review.read_seal(repository / review.PROTOCOL_PATH)
    lineage = dict(
        P020_registry_fingerprint=review.PINS[review.BASE / "p020-registry-v2.json"],
        P021_A_commit=P021_A,
        protocol_fingerprint=protocol["fingerprint"],
        agreement_fingerprint=agreement["fingerprint"],
        conflict_manifest_fingerprint=conflicts["fingerprint"],
        stable_mapping_fingerprint=pair.mapping_fingerprint,
        accepted_receipts={r: pair.receipts[r]["fingerprint"] for r in review.ROLES},
        accepted_raw_sha256={r: pair.receipts[r]["raw_sha256"] for r in review.ROLES},
        accepted_canonical_fingerprints={
            r: pair.receipts[r]["canonical_fingerprint"] for r in review.ROLES
        },
        implementation={name: review.sha(repository / name) for name in SOURCE_FILES},
    )
    branch_summary: dict[str, Any]
    if branch == "NO_ADJUDICATION_REQUIRED":
        if (result_root / "adjudication").exists():
            raise review.ReviewBlocked("P021_B_BRANCH_DRIFT")
        truth["lineage_fingerprint"] = digest(lineage)
        truth_path = result_root / "truth/final-semantic-truth.json"
        if verify_only:
            if review.read_seal(truth_path) != truth | {"fingerprint": digest(truth)}:
                raise review.ReviewBlocked("P021_B_TRUTH_DRIFT")
            frozen_truth = review.read_seal(truth_path)
        else:
            frozen_truth = freeze_exact(truth_path, truth)
        if not verify_only:
            freeze_exact(result_root / "truth/lineage.json", lineage)
        elif review.read_seal(result_root / "truth/lineage.json")["fingerprint"] != digest(lineage):
            raise review.ReviewBlocked("P021_B_TRUTH_LINEAGE_DRIFT")
        counts = Counter(c["final_category"] for c in truth["cases"])
        truth_receipt = dict(
            version="p021-consensus-truth-freeze-v1",
            raw_sha256=review.sha(truth_path),
            canonical_fingerprint=frozen_truth["fingerprint"],
            lineage_fingerprint=digest(lineage),
            categories={c: counts[c] for c in CATEGORIES},
            N=100,
            binary_eligible=sum(counts[c] for c in BINARY),
            consensus_only=True,
            version_number=1,
            append_only=True,
            semantic_correction=False,
        )
        truth_receipt = verify_or_freeze(
            result_root / "truth/freeze-receipt.json", truth_receipt, verify_only
        )
        public_truth = verify_or_freeze(
            result_root / "truth/public-verification.json",
            dict(
                version="p021-public-semantic-truth-verification-v1",
                N=100,
                categories=truth_receipt["categories"],
                binary_eligible=truth_receipt["binary_eligible"],
                truth_fingerprint=frozen_truth["fingerprint"],
                truth_lineage_fingerprint=digest(lineage),
                truth_receipt_fingerprint=truth_receipt["fingerprint"],
                raw_truth_sha256=truth_receipt["raw_sha256"],
                human_consensus_only=True,
                final_semantic_truth_frozen=True,
            ),
            verify_only,
        )
        branch_summary = dict(
            final_semantic_truth_frozen=True,
            adjudication_required=False,
            truth_raw_sha256=truth_receipt["raw_sha256"],
            truth_fingerprint=frozen_truth["fingerprint"],
            truth_lineage_fingerprint=digest(lineage),
            truth_receipt_fingerprint=truth_receipt["fingerprint"],
            public_truth_verification_fingerprint=public_truth["fingerprint"],
            truth_categories=truth_receipt["categories"],
            binary_eligible=truth_receipt["binary_eligible"],
            final_status="READY_FOR_P022_DEVELOPMENT_LLM_APPROVAL",
        )
        if not verify_only:
            audit(repository, "FINAL_SEMANTIC_TRUTH_FROZEN", frozen_truth["fingerprint"])
    else:
        if (result_root / "truth").exists():
            raise review.ReviewBlocked("P021_B_BRANCH_DRIFT")
        adj = (
            verify_adjudication(result_root / "adjudication", conflicts)
            if verify_only
            else prepare_adjudication(authority, pair, conflicts, result_root / "adjudication")
        )
        branch_summary = dict(
            final_semantic_truth_frozen=False,
            adjudication_required=True,
            adjudication_packet_manifest_fingerprint=adj["packet_manifest_fingerprint"],
            adjudication_assignment_fingerprint=adj["assignment_fingerprint"],
            adjudication_receipt_fingerprint=adj["fingerprint"],
            adjudication_packets=adj["packets"],
            nonconflict_adjudication_packets=0,
            final_status="WAITING_FOR_THIRD_REAL_HUMAN",
        )
        if not verify_only:
            audit(repository, "ADJUDICATION_HANDOFF_FROZEN", adj["fingerprint"])
    summary = dict(
        version="p021-b-human-intake-summary-v1",
        status="P021_B_HUMAN_INTAKE_COMPLETE",
        authoritative_handoff_reconciled=True,
        accepted={
            r: dict(
                role=r,
                schema=pair.receipts[r]["schema_version"],
                bundle_fingerprint=pair.receipts[r]["bundle_fingerprint"],
                raw_sha256=pair.receipts[r]["raw_sha256"],
                canonical_fingerprint=pair.receipts[r]["canonical_fingerprint"],
                accepted=True,
                accepted_version="v0001",
                responses=100,
                unique_ids=100,
                missing=0,
                extras=0,
                duplicates=0,
                invalid_categories=0,
                blank_rationales=0,
                invalid_evidence=0,
                identity_format="PASS",
                attestation="PASS",
                receipt_fingerprint=pair.receipts[r]["fingerprint"],
            )
            for r in review.ROLES
        },
        identities_equal=False,
        authorship_detector_used=False,
        AI_reviewer_used=False,
        agreement=agreement,
        conflict_summary=public_conflicts(pair, conflicts),
        branch=branch,
        agreement_freeze_receipt_fingerprint=digest(
            dict(
                agreement_fingerprint=agreement["fingerprint"],
                accepted_receipts={r: pair.receipts[r]["fingerprint"] for r in review.ROLES},
            )
        ),
        **branch_summary,
        provider_calls=0,
        connectivity_calls=0,
        paid_spend_usd=0,
        paid_execution_approved=False,
        construction_intent_opened=False,
        model_predictions_joined=False,
        hybrid_trained=False,
        ablations_executed=False,
        final_evaluation=False,
        security_executed=False,
    )
    verify_or_freeze(
        result_root / "agreement-freeze-receipt.json",
        dict(
            agreement_fingerprint=agreement["fingerprint"],
            accepted_receipts={r: pair.receipts[r]["fingerprint"] for r in review.ROLES},
        ),
        verify_only,
    )
    verify_or_freeze(result_root / "summary.json", summary, verify_only)
    verify_chronology(repository)
    return summary


def verify_or_freeze(path: Path, payload: dict[str, Any], verify: bool) -> dict[str, Any]:
    if verify:
        value = review.read_seal(path)
        if value != payload | {"fingerprint": digest(payload)}:
            raise review.ReviewBlocked("P021_B_IMMUTABLE_ARTIFACT_DRIFT")
        return value
    return freeze_exact(path, payload)


def verify_chronology(repository: Path) -> None:
    rows = [
        json.loads(line) for line in (repository / INTAKE / "audit.jsonl").read_bytes().splitlines()
    ]
    order = {r["event"]: i for i, r in enumerate(rows)}
    required = (
        "P021_B_START",
        "INCOMING_SOURCE_BINDING_FROZEN",
        "A_INTAKE_RAW_HASH",
        "A_VALIDATION_PASS",
        "A_FROZEN",
        "B_INTAKE_RAW_HASH",
        "B_VALIDATION_PASS",
        "B_FROZEN",
        "STABLE_JOIN",
        "AGREEMENT_COMPUTED",
        "CONFLICT_MANIFEST_FROZEN",
        "BRANCH_SELECTED",
    )
    if any(name not in order for name in required) or [order[n] for n in required] != sorted(
        order[n] for n in required
    ):
        raise review.ReviewBlocked("P021_B_CHRONOLOGY_DRIFT")
    previous = "0" * 64
    for i, row in enumerate(rows):
        if (
            row["previous"] != previous
            or row["sequence"] != i
            or row["fingerprint"] != digest({k: v for k, v in row.items() if k != "fingerprint"})
        ):
            raise review.ReviewBlocked("P021_B_AUDIT_CHAIN_DRIFT")
        previous = row["fingerprint"]
