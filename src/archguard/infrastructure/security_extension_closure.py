"P036 public-only synthesis of frozen Security evidence; no experiment execution."

import hashlib
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
from types import FrameType
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.infrastructure import security_foundation as foundation
from archguard.infrastructure import unified_human_review as io
from archguard.security.rules import NAMES

ROOT = Path("experiments/security/security-extension-v1")
PUBLIC = ROOT / "public"
DOC = Path("docs/verification/PROMPT_036.md")
BASE = "babcba6af3c04be30647820d0d11c03ac5535d96"
INPUT_FP = "158e8fc65e85a5727316b3dee3366f363eda2207f096b51227a9b8e4b1aa5802"
SOURCES = (
    "src/archguard/infrastructure/security_extension_closure.py",
    "src/archguard/infrastructure/security_closure_test_guard.py",
    "scripts/prompt036_security_closure.py",
    "tests/security/test_security_extension_closure.py",
    str(ROOT / ".gitignore"),
)
ZERO = dict.fromkeys(
    (
        "FINAL_ANALYZER_EXECUTIONS_DURING_P036",
        "DEV_ANALYZER_EXECUTIONS_DURING_P036",
        "ORIGINAL_FINAL_TRUTH_READS_DURING_P036",
        "HUMAN_TRUTH_300_READS",
        "DEV_TRUTH_READS",
        "CONSTRUCTION_INTENT_READS",
        "REVIEW_RATIONALE_READS",
        "ADJUDICATION_RATIONALE_READS",
        "PROVIDER_CALLS",
        "NETWORK_PROVIDER_CALLS",
        "OPENAI_CALLS",
        "LLM_CALLS",
        "CREDENTIAL_READS",
        "PAID_SPEND",
        "POST_FINAL_TUNING",
        "PRIVATE_HUMAN_DATA_COMMITTED",
        "PRIVATE_TRUTH_ROWS_COMMITTED",
        "PRIVATE_PREDICTION_ROWS_COMMITTED",
        "PRIVATE_ERROR_ROWS_COMMITTED",
        "CONSTRUCTION_INTENT_COMMITTED",
        "CREDENTIALS_COMMITTED",
    ),
    0,
)
INTERPRETATION = (
    "Precision among definitive positives is 92.68%. Under frozen P030 conditional "
    "confusion semantics, Recall=1.0 and F1=0.9620 because no definitive negative "
    "prediction was emitted. However, 47 of 85 human-positive FINAL cases remained "
    "nondefinitive: effective positive recovery is 44.71%, and binary definitive "
    "coverage is 21.47%. FN=0 does not mean no missed human-positive cases. "
    "Of 106 human negatives, 103 remained nondefinitive and 3 were false positives. "
    "Zero definitive negatives and zero true negatives mean definitive negative "
    "classification was not demonstrated; effective negative correctness is 0. "
    "The conditional FPR=1.0 uses the three definitive negative-truth outcomes, "
    "not all 106 human negatives. Controlled benchmark; no production guarantee."
)
LIMITATIONS = (
    "Controlled benchmark; not natural vulnerability prevalence.",
    "TOTAL=300, DEV=100, FINAL=200.",
    "Per-rule FINAL N=20.",
    "Java and TypeScript only.",
    "TypeScript SEC005 remains CONTRACT_ONLY.",
    "Human UNCERTAIN truth is excluded from binary metrics; FINAL has nine such cases.",
    "Bounded static/interprocedural analysis intentionally abstains often.",
    "FINAL nondefinitive rate is 79.5%.",
    "No definitive negative FINAL outputs; negative classification not demonstrated.",
    ("Conditional P/R/F1 do not represent recovery over all positives; 47 remained nondefinitive."),
    "Effective positive recovery is 44.71%.",
    "Definitive binary coverage is 21.47%.",
    "Three FINAL false positives, all within SEC001.",
    "DEV was used for V3 refinement; DEV results are development evidence.",
    ("FINAL truth was blind to detector tuning until prediction freeze; no post-FINAL tuning."),
    "P029 has no unbiased FINAL baseline; P029 FINAL effectiveness NOT_EVALUATED.",
    "Controlled benchmark family includes synthetic/mutation-based material.",
    "No production Security guarantee.",
    "No proof of whole-program soundness or completeness.",
    ("Completeness certificates are rule-scoped and bounded; no benchmark negatives certified."),
    ("No natural-prevalence or causal-effect claim, including language/capability comparisons."),
    "No scalability conclusion beyond measured controlled executions.",
)


