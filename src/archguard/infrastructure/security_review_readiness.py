"""P031 Outcome A: structural intake only. Never writes responses, labels or truth."""

import ast
import hashlib
import json
import os
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any
from unittest.mock import patch

from archguard.benchmark.oss.models import digest
from archguard.infrastructure import security_analysis_v1 as v1
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_benchmark as benchmark
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security_benchmark.protocol import ReviewPacket, ReviewResponse

SOURCE = "eaaabe47781f63bcad5d83885a5d71b940f9d758"
BASE = Path("experiments/security/security-human-review-v1")
PRIVATE = BASE / "private"
PUBLIC = BASE / "public"
SOURCES = (
    "src/archguard/infrastructure/security_review_readiness.py",
    "scripts/prompt031_security_readiness.py",
    "tests/security/test_review_readiness.py",
)
DOC = "docs/verification/PROMPT_031.md"
PUBLIC_FILES = ("readiness.json", "quality-verification.json", "freeze-index.json")
IGNORE = (
    "\n# Human Security review: missing inventories and real responses remain private.\n"
    "experiments/security/security-human-review-v1/private/\n"
)


def gate() -> None:
    allowed = (*SOURCES, DOC, ".gitignore", *(str(PUBLIC / n) for n in PUBLIC_FILES))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    if subprocess.run(
        ["git", "merge-base", "--is-ancestor", SOURCE, "HEAD"], capture_output=True
    ).returncode:
        raise ValueError("P031_LINEAGE_DRIFT")
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
        .decode()
        .splitlines()
    )
    if any(p not in allowed for p in changed):
        raise ValueError("P031_COMMITTED_SCOPE_DRIFT")
    original = subprocess.check_output(["git", "show", f"{SOURCE}:.gitignore"]).decode()
    if Path(".gitignore").read_text() != original + IGNORE:
        raise ValueError("P031_IGNORE_DRIFT")
    if subprocess.run(
        ["git", "check-ignore", "-q", str(PRIVATE / "responses/A")], capture_output=True
    ).returncode:
        raise ValueError("P031_PRIVATE_ROOT_NOT_IGNORED")
    if subprocess.check_output(["git", "ls-files", "--", str(PRIVATE)]):
        raise ValueError("P031_PRIVATE_DATA_TRACKED")


def safe(path: Path) -> None:
    if ".." in path.parts or any(
        p.is_symlink() or p.name.startswith(".env") for p in (path, *path.parents)
    ):
        raise ValueError("P031_UNSAFE_PATH")


def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in pairs:
        if k in result:
            raise ValueError("P031_DUPLICATE_JSON_FIELD")
        result[k] = v
    return result


def load(path: Path) -> dict[str, Any]:
    safe(path)
    if not path.is_file() or path.stat().st_size > 128_000:
        raise ValueError("P031_INVALID_INPUT_FILE")
    value = json.loads(path.read_bytes(), object_pairs_hook=unique)
    if not isinstance(value, dict):
        raise ValueError("P031_INVALID_JSON_OBJECT")
    return value


