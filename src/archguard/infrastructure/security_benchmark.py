"""P030 immutable offline materialization and publication receipts; no detector execution."""

import hashlib
import re
import subprocess
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from archguard.application.build_iam import BuildIAM
from archguard.application.parse_repository import ParseRepository
from archguard.benchmark.oss.models import digest
from archguard.extraction.config import ExtractionConfig
from archguard.extraction.factory import create_extractor_registry
from archguard.iam_building.validation import validate_built_iam
from archguard.infrastructure import security_analysis_v1 as v1
from archguard.infrastructure import security_analysis_v2 as v2
from archguard.infrastructure import security_foundation
from archguard.infrastructure import thesis_closure as thesis
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.repository.factory import create_discovery
from archguard.parsing.config import ParserConfig
from archguard.parsing.factory import create_parser_registry
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from archguard.security_benchmark.foundation import (
    blindness_audit,
    material,
    private_material,
    serialized,
)
from archguard.security_benchmark.protocol import (
    ReviewPacket,
    ReviewResponse,
    human_protocol,
    metric_protocol,
)
from archguard.security_benchmark.templates import VERSION

SOURCE = "3274504a80abe0ae688796c28322a87f7f5272c9"
IMPLEMENTATION_V2 = "ae99aa94c818f89a4d988bca99c73eb18b6a74cf"
BASE = Path("experiments/security/security-benchmark-v1")
PUBLIC = BASE / "public"
PRIVATE = BASE / "private"
SOURCES = (
    "src/archguard/security_benchmark/__init__.py",
    "src/archguard/security_benchmark/protocol.py",
    "src/archguard/security_benchmark/templates.py",
    "src/archguard/security_benchmark/foundation.py",
    "src/archguard/infrastructure/security_benchmark.py",
    "scripts/prompt030_security_benchmark.py",
    "tests/security/test_benchmark_foundation.py",
    "tests/security/test_benchmark_receipts.py",
)
DOCS = (
    "docs/security/SECURITY_BENCHMARK_PROTOCOL.md",
    "docs/security/SECURITY_REVIEWER_GUIDE.md",
    "docs/verification/PROMPT_030.md",
)
ARTIFACTS = (
    "benchmark-protocol.json",
    "human-review-protocol.json",
    "security-metric-protocol.json",
    "review-packet.schema.json",
    "review-response.schema.json",
    "aggregate-inventory.json",
    "split-separation-certificate.json",
    "leakage-audit.json",
    "construction-validation.json",
    "private-fingerprint-manifest.json",
    "p031-human-review-handoff.json",
    "benchmark-manifest.json",
    "quality-verification.json",
    "freeze-index.json",
)
PINS = {
    "summary-protocol.json": "d7df5af8fa93344b62c2fc54927a15a2b5b49aef0ffb358643556422f24d0388",
    "call-resolution-protocol.json": (
        "a9441b152dd0f1dd618b6e3deb3ef5c62818ebc33c3a09dd507870ed58259560"
    ),
    "framework-pack-registry.json": (
        "8af448d672af6cb8ce9462bf8032bcc1ec4d6b2fae0f10d09d52c658f3302283"
    ),
    "security-proof-registry.json": (
        "71c878c72406a3856e6a4f9e6e3a0c7ac2bee45f79c503b1186f7abe4335332a"
    ),
    "detector-registry-v2.json": "822701f320cc0e604053c3d70556de0e43867de66695a329db201982a70897ab",
    "security-capability-matrix-v2.json": (
        "863c33fe50134ef653c6f3b5bad261e0f68668c8a805acc4eb16d8b56e874a24"
    ),
    "analysis-boundary-v2.json": "a89d108f8a2ca144da959adcb707a611fd6c8648c04ef34400bbea8aa000130c",
    "security-analysis-v2.json": "c74ab979768cd597ffaa91567a7e6424a1ec4e28938a32889f8fd4572c35e2c7",
}
BOUNDARIES = dict(
    provider_calls=0,
    connectivity_calls=0,
    credential_reads=0,
    paid_spend=0,
    detector_predictions=0,
    reviewer_A_responses=0,
    reviewer_B_responses=0,
    adjudications=0,
    AI_generated_human_labels=0,
    Security_ground_truth="NOT_AVAILABLE",
    Security_precision="NOT_AVAILABLE",
    Security_recall="NOT_AVAILABLE",
    Security_F1="NOT_AVAILABLE",
    confusion="NOT_COMPUTED",
    Security_effectiveness="NOT_EVALUATED",
    Architecture_science_drift=0,
    P029_detector_drift=0,
    UI="NOT_STARTED",
    P031="NOT_STARTED",
)