def seal(value: dict[str, Any]) -> dict[str, Any]:
    return value | {"fingerprint": digest(value)}


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args]).decode().strip()


def guard_reason(event: str, args: tuple[Any, ...], root: Path) -> str | None:
    if event.startswith("socket.connect"):
        return "P036_OFFLINE_NETWORK_DENIED"
    if event != "open" or isinstance(args[0], int):
        return None
    path = Path(os.path.realpath(os.fsdecode(args[0])))
    security = root / "experiments/security"
    opaque = security / "security-benchmark-v1/private/freeze-index.json"
    own = root / ROOT
    if path.name.startswith(".env") and path.name != ".env.example":
        return "P036_CREDENTIAL_READ_DENIED"
    if path.is_relative_to(security) and not path.is_relative_to(own):
        relative = path.relative_to(security)
        if "private" in relative.parts and path != opaque:
            return "P036_PRIVATE_TRUTH_REVIEW_INTENT_PREDICTION_DENIED"
        flags = args[2] if len(args) > 2 and isinstance(args[2], int) else 0
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return "P036_FROZEN_SCIENTIFIC_WRITE_DENIED"
    return None


def access_guard(event: str, args: tuple[Any, ...]) -> None:
    reason = guard_reason(event, args, Path.cwd())
    if reason:
        raise PermissionError(reason)
    if event == "subprocess.Popen" and Path(os.fsdecode(args[0])).name != "git":
        raise PermissionError("P036_EXPERIMENT_PROCESS_DENIED")


def deny_analyzer(frame: FrameType, event: str, arg: Any) -> None:
    if (
        event == "call"
        and frame.f_code.co_name == "analyze"
        and frame.f_globals.get("__name__", "").startswith("archguard.security.analyzer")
    ):
        raise PermissionError("P036_ANALYZER_EXECUTION_DENIED")


def historical_audit() -> dict[str, Any]:
    config = io.read_seal(PUBLIC / "security-closure-inputs.json", INPUT_FP)
    indexes = {}
    for stage, entry in config["stages"].items():
        for key in ("implementation_commit", "corrective_commit", "closure_commit"):
            if entry.get(key):
                subprocess.run(
                    ["git", "merge-base", "--is-ancestor", entry[key], "HEAD"], check=True
                )
        path = Path(entry["index"])
        index = io.read_seal(path, entry["index_fingerprint"])
        historical = subprocess.check_output(["git", "show", f"{entry['closure_commit']}:{path}"])
        if io.sha(path) != entry["index_sha256"] or path.read_bytes() != historical:
            raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:" + stage)
        io.verify_files(path.parent, index["files"] | {path.name: io.sha(path)})
        if index.get("fingerprints", {}) != entry["scientific_pins"]:
            raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:" + stage)
        for name, expected in index.get("source_bindings", {}).items():
            if io.sha(Path(name)) != expected:
                raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:SOURCE")
        for name, expected in index.get("documents", {}).items():
            if expected != config["latest_source_document_bindings"][name]:
                original = subprocess.check_output(
                    ["git", "show", f"{entry['closure_commit']}:{name}"]
                )
                if hashlib.sha256(original).hexdigest() != expected:
                    raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:DOCUMENT")
        indexes[stage] = index
    for name, expected in config["latest_source_document_bindings"].items():
        if io.sha(Path(name)) != expected:
            raise ValueError("P036_INVALID_SCIENTIFIC_MUTATION:" + name)
    # P030 implementation bindings are nested in its public manifest.
    manifest = io.read_seal(
        Path(config["stages"]["P030"]["index"]).parent / "benchmark-manifest.json"
    )
    for name, expected in manifest["source_bindings"].items():
        if io.sha(Path(name)) != expected:
            raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:P030_SOURCE")
    architecture = config["architecture"]
    arch_path = Path(architecture["index"])
    arch_index = io.read_seal(arch_path, architecture["index_fingerprint"])
    io.verify_files(arch_path.parent, arch_index["files"] | {arch_path.name: io.sha(arch_path)})
    frozen = io.read_seal(foundation.ROOT / "security-boundary-receipt.json")["science_freeze"]
    for name, expected in frozen["architecture_source_hashes"].items():
        if io.sha(Path(name)) != expected:
            raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:ARCHITECTURE")
    if foundation.import_firewall()["status"] != "PASS":
        raise ValueError("P036_ARCHITECTURE_SEPARATION_FAILURE")
    for name in ("final-primary-metrics.json", "final-hypothesis.json", "evaluation-receipt.json"):
        expected = architecture[
            {
                "final-primary-metrics.json": "primary",
                "final-hypothesis.json": "hypothesis",
                "evaluation-receipt.json": "receipt",
            }[name]
        ]
        io.read_seal(Path("experiments/unified-hybrid/p025-final-results-v1") / name, expected)
    p035 = indexes["P035"]
    if (
        not p035["READY_FOR_P036_SECURITY_EXTENSION_CLOSURE"]
        or p035["status"] != "P035_SECURITY_FINAL_EVALUATION_COMPLETE"
    ):
        raise ValueError("P036_P035_INCOMPLETE")
    private_manifest = io.read_seal(
        Path(config["stages"]["P030"]["index"]).parent / "private-fingerprint-manifest.json"
    )
    if private_manifest["private_files"] + 1 != 927:
        raise ValueError("P036_BLOCKED_HISTORICAL_DRIFT:P030_INVENTORY")
    return seal(
        dict(
            status="PASS",
            stages=config["stages"],
            architecture=architecture,
            P030_inventory=config["P030_inventory_audit"],
            source_document_bindings="PASS",
            import_firewall="PASS",
            protected_private_content_reads=0,
            **ZERO,
        )
    )


