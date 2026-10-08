"""Source-only P021 handoffs and formal, append-only future human intake; no inference."""

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.semantic_review import (
    ReviewerABundle,
    ReviewerASubmission,
    ReviewerBBundle,
    ReviewerBSubmission,
    validate_submission,
)
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal
from archguard.infrastructure.semantic_review import audit_bundle

Role = Literal["A", "B"]
ROLES: tuple[Role, ...] = ("A", "B")
Bundle = ReviewerABundle | ReviewerBBundle
Submission = ReviewerASubmission | ReviewerBSubmission
BASE = Path("experiments/unified-hybrid")
PRIVATE = BASE / "private/unified-hybrid-experiment-v1"
FINAL = PRIVATE / "final"
REVIEW = FINAL / "review-v2"
HANDOFF = PRIVATE / "human-handoff"
WORKTREE_EXCEPTION = "index(визуал).html"
COMMITS = {
    "P017": "8a11b012dadde660318053f2cb6845703cae7547",
    "P018": "264e7cc237f96714fc1d066d04418944e397a6e2",
    "P019": "2f596fb57b00a1d8374cdcba50a98ab6ffbe4023",
    "P020_ALIGNMENT": "b16e91b99708cc84bfec88c63c9dcef62c67bc92",
    "P020_HOLDOUT": "8d561c9c33a35bb8ce8717ff7020d8e212ad0505",
    "P020_CORRECTION": "29e9c1782d3ec60b65d4e1f1bb1ad721f4d03758",
    "P020_CLOSURE": "1891fa553218200139f027ed9c3a82d100f61462",
}
PINS = {
    BASE / "p020-final-holdout-freeze-v1.json": (
        "fad0026e938a04a626fcf3b4ce73a8c78d05f6f1835ad42f4db1e03fc5d5be06"
    ),
    FINAL
    / "inputs/manifest.json": "44f397e9ea9660dc270744338a175ccfc78b742a9cc014a455492c50b46b31a7",
    FINAL
    / "evidence/evidence.json": "bcefd040216b64a1d636a155ec2b62b6aeb9d089be92405d9899874c86971633",
    FINAL
    / "requests/contexts.json": "852f827060673d7189aecf72b1d4f81d19617d7c9e171868dd3230ac568d8c22",
    FINAL
    / "requests/manifest.json": "efa1dec52b7694122e6b13779ed1b9683b771c0fc6cd4031f5c16b8671d2e507",
    BASE / "p020-hybrid-protocol-v1.json": (
        "331ffb2bc8d9c9d8b99c2bd4d12fd5e929ba50b584b02eb49360b2e9eba2b77a"
    ),
    BASE / "p020-ablation-protocol-v1.json": (
        "b0f57d269f7c945afa10d9ecd604700d1c1892eb95a98dac2e197fed0dc4b959"
    ),
    BASE
    / "p020-registry-v2.json": "2bec29bb5d19419d90e8a5627a49044c82c33f7f13528116d587ade70d0a4116",
    REVIEW
    / "packet-inventory.json": "0fe24c499e544e24343c0bceb5fa0367e0a6af946b3878954ce053fa3ad60843",
    REVIEW / "assignment-manifest.json": (
        "dd51cb05ff374f07ac21cc9b2906351c5d18c90a596150b08b4719745a2eedbc"
    ),
    BASE / "p020-blinded-review-handoff-v2.json": (
        "dcc25eb58fcb25055de10c17ea94c5796edf7ae81f30e4c575f417c8d041f3aa"
    ),
}
PROTOCOL_PATH = BASE / "p021-a-human-review-protocol-v1.json"
SOURCE_FILES = (
    "src/archguard/infrastructure/unified_human_review.py",
    "scripts/prompt021a_human_handoff.py",
    "tests/benchmark/test_unified_human_review.py",
)
PUBLIC_FILES = (
    *SOURCE_FILES,
    PROTOCOL_PATH.as_posix(),
    (BASE / "p021-a-handoff-readiness-v1.json").as_posix(),
    (BASE / "p021-a-verification-v1.json").as_posix(),
    "docs/verification/PROMPT_021_A.md",
)
_CAPABILITY: ContextVar[tuple[Path, tuple[Path, ...], tuple[Path, ...]] | None] = ContextVar(
    "p021_review_io", default=None
)


class ReviewBlocked(ValueError):
    """Safe error codes only; never leak source, human answers or credentials."""