def gate() -> None:
    allowed = (*SOURCES, *DOCS, ".gitignore", *(str(PUBLIC / n) for n in ARTIFACTS))
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        allowed,
    )
    for commit in (
        thesis.SOURCE,
        security_foundation.SOURCE,
        v1.P027_IMPLEMENTATION,
        v1.SOURCE,
        v2.IMPLEMENTATION_V1,
        v2.SOURCE,
        IMPLEMENTATION_V2,
        SOURCE,
    ):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", commit, "HEAD"], capture_output=True
        ).returncode:
            raise ValueError("P030_LINEAGE_DRIFT")
    names = (
        subprocess.check_output(["git", "diff", "--name-only", SOURCE, "HEAD"])
        .decode()
        .splitlines()
    )
    if any(p not in allowed for p in names):
        raise ValueError("P030_COMMITTED_SCOPE_DRIFT")
    original = subprocess.check_output(["git", "show", f"{SOURCE}:.gitignore"]).decode()
    if Path(".gitignore").read_text() != original + (
        "\n# Prospective Security benchmark: case evidence, construction intent "
        "and future human "
        "truth.\nexperiments/security/security-benchmark-v1/private/\n"
    ):
        raise ValueError("P030_IGNORE_RULE_DRIFT")
    if subprocess.run(
        ["git", "check-ignore", "-q", str(PRIVATE / "coordinator/case-inventory.json")],
        capture_output=True,
    ).returncode:
        raise ValueError("private benchmark root must be ignored")
    if subprocess.check_output(["git", "ls-files", "--", str(PRIVATE)]):
        raise ValueError("private benchmark material tracked")


def historical_audit() -> dict[str, Any]:
    gate()
    for n, fp in PINS.items():
        io.read_seal(v2.ROOT / n, fp)
    # Replace ONLY the old stage's changed-file gate with the new stricter P030 gate.
    # Its complete byte/source/document/science/rebuild verifier stays unchanged.
    with patch.object(v2, "gate", gate):
        receipt = v2.verify()
    if receipt["status"] != "P029_SECURITY_INTERPROCEDURAL_V2_COMPLETE":
        raise ValueError("P030_P029_NOT_COMPLETE")
    return dict(
        status="PASS",
        P029_fingerprints=PINS,
        P029_status=receipt["status"],
        P025_P026_P027_P028_freeze=receipt["historical_freeze"],
        initial_HEAD=SOURCE,
        HTML_deletion="PRESERVED_UNSTAGED",
        Architecture_science_drift=0,
        P029_detector_drift=0,
    )