def evidence(stage: str, name: str) -> dict[str, Any]:
    config = io.read_seal(PUBLIC / "security-closure-inputs.json", INPUT_FP)
    root = Path(config["stages"][stage]["index"]).parent
    return io.read_seal(root / name)


def wording_guard(text: str) -> None:
    lowered = text.lower()
    if any(
        s in lowered
        for s in (
            "100% recall",
            "high accuracy",
            "detects vulnerabilities accurately",
            "fully supports sec001",
            "zero false negatives",
        )
    ):
        raise ValueError("P036_BLOCKED_SCIENTIFIC_OVERCLAIM")
    if re.search(r"recall\s*[=:]|f1\s*[=:]", lowered) and not all(
        s in lowered for s in ("conditional", "44.71%", "21.47%", "47", "nondefinitive")
    ):
        raise ValueError("P036_BLOCKED_SCIENTIFIC_OVERCLAIM")


def build() -> dict[str, dict[str, Any]]:
    history = historical_audit()
    catalog = evidence("P027", "sec-rule-registry.json")
    rules = [{"rule_id": r["rule_id"], "name": r["name"]} for r in catalog["rules"]]
    if [r["name"] for r in rules] != list(NAMES) or [r["rule_id"] for r in rules] != [
        f"SEC{i:03d}" for i in range(1, 11)
    ]:
        raise ValueError("P036_RULE_CATALOG_DRIFT")
    cap = evidence("P033", "candidate-capability-matrix.json")
    limits = evidence("P033", "candidate-limits.json")
    cells = []
    for rule, languages in cap["matrix"].items():
        for language, status in languages.items():
            cells.append(
                dict(
                    rule=rule,
                    language=language,
                    capability_status=status,
                    positive_path_status="UNSUPPORTED"
                    if status == "CONTRACT_ONLY"
                    else "BOUNDED_RECOGNIZED_PATTERNS",
                    negative_completeness_status="CLOSED_LITERAL_TS_CRYPTO_GRAMMAR_ONLY"
                    if (rule, language) == ("SEC008", "TYPESCRIPT")
                    else "NOT_PROVEN",
                    interprocedural_scope=(
                        "Bounded local summaries, call resolution and object flow; "
                        "no whole-program proof"
                    ),
                    known_limitation="No TypeScript object deserialization model"
                    if status == "CONTRACT_ONLY"
                    else catalog["rules"][int(rule[3:]) - 1]["limitations"][0],
                )
            )
    primary = evidence("P035", "security-final-metrics.json")
    comparison = evidence("P035", "security-dev-final-generalization.json")
    baseline = evidence("P032", "security-dev-baseline-metrics.json")
    truth = evidence("P031", "security-human-truth-closure.json")
    agreement = evidence("P031", "security-human-agreement.json")["statistics"]["ALL"]
    summary = dict(
        scope="Controlled Security extension; Architecture RQ1–RQ6 unchanged",
        P029_V2_DEV=baseline,
        P033_V3_DEV=comparison["DEV"],
        P035_V3_FINAL=primary,
        P034_scope="One-shot blind FINAL prediction acquisition before P035 truth opening",
        DEV_USED_FOR_REFINEMENT=True,
        P029_FINAL_EFFECTIVENESS="NOT_EVALUATED",
        interpretation=INTERPRETATION,
        limitations=list(LIMITATIONS),
        benchmark=dict(TOTAL=300, DEV=100, FINAL=200, JAVA=150, TYPESCRIPT=150, per_rule=30),
        human_agreement=agreement,
        human_truth=truth,
        generalization=comparison,
        rules=evidence("P035", "security-final-rule-metrics.json")["groups"],
        languages=evidence("P035", "security-final-language-metrics.json")["groups"],
        capabilities=evidence("P035", "security-final-capability-metrics.json")["groups"],
        errors=evidence("P035", "security-final-error-summary.json"),
        strata_interpretation=(
            "Descriptive only; rule/composition differs; diagnostic gaps overlap "
            "and are not mutually exclusive causes"
        ),
        baseline_interpretation=(
            "V2 DEV P/R/F1 are conditional on definitive predictions; 7/37 "
            "positives recovered (18.92%), binary coverage 7/89 (7.87%); not "
            "comprehensive recall"
        ),
        generalization_interpretation=(
            "V3 gains did not collapse completely; FINAL recovery and precision "
            "were lower than DEV, while coverage remained similarly low. No blind "
            "P029 FINAL comparison exists."
        ),
    )
    wording_guard(INTERPRETATION)
    claims = [
        (
            "SCLM001",
            "SUPPORTED_WITHIN_CONTROLLED_BENCHMARK",
            (
                "Bounded static/interprocedural analysis produces high-precision "
                "definitive positives for a subset of SEC001–SEC010 patterns"
            ),
            "FINAL precision 92.68%; recovery 44.71%; binary coverage 21.47%",
        ),
        (
            "SCLM002",
            "SUPPORTED_WITH_LIMITATIONS",
            "Generic DEV-guided V3 refinement increased observed DEV positive recovery",
            "18.92% to 56.76% on DEV; development evidence, not blind FINAL comparison",
        ),
        (
            "SCLM003",
            "SUPPORTED_WITH_LIMITATIONS",
            "Frozen V3 retained partial positive-detection capability on held-out FINAL",
            "44.71% recovery; 47 positive nondefinitive; 21.47% binary coverage",
        ),
        (
            "SCLM004",
            "NOT_SUPPORTED",
            "Reliable definitive negative Security decisions",
            "Zero definitive negatives; effective negative correctness 0",
        ),
        (
            "SCLM005",
            "NOT_ESTABLISHED",
            "Generalization to natural real-world vulnerability prevalence",
            "Controlled synthetic/mutation-based benchmark",
        ),
    ]
    answers = dict(
        Q_SEC_A="YES within controlled FINAL evidence and definitive-positive subset",
        Q_SEC_B="YES on DEV: effective positive recovery 18.92% to 56.76%",
        Q_SEC_C="NO full persistence: held-out recovery 44.71%, below DEV 56.76%",
        Q_SEC_D="NOT DEMONSTRATED: zero definitive negatives on FINAL",
        Q_SEC_E="NO production completeness",
    )
    result = {
        "security-history-receipt.json": history,
        "security-rule-catalog.json": seal(
            dict(
                rules=rules,
                frozen_since="P027",
                aliases={"SEC006": "SSRF Risk", "SEC007": "XSS Risk"},
                renamed=0,
                added=0,
                removed=0,
                source_fingerprint=catalog["fingerprint"],
            )
        ),
        "security-final-capability-matrix.json": seal(
            dict(
                version="security-bounded-v3",
                candidate="iteration-004",
                cells=cells,
                limits=limits,
                engineering_scope=(
                    "Capability is engineering scope, never inferred from benchmark scores"
                ),
                source_fingerprint=cap["fingerprint"],
                metric_reference="security-experiment-summary.json",
            )
        ),
        "security-experiment-summary.json": seal(summary),
        "security-scientific-claims.json": seal(
            dict(
                claims=[dict(id=i, status=s, claim=c, evidence=e) for i, s, c, e in claims],
                security_questions=answers,
                architecture_RQ_rewrite=False,
            )
        ),
        "security-limitations.json": seal(
            dict(
                limitations={f"L{i}": t for i, t in enumerate(LIMITATIONS, 1)},
                interpretation=INTERPRETATION,
            )
        ),
        "security-resource-summary.json": evidence(
            "P035", "security-final-evaluation-resources.json"
        ),
        "security-reproducibility-manifest.json": seal(
            dict(
                commits=history["stages"],
                runtime=dict(
                    Python="CPython 3.13.14",
                    platform="macOS; P034 Seatbelt sandbox-exec",
                    dependencies=(
                        "Frozen repository environment; tree-sitter Java/TypeScript; "
                        "no new dependencies"
                    ),
                ),
                quality_command=(
                    "env -i PATH=/usr/bin:/bin:/usr/sbin:/sbin PYTHONHASHSEED=0 "
                    "PYTHONDONTWRITEBYTECODE=1 "
                    "PYTEST_PLUGINS=archguard.infrastructure.security_closure_test_guard "
                    "make check"
                ),
                public_verify_command=(
                    ".venv/bin/python scripts/prompt036_security_closure.py verify"
                ),
                published_verify_command=(
                    ".venv/bin/python scripts/prompt036_security_closure.py verify-published"
                ),
                levels={
                    "LEVEL_1_PUBLIC_VERIFICATION": (
                        "Public Git commits, sealed receipts, opaque fingerprints and "
                        "aggregates; private human/case content not required"
                    ),
                    "LEVEL_2_AUTHORIZED_SCIENTIFIC_REPLAY": (
                        "Custodian-approved frozen P034 predictions plus frozen P035 truth "
                        "copy; deterministic join/metrics/aggregates only; inputs remain "
                        "immutable. Not performed by P036"
                    ),
                    "LEVEL_3_EXPERIMENT_REEXECUTION": (
                        "Original private benchmark sources, frozen candidate and matching "
                        "runtime required; future run is a replication, never replacement of "
                        "historical blind P034 acquisition"
                    ),
                },
                do_not_rerun=(
                    "P034 one-shot blind acquisition; P029 FINAL baseline after truth "
                    "exposure; DEV refinement or detector tuning"
                ),
                private_required=(
                    "Frozen benchmark source bundle; raw/adapted predictions; human truth; "
                    "private join/error custody inventories. Human review/adjudication "
                    "records remain under separate custody"
                ),
                never_commit=(
                    "Human responses/identities/rationales, case truth/predictions, "
                    "joins/errors, construction intent, credentials, host sandbox profiles, "
                    "private quality logs"
                ),
                public_only_limit=(
                    "Private byte rehash and scientific replay require separate custody "
                    "authorization; public fingerprints establish bindings, not independent "
                    "access to hidden bytes"
                ),
                fingerprint_policy=(
                    "Canonical sorted JSON, SHA-256, no operational timestamps; historical "
                    "fingerprints copied unchanged"
                ),
            )
        ),
        "security-privacy-custody-receipt.json": seal(
            dict(
                status="PASS",
                verification_scope=(
                    "Security public scientific artifacts and tracked/staged publication "
                    "paths; private content never reopened"
                ),
                guard=(
                    "Deny protected opens, real network and credentials; CLI denies "
                    "analyzer execution and non-Git subprocesses"
                ),
                **ZERO,
            )
        ),
        "security-scientific-status.json": seal(
            dict(
                architecture_research_core="COMPLETE",
                security_rule_implementation="COMPLETE_AS_BOUNDED_RESEARCH_PROTOTYPE",
                prospective_benchmark="COMPLETE",
                independent_human_truth="COMPLETE",
                DEV_baseline="COMPLETE",
                DEV_refinement="COMPLETE",
                blind_FINAL_prediction="COMPLETE",
                FINAL_evaluation="COMPLETE",
                production_guarantee="NOT_CLAIMED",
                natural_prevalence_validation="NOT_ESTABLISHED",
                whole_program_completeness="NOT_CLAIMED",
                UI_UX="OUT_OF_SCOPE_FOR_P036",
                completion_semantics=(
                    "Bounded SEC001–SEC010 scope, benchmark, human truth, DEV "
                    "baseline/refinement, one frozen candidate, blind FINAL predictions, "
                    "later truth join, evaluated effectiveness, reproducible frozen results "
                    "and limitations under custody"
                ),
                excluded_completion_claims=(
                    "No solution to all vulnerability classes; no production readiness or "
                    "general negative classification; no whole-program "
                    "soundness/completeness; no UI/UX or manuscript completion"
                ),
            )
        ),
    }
    result["security-scientific-registry.json"] = seal(
        dict(
            extension_version="security-extension-v1",
            languages=["JAVA", "TYPESCRIPT"],
            stages=history["stages"],
            architecture_separation=history["architecture"],
            P036_scope="CLOSURE_ONLY; no new experiments or metrics",
            candidate="security-bounded-v3/iteration-004",
            artifacts={name: value["fingerprint"] for name, value in result.items()},
            interpretation=INTERPRETATION,
            limitations=list(LIMITATIONS),
            **ZERO,
        )
    )
    return result


