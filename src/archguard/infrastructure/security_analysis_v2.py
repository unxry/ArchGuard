"""P029 public engineering freeze; immutable P025–P028 evidence is checked read-only."""

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import final_evaluation, security_foundation
from archguard.infrastructure import security_analysis_v1 as v1
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security import frameworks_v2
from archguard.security.rules import canonical_rules
from archguard.security.summaries_v2 import (
    VERSION,
    FunctionSummary,
    ParameterFlow,
    ReturnFlow,
    SafetyProof,
    SinkEffect,
    V2Limits,
)

SOURCE = "e93ada51108223e784d38df513183632a48b20ba"
IMPLEMENTATION_V1 = "d790da7e50e393ffe0225007182b64efd1db4979"
ROOT = Path("experiments/security/security-interprocedural-v2")
FIXTURES = Path("tests/fixtures/security/v2/cases.json")
SOURCES = (
    "src/archguard/security/summaries_v2.py",
    "src/archguard/security/index_v2.py",
    "src/archguard/security/frameworks_v2.py",
    "src/archguard/security/engine_v2.py",
    "src/archguard/security/analyzer_v2.py",
    "src/archguard/infrastructure/security_analysis_v2.py",
    "scripts/prompt029_security_analysis.py",
    "tests/security/test_analysis_v2.py",
    "tests/security/test_receipts_v2.py",
    str(FIXTURES),
)
DOCS = (
    "docs/security/SECURITY_ANALYSIS_V2.md",
    "docs/verification/PROMPT_029.md",
    "docs/security/SECURITY_RULES.md",
    "docs/security/SECURITY_ARCHITECTURE.md",
)
ARTIFACTS = (
    "summary-protocol.json",
    "call-resolution-protocol.json",
    "framework-pack-registry.json",
    "security-proof-registry.json",
    "detector-registry-v2.json",
    "security-capability-matrix-v2.json",
    "fixture-inventory.json",
    "analysis-boundary-v2.json",
    "security-analysis-v2.json",
    "quality-verification.json",
    "freeze-index.json",
)
V1_PINS = {
    "analysis-protocol.json": "8515ef759a9cd890fff18aab20b68f80b6d61a254d7fede0404cae22927d23d2",
    "detector-registry.json": "3a7a31f8515de16f44de1e98416e3e89151e05db226bb4a6b465ff3b19100ab0",
    "security-api-registry.json": (
        "ebffa8579e93b3502d8bc686beb50940dd694617063fa33d6532bd44fe7c4741"
    ),
    "security-capability-matrix.json": (
        "69431d3646e67596010c09f9d24e791b8fefa575f88231809c44d91585a6d8da"
    ),
    "analysis-boundary.json": "92c24315c03f78b5f21941d112c16edf3778b7396bb810f03ce3708aa09ea6f9",
    "security-analysis-v1.json": "79a0274183d276f9c32b8c5a1f76f8ecc776ee12f61dd008987b4cb50683f708",
}
BOUNDARIES = dict(
    provider_calls=0,
    connectivity_calls=0,
    credential_reads=0,
    paid_spend=0,
    Security_LLM=False,
    Security_benchmark=False,
    Security_ground_truth="NOT_AVAILABLE",
    Security_precision="NOT_AVAILABLE",
    Security_recall="NOT_AVAILABLE",
    Security_F1="NOT_AVAILABLE",
    Security_FPR="NOT_AVAILABLE",
    Security_FNR="NOT_AVAILABLE",
    Architecture_Hybrid_contamination=False,
    API_CHANGE="NO",
    PERSISTENCE_CHANGE="NO",
    P030="NOT_STARTED",
    UI="NOT_STARTED",
)


def gate() -> None:
    allowed = (*SOURCES, *DOCS, *(str(ROOT / n) for n in ARTIFACTS))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for commit in (
        thesis.SOURCE,
        security_foundation.SOURCE,
        v1.P027_IMPLEMENTATION,
        v1.SOURCE,
        IMPLEMENTATION_V1,
        SOURCE,
    ):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P029_LINEAGE_DRIFT")
    names = (
        subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
        .decode()
        .splitlines()
    )
    if any(p not in allowed for p in names):
        raise ValueError("P029_COMMITTED_SCOPE_DRIFT")


