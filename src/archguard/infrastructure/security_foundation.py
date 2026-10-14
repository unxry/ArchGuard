"""Public-safe P027 receipts and read-only P025/P026 integrity; no Security evaluation."""

import ast
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import final_evaluation
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.security import dataflow, domain, ports, rules

SOURCE = "1fcb8e8f1f3eaf049c2de4f282910309088eed2f"
ROOT = Path("experiments/security/security-foundation-v1")
SECURITY_ROOT = Path("src/archguard/security")
P026_MANIFEST = "69e17bfe8d573b580ff40099eece74f18dbc90d3be24e5e0077842d55fc97b26"
SOURCES = (
    "src/archguard/security/domain.py",
    "src/archguard/security/ports.py",
    "src/archguard/security/rules.py",
    "src/archguard/security/dataflow.py",
    "src/archguard/security/analysis.py",
    "src/archguard/infrastructure/security_foundation.py",
    "scripts/prompt027_security_foundation.py",
    "tests/security/test_foundation.py",
)
DOCS = (
    Path("docs/security/SECURITY_RULES.md"),
    Path("docs/security/SECURITY_ARCHITECTURE.md"),
    Path("src/archguard/security/README.md"),
    Path("docs/verification/PROMPT_027.md"),
)
ARTIFACTS = (
    "sec-rule-registry.json",
    "security-domain-model.json",
    "security-analysis-boundary.json",
    "security-capability-matrix.json",
    "security-boundary-receipt.json",
    "security-foundation.json",
    "freeze-index.json",
)
ARCH_PATHS = (
    Path("src/archguard/architecture"),
    Path("src/archguard/benchmark"),
    Path("src/archguard/calibration"),
    Path("src/archguard/iam"),
    Path("src/archguard/iam_building"),
    Path("src/archguard/parsing"),
    Path("src/archguard/extraction"),
    Path("src/archguard/core"),
    Path("src/archguard/api"),
)
BOUNDARIES = dict(
    provider_calls=0,
    connectivity_calls=0,
    credential_reads=0,
    Security_LLM=False,
    Security_benchmark=False,
    Security_metrics="NOT_AVAILABLE",
    UI="NOT_STARTED",
    Hybrid_contamination=False,
    persistence="NOT_REQUIRED_P027",
    migration="NOT_REQUIRED_P027",
    HTTP_API_changed=False,
)


def gate() -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    io.scientific_status(
        status, (*SOURCES, *(str(p) for p in DOCS), *(str(ROOT / n) for n in ARTIFACTS))
    )
    for commit in (thesis.SOURCE, SOURCE):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P027_BLOCKED_LINEAGE")
    allowed = {*SOURCES, *(str(p) for p in DOCS), *(str(ROOT / n) for n in ARTIFACTS)}
    changed = (
        subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
        .decode()
        .splitlines()
    )
    if any(path not in allowed for path in changed):
        raise ValueError("P027_BLOCKED_COMMITTED_SCOPE_DRIFT")