def privacy(paths: list[Path]) -> None:
    pattern = r"sc-[a-f0-9]{24}|/Us" + r"ers/|Unit[a-f0-9]{8}|sk-[A-Za-z0-9]{16,}"
    for path in paths:
        if re.search(pattern, path.read_text()):
            raise ValueError("P036_PRIVACY_PUBLICATION_VIOLATION")
    tracked = git("ls-files", "--", "experiments/security").splitlines()
    staged = git("diff", "--cached", "--name-only").splitlines()
    if any("private" in Path(p).parts for p in tracked + staged) or any(
        Path(p).suffix == ".html" for p in staged
    ):
        raise ValueError("P036_PRIVACY_PUBLICATION_VIOLATION")


def write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical(value) + "\n")


def prepare() -> dict[str, Any]:
    if git("rev-parse", "HEAD") != BASE or git("rev-parse", "origin/main") != BASE:
        raise ValueError("P036_INVALID_START_HEAD")
    first, second = build(), build()
    if first != second:
        raise ValueError("P036_NONDETERMINISTIC_CLOSURE")
    for name, value in first.items():
        write(PUBLIC / name, value)
    privacy(list(PUBLIC.glob("*.json")))
    return dict(status="P036_PREPARED_QUALITY_REQUIRED", artifacts=len(first), **ZERO)


