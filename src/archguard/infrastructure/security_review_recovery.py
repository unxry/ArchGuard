"""P031 mechanical recovery and human-only agreement custody; no semantic inference."""

import hashlib
import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_analysis_v1 as v1
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_review_readiness as readiness
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security_benchmark.protocol import ReviewPacket, ReviewResponse, TruthLabel

SOURCE = "08a95548d2ed15c3415aa780b6c54f2b09907d1e"
PREVIOUS_DIAGNOSTIC = "e1bc2e130c60b32015cd22b0fe4e71b073157c4d4f1a63b23ee502d36bb97701"
NESTED = Path("experiments/security/security-human-review-v1/private/responses")
FIELDS = ("reviewer_slot", "case_id", "label", "rationale", "evidence_note", "completed")
EXTRAS = frozenset(("ordinal", "rule_id", "packet_reference", "response_destination"))
SOURCES = (
    "src/archguard/infrastructure/security_review_recovery.py",
    "scripts/prompt031_security_recovery.py",
    "tests/security/test_review_recovery.py",
)
DOCS = (readiness.DOC, "docs/security/SECURITY_HUMAN_REVIEW.md")
PUBLIC_NAMES = (
    "response-recovery.json",
    "review-completeness.json",
    "security-human-agreement.json",
    "resume-quality.json",
    "resume-freeze-index.json",
)
PRIVATE = readiness.PRIVATE
PUBLIC = readiness.PUBLIC


def gate() -> None:
    allowed = (*SOURCES, *DOCS, *(str(PUBLIC / n) for n in PUBLIC_NAMES))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for commit in ("624eb05609e4e24f0cedcc50ce7a3587de0dcf60", readiness.SOURCE, SOURCE):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P031_RECOVERY_LINEAGE_DRIFT")
    changed = subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
    if any(p not in allowed for p in changed.decode().splitlines()):
        raise ValueError("P031_RECOVERY_COMMITTED_SCOPE_DRIFT")
    if Path(".gitignore").read_bytes() != subprocess.check_output(
        ["git", "show", f"{SOURCE}:.gitignore"]
    ) or subprocess.check_output(["git", "ls-files", "--", str(PRIVATE)]):
        raise ValueError("P031_PRIVATE_IGNORE_DRIFT")
    if subprocess.run(
        ["git", "check-ignore", "-q", str(PRIVATE / "responses/A")], capture_output=True
    ).returncode:
        raise ValueError("P031_PRIVATE_NOT_IGNORED")
    old = io.read_seal(PUBLIC / "freeze-index.json")
    for p, h in old["source_bindings"].items():
        if io.sha(Path(p)) != h:
            raise ValueError("P031_READINESS_SOURCE_DRIFT")
    for p, h in old["documents"].items():
        frozen = subprocess.check_output(["git", "show", f"{SOURCE}:{p}"])
        if hashlib.sha256(frozen).hexdigest() != h or not Path(p).read_bytes().startswith(frozen):
            raise ValueError("P031_READINESS_CHRONOLOGY_DRIFT")
    for name, h in old["files"].items():
        if io.sha(PUBLIC / name) != h:
            raise ValueError("P031_READINESS_RECEIPT_DRIFT")


def read_object(path: Path, limit: int = 4_000_000) -> dict[str, Any]:
    readiness.safe(path)
    if not path.is_file() or path.stat().st_nlink != 1 or path.stat().st_size > limit:
        raise ValueError("P031_UNSAFE_INPUT_FILE")
    value = json.loads(path.read_bytes(), object_pairs_hook=readiness.unique)
    if not isinstance(value, dict):
        raise ValueError("P031_EXPECTED_OBJECT")
    return value


def write_once(path: Path, value: dict[str, Any]) -> None:
    readiness.safe(path)
    raw = (canonical(value) + "\n").encode()
    if path.exists():
        if path.stat().st_nlink != 1 or path.read_bytes() != raw:
            raise ValueError("P031_IMMUTABLE_OUTPUT_DRIFT")
        return
    previous = os.umask(0o077)
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with path.open("xb") as stream:
            stream.write(raw)
    finally:
        os.umask(previous)


