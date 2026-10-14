"""Offline P028 engineering receipts and historical science/source integrity checks."""

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import final_evaluation, security_foundation
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security import api_v1
from archguard.security.flow_v1 import VERSION, FlowLimits
from archguard.security.rules import canonical_rules

SOURCE = "38778bb25e1fd993ce80fc50c207a76e958d4eaf"
P027_IMPLEMENTATION = "899cec534849a899e7d4ddf28a8cad5672e0fffc"
ROOT = Path("experiments/security/security-static-dataflow-v1")
FIXTURES = Path("tests/fixtures/security/v1/cases.json")
SOURCES = (
    "src/archguard/security/flow_v1.py",
    "src/archguard/security/api_v1.py",
    "src/archguard/security/engine_v1.py",
    "src/archguard/security/analyzer_v1.py",
    "src/archguard/infrastructure/security_analysis_v1.py",
    "scripts/prompt028_security_analysis.py",
    "tests/security/test_analysis_v1.py",
    "tests/security/test_receipts_v1.py",
    str(FIXTURES),
)
DOCS = (
    "docs/security/SECURITY_ANALYSIS_V1.md",
    "docs/security/SECURITY_RULES.md",
    "docs/security/SECURITY_ARCHITECTURE.md",
    "docs/verification/PROMPT_028.md",
)
ARTIFACTS = (
    "analysis-protocol.json",
    "detector-registry.json",
    "security-api-registry.json",
    "security-capability-matrix.json",
    "fixture-inventory.json",
    "analysis-boundary.json",
    "security-analysis-v1.json",
    "quality-verification.json",
    "freeze-index.json",
)
P027_PINS = {
    "sec-rule-registry.json": "9389a584676333887efb1d0e259078ecf8837dfe3f0492bf6c6907640e1c5320",
    "security-domain-model.json": (
        "4330b32e557a4f8e6670f4deecb442d0bcb04763ddf750e6cb00c78409efe9ac"
    ),
    "security-analysis-boundary.json": (
        "ccd79bd21f87eaa4e868cfc93379dd97182d8e3b39fa2af3a5b5c522d1df27b0"
    ),
    "security-boundary-receipt.json": (
        "4de191d80be96c2fbd46d4486e6a5b093a3285cc0ba11136817338ff0f94ef43"
    ),
    "security-capability-matrix.json": (
        "76c634aa9abde653784ad3d6f0e49805fb1f55b8c6288b8af370645803c264bb"
    ),
    "security-foundation.json": "0b83e2ff509249829c9c61a2b32cb800805ed186fb8b7b67d2ae8f3d75e0fc5f",
}
BOUNDARIES = dict(
    provider_calls=0,
    connectivity_calls=0,
    credential_reads=0,
    Security_LLM=False,
    Security_benchmark=False,
    UI="NOT_STARTED",
    P029="NOT_STARTED",
    API_CHANGE="NO",
    PERSISTENCE_CHANGE="NO",
    Security_ground_truth="NOT_AVAILABLE",
    Security_precision="NOT_AVAILABLE",
    Security_recall="NOT_AVAILABLE",
    Security_F1="NOT_AVAILABLE",
    Architecture_Hybrid_contamination=False,
)
LIMITATIONS = (
    "Literal declarations only; no configuration/env scanning or cross-file constants",
    "Statement/pg string queries only; no ORM/custom wrapper modeling",
    "Runtime/ProcessBuilder and explicit child_process imports; no process wrappers",
    "Direct file-read paths only; normalization propagates taint; confinement unsupported",
    "Java locally constructed ObjectInputStream only; filters UNKNOWN; TypeScript unsupported",
    "Java URL and node:http/https string URLs only; no DNS/redirect/allowlist proof",
    "JSP writer and typed DOM HTML writes; only default DOMPurify sanitization",
    "Selected weak algorithms; purpose from receiving symbol; unclear context POTENTIAL",
    "Selected platform PRNG with receiving symbol purpose; no downstream use analysis",
    "Selected code-evaluation APIs only; string timers only; no reflection heuristic",
)