def metric_audit() -> None:
    m = evidence("P035", "security-final-metrics.json")
    p, n = m["truth_distribution"]["POSITIVE"], m["truth_distribution"]["NEGATIVE"]
    checks = dict(
        precision=m["TP"] / (m["TP"] + m["FP"]),
        effective_positive_recovery=m["TP"] / p,
        effective_negative_correctness=m["TN"] / n,
        definitive_coverage=(m["TP"] + m["FP"] + m["TN"] + m["FN"]) / m["binary_eligible"],
        effective_correctness=(m["TP"] + m["TN"]) / m["binary_eligible"],
        unified_correctness=(m["TP"] + m["TN"]) / m["N"],
        nondefinitive_rate=1 - sum(m[k] for k in ("TP", "FP", "TN", "FN")) / m["N"],
    )
    if any(not math.isclose(m[k], v, abs_tol=1e-15) for k, v in checks.items()) or (
        m["TP"],
        m["FP"],
        m["TN"],
        m["FN"],
        m["positive_nondefinitive"],
        m["negative_nondefinitive"],
    ) != (38, 3, 0, 0, 47, 103):
        raise ValueError("P036_FINAL_ARITHMETIC_DRIFT")


def verify() -> dict[str, Any]:
    expected = build()
    for name, value in expected.items():
        if io.read_seal(PUBLIC / name) != value:
            raise ValueError("P036_CLOSURE_DRIFT:" + name)
    metric_audit()
    privacy(list(PUBLIC.glob("*.json")) + [DOC] + [Path(p) for p in SOURCES])
    wording_guard(DOC.read_text())
    return dict(status="PASS", artifacts=len(expected), **ZERO)