def clean_metadata(root: Path, expected: dict[str, str], count: int) -> list[dict[str, str]]:
    """Delete only unmanifested regular Finder metadata after exact expected-byte checks."""
    readiness.safe(root)
    wanted = set(expected)
    for name in expected:
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("P031_UNSAFE_INVENTORY")
        wanted.update(p.as_posix() for p in Path(name).parents if p != Path("."))
    paths = list(root.rglob("*"))
    for path in paths:
        readiness.safe(path)
    actual = {p.relative_to(root).as_posix() for p in paths}
    if wanted - actual or any(io.sha(root / n) != h for n, h in expected.items()):
        raise ValueError("P031_RECOVERY_BLOCKED_P030_FREEZE_RISK")
    extras = sorted(actual - wanted)
    if len(extras) != count:
        raise ValueError("P031_UNEXPECTED_METADATA_COUNT")
    receipt = []
    for name in extras:
        path = root / name
        if (
            path.name != ".DS_Store"
            or not path.is_file()
            or path.stat().st_nlink != 1
            or path.read_bytes()[:8] != b"\x00\x00\x00\x01Bud1"
        ):
            raise ValueError("P031_RECOVERY_BLOCKED_P030_FREEZE_RISK")
        receipt.append(dict(path=name, byte_hash=io.sha(path)))
    for row in receipt:
        (root / row["path"]).unlink()
    io.verify_files(root, expected)
    return receipt


def project(raw: dict[str, Any], slot: str) -> dict[str, Any]:
    allowed = set(FIELDS) | (EXTRAS if slot == "B" else set())
    if not set(FIELDS) <= set(raw) or set(raw) - allowed:
        raise ValueError("P031_UNAPPROVED_RESPONSE_FIELDS")
    if raw["reviewer_slot"] != slot:
        raise ValueError("P031_WRONG_SLOT")
    return {k: raw[k] for k in FIELDS}


def bind(raw: dict[str, Any], slot: str, packets: dict[str, ReviewPacket]) -> Path:
    response = ReviewResponse.model_validate(raw)
    if not response.completed or response.reviewer_slot != slot:
        raise ValueError("P031_INCOMPLETE_OR_WRONG_SLOT")
    packet = packets.get(response.case_id)
    if packet is None or packet.reviewer_slot != slot:
        raise ValueError("P031_UNKNOWN_CASE_OR_SLOT")
    destination = PRIVATE / packet.response_destination
    if destination != PRIVATE / "responses" / slot / f"{response.case_id}.json":
        raise ValueError("P031_WRONG_DESTINATION")
    readiness.safe(destination)
    return destination