def offline_guard(event: str, args: tuple[Any, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "urllib.Request", "http.client.connect"}:
        raise PermissionError("P021_A_NO_NETWORK")
    if event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0]))
    if any(p.startswith(".env") for p in path.parts):
        raise PermissionError("P021_A_NO_CREDENTIAL_ACCESS")
    policy = _CAPABILITY.get()
    if policy is None:
        return
    root, inputs, outputs = policy
    resolved = path.resolve()
    if root != resolved and root not in resolved.parents:
        return
    writes = any(c in (args[1] or "") for c in "wax+") or bool(
        args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
    )
    if any(resolved == p or p in resolved.parents for p in outputs):
        return
    if not writes and any(resolved == p or p in resolved.parents for p in inputs):
        return
    raise PermissionError("P021_A_PRIVATE_CAPABILITY_DENIED")


@contextmanager
def handoff_capability(repository: Path) -> Iterator[None]:
    token = _CAPABILITY.set(
        (
            (repository / PRIVATE).resolve(),
            tuple((repository / p).resolve() for p in (*PINS, REVIEW)),
            ((repository / HANDOFF).resolve(),),
        )
    )
    try:
        yield
    finally:
        _CAPABILITY.reset(token)


def _safe_path(path: Path) -> None:
    if path.name == WORKTREE_EXCEPTION or any(
        p.name.startswith(".env") or p.is_symlink() for p in (path, *path.parents)
    ):
        raise ReviewBlocked("P021_A_UNSAFE_PATH")