def completion(quality: dict[str, Any], bundle: dict[str, dict[str, Any]]) -> dict[str, Any]:
    required = (
        "Ruff",
        "format",
        "strict_mypy",
        "privacy",
        "secret_audit",
        "determinism",
        "diff_check",
    )
    if (
        quality.get("status") != "PASS"
        or quality.get("make_check", {}).get("returncode") != 0
        or quality.get("make_check", {}).get("passed", 0) <= 0
        or not isinstance(quality.get("make_check", {}).get("warnings"), list)
        or any(quality.get(key) != "PASS" for key in required)
    ):
        raise ValueError("P036_QUALITY_INCOMPLETE")
    statuses: dict[str, Any] = dict.fromkeys(
        (
            "SECURITY_EXTENSION_COMPLETE",
            "SECURITY_RESEARCH_PROTOTYPE_COMPLETE",
            "SECURITY_RULE_CATALOG_FROZEN",
            "SECURITY_BENCHMARK_COMPLETE",
            "SECURITY_HUMAN_TRUTH_COMPLETE",
            "SECURITY_DEV_BASELINE_COMPLETE",
            "SECURITY_DEV_REFINEMENT_COMPLETE",
            "SECURITY_FINAL_BLIND_PREDICTION_COMPLETE",
            "SECURITY_FINAL_EVALUATION_COMPLETE",
            "P033_SECURITY_CANDIDATE_FROZEN",
            "FINAL_PREDICTION_REGISTRY_FROZEN",
            "ARCHITECTURE_SCIENCE_UNCHANGED",
            "CORE_THESIS_COMPLETE",
            "READY_FOR_NON_UI_BACKEND_PRODUCT_CLOSURE_OR_THESIS_INTEGRATION",
        ),
        "YES",
    )
    return seal(
        dict(
            status="P036_SECURITY_EXTENSION_CLOSURE_COMPLETE",
            artifacts={name: value["fingerprint"] for name, value in bundle.items()},
            quality_fingerprint=quality["fingerprint"],
            **statuses,
            **ZERO,
            SECURITY_FINAL_EFFECTIVENESS="EVALUATED",
            SECURITY_PRODUCTION_READINESS="NOT_CLAIMED",
            SECURITY_WHOLE_PROGRAM_SOUNDNESS="NOT_CLAIMED",
            SECURITY_NATURAL_PREVALENCE_GENERALIZATION="NOT_ESTABLISHED",
            UI_UX_STATUS="OUT_OF_SCOPE_FOR_P036",
            interpretation=INTERPRETATION,
            completion_scope="Bounded research prototype and frozen experiment; limitations remain",
        )
    )


