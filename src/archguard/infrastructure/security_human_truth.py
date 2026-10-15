"""P031.A.3: copy human adjudications and join frozen truth without semantic inference."""

import json
import os
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any, Literal
from unittest.mock import patch

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import security_review_readiness as readiness
from archguard.infrastructure import security_review_recovery as recovery
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security_benchmark.foundation import PredictionInputs
from archguard.security_benchmark.protocol import TruthLabel

BASE = "18eb49759f260c9ce288f40d8f77ed14d852ed6d"
PRIVATE = readiness.PRIVATE
PUBLIC = readiness.PUBLIC
ADJ = PRIVATE / "adjudication"
TRUTH = PRIVATE / "truth"
SOURCES = (
    "src/archguard/infrastructure/security_human_truth.py",
    "scripts/prompt031_security_truth.py",
    "tests/security/test_human_truth.py",
    "tests/security/test_review_provenance_binding.py",
)
PUBLIC_NAMES = (
    "security-human-truth-closure.json",
    "security-final-truth-custody.json",
    "truth-quality.json",
    "truth-freeze-index.json",
)
BANNER = (
    "Current status: **P031_SECURITY_HUMAN_TRUTH_COMPLETE**. "
    "Human truth 300 / DEV 100 / FINAL 200 is frozen; P032 is NOT_STARTED.\n\n"
    "The historical verification chronology below is retained verbatim.\n\n---\n\n"
)
RESPONSE_PINS = {
    "A": "e935ff30c565e3f6597fc7d4ef38928593666f607079e815dd56b27ee1beb20a",
    "B": "01e5b7e8f15be7dd0a2f0a055fed52e82307ebf69a273f9ba79490340f5e5b47",
}
PINS = {
    "review-completeness.json": "7754de726bf6a19748703253548b21e12fb2194be94388c3928419b101293f2a",
    "security-human-agreement.json": (
        "0bed58cc8a2ccdb2590d3bc27005b1d13fdec23d8ca1ddd1a3a905733578f0fb"
    ),
    "security-human-provenance-receipt.json": (
        "ccade82d8ea78888ae7b38e231d7927e9736dafb09a721c9fd2b384214372c3c"
    ),
}
DISAGREEMENT_PIN = "8a406d5992e03ba771d9e63c6fb72579b879367c167b9f7613c690f2b79791f4"
PACKET_PIN = "e0ba3d3f4240c08d574d07cbad6c155520dfd0fba0e66cf59930211a33fd8577"
FIELDS = ("case_id", "final_label", "rationale", "completed")
TRANSPORT_FIELDS = {"ordinal", "rule_id", "file", "reviewer_slot", "total"}
LABELS = tuple(x.value for x in TruthLabel)