def gate() -> None:
    allowed = (*SOURCES, *DOCS, *(str(ROOT / n) for n in ARTIFACTS))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for commit in (thesis.SOURCE, security_foundation.SOURCE, P027_IMPLEMENTATION, SOURCE):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P028_LINEAGE_DRIFT")
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
        .decode()
        .splitlines()
    )
    if any(p not in allowed for p in changed):
        raise ValueError("P028_COMMITTED_SCOPE_DRIFT")


def science_audit() -> dict[str, Any]:
    gate()
    thesis.prior_integrity()
    final_evaluation.verify_acquisition()
    bundle = thesis.build()
    for name, expected in bundle.items():
        if io.read_seal(thesis.ROOT / name) != expected:
            raise ValueError("P028_P026_SCIENCE_DRIFT")
    manifest = io.read_seal(
        thesis.ROOT / "closure-manifest.json", security_foundation.P026_MANIFEST
    )
    quality = io.read_seal(
        thesis.ROOT / "quality-verification.json", manifest["quality_fingerprint"]
    )
    if (
        manifest != thesis.manifest_value(bundle, quality, thesis.document_gate(bundle))
        or not manifest["CORE_THESIS_COMPLETE"]
    ):
        raise ValueError("P028_P026_CLOSURE_DRIFT")
    index = io.read_seal(thesis.ROOT / "freeze-index.json")
    io.verify_files(
        thesis.ROOT,
        index["files"] | {"freeze-index.json": io.sha(thesis.ROOT / "freeze-index.json")},
    )
    old = io.read_seal(security_foundation.ROOT / "freeze-index.json")
    io.verify_files(
        security_foundation.ROOT,
        old["files"]
        | {"freeze-index.json": io.sha(security_foundation.ROOT / "freeze-index.json")},
    )
    for name, pin in P027_PINS.items():
        io.read_seal(security_foundation.ROOT / name, pin)
    for path, expected in old["source_bindings"].items():
        if io.sha(Path(path)) != expected:
            raise ValueError("P028_P027_IMPLEMENTATION_DRIFT")
    # Updated Security docs are a new stage. Their P027 editions stay Git-bound.
    for path, expected in old["documents"].items():
        raw = subprocess.check_output(["git", "show", f"{SOURCE}:{path}"])
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("P028_P027_HISTORICAL_DOCUMENT_DRIFT")
        if path not in DOCS and io.sha(Path(path)) != expected:
            raise ValueError("P028_P027_DOCUMENT_DRIFT")
    protected = io.read_seal(security_foundation.ROOT / "security-boundary-receipt.json")[
        "science_freeze"
    ]["architecture_source_hashes"]
    for path, expected in protected.items():
        if io.sha(Path(path)) != expected:
            raise ValueError("P028_ARCHITECTURE_IMPLEMENTATION_DRIFT")
    return dict(
        P025_primary=thesis.PINS["final-primary-metrics.json"],
        P025_hypothesis=thesis.PINS["final-hypothesis.json"],
        P025_receipt=thesis.PINS["evaluation-receipt.json"],
        P026_scientific_registry=bundle["scientific-registry.json"]["fingerprint"],
        P026_claim_registry=bundle["claim-registry.json"]["fingerprint"],
        P026_closure=manifest["fingerprint"],
        P027=P027_PINS,
        CORE_THESIS_COMPLETE=True,
        status="PASS",
        protected_implementation_files=len(protected),
    )