def historical_audit() -> dict[str, Any]:
    gate()
    thesis.prior_integrity()
    final_evaluation.verify_acquisition()
    bundle = thesis.build()
    for name, value in bundle.items():
        if io.read_seal(thesis.ROOT / name) != value:
            raise ValueError("P029_ARCHITECTURE_SCIENCE_DRIFT")
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
        raise ValueError("P029_P026_CLOSURE_DRIFT")
    index = io.read_seal(thesis.ROOT / "freeze-index.json")
    io.verify_files(
        thesis.ROOT,
        index["files"] | {"freeze-index.json": io.sha(thesis.ROOT / "freeze-index.json")},
    )
    historical = {}
    for root, commit, pins in (
        (security_foundation.ROOT, v1.SOURCE, v1.P027_PINS),
        (v1.ROOT, SOURCE, V1_PINS),
    ):
        old = io.read_seal(root / "freeze-index.json")
        io.verify_files(
            root, old["files"] | {"freeze-index.json": io.sha(root / "freeze-index.json")}
        )
        for name, fp in pins.items():
            io.read_seal(root / name, fp)
        for p, h in old["source_bindings"].items():
            if io.sha(Path(p)) != h:
                raise ValueError("P029_HISTORICAL_IMPLEMENTATION_DRIFT")
        for p, h in old["documents"].items():
            raw = subprocess.check_output(["git", "show", f"{commit}:{p}"])
            if hashlib.sha256(raw).hexdigest() != h:
                raise ValueError("P029_HISTORICAL_DOCUMENT_DRIFT")
            if p not in DOCS and io.sha(Path(p)) != h:
                raise ValueError("P029_FROZEN_DOCUMENT_DRIFT")
        historical[str(root)] = dict(
            fingerprints=old["fingerprints"],
            byte_inventory="PASS",
            source_bindings="PASS",
            historical_documents="PASS",
        )
    protected = io.read_seal(security_foundation.ROOT / "security-boundary-receipt.json")[
        "science_freeze"
    ]["architecture_source_hashes"]
    for p, h in protected.items():
        if io.sha(Path(p)) != h:
            raise ValueError("P029_ARCHITECTURE_IMPLEMENTATION_DRIFT")
    return dict(
        status="PASS",
        P025_primary=thesis.PINS["final-primary-metrics.json"],
        P025_hypothesis=thesis.PINS["final-hypothesis.json"],
        P025_receipt=thesis.PINS["evaluation-receipt.json"],
        P026_scientific_registry=bundle["scientific-registry.json"]["fingerprint"],
        P026_claim_registry=bundle["claim-registry.json"]["fingerprint"],
        P026_closure=manifest["fingerprint"],
        CORE_THESIS_COMPLETE=True,
        protected_implementation_files=len(protected),
        historical=historical,
    )