def intake(rows: tuple[dict[str, Any], ...]) -> dict[str, Any]:
    """Normal discovery → ParseRepository → BuildIAM → validate_iam; static bytes only."""
    checked = []
    runtimes: dict[str, Any] = {}
    for row in rows:
        with TemporaryDirectory(prefix="archguard-p030-") as directory:
            root = Path(directory)
            for source in row["source_files"]:
                p = root / source["path"]
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(source["content"])
            builder = BuildIAM(
                ParseRepository(create_parser_registry(), ParserConfig(strict_syntax_errors=True)),
                create_extractor_registry(),
                ExtractionConfig(
                    repository_namespace=row["project_id"], project_name=row["project_id"]
                ),
            )
            with create_discovery().open(
                RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
            ) as repo:
                result = builder.execute(repo.snapshot, repo.workspace)
            if (
                not result.is_valid
                or not result.is_complete
                or result.statistics.files_with_parse_errors
                or result.statistics.files_extracted != len(row["source_files"])
            ):
                raise ValueError("P030_PARSE_IAM_INVALID:" + row["case_id"])
            validate_built_iam(result.iam)
            locations = [
                n.source_location for n in result.iam.nodes if n.source_location is not None
            ]
            if {f["path"] for f in row["source_files"]} - {
                loc.file_path for loc in locations
            } or any(loc.start_line < 1 for loc in locations):
                raise ValueError("P030_SOURCE_LOCATION_INVALID")
            for meta in result.parsing.files:
                if meta.has_syntax_errors or meta.parser is None or meta.language is None:
                    raise ValueError("P030_PARSE_INVALID")
                runtimes[meta.language.value] = meta.parser.model_dump(mode="json")
            checked.append(
                dict(
                    case_id=row["case_id"],
                    source_bundle_fingerprint=row["source_bundle_fingerprint"],
                    files=result.statistics.files_extracted,
                    symbols=len(result.iam.symbols),
                    locations=len(locations),
                    status="VALID",
                )
            )
    return dict(
        status="PASS",
        cases=len(checked),
        parse_success=len(checked),
        IAM_valid=len(checked),
        source_location_mapping="PASS",
        method=(
            "normal discovery/ParseRepository/BuildIAM/validate_iam; no compiler, "
            "external dependency install, source execution or detector"
        ),
        parser_runtimes=runtimes,
        validation_inventory_fingerprint=digest(checked),
    )


def protocol() -> dict[str, Any]:
    return dict(
        version=VERSION,
        purpose="Controlled post-thesis Security rule-level effectiveness foundation; no results",
        size=dict(total=300, DEV=100, FINAL=200),
        languages=dict(JAVA=150, TYPESCRIPT=150),
        cases_per_rule=30,
        per_rule=dict(
            DEV=dict(JAVA=5, TYPESCRIPT=5, mutation=5, control=5),
            FINAL=dict(JAVA=10, TYPESCRIPT=10, mutation=10, control=10),
        ),
        generation=dict(
            algorithm="ordered rule/language/variant enumeration, SHA256 design identities",
            randomness=False,
            seed=None,
            generator_version=VERSION,
            projects=300,
            template_families=300,
            selection="all valid generated cases; no detector filtering",
        ),
        intent_is_truth=False,
        human_truth="NOT_YET_AVAILABLE",
        detector_predictions=0,
        framework_scope=(
            "P029 partial selected semantics, supplied external API contracts; "
            "opaque wrappers/unsupported syntax are deliberate uncertainty "
            "contexts; no full compiler/framework/runtime guarantee"
        ),
        TS_SEC005=(
            "15 cases carry PRIVATE UNSUPPORTED_BY_CURRENT_DETECTOR expectation; "
            "human label decided independently, never forced OOS"
        ),
        final_chronology=[
            "human review collection in restricted custody",
            "DEV may inform a new version, never overwrite P029",
            "freeze detector/config/version",
            "run FINAL through source-only capability without truth or intent",
            "freeze FINAL predictions",
            "explicit later truth-open stage",
            "evaluate without remapping",
        ],
        access=(
            "Separate reviewer A/B packet roots; coordinator ledger outside worker "
            "root; split-specific prediction source allowlist; later process/OS "
            "mounts must enforce custody isolation. P030 only prepares directories "
            "and application guard, no execution authorization."
        ),
        limitations=[
            "controlled synthetic, not natural vulnerability prevalence",
            "N=300, DEV100/FINAL200; rule strata small",
            "Java/TypeScript only",
            "P029 selected framework semantics",
            "TS SEC005 unsupported",
            "human truth unavailable",
            "construction artifacts and shared semantic concepts",
            "real-world OSS effectiveness and exploitability not established",
        ],
        next_stage="P031_SECURITY_HUMAN_REVIEW",
        P031_started=False,
    )