def build(quality: dict[str, Any], implementation_commit: str) -> dict[str, dict[str, Any]]:
    science = science_audit()
    firewall = security_foundation.import_firewall()
    protocol = thesis.sealed(
        dict(
            version=VERSION,
            implementation_hashes={p: io.sha(Path(p)) for p in SOURCES},
            rule_registry_fingerprint=P027_PINS["sec-rule-registry.json"],
            limits=FlowLimits().model_dump(mode="json"),
            lattice=(
                "UNKNOWN dominates; otherwise taint; "
                "sanitizer intersection for tainted contributors"
            ),
            returns="Local return expressions traversed; function return summaries unsupported",
            branch_semantics="Both branches; merge survivors; taint never becomes safe",
            loops="Unsupported: invalidate environment; diagnostic; do not execute once",
            alias_semantics="Immutable locals; static object projection; aliased writes UNKNOWN",
            flow_identity="P027 UUID5; distinct path/sink findings; exact duplicates collapse",
            finding_serialization=(
                "P027 schemas unchanged; locations/API IDs only; "
                "no raw values, snippets or secret hashes"
            ),
            interprocedural=False,
            whole_program_resolution=False,
        )
    )
    pack = api_v1.entries()
    api = thesis.sealed(dict(version=VERSION, entries=[e.model_dump(mode="json") for e in pack]))
    detectors = thesis.sealed(
        dict(
            version=VERSION,
            detectors=[
                dict(
                    detector_id=f"{r.rule_id.value.lower()}-v1",
                    rule_ids=[r.rule_id.value],
                    languages=["JAVA"] if r.rule_id.value == "SEC005" else ["JAVA", "TYPESCRIPT"],
                    status="IMPLEMENTED_V1" if r.rule_id.value == "SEC001" else "PARTIAL_V1",
                    api_ids=[e.id for e in pack if r.rule_id in e.rule_ids],
                    source_kinds=["AST_LITERAL"]
                    if r.rule_id.value == "SEC001"
                    else ["EXPLICIT_PLATFORM_API"],
                    sink_kinds=[
                        e.qualified_api
                        for e in pack
                        if r.rule_id in e.rule_ids and e.role == "SINK"
                    ],
                    sanitizers=[
                        e.id for e in pack if r.rule_id in e.rule_ids and e.role == "SANITIZER"
                    ],
                    known_limitations=[LIMITATIONS[i]],
                    implementation_path=SOURCES[3],
                    engine_path=SOURCES[2],
                    test_path=SOURCES[6],
                    version=VERSION,
                )
                for i, r in enumerate(canonical_rules())
            ],
        )
    )
    matrix = thesis.sealed(
        dict(
            version=VERSION,
            rows=[
                dict(
                    rule_id=r.rule_id.value,
                    P027="CONTRACT_FROZEN",
                    P028="IMPLEMENTED_V1" if i == 0 else "PARTIAL_V1",
                    JAVA="IMPLEMENTED_V1" if i == 0 else "PARTIAL_V1",
                    TYPESCRIPT="CONTRACT_ONLY"
                    if i == 4
                    else "IMPLEMENTED_V1"
                    if i == 0
                    else "PARTIAL_V1",
                    analysis_type="AST_STATIC" if i in (0, 4, 7, 8) else "AST_STATIC_BOUNDED_TAINT",
                    dataflow=i in (1, 2, 3, 5, 6, 9),
                    interprocedural=False,
                    known_blind_spots=[LIMITATIONS[i]],
                )
                for i, r in enumerate(canonical_rules())
            ],
            JS_TSX="NOT_DECLARED_SECURITY_LANGUAGE",
            effectiveness="NOT_AVAILABLE",
        )
    )
    fixture_data = json.loads(FIXTURES.read_text())
    inventory = thesis.sealed(
        dict(
            version=VERSION,
            purpose=fixture_data["purpose"],
            fixture_file=str(FIXTURES),
            fixture_sha256=io.sha(FIXTURES),
            cases=[{k: v for k, v in c.items() if k != "source"} for c in fixture_data["cases"]],
            fixture_count=len(fixture_data["cases"]),
            benchmark=False,
            deterministic_double_run=True,
            assertions="Rule/count/status, locations, evidence, JSON round-trip, determinism",
        )
    )
    boundary = thesis.sealed(
        dict(
            version=VERSION,
            science_freeze=science,
            import_firewall=firewall,
            runtime_isolation_tests="tests/security/test_foundation.py",
            **BOUNDARIES,
        )
    )
    manifest = thesis.sealed(
        dict(
            version=VERSION,
            status="P028_SECURITY_STATIC_DATAFLOW_V1_COMPLETE",
            source_commit=SOURCE,
            implementation_commit=implementation_commit,
            P027_implementation=P027_IMPLEMENTATION,
            analysis_protocol_fingerprint=protocol["fingerprint"],
            detector_registry_fingerprint=detectors["fingerprint"],
            api_registry_fingerprint=api["fingerprint"],
            capability_matrix_fingerprint=matrix["fingerprint"],
            fixture_inventory_fingerprint=inventory["fingerprint"],
            analysis_boundary_fingerprint=boundary["fingerprint"],
            domain_model_fingerprint=P027_PINS["security-domain-model.json"],
            quality_fingerprint=quality["fingerprint"],
            executable_detectors=10,
            IMPLEMENTED_V1=1,
            PARTIAL_V1=9,
            CONTRACT_ONLY=0,
            fixture_count=len(fixture_data["cases"]),
            determinism="PASS",
            science_freeze="PASS",
            **BOUNDARIES,
        )
    )
    return dict(
        zip(
            ARTIFACTS[:-1],
            (protocol, detectors, api, matrix, inventory, boundary, manifest, quality),
            strict=True,
        )
    )