def freeze() -> dict[str, Any]:
    if (PUBLIC / "freeze-index.json").exists():
        raise ValueError("P036_ALREADY_FROZEN")
    verify()
    bundle = {p.name: io.read_seal(p) for p in PUBLIC.glob("*.json")}
    quality = bundle.pop("quality-verification.json")
    implementation = quality["implementation_commit"]
    subprocess.run(
        ["git", "merge-base", "--is-ancestor", implementation, "origin/main"], check=True
    )
    for name in SOURCES:
        if Path(name).read_bytes() != subprocess.check_output(
            ["git", "show", f"{implementation}:{name}"]
        ):
            raise ValueError("P036_UNTESTED_SOURCE_MUTATION")
    closed = completion(quality, bundle)
    write(PUBLIC / "security-extension-closure.json", closed)
    final = seal(
        dict(
            extension_version="security-extension-v1",
            closure_fingerprint=closed["fingerprint"],
            scientific_registry=bundle["security-scientific-registry.json"]["fingerprint"],
            quality_fingerprint=quality["fingerprint"],
            SECURITY_EXTENSION_COMPLETE="YES",
        )
    )
    write(PUBLIC / "security-extension-final.json", final)
    names = dict(
        RULE_CATALOG="security-rule-catalog.json",
        SCIENTIFIC_REGISTRY="security-scientific-registry.json",
        CAPABILITY_MATRIX="security-final-capability-matrix.json",
        EXPERIMENT_SUMMARY="security-experiment-summary.json",
        SCIENTIFIC_CLAIMS="security-scientific-claims.json",
        LIMITATIONS="security-limitations.json",
        REPRODUCIBILITY_MANIFEST="security-reproducibility-manifest.json",
        PRIVACY_CUSTODY_RECEIPT="security-privacy-custody-receipt.json",
        QUALITY_RECEIPT="quality-verification.json",
        EXTENSION_CLOSURE="security-extension-closure.json",
    )
    fingerprints = {
        f"SECURITY_P036_{key}_FINGERPRINT": io.read_seal(PUBLIC / name)["fingerprint"]
        for key, name in names.items()
    }
    fingerprints["SECURITY_EXTENSION_FINAL_FINGERPRINT"] = final["fingerprint"]
    index = seal(
        dict(
            status=closed["status"],
            fingerprints=fingerprints,
            history=bundle["security-history-receipt.json"],
            files={p.name: io.sha(p) for p in sorted(PUBLIC.glob("*.json"))},
            source_bindings={name: io.sha(Path(name)) for name in SOURCES},
            documents={str(DOC): io.sha(DOC)},
            implementation_commit=implementation,
            quality_run_commit=implementation,
            git_publication=dict(
                implementation="PUBLISHED_TO_ORIGIN_MAIN",
                closure_commit="Containing commit; self-reference excluded from hashes",
                closure_publication=(
                    "Require normal push then verify-published; "
                    "final remote equality verified externally"
                ),
            ),
            **{k: v for k, v in closed.items() if k not in {"artifacts", "fingerprint", "status"}},
        )
    )
    write(PUBLIC / "freeze-index.json", index)
    return dict(
        status=closed["status"], fingerprint=index["fingerprint"], fingerprints=fingerprints
    )