def build_public(
    rows: tuple[dict[str, Any], ...],
    review: dict[str, dict[str, Any]],
    audit: dict[str, Any],
    validation: dict[str, Any],
    history: dict[str, Any],
    quality: dict[str, Any],
    implementation: str,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    private = private_material(rows, review)
    private_hashes = {
        p: hashlib.sha256(serialized(v).encode()).hexdigest() for p, v in private.items()
    }
    parts = {
        "SECURITY_BENCHMARK_CASE_INVENTORY_FINGERPRINT": digest(
            private["coordinator/case-inventory.json"]
        ),
        "SECURITY_DEV_COHORT_FINGERPRINT": digest(private["coordinator/DEV-cohort.json"]),
        "SECURITY_FINAL_COHORT_FINGERPRINT": digest(private["coordinator/FINAL-cohort.json"]),
        "SECURITY_REVIEWER_A_PACKET_SET_FINGERPRINT": digest(
            {p: v for p, v in review.items() if p.startswith("packets/A/")}
        ),
        "SECURITY_REVIEWER_B_PACKET_SET_FINGERPRINT": digest(
            {p: v for p, v in review.items() if p.startswith("packets/B/")}
        ),
        "construction_intent_ledger_fingerprint": digest(
            private["coordinator/construction-intent.json"]
        ),
        "private_bundle_fingerprint": digest(private_hashes),
    }
    values = {
        "benchmark-protocol.json": protocol(),
        "human-review-protocol.json": human_protocol(),
        "security-metric-protocol.json": metric_protocol(),
        "review-packet.schema.json": ReviewPacket.model_json_schema(),
        "review-response.schema.json": ReviewResponse.model_json_schema(),
        "aggregate-inventory.json": dict(
            **audit["counts"],
            per_rule={
                rule: dict(total=30, DEV=10, FINAL=20, JAVA=15, TYPESCRIPT=15)
                for rule in (f"SEC{i:03d}" for i in range(1, 11))
            },
            framework_counts=dict(sorted(Counter(r["framework_context"] for r in rows).items())),
            flow_shape_counts=dict(sorted(Counter(r["flow_shape"] for r in rows).items())),
            TS_SEC005_unsupported=15,
            detector_predictions=0,
        ),
        "split-separation-certificate.json": audit["separation"],
        "leakage-audit.json": dict(
            **audit["blindness"],
            dependency=audit["dependency"],
            public_case_metadata=False,
            synthetic_source_provenance="generated only; no secret-bearing file read",
        ),
        "construction-validation.json": validation,
        "private-fingerprint-manifest.json": dict(
            **parts,
            private_files=len(private_hashes),
            case_sources_not_public=True,
            public_case_IDs=False,
            reproduction=(
                "scripts/prompt030_security_benchmark.py freeze/verify from committed "
                "source; reproduce in a private ignored root"
            ),
        ),
        "p031-human-review-handoff.json": dict(
            review_required=True,
            reviewers=["A", "B"],
            cases_per_reviewer=300,
            independent=True,
            AI_labels_permitted=False,
            construction_intent_visible=False,
            detector_output_visible=False,
            truth_available=False,
            next_stage="P031_SECURITY_HUMAN_REVIEW",
            started=False,
            delivery=(
                "coordinator delivers ONLY the respective packets/A or packets/B root "
                "plus reviewer guide/schema; no coordinator/prediction roots, Git "
                "generator or opposite reviewer materials"
            ),
        ),
        "quality-verification.json": {k: v for k, v in quality.items() if k != "fingerprint"},
    }
    sealed = {n: thesis.sealed(v) for n, v in values.items()}
    fingerprints = parts | {
        "SECURITY_BENCHMARK_PROTOCOL_FINGERPRINT": sealed["benchmark-protocol.json"]["fingerprint"],
        "SECURITY_DEV_FINAL_SEPARATION_FINGERPRINT": sealed["split-separation-certificate.json"][
            "fingerprint"
        ],
        "SECURITY_HUMAN_REVIEW_PROTOCOL_FINGERPRINT": sealed["human-review-protocol.json"][
            "fingerprint"
        ],
        "SECURITY_METRIC_PROTOCOL_FINGERPRINT": sealed["security-metric-protocol.json"][
            "fingerprint"
        ],
        "SECURITY_REVIEW_PACKET_SCHEMA_FINGERPRINT": sealed["review-packet.schema.json"][
            "fingerprint"
        ],
        "SECURITY_REVIEW_RESPONSE_SCHEMA_FINGERPRINT": sealed["review-response.schema.json"][
            "fingerprint"
        ],
    }
    manifest = thesis.sealed(
        dict(
            version=VERSION,
            status="P030_SECURITY_BENCHMARK_FOUNDATION_COMPLETE",
            initial_HEAD=SOURCE,
            implementation_commit=implementation,
            counts=audit["counts"],
            fingerprints=fingerprints,
            source_bindings={p: io.sha(Path(p)) for p in SOURCES},
            historical_freeze=history,
            protocol_fingerprints={n: v["fingerprint"] for n, v in sealed.items()},
            benchmark_cohort="FROZEN",
            human_truth="NOT_YET_AVAILABLE",
            Security_effectiveness="NOT_EVALUATED",
            **{k: v for k, v in BOUNDARIES.items() if k != "Security_effectiveness"},
        )
    )
    sealed["benchmark-manifest.json"] = manifest
    return sealed, private


def privacy(paths: tuple[Path, ...]) -> dict[str, Any]:
    v1.privacy(paths)
    # Public JSON contains aggregate counts/protocols/hashes only; source material stays ignored.
    for p in paths:
        if p.suffix == ".json":
            text = p.read_text()
            if re.search(
                (
                    '"case_id"\\s*:\\s*"sc-[a-f0-9]{24}"|"source_files"\\s*:\\s*\\[|"constructio'
                    'n_intent"\\s*:\\s*"'
                ),
                text,
            ):
                raise ValueError("P030_PUBLIC_CASE_LEAKAGE")
    return dict(
        status="PASS",
        public_files=len(paths),
        credential_reads=0,
        private_literals_persisted_publicly=False,
    )


def validate() -> dict[str, Any]:
    history = historical_audit()
    rows, review, audit = material()
    if (rows, review, audit) != material():
        raise ValueError("P030_NONDETERMINISTIC_GENERATION")
    validation = intake(rows)
    return dict(status="PASS", history=history, design=audit, construction=validation, **BOUNDARIES)


def write_new(path: Path, value: Any, private: bool = False) -> None:
    content = serialized(value)
    if (
        path.name.startswith(".env")
        or path.is_symlink()
        or any(p.is_symlink() for p in path.parents)
    ):
        raise ValueError("unsafe output path")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700 if private else 0o755)
    with path.open("x") as stream:
        stream.write(content)
    if private:
        path.chmod(0o600)