def recover(
    sets: dict[str, dict[str, ReviewPacket]], removed: list[dict[str, str]]
) -> dict[str, Any]:
    receipt_path = PRIVATE / "recovery/content-preservation.json"
    if receipt_path.exists():
        return io.read_seal(receipt_path)
    planned = []
    masters = []
    crosschecks = {}
    for slot in ("A", "B"):
        root = PRIVATE / "responses" / slot
        readiness.safe(root)
        nested = root / NESTED / slot
        readiness.safe(nested)
        found = sorted(nested.glob("*.json"))
        if len(found) != len(sets[slot]):
            raise ValueError("P031_NESTED_COUNT_MISMATCH")
        seen = set()
        slot_rows = {}
        for source in found:
            raw = read_object(source, 128_000)
            projected = project(raw, slot)
            destination = bind(projected, slot, sets[slot])
            case = projected["case_id"]
            if case in seen:
                raise ValueError("P031_DUPLICATE_SOURCE_CASE")
            seen.add(case)
            slot_rows[case] = projected
            if destination.exists() and read_object(destination) != projected:
                raise ValueError("P031_EXISTING_CANONICAL_RESPONSE_CONFLICT")
            planned.append(
                (
                    source,
                    destination,
                    projected,
                    dict(
                        source=str(source),
                        destination=str(destination),
                        source_hash=io.sha(source),
                        semantic_hash=digest(projected),
                        removed_fields=sorted(set(raw) - set(projected)),
                    ),
                )
            )
        if seen != set(sets[slot]):
            raise ValueError("P031_CASE_SET_MISMATCH")
        candidates = [p for p in root.glob("*.json") if p.stem not in sets[slot]]
        if len(candidates) != 1:
            raise ValueError("P031_AGGREGATE_MASTER_REQUIRED")
        master = candidates[0]
        value = read_object(master)
        if value.get("reviewer_slot") != slot or value.get("total") != len(slot_rows):
            raise ValueError("P031_AGGREGATE_BINDING_MISMATCH")
        for field in ("human_origin_attestation", "independence_attestation"):
            if not isinstance(value.get(field), str) or not value[field].strip():
                raise ValueError("P031_SET_ATTESTATION_REQUIRED")
        aggregate = {}
        for row in value.get("responses", []):
            projected = project(row, slot)
            case = projected["case_id"]
            if case in aggregate:
                raise ValueError("P031_DUPLICATE_AGGREGATE_CASE")
            aggregate[case] = projected
        if set(aggregate) != set(slot_rows) or any(
            aggregate[c][k] != slot_rows[c][k]
            for c in slot_rows
            for k in ("reviewer_slot", "case_id", "label", "completed")
        ):
            raise ValueError("P031_AGGREGATE_SOURCE_CROSSCHECK_FAILED")
        crosschecks[slot] = {
            k: dict(
                identical=sum(aggregate[c][k] == slot_rows[c][k] for c in slot_rows),
                different=sum(aggregate[c][k] != slot_rows[c][k] for c in slot_rows),
            )
            for k in FIELDS
        }
        masters.append((master, PRIVATE / "provenance" / slot / "aggregate-master.json"))
    # Preflight every direct/nested entry before creating or deleting any response.
    permitted = {s for s, _, _, _ in planned} | {p for p, _ in masters}
    metadata = []
    for slot in ("A", "B"):
        root = PRIVATE / "responses" / slot
        for path in root.rglob("*"):
            readiness.safe(path)
            if path.is_dir() or path in permitted or path in {d for _, d, _, _ in planned}:
                continue
            if path.name != ".DS_Store" or not path.is_file() or path.stat().st_nlink != 1:
                raise ValueError("P031_UNEXPECTED_RESPONSE_TREE_ENTRY")
            if path.read_bytes()[:8] != b"\x00\x00\x00\x01Bud1":
                raise ValueError("P031_UNEXPECTED_OS_METADATA")
            metadata.append(path)
    for source, target in masters:
        readiness.safe(target)
        previous = os.umask(0o077)
        try:
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if target.exists():
                if target.read_bytes() != source.read_bytes():
                    raise ValueError("P031_PROVENANCE_DESTINATION_EXISTS")
            else:
                with target.open("xb") as stream:
                    stream.write(source.read_bytes())
        finally:
            os.umask(previous)
        if source.read_bytes() != target.read_bytes():
            raise ValueError("P031_PROVENANCE_COPY_MISMATCH")
    for _, destination, projected, _ in planned:
        write_once(destination, projected)
        if read_object(destination) != projected:
            raise ValueError("P031_SEMANTIC_PRESERVATION_FAILED")
    # Delete obsolete sources only after ALL canonical responses validate and match.
    for source, _, _, row in planned:
        if io.sha(source) != row["source_hash"]:
            raise ValueError("P031_SOURCE_CHANGED_DURING_RECOVERY")
    for source, _, _, _ in planned:
        source.unlink()
    for source, _ in masters:
        source.unlink()
    for path in metadata:
        path.unlink()
    for slot in ("A", "B"):
        nested_root = PRIVATE / "responses" / slot / "experiments"
        for path in sorted(nested_root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir():
                path.rmdir()
        nested_root.rmdir()
    value = dict(
        status="P031_MECHANICAL_RECOVERY_COMPLETE",
        sources=[row for _, _, _, row in planned],
        preserved={
            s: dict(
                source=len(sets[s]),
                canonical=len(sets[s]),
                labels=len(sets[s]),
                rationales=len(sets[s]),
                evidence_notes=len(sets[s]),
                semantic_changes=0,
            )
            for s in ("A", "B")
        },
        B_removed_field_kinds=sorted(EXTRAS),
        P030_metadata_removed=removed,
        response_metadata_removed=len(metadata),
        provenance_masters_preserved=2,
        aggregate_crosschecks=crosschecks,
        source_authority=(
            "Nested per-case values; aggregate masters retained separately without edits"
        ),
        previous_diagnostic_fingerprint=io.read_seal(
            PRIVATE / "readiness/resume-structural-diagnostics.json"
        )["fingerprint"],
    )
    return io.append_seal(receipt_path, value)


def agreement(a: list[str], b: list[str], labels: tuple[str, ...]) -> dict[str, Any]:
    if len(a) != len(b) or any(x not in labels for x in (*a, *b)):
        raise ValueError("P031_INVALID_AGREEMENT_INPUT")
    n = len(a)
    ca, cb = Counter(a), Counter(b)
    same = sum(x == y for x, y in zip(a, b, strict=True))
    denominator = n * n - sum(ca[x] * cb[x] for x in labels)
    return dict(
        N=n,
        exact_agreements=same,
        disagreements=n - same,
        raw_agreement=same / n if n else None,
        cohens_kappa=(same * n - sum(ca[x] * cb[x] for x in labels)) / denominator
        if denominator
        else None,
        A_distribution={x: ca[x] for x in labels},
        B_distribution={x: cb[x] for x in labels},
        cross_tab={
            x: {y: sum(u == x and v == y for u, v in zip(a, b, strict=True)) for y in labels}
            for x in labels
        },
    )


def integrity(a: dict[str, dict[str, Any]], b: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if set(a) != set(b):
        raise ValueError("P031_JOIN_CASE_SET_MISMATCH")
    same = {
        k: sum(a[c][k] == b[c][k] for c in sorted(a))
        for k in ("label", "rationale", "evidence_note")
    }
    bodies = sum(all(a[c][k] == b[c][k] for k in FIELDS if k != "reviewer_slot") for c in a)
    authored_text = any(a[c][k] for c in a for k in ("rationale", "evidence_note"))
    cloned_text = bool(authored_text) and same["rationale"] == same["evidence_note"] == len(a)
    return dict(
        N=len(a),
        same_labels=same["label"],
        different_labels=len(a) - same["label"],
        identical_rationales=same["rationale"],
        different_rationales=len(a) - same["rationale"],
        identical_evidence_notes=same["evidence_note"],
        different_evidence_notes=len(a) - same["evidence_note"],
        identical_response_bodies_excluding_slot=bodies,
        normalized_sets_identical=bool(a) and bodies == len(a),
        cloned_free_text_set=cloned_text,
        independence_accepted=bool(a) and not cloned_text and bodies != len(a),
    )


def adjudication_packet(
    packet: ReviewPacket, responses: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    return dict(
        case_id=packet.evidence.case_id,
        evidence=packet.evidence.model_dump(mode="json"),
        evidence_fingerprint=packet.evidence_fingerprint,
        reviewers={s: {k: responses[s][k] for k in ("label", "rationale")} for s in ("A", "B")},
        allowed_final_labels=[x.value for x in TruthLabel],
    )


def privacy(paths: tuple[Path, ...]) -> None:
    v1.privacy(paths)

    def check(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {
                    "source_files",
                    "evidence",
                    "responses",
                    "human_origin_attestation",
                    "independence_attestation",
                }:
                    raise ValueError("P031_PRIVATE_PUBLIC_FIELD")
                if key in {"label", "case_id", "rationale", "evidence_note"} and (
                    not isinstance(item, dict)
                    or set(item) != {"identical", "different"}
                    or any(type(n) is not int for n in item.values())
                ):
                    raise ValueError("P031_PRIVATE_PUBLIC_VALUE")
                check(item)
        elif isinstance(value, list):
            for item in value:
                check(item)

    for path in paths:
        raw = path.read_text()
        if re.search(r"sc-[a-f0-9]{24}|\/Users\/|\/home\/", raw):
            raise ValueError("P031_PUBLIC_PRIVATE_IDENTIFIER")
        if path.suffix == ".json":
            check(json.loads(raw, object_pairs_hook=readiness.unique))


def analyze(sets: dict[str, dict[str, ReviewPacket]]) -> tuple[dict[str, Any], dict[str, Any]]:
    counts, _ = readiness.inspect_responses(PRIVATE, sets, human_attested=True)
    if any(
        c != dict(expected=300, valid=300, missing=0, invalid=0, submitted_files=300)
        for c in counts.values()
    ):
        raise ValueError("P031_HUMAN_REVIEW_AWAITING_RESPONSES")
    rows = {
        s: {
            c: read_object(PRIVATE / p.response_destination, 128_000)
            for c, p in sorted(sets[s].items())
        }
        for s in ("A", "B")
    }
    frozen = {s: thesis.sealed(dict(reviewer_slot=s, responses=rows[s])) for s in ("A", "B")}
    for s in ("A", "B"):
        # Lock assessments before computing similarities, agreement, or conflicts.
        write_once(PRIVATE / "frozen" / f"reviewer-{s}.json", frozen[s])
        provenance = read_object(PRIVATE / "provenance" / s / "aggregate-master.json")
        if any(
            not isinstance(provenance.get(k), str) or not provenance[k].strip()
            for k in ("human_origin_attestation", "independence_attestation")
        ):
            raise ValueError("P031_SET_ATTESTATION_REQUIRED")
    similarity = integrity(rows["A"], rows["B"])
    if not similarity["independence_accepted"]:
        raise ValueError("P031_INDEPENDENCE_BLOCKED_CLONED_SET")
    splits = {}
    for split, n in (("DEV", 100), ("FINAL", 200)):
        roster = read_object(benchmark.PRIVATE / "prediction" / split / "roster.json")
        if set(roster) != {"cases"} or len(roster["cases"]) != n:
            raise ValueError("P031_INVALID_SANITIZED_SPLIT_ROSTER")
        for row in roster["cases"]:
            if set(row) != {"case_id", "rule_id", "language", "source_paths"}:
                raise ValueError("P031_FORBIDDEN_ROSTER_METADATA")
            case = row["case_id"]
            packet = sets["A"].get(case)
            if (
                case in splits
                or packet is None
                or row["rule_id"] != packet.evidence.rule_id
                or row["language"] != packet.evidence.language
            ):
                raise ValueError("P031_SPLIT_ROSTER_BINDING_DRIFT")
            splits[case] = split
    if set(splits) != set(rows["A"]):
        raise ValueError("P031_SPLIT_COVERAGE_DRIFT")
    labels = tuple(x.value for x in TruthLabel)
    groups = {"ALL": sorted(rows["A"])}
    groups.update({s: [c for c in sorted(splits) if splits[c] == s] for s in ("DEV", "FINAL")})
    groups.update(
        {
            lang: [c for c in sorted(splits) if sets["A"][c].evidence.language == lang]
            for lang in ("JAVA", "TYPESCRIPT")
        }
    )
    groups.update(
        {
            f"SEC{i:03}": [
                c for c in sorted(splits) if sets["A"][c].evidence.rule_id == f"SEC{i:03}"
            ]
            for i in range(1, 11)
        }
    )
    stats = {
        g: agreement(
            [rows["A"][c]["label"] for c in cases], [rows["B"][c]["label"] for c in cases], labels
        )
        for g, cases in groups.items()
    }
    conflicts, packets = [], {}
    for case in sorted(rows["A"]):
        if rows["A"][case]["label"] == rows["B"][case]["label"]:
            continue
        packet = sets["A"][case]
        conflicts.append(
            dict(
                case_id=case,
                A=rows["A"][case]["label"],
                B=rows["B"][case]["label"],
                evidence_fingerprint=packet.evidence_fingerprint,
                status="NEEDS_HUMAN_ADJUDICATION",
            )
        )
        packets[case] = adjudication_packet(packet, {s: rows[s][case] for s in ("A", "B")})
    if not conflicts:
        raise ValueError("P031_NO_CONFLICTS; separate authorized truth-freeze path required")
    adjudication_root = PRIVATE / "adjudication/responses"
    readiness.safe(adjudication_root)
    if adjudication_root.exists() and any(adjudication_root.iterdir()):
        raise ValueError("P031_EXISTING_HUMAN_ADJUDICATION_REQUIRES_SEPARATE_VALIDATION")
    private = dict(
        disagreement_inventory=thesis.sealed(dict(cases=conflicts)),
        adjudication_packets=thesis.sealed(dict(packets=packets)),
    )
    pub = dict(
        status="P031_HUMAN_ADJUDICATION_REQUIRED",
        counts=counts,
        integrity=similarity,
        agreement=stats,
        response_fingerprints={s: frozen[s]["fingerprint"] for s in ("A", "B")},
        disagreement_inventory_fingerprint=private["disagreement_inventory"]["fingerprint"],
        adjudication_packet_set_fingerprint=private["adjudication_packets"]["fingerprint"],
        human_origin={s: "COORDINATOR_ATTESTED" for s in ("A", "B")},
        independence_protocol={s: "ATTESTED" for s in ("A", "B")},
        provenance_caveat=(
            "Procedural coordinator attestation; no cryptographic authorship/noncommunication proof"
        ),
        human_adjudications_completed=0,
        human_adjudications_remaining=len(conflicts),
        AI_GENERATED_LABELS=0,
        AI_REWRITES=0,
        AI_ADJUDICATION=0,
        intent_tie_breaks=0,
        detector_tie_breaks=0,
        DEV_detector_predictions=0,
        FINAL_detector_predictions=0,
        truth_300="NOT_FROZEN",
        DEV_truth="NOT_FROZEN",
        FINAL_truth="NOT_FROZEN",
        binary_eligibility="NOT_COMPUTED_AS_FINAL_TRUTH",
        Security_effectiveness="NOT_EVALUATED",
        TP_FP_TN_FN="NOT_COMPUTED",
        precision=None,
        recall=None,
        F1=None,
        provider_calls=0,
        connectivity_calls=0,
        credential_reads=0,
        paid_spend=0,
        P032="NOT_STARTED",
        UI="NOT_STARTED",
        next_action="WAITING_FOR_REAL_HUMAN_ADJUDICATION",
    )
    return pub, private


def run() -> dict[str, Any]:
    gate()
    io.read_seal(PRIVATE / "readiness/resume-structural-diagnostics.json", PREVIOUS_DIAGNOSTIC)
    with patch.object(v2, "gate", gate):
        v2.verify()
    public_index = io.read_seal(benchmark.PUBLIC / "freeze-index.json")
    old = io.read_seal(
        benchmark.PRIVATE / "freeze-index.json", public_index["private_freeze_fingerprint"]
    )
    expected = old["files"] | {"freeze-index.json": io.sha(benchmark.PRIVATE / "freeze-index.json")}
    if len(expected) != 927:
        raise ValueError("P031_P030_EXPECTED_COUNT_DRIFT")
    metadata_path = PRIVATE / "recovery/metadata-cleanup.json"
    if metadata_path.exists():
        removed = io.read_seal(metadata_path)["removed"]
        io.verify_files(benchmark.PRIVATE, expected)
    else:
        removed = clean_metadata(benchmark.PRIVATE, expected, 2)
        io.append_seal(metadata_path, dict(removed=removed))
    with patch.object(readiness, "gate", gate):
        sets, history = readiness.verify_packets()
    recovery = recover(sets, removed)
    pub, private = analyze(sets)
    again, again_private = analyze(sets)
    if canonical((pub, private)) != canonical((again, again_private)):
        raise ValueError("P031_NONDETERMINISTIC_BUILD")
    for key, filename in (
        ("disagreement_inventory", "disagreement-inventory.json"),
        ("adjudication_packets", "packet-set.json"),
    ):
        write_once(PRIVATE / "adjudication" / filename, private[key])
    for case, packet in private["adjudication_packets"]["packets"].items():
        write_once(PRIVATE / "adjudication/packets" / f"{case}.json", packet)
    response_root = PRIVATE / "adjudication/responses"
    response_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_once(
        PRIVATE / "adjudication/response.schema.json",
        dict(
            type="object",
            additionalProperties=False,
            required=["case_id", "final_label", "completed"],
            properties=dict(
                case_id=dict(type="string", pattern=r"^sc-[a-f0-9]{24}$"),
                final_label=dict(type="string", enum=[x.value for x in TruthLabel]),
                rationale=dict(type="string", maxLength=8000),
                completed=dict(type="boolean", const=True),
            ),
        ),
    )
    recovered = thesis.sealed(
        dict(
            status="P031_MECHANICAL_RECOVERY_COMPLETE",
            preservation=recovery["preserved"],
            B_removed_field_kinds=recovery["B_removed_field_kinds"],
            direct_root_invalid_metadata_resolved=True,
            provenance_masters_preserved=recovery["provenance_masters_preserved"],
            P030_DS_Store_removed=len(recovery["P030_metadata_removed"]),
            P030_strict_verification="PASS",
            private_preservation_fingerprint=recovery["fingerprint"],
            aggregate_crosschecks=recovery["aggregate_crosschecks"],
            history=history,
        )
    )
    agreement_receipt = thesis.sealed(
        dict(
            statistics=pub["agreement"],
            adjudication_required=pub["human_adjudications_remaining"],
            response_fingerprints=pub["response_fingerprints"],
            caveat="Descriptive reviewer agreement, not objective truth or detector accuracy",
        )
    )
    complete = thesis.sealed(
        {k: v for k, v in pub.items() if k != "agreement"}
        | dict(
            recovery_fingerprint=recovered["fingerprint"],
            agreement_fingerprint=agreement_receipt["fingerprint"],
        )
    )
    for name, value in (
        ("response-recovery.json", recovered),
        ("security-human-agreement.json", agreement_receipt),
        ("review-completeness.json", complete),
    ):
        write_once(PUBLIC / name, value)
    with patch.object(readiness, "gate", gate):
        _, after = readiness.verify_packets()
    if history != after:
        raise ValueError("P031_POST_RECOVERY_FREEZE_DRIFT")
    return complete