def main() -> None:
    sys.addaudithook(access_guard)
    sys.setprofile(deny_analyzer)
    try:
        action = sys.argv[1]
        if action == "prepare":
            result = prepare()
        elif action == "freeze":
            result = freeze()
        elif action in {"verify", "verify-published"}:
            result = verify()
            if (PUBLIC / "freeze-index.json").exists():
                index = io.read_seal(PUBLIC / "freeze-index.json")
                io.verify_files(
                    PUBLIC,
                    index["files"] | {"freeze-index.json": io.sha(PUBLIC / "freeze-index.json")},
                )
                for name, expected in (index["source_bindings"] | index["documents"]).items():
                    if io.sha(Path(name)) != expected:
                        raise ValueError("P036_FINAL_BINDING_DRIFT")
                quality = io.read_seal(PUBLIC / "quality-verification.json")
                bundle = build() | {
                    "security-closure-inputs.json": io.read_seal(
                        PUBLIC / "security-closure-inputs.json", INPUT_FP
                    )
                }
                closed = io.read_seal(PUBLIC / "security-extension-closure.json")
                if closed != completion(quality, bundle):
                    raise ValueError("P036_FINAL_COMPLETION_DRIFT")
            if action == "verify-published":
                if not (PUBLIC / "freeze-index.json").exists() or not (
                    git("rev-parse", "HEAD") == git("rev-parse", "origin/main")
                ):
                    raise ValueError("P036_GIT_PUBLICATION_INCOMPLETE")
                result["HEAD_equals_origin_main"] = True
                remote = git("ls-remote", "origin", "refs/heads/main").split()[0]
                if remote != git("rev-parse", "HEAD"):
                    raise ValueError("P036_GIT_PUBLICATION_INCOMPLETE")
                result["HEAD_equals_remote_main"] = True
        else:
            raise ValueError("P036_UNKNOWN_ACTION")
    finally:
        sys.setprofile(None)
    print(json.dumps(result, sort_keys=True))