def freeze(quality_path: Path, implementation: str) -> dict[str, Any]:
    if quality_path.name.startswith(".env") or quality_path.suffix != ".json":
        raise ValueError("unsafe quality path")
    quality = io.read_seal(quality_path)
    required = (
        "make_check",
        "ruff",
        "format",
        "strict_mypy",
        "targeted_tests",
        "Security_regressions",
        "parser_regressions",
        "ARCH_SEC_firewall",
        "privacy",
        "secret_audit",
        "diff_check",
    )
    if any(quality.get(k) != "PASS" for k in required) or any(
        quality.get(k) != 0 for k in ("provider_calls", "credential_reads", "detector_predictions")
    ):
        raise ValueError("P030_QUALITY_INCOMPLETE")
    if quality.get("source_bindings") != {p: io.sha(Path(p)) for p in SOURCES}:
        raise ValueError("P030_QUALITY_SOURCE_DRIFT")
    if subprocess.check_output(["git", "rev-parse", "HEAD"]).decode().strip() != implementation:
        raise ValueError("implementation HEAD mismatch")
    history = historical_audit()
    rows, review, audit = material()
    validation = intake(rows)
    public, private = build_public(
        rows, review, audit, validation, history, quality, implementation
    )
    if (public, private) != build_public(*material(), validation, history, quality, implementation):
        raise ValueError("P030_NONDETERMINISTIC_FREEZE")
    if PUBLIC.exists() or PRIVATE.exists():
        raise ValueError("P030_FROZEN_ROOT_ALREADY_EXISTS")
    privacy(tuple(Path(p) for p in (*SOURCES, *DOCS, ".gitignore")))
    for p, v in private.items():
        write_new(PRIVATE / p, v, True)
    private_index = thesis.sealed(
        dict(files={p: io.sha(PRIVATE / p) for p in private}, intent_is_truth=False)
    )
    write_new(PRIVATE / "freeze-index.json", private_index, True)
    for n, v in public.items():
        write_new(PUBLIC / n, v)
    privacy(tuple(PUBLIC / n for n in public))
    index = thesis.sealed(
        dict(
            files={n: io.sha(PUBLIC / n) for n in public},
            fingerprints={n: v["fingerprint"] for n, v in public.items()},
            documents={p: io.sha(Path(p)) for p in DOCS},
            private_freeze_fingerprint=private_index["fingerprint"],
        )
    )
    write_new(PUBLIC / "freeze-index.json", index)
    return verify()