def verify_packets() -> tuple[dict[str, dict[str, ReviewPacket]], dict[str, Any]]:
    gate()
    with patch.object(v2, "gate", gate):
        prior = v2.verify()
    manifest = io.read_seal(benchmark.PUBLIC / "benchmark-manifest.json")
    if manifest["status"] != "P030_SECURITY_BENCHMARK_FOUNDATION_COMPLETE":
        raise ValueError("P031_P030_INCOMPLETE")
    pub = io.read_seal(benchmark.PUBLIC / "freeze-index.json")
    for name in benchmark.ARTIFACTS:
        path = benchmark.PUBLIC / name
        frozen = subprocess.check_output(["git", "show", f"{SOURCE}:{path}"])
        if io.sha(path) != hashlib.sha256(frozen).hexdigest():
            raise ValueError("P031_P030_GIT_BOUND_PIN_DRIFT")
    io.verify_files(
        benchmark.PUBLIC,
        pub["files"] | {"freeze-index.json": io.sha(benchmark.PUBLIC / "freeze-index.json")},
    )
    private_index = io.read_seal(
        benchmark.PRIVATE / "freeze-index.json", pub["private_freeze_fingerprint"]
    )
    # Hash-only inventory verification; do not decode construction metadata or regenerate cases.
    io.verify_files(
        benchmark.PRIVATE,
        private_index["files"]
        | {"freeze-index.json": io.sha(benchmark.PRIVATE / "freeze-index.json")},
    )
    for p, h in manifest["source_bindings"].items():
        if io.sha(Path(p)) != h:
            raise ValueError("P031_P030_SOURCE_DRIFT")
    for p, h in pub["documents"].items():
        if io.sha(Path(p)) != h:
            raise ValueError("P031_P030_DOCUMENT_DRIFT")
    sets: dict[str, dict[str, ReviewPacket]] = {}
    for slot in ("A", "B"):
        packets: dict[str, ReviewPacket] = {}
        raw_set = {}
        for path in sorted((benchmark.PRIVATE / "packets" / slot).glob("*.json")):
            raw = load(path)
            packet = ReviewPacket.model_validate(raw)
            if (
                packet.reviewer_slot != slot
                or path.stem != packet.evidence.case_id
                or path.stem in packets
            ):
                raise ValueError("P031_INVALID_PACKET_BINDING")
            packets[path.stem] = packet
            raw_set[f"packets/{slot}/{path.name}"] = raw
        if (
            len(packets) != 300
            or digest(raw_set)
            != manifest["fingerprints"][f"SECURITY_REVIEWER_{slot}_PACKET_SET_FINGERPRINT"]
        ):
            raise ValueError("P031_PACKET_SET_DRIFT")
        sets[slot] = packets
    if set(sets["A"]) != set(sets["B"]) or any(
        sets["A"][c].evidence != sets["B"][c].evidence for c in sets["A"]
    ):
        raise ValueError("P031_A_B_EVIDENCE_MISMATCH")
    return sets, dict(
        P030_freeze="PASS",
        P029_freeze=prior["status"],
        architecture_science="UNCHANGED",
        P030_manifest_fingerprint=manifest["fingerprint"],
        packet_schema_fingerprint=manifest["fingerprints"][
            "SECURITY_REVIEW_PACKET_SCHEMA_FINGERPRINT"
        ],
        response_schema_fingerprint=manifest["fingerprints"][
            "SECURITY_REVIEW_RESPONSE_SCHEMA_FINGERPRINT"
        ],
        packet_sets={
            s: manifest["fingerprints"][f"SECURITY_REVIEWER_{s}_PACKET_SET_FINGERPRINT"]
            for s in ("A", "B")
        },
    )