def privacy(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if path.name.startswith(".env") or path.is_symlink():
            raise ValueError("P028_UNSAFE_PUBLIC_PATH")
        raw = path.read_text()
        if any(
            re.search(p, raw)
            for p in (
                r"sk-[A-Za-z0-9_-]{16,}",
                r"github_pat_[A-Za-z0-9_]{20,}",
                r"(?i)Bearer\s+[A-Za-z0-9._-]{12,}",
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\\nr\s]+[A-Za-z0-9+/]{32,}",
            )
        ):
            raise ValueError("P028_SECRET_AUDIT_FAILED")
    thesis.privacy_audit([p for p in paths if p.suffix == ".json" and p.parent == ROOT])


def freeze(quality_path: Path, implementation_commit: str) -> dict[str, Any]:
    if quality_path.name.startswith(".env") or quality_path.suffix != ".json":
        raise ValueError("P028_INVALID_QUALITY_PATH")
    quality = io.read_seal(quality_path)
    if any(
        quality.get(k) != "PASS"
        for k in (
            "make_check",
            "ruff",
            "format",
            "strict_mypy",
            "regressions",
            "science_freeze",
            "privacy",
            "secret_audit",
            "diff_check",
        )
    ):
        raise ValueError("P028_QUALITY_INCOMPLETE")
    if quality.get("provider_calls") != 0 or quality.get("credential_reads") != 0:
        raise ValueError("P028_FORBIDDEN_ACTIVITY")
    if (
        subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip()
        != implementation_commit
    ):
        raise ValueError("P028_IMPLEMENTATION_COMMIT_MISMATCH")
    bundle = build(quality, implementation_commit)
    if bundle != build(quality, implementation_commit):
        raise ValueError("P028_NONDETERMINISTIC_RECEIPTS")
    privacy(tuple(Path(p) for p in (*SOURCES, *DOCS)))
    for name, value in bundle.items():
        thesis.write_new(ROOT / name, canonical(value) + "\n")
    index = thesis.sealed(
        dict(
            files={n: io.sha(ROOT / n) for n in bundle},
            fingerprints={n: v["fingerprint"] for n, v in bundle.items()},
            source_bindings={p: io.sha(Path(p)) for p in SOURCES},
            documents={p: io.sha(Path(p)) for p in DOCS},
        )
    )
    thesis.write_new(ROOT / "freeze-index.json", canonical(index) + "\n")
    return verify()


def verify() -> dict[str, Any]:
    index = io.read_seal(ROOT / "freeze-index.json")
    io.verify_files(
        ROOT, index["files"] | {"freeze-index.json": io.sha(ROOT / "freeze-index.json")}
    )
    manifest = io.read_seal(
        ROOT / "security-analysis-v1.json", index["fingerprints"]["security-analysis-v1.json"]
    )
    quality = io.read_seal(ROOT / "quality-verification.json", manifest["quality_fingerprint"])
    bundle = build(quality, manifest["implementation_commit"])
    for name, expected in bundle.items():
        if io.read_seal(ROOT / name, index["fingerprints"][name]) != expected:
            raise ValueError("P028_FROZEN_ARTIFACT_DRIFT")
    for p, h in (index["source_bindings"] | index["documents"]).items():
        if io.sha(Path(p)) != h:
            raise ValueError("P028_IMPLEMENTATION_OR_DOCUMENT_DRIFT")
    privacy(tuple(Path(p) for p in (*SOURCES, *DOCS)) + tuple(ROOT / n for n in ARTIFACTS))
    return dict(
        status=manifest["status"],
        fingerprints=index["fingerprints"],
        science_freeze="PASS",
        **BOUNDARIES,
    )