def verify() -> dict[str, Any]:
    history = historical_audit()
    index = io.read_seal(PUBLIC / "freeze-index.json")
    io.verify_files(
        PUBLIC, index["files"] | {"freeze-index.json": io.sha(PUBLIC / "freeze-index.json")}
    )
    private_index = io.read_seal(PRIVATE / "freeze-index.json", index["private_freeze_fingerprint"])
    io.verify_files(
        PRIVATE,
        private_index["files"] | {"freeze-index.json": io.sha(PRIVATE / "freeze-index.json")},
    )
    manifest = io.read_seal(
        PUBLIC / "benchmark-manifest.json", index["fingerprints"]["benchmark-manifest.json"]
    )
    quality = io.read_seal(
        PUBLIC / "quality-verification.json",
        manifest["protocol_fingerprints"]["quality-verification.json"],
    )
    validation = io.read_seal(PUBLIC / "construction-validation.json")
    rows, review, audit = material()
    public, private = build_public(
        rows,
        review,
        audit,
        {k: v for k, v in validation.items() if k != "fingerprint"},
        history,
        quality,
        manifest["implementation_commit"],
    )
    for n, v in public.items():
        if io.read_seal(PUBLIC / n, index["fingerprints"][n]) != v:
            raise ValueError("P030_PUBLIC_FREEZE_DRIFT")
    for p, v in private.items():
        if (PRIVATE / p).read_text() != serialized(v):
            raise ValueError("P030_PRIVATE_REPRODUCTION_DRIFT")
    for p, h in index["documents"].items():
        if io.sha(Path(p)) != h:
            raise ValueError("P030_DOCUMENT_DRIFT")
    blindness_audit(review)
    privacy(
        tuple(Path(p) for p in (*SOURCES, *DOCS, ".gitignore"))
        + tuple(PUBLIC / n for n in ARTIFACTS)
    )
    return dict(
        status=manifest["status"],
        counts=manifest["counts"],
        fingerprints=manifest["fingerprints"]
        | {"SECURITY_BENCHMARK_MANIFEST_FINGERPRINT": manifest["fingerprint"]},
        private_freeze="PASS",
        historical_freeze="PASS",
        **BOUNDARIES,
    )