def build(quality: dict[str, Any], implementation: str) -> dict[str, dict[str, Any]]:
    history = historical_audit()
    firewall = security_foundation.import_firewall()
    limits = V2Limits().model_dump(mode="json")
    hashes = {p: io.sha(Path(p)) for p in SOURCES}
    summary = thesis.sealed(
        dict(
            version=VERSION,
            implementation_hashes=hashes,
            schemas={
                m.__name__: m.model_json_schema()
                for m in (
                    FunctionSummary,
                    ParameterFlow,
                    ReturnFlow,
                    SinkEffect,
                    SafetyProof,
                    V2Limits,
                )
            },
            flow_relations=[
                "PARAMETER_TO_RETURN",
                "PARAMETER_TO_SINK",
                "PARAMETER_TO_FIELD",
                "FIELD_TO_RETURN",
                "SANITIZER_TO_RETURN",
                "SOURCE_IN_CALLEE_TO_RETURN",
                "SOURCE_IN_CALLEE_TO_SINK",
            ],
            call_states=["EXACT", "UNAMBIGUOUS_LOCAL", "PARTIAL", "AMBIGUOUS", "UNRESOLVED"],
            algorithm="Cached symbolic effects; bounded bodies specialized against arguments/heap",
            cache="Symbol / private input-graph version / protocol / config / deterministic budget",
            private_cache_keys="NOT_SERIALIZED; no secret-value digest or raw source in summaries",
            recursion="Direct/mutual cycle returns UNKNOWN; no fixed-point claim",
            merge="UNKNOWN dominates; rule-specific sanitation; field slots merge conservatively",
            bounds=limits,
            unknown="UNKNOWN invents no source; known uncertain source-to-sink path is POTENTIAL",
            serialization="P027 finding schemas retained; locations/API classification only",
        )
    )
    resolution = thesis.sealed(
        dict(
            version=VERSION,
            priority=[
                "Same lexical declared function",
                "Same-class local method",
                "Known local constructor instance",
                "Explicit class static target",
                "Explicit relative named/namespace import",
            ],
            supported="Java local/static arity; TS declarations, assigned arrows, relative exports",
            ambiguity="Same-arity multiple targets UNKNOWN and sorted; never arbitrary selection",
            instance_dispatch="Type without known instance is PARTIAL; no definite summary",
            unsupported=[
                "Wildcard/re-export/default module resolution",
                "Inheritance/virtual dispatch",
                "Rest/default/destructured parameters",
                "Closures/framework callback lifecycle",
                "External bodies",
            ],
            bounds=limits,
            determinism="Sorted units/symbols/targets; serial execution; stable UUID5 identities",
        )
    )
    packs = frameworks_v2.packs()
    framework = thesis.sealed(
        dict(
            version=VERSION,
            packs=[
                thesis.sealed(
                    p.model_dump(mode="json")
                    | dict(
                        source_count=sum(e.role == "SOURCE" for e in p.apis),
                        sink_count=sum(e.role == "SINK" for e in p.apis),
                        sanitizer_count=sum(e.role == "SANITIZER" for e in p.apis),
                        safe_boundary_count=len(p.safe_boundaries),
                        rules=sorted({r.value for e in p.apis for r in e.rule_ids}),
                        status="PARTIAL_V2",
                    )
                )
                for p in packs
            ],
            counts="Semantic API groups; not ecosystem coverage; proof preconditions independent",
        )
    )
    proof = thesis.sealed(
        dict(
            version=VERSION,
            proofs=[p.model_dump(mode="json") for p in frameworks_v2.proofs()],
            command_note="Argument boundary does not prove operands safe; taint remains POTENTIAL",
            path_note="Lexical canonical containment; not symlink/race/realpath security",
            ssrf_note="Exact host only; no DNS/rebinding/redirect guarantee",
        )
    )
    old_caps = io.read_seal(v1.ROOT / "security-capability-matrix.json")
    rows = []
    for i, r in enumerate(canonical_rules()):
        relevant = [p for p in packs if any(r.rule_id in e.rule_ids for e in p.apis)]
        rows.append(
            dict(
                rule_id=r.rule_id.value,
                V1=old_caps["rows"][i]["P028"],
                V2="IMPLEMENTED_V2" if i == 0 else "PARTIAL_V2",
                JAVA="IMPLEMENTED_V2" if i == 0 else "PARTIAL_V2",
                TYPESCRIPT="CONTRACT_ONLY"
                if i == 4
                else "IMPLEMENTED_V2"
                if i == 0
                else "PARTIAL_V2",
                static=True,
                intraprocedural=i != 0,
                interprocedural=i != 0,
                object_fields=i != 0,
                framework_packs=[p.pack_id for p in relevant],
                proofs=[p.kind.value for p in frameworks_v2.proofs() if r.rule_id in p.rules],
                limitations=[
                    "Declared bounded subset; no whole-program/compiler completeness",
                    "Unsupported frameworks/dispatch/heap cases UNKNOWN/PARTIAL",
                ],
                next_gap="P030 independent benchmark protocol; no detector-derived labels",
            )
        )
    detectors = thesis.sealed(
        dict(
            version=VERSION,
            detectors=[
                row
                | dict(
                    detector_id=row["rule_id"].lower() + "-v2",
                    implementation_path=SOURCES[4],
                    engine_path=SOURCES[3],
                    test_path=SOURCES[7],
                )
                for row in rows
            ],
        )
    )
    capability = thesis.sealed(
        dict(
            version=VERSION,
            rows=rows,
            coverage_statuses=["SUPPORTED_PARTIAL_V2_SCOPE", "CONTRACT_ONLY", "FAILED"],
            scope="Coverage refers to declared tested subsets, never ecosystem FULL",
            JS_TSX="SECURITY_LANGUAGE_NOT_DECLARED",
            effectiveness="NOT_AVAILABLE",
        )
    )
    cases = json.loads(FIXTURES.read_text())
    inventory = thesis.sealed(
        dict(
            version=VERSION,
            purpose=cases["purpose"],
            fixture_file=str(FIXTURES),
            fixture_sha256=io.sha(FIXTURES),
            fixture_count=len(cases["cases"]),
            cases=[
                {k: v for k, v in c.items() if k not in {"source", "files"}} for c in cases["cases"]
            ],
            double_run="COLD/HOT CACHE CANONICAL OUTPUT",
            benchmark=False,
            ground_truth="NOT_AVAILABLE",
        )
    )
    boundary = thesis.sealed(
        dict(
            version=VERSION,
            historical_freeze=history,
            firewall=firewall,
            runtime_boundary_tests="tests/security/test_foundation.py",
            **BOUNDARIES,
        )
    )
    manifest = thesis.sealed(
        dict(
            version=VERSION,
            status="P029_SECURITY_INTERPROCEDURAL_V2_COMPLETE",
            source_commit=SOURCE,
            implementation_commit=implementation,
            P028_implementation=IMPLEMENTATION_V1,
            P027_contracts=v1.P027_PINS,
            P028_protocol=V1_PINS,
            summary_protocol_fingerprint=summary["fingerprint"],
            call_resolution_fingerprint=resolution["fingerprint"],
            framework_registry_fingerprint=framework["fingerprint"],
            proof_registry_fingerprint=proof["fingerprint"],
            detector_registry_fingerprint=detectors["fingerprint"],
            capability_matrix_fingerprint=capability["fingerprint"],
            fixture_inventory_fingerprint=inventory["fingerprint"],
            analysis_boundary_fingerprint=boundary["fingerprint"],
            implementation_fingerprint=thesis.sealed(hashes)["fingerprint"],
            quality_fingerprint=quality["fingerprint"],
            framework_pack_count=len(packs),
            fixture_count=len(cases["cases"]),
            executable_detectors=10,
            IMPLEMENTED_V2=1,
            PARTIAL_V2=9,
            CONTRACT_ONLY=0,
            TYPESCRIPT_SEC005="CONTRACT_ONLY",
            science_freeze="PASS",
            Git_publication=dict(
                required="ORDINARY_PUSH_ORIGIN_MAIN",
                required_final_tree="ONLY_AUTHORIZED_HTML_DELETION",
                verification="POST_COMMIT_REMOTE_CHECK_IN_FINAL_RESPONSE",
            ),
            **BOUNDARIES,
        )
    )
    return dict(
        zip(
            ARTIFACTS[:-1],
            (
                summary,
                resolution,
                framework,
                proof,
                detectors,
                capability,
                inventory,
                boundary,
                manifest,
                quality,
            ),
            strict=True,
        )
    )