def import_firewall() -> dict[str, Any]:
    checked = {}
    for root, forbidden in (
        (
            SECURITY_ROOT,
            (
                "archguard.architecture",
                "archguard.benchmark",
                "archguard.calibration",
                "archguard.infrastructure",
                "archguard.api",
            ),
        ),
        (Path("src/archguard/architecture"), ("archguard.security",)),
        (Path("src/archguard/benchmark"), ("archguard.security",)),
        (Path("src/archguard/calibration"), ("archguard.security",)),
    ):
        for path in sorted(root.rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text())):
                names = (
                    [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else []
                )
                if any(n == f or n.startswith(f + ".") for n in names for f in forbidden):
                    raise ValueError("P027_IMPORT_ISOLATION_FAILED")
                if root == SECURITY_ROOT:
                    if isinstance(node, ast.ImportFrom) and node.level > 1:
                        raise ValueError("P027_RELATIVE_IMPORT_BOUNDARY_FAILED")
                    if isinstance(node, ast.Call) and (
                        isinstance(node.func, ast.Name)
                        and node.func.id == "__import__"
                        or isinstance(node.func, ast.Attribute)
                        and node.func.attr == "import_module"
                    ):
                        raise ValueError("P027_DYNAMIC_IMPORT_BOUNDARY_FAILED")
            checked[str(path)] = io.sha(path)
    return dict(status="PASS", inspected_modules=len(checked), module_hashes=checked)


def science_freeze() -> dict[str, Any]:
    """P026's stage-specific worktree gate is replaced here by the stricter P027 gate only.

    All byte, manifest, model, truth and source checks remain read-only and unchanged.
    """
    gate()
    thesis.prior_integrity()
    final_evaluation.verify_acquisition()
    bundle = thesis.build()
    for name, expected in bundle.items():
        if io.read_seal(thesis.ROOT / name) != expected:
            raise ValueError("P027_BLOCKED_SCIENTIFIC_FREEZE_DRIFT")
    manifest = io.read_seal(thesis.ROOT / "closure-manifest.json", P026_MANIFEST)
    quality = io.read_seal(
        thesis.ROOT / "quality-verification.json", manifest["quality_fingerprint"]
    )
    if manifest != thesis.manifest_value(bundle, quality, thesis.document_gate(bundle)):
        raise ValueError("P027_BLOCKED_SCIENTIFIC_FREEZE_DRIFT")
    index = io.read_seal(thesis.ROOT / "freeze-index.json")
    io.verify_files(
        thesis.ROOT,
        index["files"] | {"freeze-index.json": io.sha(thesis.ROOT / "freeze-index.json")},
    )
    if not manifest["CORE_THESIS_COMPLETE"]:
        raise ValueError("P027_BLOCKED_CORE_THESIS_INCOMPLETE")
    original = {}
    for root in ARCH_PATHS:
        paths = sorted(root.rglob("*.py")) if root.is_dir() else (root,)
        for path in paths:
            raw = subprocess.check_output(["git", "show", f"{SOURCE}:{path}"])
            import hashlib

            expected_sha = hashlib.sha256(raw).hexdigest()
            if io.sha(path) != expected_sha:
                raise ValueError("P027_BLOCKED_ARCHITECTURE_IMPLEMENTATION_DRIFT")
            original[str(path)] = expected_sha
    return dict(
        P026_closure=P026_MANIFEST,
        CORE_THESIS_COMPLETE=True,
        P025_primary=thesis.PINS["final-primary-metrics.json"],
        P025_hypothesis=thesis.PINS["final-hypothesis.json"],
        P025_evaluation_receipt=thesis.PINS["evaluation-receipt.json"],
        P026_scientific_registry=bundle["scientific-registry.json"]["fingerprint"],
        P026_claim_registry=bundle["claim-registry.json"]["fingerprint"],
        scientific_artifacts_unchanged="PASS",
        architecture_source_hashes=original,
    )


def build(quality: dict[str, Any]) -> dict[str, dict[str, Any]]:
    freeze = science_freeze()
    firewall = import_firewall()
    registry = thesis.sealed(
        dict(
            version=rules.REGISTRY_VERSION,
            rules=[r.model_dump(mode="json") for r in rules.canonical_rules()],
            canonical_meanings=(
                "P027 initial frozen contract; supersedes historical unimplemented SEC placeholders"
            ),
        )
    )
    models = (
        domain.SecurityFinding,
        domain.SecurityEvidence,
        domain.SecuritySourceReference,
        domain.FlowPath,
        domain.SecurityAnalysisContext,
        domain.SecurityAnalysisResult,
        domain.SecurityReportSection,
        ports.DetectorRegistration,
        ports.DetectorResult,
        dataflow.SecurityAPIContract,
        rules.SecurityRuleDefinition,
    )
    schemas = thesis.sealed(
        dict(
            version="security-domain-model-v1",
            schemas={m.__name__: m.model_json_schema() for m in models},
            implementation_hashes={p: io.sha(Path(p)) for p in SOURCES[:4]},
            evidence_kinds_implemented="TYPED_CONTRACTS_ONLY",
            confidence="QUALITATIVE_NOT_PROBABILITY",
            identity=(
                "UUID5 of repository, snapshot, rule, primary/sink source "
                "and flow; not runtime UUID"
            ),
            duplicates="Collapse identical same-ID output; reject conflicting same-ID output",
            raw_secret_values="NOT_A_MODEL_FIELD; future evidence must be source-safe/redacted",
        )
    )
    boundary = thesis.sealed(
        dict(
            version="security-analysis-boundary-v1",
            implementation_hashes={
                p: io.sha(Path(p)) for p in (SOURCES[1], SOURCES[3], SOURCES[4])
            },
            detector_set_version="empty-detector-set-v1",
            executable_detectors=[],
            source_sink_registry_version=dataflow.API_REGISTRY_VERSION,
            source_sink_registry_entries=[],
            dataflow_protocol_version=dataflow.DATAFLOW_VERSION,
            dataflow_implemented=False,
            taint_implemented=False,
            default_result="ZERO_FINDINGS_ALL_REQUESTED_RULES_UNSUPPORTED",
            applicability=(
                "Evaluated and applicable are separate; unsupported does not mean secure"
            ),
            report_sections=(
                "SECURITY result and summary remain distinct from existing ARCH/Hybrid outputs"
            ),
            configuration_categories=[k.value for k in domain.ConfigurationCategory],
            intake_expansion=False,
            exclusions="No production filtering heuristic added",
            firewall=firewall,
            **BOUNDARIES,
        )
    )
    matrix = thesis.sealed(
        dict(
            version="security-capability-matrix-v1",
            rows=[
                dict(
                    rule_id=r.rule_id.value,
                    contract_frozen=True,
                    required_evidence_capabilities=[c.value for c in r.evidence_requirements],
                    implemented_evidence_capabilities=[],
                    implemented_detector=None,
                    JAVA="CONTRACT_FROZEN",
                    TYPESCRIPT="CONTRACT_FROZEN",
                    known_limitations=list(r.limitations),
                    next_implementation_dependency=(
                        "P028 tested source/sink/context and applicable static/dataflow evidence"
                    ),
                )
                for r in rules.canonical_rules()
            ],
            JS_TSX="PARSERS_AVAILABLE_SECURITY_LANGUAGE_CONTRACT_NOT_DECLARED",
            effectiveness="NOT_EVALUATED_NO_BENCHMARK",
        )
    )
    arch_registry = thesis.sealed(
        dict(
            files={
                p: h
                for p, h in freeze["architecture_source_hashes"].items()
                if "/rules/" in p or "/specification/" in p
            }
        )
    )
    receipt = thesis.sealed(
        dict(
            version="security-boundary-receipt-v1",
            science_freeze=freeze,
            ARCH_registry_fingerprint=arch_registry["fingerprint"],
            ARCH_registry=arch_registry,
            SEC_registry_fingerprint=registry["fingerprint"],
            Hybrid_implementation_hash=digest(
                {
                    p: h
                    for p, h in freeze["architecture_source_hashes"].items()
                    if "/hybrid/" in p or "/calibration/" in p
                }
            ),
            Security_domain_implementation_hash=digest(schemas["implementation_hashes"]),
            isolation_tests={SOURCES[-1]: io.sha(Path(SOURCES[-1]))},
            import_isolation="PASS",
            quality=quality,
            **BOUNDARIES,
        )
    )
    manifest = thesis.sealed(
        dict(
            version=domain.SECURITY_VERSION,
            source_commit=SOURCE,
            implementation_commit=subprocess.check_output(
                ["git", "log", "-1", "--format=%H", "--", *SOURCES], text=True
            ).strip(),
            required_lineage={"P025": thesis.SOURCE, "P026": SOURCE},
            status="P027_SECURITY_FOUNDATION_COMPLETE",
            next_stage="READY_FOR_P028_SECURITY_STATIC_AND_DATAFLOW_ANALYSIS",
            rule_registry_fingerprint=registry["fingerprint"],
            domain_model_fingerprint=schemas["fingerprint"],
            capability_matrix_fingerprint=matrix["fingerprint"],
            analysis_boundary_fingerprint=boundary["fingerprint"],
            boundary_receipt_fingerprint=receipt["fingerprint"],
            supported_language_contract=[language.value for language in domain.SecurityLanguage],
            detector_implementation_status={
                r.rule_id.value: r.implementation_status.value for r in rules.canonical_rules()
            },
            architecture_isolation="PASS",
            architecture_science="UNCHANGED",
            fake_production_findings=0,
            Security="FOUNDATION_READY",
            SEC001_SEC010="CONTRACT_FROZEN",
            **BOUNDARIES,
        )
    )
    return dict(
        zip(ARTIFACTS[:-1], (registry, schemas, boundary, matrix, receipt, manifest), strict=True)
    )


def privacy(paths: tuple[Path, ...]) -> None:
    for path in paths:
        text = path.read_text()
        if any(
            re.search(pattern, text)
            for pattern in (
                r"sk-[A-Za-z0-9_-]{16,}",
                r"github_pat_[A-Za-z0-9_]{20,}",
                r"(?i)Bearer\s+[A-Za-z0-9._-]{12,}",
                r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
            )
        ):
            raise ValueError("P027_PUBLIC_SECRET_AUDIT_FAILED")
    thesis.privacy_audit([ROOT / n for n in ARTIFACTS if (ROOT / n).exists()])


def freeze(quality_path: Path) -> dict[str, Any]:
    if quality_path.name.startswith(".env") or quality_path.suffix != ".json":
        raise ValueError("P027_INVALID_QUALITY_RECEIPT")
    quality = json.loads(quality_path.read_text())
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
        raise ValueError("P027_QUALITY_INCOMPLETE")
    if quality.get("provider_calls") != 0 or quality.get("credential_reads") != 0:
        raise ValueError("P027_PROVIDER_OR_CREDENTIAL_ACTIVITY")
    bundle = build(quality)
    if bundle != build(quality):
        raise ValueError("P027_NONDETERMINISTIC_REGISTRY")
    for name, value in bundle.items():
        thesis.write_new(ROOT / name, canonical(value) + "\n")
    index = thesis.sealed(
        dict(
            files={n: io.sha(ROOT / n) for n in bundle},
            fingerprints={n: v["fingerprint"] for n, v in bundle.items()},
            source_bindings={p: io.sha(Path(p)) for p in SOURCES},
            documents={str(p): io.sha(p) for p in DOCS},
        )
    )
    thesis.write_new(ROOT / "freeze-index.json", canonical(index) + "\n")
    return verify()


def verify() -> dict[str, Any]:
    index = io.read_seal(ROOT / "freeze-index.json")
    io.verify_files(
        ROOT, index["files"] | {"freeze-index.json": io.sha(ROOT / "freeze-index.json")}
    )
    receipt = io.read_seal(ROOT / "security-boundary-receipt.json")
    bundle = build(receipt["quality"])
    for name, expected in bundle.items():
        if io.read_seal(ROOT / name, index["fingerprints"][name]) != expected:
            raise ValueError("P027_FOUNDATION_FREEZE_DRIFT")
    for path, sha in (index["source_bindings"] | index["documents"]).items():
        if io.sha(Path(path)) != sha:
            raise ValueError("P027_IMPLEMENTATION_OR_DOCUMENT_DRIFT")
    privacy((*(ROOT / n for n in ARTIFACTS), *(Path(p) for p in SOURCES), *DOCS))
    return dict(
        status="P027_SECURITY_FOUNDATION_COMPLETE",
        rule_count=10,
        fingerprints={n: v["fingerprint"] for n, v in bundle.items()},
        architecture_science_unchanged=True,
        next_stage="READY_FOR_P028_SECURITY_STATIC_AND_DATAFLOW_ANALYSIS",
        **BOUNDARIES,
    )