def inspect_responses(
    root: Path, sets: dict[str, dict[str, ReviewPacket]], *, human_attested: bool = False
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    safe(root)
    if root != PRIVATE or root.parts[-2:] != ("security-human-review-v1", "private"):
        raise ValueError("P031_UNEXPECTED_RESPONSE_ROOT")
    for slot in ("A", "B"):
        safe(root / "responses" / slot)
    files = {
        slot: sorted((root / "responses" / slot).iterdir())
        if (root / "responses" / slot).exists()
        else []
        for slot in ("A", "B")
    }
    for slot in ("A", "B"):
        safe(root / "responses" / slot)
    if any(files.values()) and not human_attested:
        raise ValueError("P031_HUMAN_ORIGIN_ATTESTATION_REQUIRED")
    identities = Counter(
        (p.stat().st_dev, p.stat().st_ino)
        for group in files.values()
        for p in group
        if not p.is_symlink() and p.is_file()
    )
    counts, missing = {}, {}
    for slot in ("A", "B"):
        completed: set[str] = set()
        invalid = 0
        for path in files[slot]:
            try:
                safe(path)
                if path.suffix != ".json" or path.stem not in sets[slot]:
                    raise ValueError("foreign case or file")
                stat = path.stat()
                if stat.st_nlink != 1 or identities[(stat.st_dev, stat.st_ino)] != 1:
                    raise ValueError("duplicate file alias")
                response = ReviewResponse.model_validate(load(path))
                packet = sets[slot][path.stem]
                if (
                    response.reviewer_slot != slot
                    or response.case_id != path.stem
                    or packet.response_destination != f"responses/{slot}/{path.name}"
                ):
                    raise ValueError("slot/case/frozen destination mismatch")
                if response.completed:
                    completed.add(response.case_id)
            except (ValueError, OSError):
                invalid += 1
        missing[slot] = sorted(set(sets[slot]) - completed)
        counts[slot] = dict(
            expected=len(sets[slot]),
            valid=len(completed),
            missing=len(missing[slot]),
            invalid=invalid,
            submitted_files=len(files[slot]),
        )
    return counts, missing


def dependency_guard() -> None:
    tree = ast.parse(Path(SOURCES[0]).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if name in {
                "run_security_analysis",
                "analyze",
                "metrics",
                "reconcile",
                "agreement",
                "generate",
                "eval",
                "exec",
            }:
                raise ValueError("P031_FORBIDDEN_LABEL_OR_EXECUTION_PATH")
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
            ("openai", "archguard.security.analyzer", "archguard.security.engine")
        ):
            raise ValueError("P031_DETECTOR_PROVIDER_DEPENDENCY")


def privacy(paths: tuple[Path, ...]) -> None:
    import re

    v1.privacy(paths)
    for path in paths:
        text = path.read_text()
        if (
            re.search(r"sc-[a-f0-9]{24}|\/Users\/|\/home\/", text)
            or path.suffix == ".json"
            and re.search(r'"(?:label|rationale|source_files|construction_intent)"\s*:', text)
        ):
            raise ValueError("P031_PUBLIC_PRIVATE_LEAKAGE")


def prepare() -> dict[str, Any]:
    sets, history = verify_packets()
    dependency_guard()
    safe(PRIVATE)
    previous = os.umask(0o077)
    try:
        for slot in ("A", "B"):
            (PRIVATE / "responses" / slot).mkdir(parents=True, exist_ok=True, mode=0o700)
        counts, missing = inspect_responses(PRIVATE, sets)
        value = dict(
            status="P031_HUMAN_REVIEW_AWAITING_RESPONSES",
            counts=counts,
            history=history,
            human_origin="NOT_PROVIDED",
            AI_GENERATED_BY_P031="NO",
            AI_GENERATED_LABELS=0,
            AI_ADJUDICATION=0,
            agreement="NOT_COMPUTED",
            adjudication="NOT_STARTED",
            DEV_truth="NOT_FROZEN",
            FINAL_truth="NOT_FROZEN",
            DEV_detector_predictions=0,
            FINAL_detector_predictions=0,
            Security_effectiveness="NOT_EVALUATED",
            provider_calls=0,
            connectivity_calls=0,
            credential_reads=0,
            paid_spend=0,
            UI="NOT_STARTED",
            P032="NOT_STARTED",
            next_action="WAITING_FOR_REAL_HUMAN_REVIEW",
            destinations={slot: str(PRIVATE / "responses" / slot) for slot in ("A", "B")},
            evidence_binding=(
                "frozen P030 packet + case ID + slot + exact response destination; "
                "frozen schema has no response fingerprint field"
            ),
            independence=dict(
                protocol_required=True,
                human_origin_attested=False,
                reviewer_noncommunication_proof="NOT_AVAILABLE",
                AI_shared_responses=False,
            ),
        )
        if any(c["valid"] == c["expected"] for c in counts.values()):
            raise ValueError("P031_OUTCOME_A_READINESS_ONLY; separate real-human freeze required")
        inventory = dict(status=value["status"], missing=missing)
        p = PRIVATE / "readiness/missing-response-inventory.json"
        if not p.exists():
            io.append_seal(p, inventory)
        elif io.read_seal(p) != thesis.sealed(inventory):
            raise ValueError("P031_READINESS_SNAPSHOT_DRIFT")
        return value | {"missing_inventory_fingerprint": digest(inventory)}
    finally:
        os.umask(previous)