class Adjudication(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(pattern=r"^sc-[a-f0-9]{24}$")
    final_label: Literal["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"]
    rationale: str = Field(default="", max_length=8000)
    completed: bool = Field(strict=True)

    @model_validator(mode="after")
    def complete(self) -> "Adjudication":
        if not self.completed:
            raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED")
        return self


def gate() -> None:
    allowed = (*SOURCES, readiness.DOC, *(str(PUBLIC / n) for n in PUBLIC_NAMES))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for sha in (
        "624eb05609e4e24f0cedcc50ce7a3587de0dcf60",
        readiness.SOURCE,
        recovery.SOURCE,
        "6b26a8ba876106efe44d4067c710ea3cea4047a4",
        "d717017ecc2db2a1ec46c77b6149d5c48b41ff34",
        BASE,
    ):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P031_A3_LINEAGE_DRIFT")
    changes = subprocess.check_output(["git", "diff", "--name-only", BASE, "HEAD"])
    if any(p not in allowed for p in changes.decode().splitlines()):
        raise ValueError("P031_A3_SCOPE_DRIFT")
    if Path(".gitignore").read_bytes() != subprocess.check_output(
        ["git", "show", f"{BASE}:.gitignore"]
    ) or subprocess.check_output(["git", "ls-files", "--", str(PRIVATE)]):
        raise ValueError("P031_A3_PRIVATE_IGNORE_DRIFT")
    for slot in ("A", "B"):
        if subprocess.run(
            ["git", "check-ignore", "-q", str(TRUTH / slot)], capture_output=True
        ).returncode:
            raise ValueError("P031_A3_TRUTH_NOT_IGNORED")
    parent = io.read_seal(
        PUBLIC / "resume-freeze-index.json",
        "8fc2f1ab0f55d1a2c785913b73eafdf725d98fb3422ca75837417cd38f83f2cd",
    )
    for name, h in parent["files"].items():
        if io.sha(PUBLIC / name) != h:
            raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    for p, h in parent["source_bindings"].items():
        if io.sha(Path(p)) != h:
            raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    original = subprocess.check_output(["git", "show", f"{BASE}:{readiness.DOC}"])
    current = Path(readiness.DOC).read_bytes()
    if not (current.startswith(original) or current.startswith(BANNER.encode() + original)):
        raise ValueError("P031_A3_REPORT_HISTORY_DRIFT")
    for p in recovery.DOCS:
        if p != readiness.DOC and io.sha(Path(p)) != parent["documents"][p]:
            raise ValueError("P031_A3_DOCUMENT_DRIFT")


def verify_history() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    gate()
    with patch.object(readiness, "gate", gate):
        sets, history = readiness.verify_packets()
    parent = io.read_seal(PUBLIC / "resume-freeze-index.json")
    old = io.read_seal(PRIVATE / "freeze-index.json", parent["private_custody_fingerprint"])
    if any(io.sha(PRIVATE / n) != h for n, h in old["files"].items()):
        raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    for name, fp in PINS.items():
        io.read_seal(PUBLIC / name, fp)
    prov = io.read_seal(PUBLIC / "security-human-provenance-receipt.json")
    rows = {}
    for slot in ("A", "B"):
        receipt = PRIVATE / "provenance" / slot / "authoritative-response-attestation.json"
        io.read_seal(receipt, prov["response_sets"][slot]["attestation_receipt_fingerprint"])
        frozen = io.read_seal(PRIVATE / "frozen" / f"reviewer-{slot}.json", RESPONSE_PINS[slot])
        raw = {
            c: recovery.read_object(PRIVATE / p.response_destination, 128_000)
            for c, p in sorted(sets[slot].items())
        }
        if frozen != thesis.sealed(dict(reviewer_slot=slot, responses=raw)):
            raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
        rows[slot] = raw
    counts, _ = readiness.inspect_responses(PRIVATE, sets, human_attested=True)
    if any(
        c != dict(expected=300, valid=300, missing=0, invalid=0, submitted_files=300)
        for c in counts.values()
    ):
        raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    conflict = io.read_seal(ADJ / "disagreement-inventory.json", DISAGREEMENT_PIN)
    packets = io.read_seal(ADJ / "packet-set.json", PACKET_PIN)
    index = recovery.read_object(ADJ / "index.json")
    entries = {}
    for entry in index["entries"]:
        case = entry["case_id"]
        if case in entries or entry["completed"] is not False:
            raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
        if entry["packet_path"] != str(ADJ / "packets" / f"{case}.json") or entry[
            "response_destination"
        ] != str(ADJ / "responses" / f"{case}.json"):
            raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
        entries[case] = entry
    if not (
        set(entries) == {r["case_id"] for r in conflict["cases"]} == set(packets["packets"])
        and len(entries) == 10
    ):
        raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    return rows, entries, history


def project(raw: dict[str, Any]) -> dict[str, Any]:
    if set(raw) - set(FIELDS) - TRANSPORT_FIELDS:
        raise ValueError("P031_A3_UNAPPROVED_TRANSPORT_FIELDS")
    value = {k: raw[k] for k in FIELDS if k in raw}
    try:
        Adjudication.model_validate(value)
    except ValidationError:
        raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED; invalid response schema") from None
    return value


def envelope(raw: bytes) -> tuple[dict[str, Any], bool]:
    text = raw.decode("utf-8")
    try:
        value = json.loads(text, object_pairs_hook=readiness.unique)
        repaired = False
    except json.JSONDecodeError as error:
        if error.pos < len(text.rstrip()) or error.msg != "Expecting ',' delimiter":
            raise ValueError("P031_A3_UNSUPPORTED_TRANSPORT_DAMAGE") from None
        value = json.loads(text.rstrip() + "}", object_pairs_hook=readiness.unique)
        repaired = True
    if not isinstance(value, dict):
        raise ValueError("P031_A3_INVALID_TRANSPORT_ENVELOPE")
    return value, repaired


def human_only(value: dict[str, Any]) -> None:
    value = {k.casefold(): v for k, v in value.items()}
    for key in (
        "ai_or_llm_assistance",
        "detector_tie_break",
        "construction_intent_tie_break",
        "answer_key_access",
    ):
        if value.get(key) in (True, "YES"):
            raise ValueError("P031_HUMAN_ADJUDICATION_REDO_REQUIRED")
    origin = value.get("human_origin_attestation", "")
    independence = value.get("independence_attestation", "")
    if not isinstance(origin, str) or not isinstance(independence, str):
        raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED; human-only provenance missing")
    if re.search(r"(?:ai|llms?).{0,20}(?:was|were|is)\s+(?:used|involved)", origin.casefold()):
        raise ValueError("P031_HUMAN_ADJUDICATION_REDO_REQUIRED")
    no_ai = value.get("ai_or_llm_assistance") in (False, "NO") or bool(
        re.search(
            r"(?:ai|llms?).{0,35}(?:not|не).{0,12}(?:used|involved|использ)|"
            r"(?:no|without).{0,15}(?:ai|llm)|не\s+использ.{0,35}(?:ai|llm)",
            origin.casefold(),
        )
    )
    personal = value.get("human_decision") in (True, "YES") or bool(
        re.search(
            r"person was involved|human|personally|myself|himself|herself|самостоятельно|лично",
            (origin + " " + independence).casefold(),
        )
    )
    independent = value.get("independent_decision_by_adjudicator") in (True, "YES") or bool(
        re.search(
            r"independent|myself|himself|herself|самостоятельно|лично|without anyone else",
            independence.casefold(),
        )
    )
    if not no_ai:
        raise ValueError("P031_HUMAN_ADJUDICATION_REDO_REQUIRED")
    if not personal or not independent:
        raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED; personal decision not attested")


def intake(entries: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    receipt_path = ADJ / "accepted/preservation.json"
    if receipt_path.exists():
        receipt = io.read_seal(receipt_path)
        if {p.name for p in (ADJ / "responses").iterdir()} != {f"{c}.json" for c in entries}:
            raise ValueError("P031_A3_WRONG_CANONICAL_DESTINATIONS")
        rows = {
            c: recovery.read_object(Path(e["response_destination"]), 128_000)
            for c, e in sorted(entries.items())
        }
        if rows != io.read_seal(ADJ / "accepted/source-manifest.json")["responses"]:
            raise ValueError("P031_A3_BLOCKED_HUMAN_ADJUDICATION_MUTATION")
        return rows, receipt
    root = ADJ / "responses"
    readiness.safe(root)
    paths = sorted(root.rglob("*"))
    for p in paths:
        readiness.safe(p)
    masters, sources, metadata = [], {}, []
    for path in paths:
        if path.is_dir():
            continue
        if path.name == ".DS_Store":
            if path.stat().st_nlink != 1 or path.read_bytes()[:8] != b"\x00\x00\x00\x01Bud1":
                raise ValueError("P031_A3_UNEXPECTED_METADATA")
            metadata.append(path)
            continue
        if path.suffix != ".json" or path.stat().st_nlink != 1 or path.stat().st_size > 4_000_000:
            raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED; unexpected input")
        raw = path.read_bytes()
        if path.parent == root and path.stem not in entries:
            wrapper, repaired = envelope(raw)
            if "responses" not in wrapper:
                raise ValueError("P031_A3_UNKNOWN_INPUT")
            masters.append((path, raw, wrapper, repaired))
            continue
        value = project(recovery.read_object(path, 128_000))
        case = value["case_id"]
        if case not in entries or case in sources:
            raise ValueError("P031_A3_DUPLICATE_OR_UNKNOWN_ADJUDICATION")
        sources[case] = (path, raw, value)
    if set(sources) != set(entries) or len(sources) != 10 or len(masters) != 1:
        raise ValueError("P031_HUMAN_ADJUDICATION_REQUIRED")
    master, original, wrapper, repaired = masters[0]
    human_only(wrapper)
    aggregate = {}
    for row in wrapper["responses"]:
        value = project(row)
        if value["case_id"] in aggregate:
            raise ValueError("P031_A3_DUPLICATE_AGGREGATE_CASE")
        aggregate[value["case_id"]] = value
    rows = {c: v for c, (_, _, v) in sorted(sources.items())}
    if aggregate != rows:
        raise ValueError("P031_A3_AGGREGATE_SOURCE_CONFLICT")
    manifest = thesis.sealed(
        dict(
            responses=rows,
            source_hashes={c: digest(raw.decode("utf-8")) for c, (_, raw, _) in sources.items()},
            aggregate_byte_hash=io.sha(master),
            original_source_paths={c: str(p) for c, (p, _, _) in sources.items()},
            aggregate_missing_closing_brace=repaired,
            ignored_transport_slot=wrapper.get("reviewer_slot"),
            ignored_transport_total=wrapper.get("total"),
        )
    )
    recovery.write_once(ADJ / "accepted/source-manifest.json", manifest)
    destination = ADJ / "provenance/original-aggregate.json"
    readiness.safe(destination)
    previous = os.umask(0o077)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.exists():
            if destination.read_bytes() != original:
                raise ValueError("P031_A3_PROVENANCE_CONFLICT")
        else:
            with destination.open("xb") as stream:
                stream.write(original)
    finally:
        os.umask(previous)
    for case, value in rows.items():
        target = Path(entries[case]["response_destination"])
        if not target.exists():
            recovery.write_once(target, value)
        if recovery.read_object(target) != value:
            raise ValueError("P031_A3_BLOCKED_HUMAN_ADJUDICATION_MUTATION")
    for case, (source, raw, _) in sources.items():
        if source.read_bytes() != raw:
            raise ValueError("P031_A3_SOURCE_CHANGED")
        if source != Path(entries[case]["response_destination"]):
            source.unlink()
    if destination.read_bytes() != original:
        raise ValueError("P031_A3_PROVENANCE_MUTATION")
    master.unlink()
    for path in metadata:
        path.unlink()
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            path.rmdir()
    if {p.name for p in root.iterdir()} != {f"{c}.json" for c in entries}:
        raise ValueError("P031_A3_WRONG_CANONICAL_DESTINATIONS")
    preservation = thesis.sealed(
        dict(
            source_decisions=10,
            canonical_decisions=10,
            final_labels_preserved=10,
            rationales_preserved=10,
            completed_preserved=10,
            semantic_changes=0,
            AI_rewrites=0,
            Astra_adjudications=0,
            human_origin="COORDINATOR_ATTESTED_HUMAN_ONLY",
            provenance_caveat="Procedural coordinator/human attestation; not cryptographic proof",
            source_manifest_fingerprint=manifest["fingerprint"],
            aggregate_original_preserved=True,
            aggregate_syntax_repaired_in_memory_only=repaired,
            transport_slot_ignored=True,
            transport_total_ignored=True,
            source_attestation="COORDINATOR_P031_A3_AND_PRIVATE_ORIGINAL",
        )
    )
    recovery.write_once(receipt_path, preservation)
    return rows, preservation


def derive(
    a: dict[str, str], b: dict[str, str], adjudications: dict[str, str]
) -> list[dict[str, str]]:
    """Join opaque supplied categories; this function never interprets evidence."""
    if set(a) != set(b):
        raise ValueError("P031_A3_REVIEWER_CASE_SET_MISMATCH")
    conflicts = {c for c in a if a[c] != b[c]}
    if conflicts != set(adjudications):
        raise ValueError("P031_A3_MISSING_DUPLICATE_OR_EXTRA_ADJUDICATION")
    return [
        dict(
            case_id=c,
            final_label=a[c] if c not in conflicts else adjudications[c],
            truth_source="A_B_AGREEMENT" if c not in conflicts else "HUMAN_ADJUDICATION",
        )
        for c in sorted(a)
    ]


def distribution(rows: list[dict[str, str]]) -> dict[str, Any]:
    counts = Counter(r["final_label"] for r in rows)
    if set(counts) - set(LABELS):
        raise ValueError("P031_A3_INVALID_TRUTH_ENUM")
    return dict(
        N=len(rows),
        labels={label: counts[label] for label in LABELS},
        binary_eligible=counts["POSITIVE"] + counts["NEGATIVE"],
    )


def build(
    reviewers: dict[str, Any], decisions: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    for row in decisions.values():
        Adjudication.model_validate(row)
    adjudicated = thesis.sealed(
        dict(responses=decisions, disagreement_packet_set_fingerprint=PACKET_PIN)
    )
    truth_rows = derive(
        {c: r["label"] for c, r in reviewers["A"].items()},
        {c: r["label"] for c, r in reviewers["B"].items()},
        {c: r["final_label"] for c, r in decisions.items()},
    )
    if len(truth_rows) != 300 or Counter(r["truth_source"] for r in truth_rows) != {
        "A_B_AGREEMENT": 290,
        "HUMAN_ADJUDICATION": 10,
    }:
        raise ValueError("P031_A3_INCOMPLETE_TRUTH")
    whole = thesis.sealed(
        dict(
            rows=truth_rows,
            response_set_fingerprints=RESPONSE_PINS,
            adjudication_response_fingerprint=adjudicated["fingerprint"],
            human_provenance_binding_fingerprint=PINS["security-human-provenance-receipt.json"],
        )
    )
    rosters, splits, split_sets = {}, {}, {}
    by_case = {r["case_id"]: r for r in truth_rows}
    case_meta = {}
    for split, n in (("DEV", 100), ("FINAL", 200)):
        roster = recovery.read_object(benchmark.PRIVATE / "prediction" / split / "roster.json")
        if set(roster) != {"cases"} or len(roster["cases"]) != n:
            raise ValueError("P031_A3_SPLIT_ROSTER_DRIFT")
        for r in roster["cases"]:
            if set(r) != {"case_id", "rule_id", "language", "source_paths"}:
                raise ValueError("P031_A3_FORBIDDEN_ROSTER_METADATA")
            if r["case_id"] in case_meta or r["case_id"] not in by_case:
                raise ValueError("P031_A3_SPLIT_OVERLAP_OR_UNKNOWN")
            case_meta[r["case_id"]] = r
        ids = {r["case_id"] for r in roster["cases"]}
        if len(ids) != n:
            raise ValueError("P031_A3_DUPLICATE_SPLIT_CASE")
        split_sets[split] = ids
        rosters[split] = roster
        splits[split] = thesis.sealed(
            dict(
                split=split,
                rows=[by_case[c] for c in sorted(ids)],
                human_truth_300_fingerprint=whole["fingerprint"],
                roster_fingerprint=digest(roster),
            )
        )
    if split_sets["DEV"] & split_sets["FINAL"] or set(case_meta) != set(by_case):
        raise ValueError("P031_A3_SPLIT_COVERAGE_DRIFT")
    source_root = benchmark.PRIVATE / "prediction/FINAL/sources"
    capability = PredictionInputs(source_root, tuple(rosters["FINAL"]["cases"]))
    source_hashes = {name: io.sha(source_root / name) for name in sorted(capability.paths)}
    for prohibited in (
        str(TRUTH / "FINAL/truth.json"),
        str(PRIVATE / "responses/A"),
        str(ADJ / "responses"),
        "../truth.json",
        "/truth.json",
    ):
        try:
            capability.read(prohibited)
        except ValueError:
            pass
        else:
            raise ValueError("P031_A3_FINAL_TRUTH_CAPABILITY_LEAK")
    policy = thesis.sealed(
        dict(
            source_root=str(source_root),
            sanitized_roster=str(benchmark.PRIVATE / "prediction/FINAL/roster.json"),
            source_hashes=source_hashes,
            final_truth_fingerprint=splits["FINAL"]["fingerprint"],
            source_only_capability_verified=True,
            worker_started=False,
            P032="NOT_STARTED",
            future_worker_mount_allowlist=[
                str(source_root),
                str(benchmark.PRIVATE / "prediction/FINAL/roster.json"),
            ],
            forbidden_mount_categories=[
                "truth",
                "reviewer_responses",
                "adjudication_responses",
                "construction_intent",
            ],
            future_os_isolated_mount_required=True,
            boundary=(
                "Application allowlist verified; no future worker has been launched or mounted"
            ),
            final_join_requires="Frozen predictions and later explicit truth-open authorization",
        )
    )
    custody = thesis.sealed(
        dict(
            status="FINAL_TRUTH_PRIVATE_SOURCE_ONLY_PREDICTION_CAPABILITY_VERIFIED",
            final_truth_fingerprint=splits["FINAL"]["fingerprint"],
            private_custody_policy_fingerprint=policy["fingerprint"],
            final_N=200,
            source_file_count=len(source_hashes),
            truth_read_capability_granted=False,
            reviewer_response_capability_granted=False,
            adjudication_response_capability_granted=False,
            intent_capability_granted=False,
            worker_started=False,
            P032="NOT_STARTED",
            OS_boundary="Required at future worker launch; no worker or mount exists in P031",
            predictions_must_freeze_before_truth_join=True,
        )
    )
    groups = {"ALL": truth_rows, "DEV": splits["DEV"]["rows"], "FINAL": splits["FINAL"]["rows"]}
    for field, values in (
        ("language", ("JAVA", "TYPESCRIPT")),
        ("rule_id", tuple(f"SEC{i:03}" for i in range(1, 11))),
    ):
        for value in values:
            groups[value] = [r for r in truth_rows if case_meta[r["case_id"]][field] == value]
    closure = thesis.sealed(
        dict(
            status="P031_SECURITY_HUMAN_TRUTH_COMPLETE",
            N=300,
            agreement_derived=290,
            adjudication_derived=10,
            distributions={g: distribution(v) for g, v in groups.items()},
            adjudication_intake=dict(
                expected=10,
                valid=10,
                missing=0,
                invalid=0,
                duplicates=0,
                unknown=0,
                wrong_destination=0,
                wrong_case_binding=0,
                semantic_changes=0,
            ),
            human_adjudication_origin="COORDINATOR_ATTESTED_HUMAN_ONLY",
            adjudications_accepted=10,
            adjudications_remaining=0,
            response_set_fingerprints=RESPONSE_PINS,
            preserved_prior_fingerprints=PINS,
            agreement=dict(
                N=300,
                exact_agreements=290,
                disagreements=10,
                raw_agreement=290 / 300,
                cohens_kappa=7959 / 8459,
            ),
            fingerprints=dict(
                adjudication_response_set=adjudicated["fingerprint"],
                human_truth_300=whole["fingerprint"],
                DEV_truth=splits["DEV"]["fingerprint"],
                FINAL_truth=splits["FINAL"]["fingerprint"],
                final_truth_custody=custody["fingerprint"],
            ),
            truth_frozen=True,
            DEV_truth="FROZEN",
            FINAL_truth="FROZEN",
            AI_generated_labels=0,
            AI_rewritten_labels=0,
            AI_adjudication=0,
            DEV_detector_predictions=0,
            FINAL_detector_predictions=0,
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
            next_action="READY_FOR_P032_SECURITY_DEV_EVALUATION",
        )
    )
    return dict(closure=closure, custody=custody), dict(
        adjudications=adjudicated,
        whole=whole,
        DEV=splits["DEV"],
        FINAL=splits["FINAL"],
        policy=policy,
    )


def run() -> dict[str, Any]:
    reviewers, entries, before = verify_history()
    decisions, preservation = intake(entries)
    public, private = build(reviewers, decisions)
    again, again_private = build(reviewers, decisions)
    if canonical((public, private)) != canonical((again, again_private)):
        raise ValueError("P031_A3_NONDETERMINISTIC_TRUTH_BUILD")
    for key, path in (
        ("adjudications", ADJ / "accepted/response-set.json"),
        ("whole", TRUTH / "human-truth-300.json"),
        ("DEV", TRUTH / "DEV/truth.json"),
        ("FINAL", TRUTH / "FINAL/truth.json"),
        ("policy", TRUTH / "final-custody-policy.json"),
    ):
        recovery.write_once(path, private[key])
    recovery.write_once(PUBLIC / "security-final-truth-custody.json", public["custody"])
    recovery.write_once(PUBLIC / "security-human-truth-closure.json", public["closure"])
    recovery.privacy(
        (PUBLIC / "security-final-truth-custody.json", PUBLIC / "security-human-truth-closure.json")
    )
    _, _, after = verify_history()
    if any(
        recovery.read_object(Path(entries[c]["response_destination"])) != v
        for c, v in decisions.items()
    ):
        raise ValueError("P031_A3_BLOCKED_HUMAN_ADJUDICATION_MUTATION")
    if before != after or preservation["semantic_changes"] != 0:
        raise ValueError("P031_A3_BLOCKED_FREEZE_DRIFT")
    return dict(public["closure"])