def sha(path: Path) -> str:
    _safe_path(path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ReviewBlocked("P021_A_DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _json(raw: bytes) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_unique)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise ReviewBlocked("P021_A_INVALID_JSON") from None


def read_seal(path: Path, expected: str | None = None) -> dict[str, Any]:
    _safe_path(path)
    value = _json(path.read_bytes())
    payload = {k: v for k, v in value.items() if k != "fingerprint"}
    if value.get("fingerprint") != digest(payload) or (
        expected is not None and value["fingerprint"] != expected
    ):
        raise ReviewBlocked("P021_A_BLOCKED_REVIEW_V2_DRIFT")
    return value


def append_seal(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    _safe_path(path)
    value = payload | {"fingerprint": digest(payload)}
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("xb") as stream:
        stream.write((canonical(value) + "\n").encode())
    path.chmod(0o600)
    return value


def verify_files(root: Path, expected: dict[str, str], *, recover_ds_store: bool = False) -> bool:
    """Exact frozen inventory; only an explicitly requested root .DS_Store recovery."""
    _safe_path(root)
    directories: set[str] = set()
    for name in expected:
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or name != relative.as_posix():
            raise ReviewBlocked("P021_A_UNSAFE_INVENTORY")
        directories.update(p.as_posix() for p in relative.parents if p != Path("."))
    paths = tuple(root.rglob("*"))
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ReviewBlocked("P021_A_UNSAFE_INVENTORY")
    actual = {p.relative_to(root).as_posix() for p in paths}
    wanted = set(expected) | directories
    if wanted - actual or any(sha(root / n) != h for n, h in expected.items()):
        raise ReviewBlocked("P021_A_INVENTORY_DRIFT")
    extras = actual - wanted
    removed = False
    if extras:
        metadata = root / ".DS_Store"
        if (
            not recover_ds_store
            or extras != {".DS_Store"}
            or any(Path(n).name == ".DS_Store" for n in expected)
            or not metadata.is_file()
        ):
            raise ReviewBlocked("P021_A_UNEXPECTED_ENTRY")
        metadata.unlink()
        removed = True
    if {p.relative_to(root).as_posix() for p in root.rglob("*")} != wanted or any(
        sha(root / n) != h for n, h in expected.items()
    ):
        raise ReviewBlocked("P021_A_INVENTORY_DRIFT")
    return removed


def scientific_status(raw: bytes, allowed: tuple[str, ...] = ()) -> None:
    entries = raw.decode().split("\0")
    if f" D {WORKTREE_EXCEPTION}" not in entries:
        raise ReviewBlocked("P021_A_BLOCKED_UNEXPECTED_WORKTREE_STATE")
    for entry in filter(None, entries):
        if entry == f" D {WORKTREE_EXCEPTION}":
            continue
        if entry[:2] not in {"??", " M", "A ", "M "} or entry[3:] not in allowed:
            raise ReviewBlocked("P021_A_BLOCKED_UNEXPECTED_WORKTREE_STATE")


def verify_lineage(repository: Path, *, allowed: tuple[str, ...] = ()) -> dict[str, str]:
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"], cwd=repository
    )
    scientific_status(status, allowed)
    for commit in COMMITS.values():
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
            cwd=repository,
            capture_output=True,
        ).returncode:
            raise ReviewBlocked("P021_A_BLOCKED_LINEAGE")
    for relative, fingerprint in PINS.items():
        path = repository / relative
        _safe_path(path)
        try:
            verify_opaque_seal(path, fingerprint)
        except ValueError:
            raise ReviewBlocked("P021_A_BLOCKED_REVIEW_V2_DRIFT") from None
    return dict(COMMITS)


def authoritative_path(path: Path, repository: Path) -> None:
    _safe_path(path)
    if path.resolve() != (repository / REVIEW).resolve():
        raise ReviewBlocked("P021_A_LEGACY_OR_UNAUTHORIZED_HANDOFF")


def verify_blind_bundle(bundle: Bundle) -> None:
    audit_bundle(bundle)
    ids = [p.blinded_id for p in bundle.packets]
    if ids != sorted(ids, key=lambda i: digest(("p020-review-order-v2", bundle.reviewer_slot, i))):
        raise ReviewBlocked("P021_A_ORDER_DRIFT")


@dataclass(frozen=True)
class Authority:
    repository: Path
    root: Path
    bundles: dict[Role, Bundle]
    files: dict[str, str]
    assignment_fingerprint: str
    material_fingerprint: str


def load_authority(repository: Path, path: Path | None = None) -> Authority:
    root = repository / REVIEW if path is None else path
    authoritative_path(root, repository)
    receipt = read_seal(
        repository / BASE / "p020-blinded-review-handoff-v2.json",
        PINS[BASE / "p020-blinded-review-handoff-v2.json"],
    )
    material = read_seal(root / "material-freeze.json", receipt["material_fingerprint"])
    expected = {
        "assignment-manifest.json",
        "guidance.json",
        "packet-inventory.json",
        "protocol.json",
        *(
            f"{role}/{name}"
            for role in ("A", "B")
            for name in ("bundle.json", "submission-schema.json", "submission-template.json")
        ),
    }
    if set(material["files"]) != expected:
        raise ReviewBlocked("P021_A_MATERIAL_INVENTORY_DRIFT")
    verify_files(
        root, material["files"] | {"material-freeze.json": sha(root / "material-freeze.json")}
    )
    inventory = read_seal(root / "packet-inventory.json", PINS[REVIEW / "packet-inventory.json"])
    assignment = read_seal(
        root / "assignment-manifest.json", PINS[REVIEW / "assignment-manifest.json"]
    )
    rows = inventory["rows"]
    packets = {r["blinded_id"]: r["packet_fingerprint"] for r in rows}
    if len(rows) != 100 or len(packets) != 100:
        raise ReviewBlocked("P021_A_PACKET_COUNT_DRIFT")
    if [r["blinded_id"] for r in rows] != sorted(
        packets, key=lambda i: digest(("p020-review-order-v2", "INVENTORY", i))
    ):
        raise ReviewBlocked("P021_A_ORDER_DRIFT")
    bundles: dict[Role, Bundle] = {}
    for role in ROLES:
        model = ReviewerABundle if role == "A" else ReviewerBBundle
        submission = ReviewerASubmission if role == "A" else ReviewerBSubmission
        bundle = model.model_validate(_json((root / role / "bundle.json").read_bytes()))
        verify_blind_bundle(bundle)
        if {p.blinded_id: p.fingerprint for p in bundle.packets} != packets:
            raise ReviewBlocked("P021_A_CASE_SET_DRIFT")
        if bundle.protocol != read_seal(
            root / "protocol.json", receipt["protocol_fingerprint"]
        ) or (bundle.guidance != read_seal(root / "guidance.json")):
            raise ReviewBlocked("P021_A_GUIDANCE_DRIFT")
        schema = read_seal(root / role / "submission-schema.json")
        if schema["schema"] != submission.model_json_schema():
            raise ReviewBlocked("P021_A_SCHEMA_DRIFT")
        template = _json((root / role / "submission-template.json").read_bytes())
        blank: dict[str, Any] = dict(
            schema_version="semantic-holdout-human-submission-v1",
            reviewer_slot=role,
            bundle_fingerprint=bundle.fingerprint,
            reviewer_identity="",
            attestation="",
            responses=[
                dict(blinded_id=p.blinded_id, decision=None, rationale="", evidence=[], note="")
                for p in bundle.packets
            ],
        )
        if template != blank:
            raise ReviewBlocked("P021_A_NONBLANK_OR_EXTENDED_FORM")
        bundles[role] = bundle
    if [p.blinded_id for p in bundles["A"].packets] == [p.blinded_id for p in bundles["B"].packets]:
        raise ReviewBlocked("P021_A_REVIEWER_ORDER_NOT_INDEPENDENT")
    if assignment["rows"] != [
        dict(reviewer_slot=r, bundle_fingerprint=bundles[r].fingerprint, packet_count=100)
        for r in ROLES
    ]:
        raise ReviewBlocked("P021_A_ASSIGNMENT_DRIFT")
    return Authority(
        repository,
        root,
        bundles,
        material["files"],
        assignment["fingerprint"],
        material["fingerprint"],
    )


def instructions(role: Role) -> bytes:
    if role not in {"A", "B"}:
        raise ReviewBlocked("P021_A_INVALID_ROLE")
    return f"""Reviewer {role}: independent HUMAN review of 100 assigned cases

Use ONLY your own package. Keep its frozen files unchanged. bundle.json contains
the frozen case order, target questions, architecture contracts and source evidence.
Read the supplied guidance.json and protocol.json. Do not browse the internet,
repository or other case material. Ordinary text editors and viewers are allowed.

Choose exactly one category per case using the frozen rule question:
POSITIVE: applicable question, sufficient context, concrete violation evidence.
NEGATIVE: applicable question and sufficient source/context to justify absence
of that violation.
UNCERTAIN: insufficient context, ambiguous role/boundary or unresolved interpretation.
OUT_OF_SCOPE: the question does not apply.
UNCERTAIN and OUT_OF_SCOPE remain distinct; neither is a negative answer.

Copy submission-template.json to completed-response.json. For each opaque
blinded_id, set decision, write your own nonempty rationale, and provide at least
one supplied evidence_id with inclusive start_line/end_line. Count lines starting
at 1 inside the decoded source evidence text, NOT inside the bundle JSON file.
The lines must belong to that case's evidence; do not invent references. An optional
note may describe limitations. Keep all IDs, the role and bundle_fingerprint intact.
Do not add fields. No category is preselected. All 100 cases must be completed.

Make the judgments and write rationales yourself. Do NOT use ChatGPT, Claude,
Gemini, Copilot, any other LLM, or an automatic architecture classifier for help.
Do not discuss answers, consult the other reviewer, or exchange completed forms
before BOTH independent submissions are frozen. Return your copy ONLY to the
coordinator, privately. Do not start adjudication yourself.

Use a stable opaque identifier of the form human- followed by 32 lowercase hex
characters in reviewer_identity. Do not enter a real name, email or account ID.
The coordinator privately verifies distinct people; pseudonyms and self-attestation
alone cannot prove identity, authorship or independence. Set attestation to
REAL_HUMAN_INDEPENDENT_REVIEW only after performing your own review of all cases.

Return your unchanged package plus completed-response.json. Do not overwrite the
blank template. Accepted answers freeze separately and cannot be overwritten.
Corrections require an explicit new human correction version, reason and receipt;
the original response is retained. No answer is automatically corrected.
""".encode()


def prepare_handoff(authority: Authority, role: Role, destination: Path) -> dict[str, Any]:
    authoritative_path(authority.root, authority.repository)
    bundle = authority.bundles[role]
    copies = {
        "bundle.json": f"{role}/bundle.json",
        "submission-schema.json": f"{role}/submission-schema.json",
        "submission-template.json": f"{role}/submission-template.json",
        "guidance.json": "guidance.json",
        "protocol.json": "protocol.json",
    }
    _safe_path(destination)
    receipt: dict[str, Any] = {}

    def build(stage: Path) -> None:
        nonlocal receipt
        stage.chmod(0o700)
        files = {}
        for name, original in copies.items():
            raw = (authority.root / original).read_bytes()
            if hashlib.sha256(raw).hexdigest() != authority.files[original]:
                raise ReviewBlocked("P021_A_COPY_SOURCE_DRIFT")
            target = stage / name
            with target.open("xb") as stream:
                stream.write(raw)
            target.chmod(0o600)
            files[name] = sha(target)
        (stage / "README.txt").write_bytes(instructions(role))
        (stage / "README.txt").chmod(0o600)
        files["README.txt"] = sha(stage / "README.txt")
        receipt = append_seal(
            stage / "handoff-receipt.json",
            dict(
                schema_version="p021-a-human-handoff-receipt-v1",
                role=role,
                expected_file_count=len(files),
                manifest_fingerprint=authority.material_fingerprint,
                assignment_fingerprint=authority.assignment_fingerprint,
                files=files,
                byte_inventory_fingerprint=digest(files),
                source_byte_inventory_fingerprint=digest({n: files[n] for n in copies}),
                copy_verification="BYTE_IDENTICAL",
                creation_verification="PASS",
            ),
        )
        verify_files(stage, files | {"handoff-receipt.json": sha(stage / "handoff-receipt.json")})
        if _json((stage / "bundle.json").read_bytes())["fingerprint"] != bundle.fingerprint:
            raise ReviewBlocked("P021_A_COPY_SOURCE_DRIFT")

    atomic_directory(destination, build)
    return receipt


def verify_handoff(authority: Authority, role: Role, destination: Path) -> dict[str, Any]:
    authoritative_path(authority.root, authority.repository)
    receipt = read_seal(destination / "handoff-receipt.json")
    expected = {
        "bundle.json": authority.files[f"{role}/bundle.json"],
        "submission-schema.json": authority.files[f"{role}/submission-schema.json"],
        "submission-template.json": authority.files[f"{role}/submission-template.json"],
        "guidance.json": authority.files["guidance.json"],
        "protocol.json": authority.files["protocol.json"],
        "README.txt": hashlib.sha256(instructions(role)).hexdigest(),
    }
    payload = dict(
        schema_version="p021-a-human-handoff-receipt-v1",
        role=role,
        expected_file_count=6,
        manifest_fingerprint=authority.material_fingerprint,
        assignment_fingerprint=authority.assignment_fingerprint,
        files=expected,
        byte_inventory_fingerprint=digest(expected),
        source_byte_inventory_fingerprint=digest(
            {n: h for n, h in expected.items() if n != "README.txt"}
        ),
        copy_verification="BYTE_IDENTICAL",
        creation_verification="PASS",
    )
    if receipt != payload | {"fingerprint": digest(payload)}:
        raise ReviewBlocked("P021_A_HANDOFF_RECEIPT_DRIFT")
    verify_files(
        destination, expected | {"handoff-receipt.json": sha(destination / "handoff-receipt.json")}
    )
    return receipt


def validate_intake(bundle: Bundle, raw: bytes) -> Submission:
    """Check only schema, assignment, evidence bounds and pseudonymous attestation."""
    data = _json(raw)
    try:
        submission: Submission = (
            ReviewerASubmission.model_validate(data)
            if bundle.reviewer_slot == "A"
            else ReviewerBSubmission.model_validate(data)
        )
        validate_submission(bundle, submission)
    except ValueError:
        raise ReviewBlocked("P021_A_FORM_OR_ASSIGNMENT_INVALID") from None
    if re.fullmatch(r"human-[a-f0-9]{32}", submission.reviewer_identity) is None:
        raise ReviewBlocked("P021_A_OPAQUE_REVIEWER_ID_REQUIRED")
    return submission


def validate_intake_directory(
    bundle: Bundle, directory: Path, manifest_fingerprint: str, *, recover_ds_store: bool = False
) -> Submission:
    """Future coordinator-pinned byte snapshot; never trust a submission's own inventory."""
    manifest_path = directory / "intake-manifest.json"
    manifest = read_seal(manifest_path, manifest_fingerprint)
    if (
        set(manifest) != {"schema_version", "role", "bundle_fingerprint", "files", "fingerprint"}
        or manifest["schema_version"] != "p021-human-intake-snapshot-v1"
        or manifest["role"] != bundle.reviewer_slot
        or manifest["bundle_fingerprint"] != bundle.fingerprint
        or set(manifest["files"]) != {"completed-response.json"}
    ):
        raise ReviewBlocked("P021_A_INTAKE_MANIFEST_INVALID")
    expected = manifest["files"] | {"intake-manifest.json": sha(manifest_path)}
    verify_files(directory, expected, recover_ds_store=recover_ds_store)
    raw = (directory / "completed-response.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != manifest["files"]["completed-response.json"]:
        raise ReviewBlocked("P021_A_INVENTORY_DRIFT")
    submission = validate_intake(bundle, raw)
    verify_files(directory, expected)
    return submission


@dataclass(frozen=True)
class HumanCorrection:
    previous_receipt_fingerprint: str
    reason: str
    attestation: Literal["REAL_HUMAN_EXPLICIT_CORRECTION"]


def verify_accepted(path: Path) -> dict[str, Any]:
    receipt = read_seal(path / "receipt.json")
    files = {
        "submission.json": receipt["submission_sha256"],
        "receipt.json": sha(path / "receipt.json"),
    }
    if receipt["version"] > 1:
        files["human-correction.json"] = receipt["correction_sha256"]
    verify_files(path, files)
    return receipt


def freeze_intake(
    bundle: Bundle, raw: bytes, store: Path, *, correction: HumanCorrection | None = None
) -> dict[str, Any]:
    """Future library operation. P021.A uses this only with synthetic temporary fixtures."""
    submission = validate_intake(bundle, raw)
    _safe_path(store)
    role = bundle.reviewer_slot
    if store.exists() and any(p.name not in {"A", "B"} or not p.is_dir() for p in store.iterdir()):
        raise ReviewBlocked("P021_A_UNEXPECTED_ENTRY")
    role_root = store / role
    previous: dict[str, Any] | None = None
    identity = submission.reviewer_identity
    for other in ("A", "B"):
        parent = store / other
        _safe_path(parent)
        versions = sorted(parent.iterdir()) if parent.exists() else []
        for index, path in enumerate(versions, 1):
            if path.name != f"v{index:04d}" or not path.is_dir():
                raise ReviewBlocked("P021_A_INTAKE_VERSION_DRIFT")
            prior_receipt = verify_accepted(path)
            if prior_receipt["role"] != other or prior_receipt["version"] != index:
                raise ReviewBlocked("P021_A_INTAKE_VERSION_DRIFT")
            prior_identity = _json((path / "submission.json").read_bytes())["reviewer_identity"]
            if other != role and prior_identity == identity:
                raise ReviewBlocked("P021_A_DISTINCT_REVIEWERS_REQUIRED")
            if other == role:
                if (
                    prior_receipt["bundle_fingerprint"] != bundle.fingerprint
                    or prior_identity != identity
                ):
                    raise ReviewBlocked("P021_A_CORRECTION_ASSIGNMENT_DRIFT")
                if prior_receipt["previous_receipt_fingerprint"] != (
                    previous["fingerprint"] if previous else None
                ):
                    raise ReviewBlocked("P021_A_INTAKE_VERSION_DRIFT")
                previous = prior_receipt
    if previous is not None and correction is None:
        raise ReviewBlocked("P021_A_ACCEPTED_SUBMISSION_IMMUTABLE")
    if correction is not None and (
        previous is None
        or correction.previous_receipt_fingerprint != previous["fingerprint"]
        or not correction.reason.strip()
        or correction.attestation != "REAL_HUMAN_EXPLICIT_CORRECTION"
    ):
        raise ReviewBlocked("P021_A_EXPLICIT_HUMAN_CORRECTION_REQUIRED")
    version = previous["version"] + 1 if previous else 1
    role_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    role_root.chmod(0o700)
    store.chmod(0o700)
    receipt: dict[str, Any] = {}

    def build(stage: Path) -> None:
        nonlocal receipt
        stage.chmod(0o700)
        (stage / "submission.json").write_bytes(raw)
        (stage / "submission.json").chmod(0o600)
        correction_sha = None
        if correction is not None:
            append_seal(
                stage / "human-correction.json",
                dict(
                    previous_receipt_fingerprint=correction.previous_receipt_fingerprint,
                    reason=correction.reason,
                    attestation=correction.attestation,
                    version=version,
                ),
            )
            correction_sha = sha(stage / "human-correction.json")
        receipt = append_seal(
            stage / "receipt.json",
            dict(
                schema_version="p021-human-submission-freeze-v1",
                role=role,
                version=version,
                submission_sha256=hashlib.sha256(raw).hexdigest(),
                submission_fingerprint=digest(submission),
                bundle_fingerprint=bundle.fingerprint,
                responses=100,
                previous_receipt_fingerprint=previous["fingerprint"] if previous else None,
                correction_sha256=correction_sha,
                formal_validation="PASS",
                semantic_normalization=False,
                final_truth_created=False,
                identity_verification="PSEUDONYMOUS_SELF_ATTESTATION_ONLY",
            ),
        )
        verify_accepted(stage)

    atomic_directory(role_root / f"v{version:04d}", build)
    return receipt