def privacy(paths: tuple[Path, ...]) -> None:
    v1.privacy(paths)
    thesis.privacy_audit([p for p in paths if p.parent == ROOT and p.suffix == ".json"])


def freeze(quality_path: Path, implementation: str) -> dict[str, Any]:
    if quality_path.name.startswith(".env") or quality_path.suffix != ".json":
        raise ValueError("P029_UNSAFE_QUALITY_PATH")
    quality = io.read_seal(quality_path)
    if any(
        quality.get(k) != "PASS"
        for k in (
            "make_check",
            "ruff",
            "format",
            "strict_mypy",
            "regressions",
            "historical_freeze",
            "privacy",
            "secret_audit",
            "diff_check",
        )
    ):
        raise ValueError("P029_QUALITY_INCOMPLETE")
    if any(
        quality.get(k) != 0 for k in ("provider_calls", "credential_reads", "connectivity_calls")
    ):
        raise ValueError("P029_FORBIDDEN_ACTIVITY")
    if subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip() != implementation:
        raise ValueError("P029_IMPLEMENTATION_COMMIT_MISMATCH")
    bundle = build(quality, implementation)
    if bundle != build(quality, implementation):
        raise ValueError("P029_NONDETERMINISTIC_RECEIPTS")
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
        ROOT / "security-analysis-v2.json", index["fingerprints"]["security-analysis-v2.json"]
    )
    quality = io.read_seal(ROOT / "quality-verification.json", manifest["quality_fingerprint"])
    for name, value in build(quality, manifest["implementation_commit"]).items():
        if io.read_seal(ROOT / name, index["fingerprints"][name]) != value:
            raise ValueError("P029_FROZEN_ARTIFACT_DRIFT")
    for p, h in (index["source_bindings"] | index["documents"]).items():
        if io.sha(Path(p)) != h:
            raise ValueError("P029_SOURCE_OR_DOCUMENT_DRIFT")
    privacy(tuple(Path(p) for p in (*SOURCES, *DOCS)) + tuple(ROOT / n for n in ARTIFACTS))
    return dict(
        status=manifest["status"],
        fingerprints=index["fingerprints"],
        historical_freeze="PASS",
        **BOUNDARIES,
    )
