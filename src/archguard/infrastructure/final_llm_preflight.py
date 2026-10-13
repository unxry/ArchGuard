"""Offline FINAL packaging from exact P020 bytes; no truth or model execution."""

import contextvars
import os
import subprocess
import sys
from collections import Counter
from collections.abc import Iterator
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.benchmark.unified_hybrid import RULES
from archguard.infrastructure import development_llm_executor as core
from archguard.infrastructure import final_llm_executor as e
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal

P016_MANIFEST = Path("experiments/semantic-holdout/private/p016-execution-v1/request-manifest.json")
PRICING = Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json")
P023 = io.PRIVATE / "p023-hybrid-models-v1"
SOURCES = (
    "src/archguard/infrastructure/final_llm_executor.py",
    "src/archguard/infrastructure/final_llm_preflight.py",
    "scripts/prompt024_final.py",
    "tests/intelligence/test_final_llm.py",
)
SHARED = (
    "src/archguard/infrastructure/development_llm_executor.py",
    "src/archguard/infrastructure/semantic_positive_live.py",
    "src/archguard/infrastructure/llm_provider.py",
    "src/archguard/infrastructure/semantic_preflight.py",
    "src/archguard/benchmark/semantic_positive_experiment.py",
    "src/archguard/benchmark/unified_hybrid.py",
    "src/archguard/benchmark/semantic_preflight.py",
)
PUBLIC = (
    *SOURCES,
    "docs/verification/PROMPT_024.md",
    *(
        str(io.BASE / n)
        for n in (
            "p024-final-preflight-v1.json",
            "p024-approval-summary-v1.json",
            "p024-model-lock-v1.json",
            "p024-verification-v1.json",
        )
    ),
)
ANCHORS = io.COMMITS | {
    "P021.A": "e82de9d0efc8e7e4dda444626aae86ce7f851628",
    "P021.B.1": "4a51a302c0b58ce148797aed14013803bf2a8488",
    "P021.B": "86f19f50de2f638a57192694e5c73afde3fa50dc",
    "P022": "8629d728bf80b4a5ba3009e8730ec14062a77abc",
    "P022.LIVE": "c416b1c1376009c8591026165323268201882495",
    "P023": "881e7b523198f40a09b79000016a1707efe4ecde",
}
_ACTIVE: contextvars.ContextVar[bool] = contextvars.ContextVar("p024_prepare_guard", default=False)
_INSTALLED = False


def prep_hook(event: str, args: tuple[Any, ...]) -> None:
    if not _ACTIVE.get() or event != "open" or isinstance(args[0], int):
        return
    path = Path(os.fsdecode(args[0])).resolve()
    if path.name.startswith(".env"):
        raise PermissionError("P024_NO_CREDENTIAL_ACCESS")
    if path.is_relative_to(io.PRIVATE.resolve()):
        allowed = {
            (io.PRIVATE / "p022-development-execution-v1/manifest.json").resolve(),
            *(
                (P023 / n).resolve()
                for n in (
                    "selected-model-registry.json",
                    "development-prediction-registry.json",
                    "validation-selection-receipt.json",
                    "final-full-hybrid-model.json",
                )
            ),
            *((P023 / "selected" / f"{k}.json").resolve() for k in ("A4", "A5", "A6", "A7")),
            (io.FINAL / "requests/manifest.json").resolve(),
            (io.FINAL / "requests/contexts.json").resolve(),
            *(
                (io.FINAL / "evidence" / n).resolve()
                for n in ("static-output.json", "graph-output.json", "evidence.json")
            ),
        }
        payload = (
            path.parent == (io.FINAL / "requests/payloads").resolve() and path.suffix == ".json"
        )
        generated = any(
            path.is_relative_to(p.resolve()) for p in (e.ROOT, e.LEDGER, e.APPROVAL_ROOT)
        )
        temporary = any(
            p.name.startswith(".archguard-review-") and p.parent == io.PRIVATE.resolve()
            for p in (path, *path.parents)
        )
        writes = any(c in (args[1] or "") for c in "wax+") or bool(
            args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        )
        if generated or temporary or (not writes and (path in allowed or payload)):
            return
        raise PermissionError("P024_FORBIDDEN_PRIVATE_ARTIFACT")
    semantic = Path("experiments/semantic-holdout/private").resolve()
    if path.is_relative_to(semantic) and path != P016_MANIFEST.resolve():
        raise PermissionError("P024_DEVELOPMENT_OR_HUMAN_TRUTH_DENIED")


@contextmanager
def offline_scope() -> Iterator[None]:
    global _INSTALLED
    if not _INSTALLED:
        sys.addaudithook(prep_hook)
        _INSTALLED = True
    if not core._INSTALLED:
        sys.addaudithook(core.audit_hook)
        core._INSTALLED = True
    active = _ACTIVE.set(True)
    guarded = core._GUARDED.set(True)
    network = core._NETWORK.set(False)
    try:
        yield
    finally:
        core._NETWORK.reset(network)
        core._GUARDED.reset(guarded)
        _ACTIVE.reset(active)


def seal(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        value = io.read_seal(path)
        if value != payload | {"fingerprint": digest(payload)}:
            raise io.ReviewBlocked("P024_FROZEN_ARTIFACT_DRIFT")
        return value
    return io.append_seal(path, payload)


def git_gate(*, live: bool = False) -> None:
    io.scientific_status(
        subprocess.check_output(["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]),
        () if live else PUBLIC,
    )
    for sha in ANCHORS.values():
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P024_LINEAGE_DRIFT")
    chain = ("P019", "P020_CLOSURE", "P021.A", "P021.B.1", "P021.B", "P022", "P022.LIVE", "P023")
    for a, b in zip(chain, chain[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", ANCHORS[a], ANCHORS[b]], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P024_LINEAGE_ORDER_DRIFT")


def model_gate() -> dict[str, Any]:
    verify_opaque_seal(
        io.BASE / "p023-hybrid-development-v1.json",
        "458ce5a8fcf1a95e9f80eed737ff75eb32e0c716b8dbc7d8af7f77eecd23af21",
    )
    registry = io.read_seal(P023 / "selected-model-registry.json", e.REGISTRY_FP)
    correction = io.read_seal(
        io.BASE / "p023-boundary-correction-v1.json",
        "d851ea5086b1da8dcf04859d64f1c6e05c03786b5076975f2ac64575cea701ae",
    )
    for name, sha in correction["corrected_source_bindings"].items():
        if io.sha(Path(name)) != sha:
            raise io.ReviewBlocked("P024_BLOCKED_P023_MODEL_DRIFT")
    pins = {
        "selected-model-registry.json": e.REGISTRY_FP,
        "development-prediction-registry.json": (
            "5e663cf3890d19fb89cac2dc0672091ef4a85249ab7eb7040ea1844b07bd6632"
        ),
        "validation-selection-receipt.json": (
            "e4220400f08739d5ec71bec0747b23e2ab412b01b40236e5b03c4bcb0ec3cb7d"
        ),
        "final-full-hybrid-model.json": e.MODEL_FP,
    }
    for name, fp in pins.items():
        verify_opaque_seal(P023 / name, fp)
    for config, entry in registry["models"].items():
        verify_opaque_seal(P023 / "selected" / f"{config}.json", entry["candidate_fingerprint"])
    if registry["post_selection_refit"] or registry["models"]["A7"]["threshold"] != 0.75:
        raise io.ReviewBlocked("P024_BLOCKED_P023_MODEL_DRIFT")
    return dict(
        version="p024-p023-model-lock-v1",
        selected_registry_fingerprint=e.REGISTRY_FP,
        final_model_fingerprint=e.MODEL_FP,
        selection_receipt_fingerprint=pins["validation-selection-receipt.json"],
        scientific_aggregate_fingerprint=(
            "458ce5a8fcf1a95e9f80eed737ff75eb32e0c716b8dbc7d8af7f77eecd23af21"
        ),
        boundary_correction_fingerprint=correction["fingerprint"],
        selected={
            k: {
                n: v[n]
                for n in (
                    "selected_family",
                    "candidate_fingerprint",
                    "threshold",
                    "preprocessing_fingerprint",
                    "parameter_fingerprint",
                    "precedence_fingerprint",
                    "implementation_fingerprint",
                )
            }
            for k, v in registry["models"].items()
        },
        retraining_authorized=False,
    )


def source_gate() -> tuple[dict[str, Any], dict[str, Any], PricingAssumption, dict[str, Any]]:
    registry = io.read_seal(
        io.BASE / "p020-registry-v2.json",
        "2bec29bb5d19419d90e8a5627a49044c82c33f7f13528116d587ade70d0a4116",
    )
    plan = io.read_seal(
        io.BASE / "p020-plan-v1.json",
        "6d8610eac7b147b45cd3fcfbdbc3f30df22a300dbadf3a15be86741dc0eda4ac",
    )
    base = plan["protocol"]
    cohort = io.read_seal(io.BASE / "p020-final-holdout-freeze-v1.json", registry["final_holdout"])
    counts = cohort["counts"]
    if (
        counts["cases"] != 300
        or counts["JAVA"] != 150
        or counts["TYPESCRIPT"] != 150
        or counts["families"] != {"NORMATIVE_STATIC": 100, "GRAPH_STRUCTURAL": 100, "SEMANTIC": 100}
        or counts["per_rule"] != {r: 20 for r in RULES}
        or cohort["overlaps"]["development_projects"] != 0
    ):
        raise io.ReviewBlocked("P024_FINAL_COHORT_DRIFT")
    cert = io.read_seal(io.BASE / "p020-development-freeze-v1.json", registry["development_freeze"])
    if cert["final_overlap"] != 0:
        raise io.ReviewBlocked("P024_DEVELOPMENT_FINAL_OVERLAP")
    evidence = io.read_seal(
        io.BASE / "p020-final-evidence-freeze-v1.json",
        "0939f9256f77677c16234635b9e679bed244c8dc1c148b17a33281419f2d2c08",
    )
    if (
        evidence["records"] != 300
        or evidence["missing"]
        or evidence["duplicates"]
        or evidence["fingerprint_binding"] != registry["final_evidence"]
    ):
        raise io.ReviewBlocked("P024_FINAL_COMPONENT_DRIFT")
    for name, key in [
        ("static-output.json", "static_output_fingerprint"),
        ("graph-output.json", "graph_output_fingerprint"),
        ("evidence.json", "fingerprint_binding"),
    ]:
        verify_opaque_seal(io.FINAL / "evidence" / name, evidence[key])
    requests = io.read_seal(io.FINAL / "requests/manifest.json", registry["final_requests"])
    contexts = io.read_seal(io.FINAL / "requests/contexts.json", registry["final_contexts"])
    rows = requests["rows"]
    dev = io.read_seal(io.PRIVATE / "p022-development-execution-v1/manifest.json")
    sem = io.read_seal(
        P016_MANIFEST, "ec83ee1485a1275846b7c14ecfafad9db4749f0ca15e06d633d6ee9254c071b5"
    )
    development_ids = {r["request_id"] for r in dev["rows"]} | {
        r["request_id"] for r in sem["requests"]
    }
    development_cases = {r["execution_id"] for r in dev["rows"]} | {
        r["execution_case_id"] for r in sem["requests"]
    }
    if (
        len(rows) != 300
        or len({r["request_id"] for r in rows}) != 300
        or len({r["execution_id"] for r in rows}) != 300
        or any(
            r["request_id"] in development_ids or r["execution_id"] in development_cases
            for r in rows
        )
        or requests["stream"] != "FINAL"
        or requests["protocol_fingerprint"] != digest(base)
        or len(contexts["rows"]) != 300
    ):
        raise io.ReviewBlocked("P024_FINAL_REQUEST_SCOPE_DRIFT")
    if [r["execution_id"] for r in rows] != sorted((r["execution_id"] for r in rows), key=digest):
        raise io.ReviewBlocked("P024_FROZEN_ORDER_DRIFT")
    if {p.name for p in (io.FINAL / "requests/payloads").iterdir()} != {
        r["request_id"] + ".json" for r in rows
    }:
        raise io.ReviewBlocked("P024_FINAL_PAYLOAD_INVENTORY_DRIFT")
    if Counter(r["target_rule_id"] for r in rows) != {r: 20 for r in RULES}:
        raise io.ReviewBlocked("P024_RULE_COVERAGE_DRIFT")
    for row in rows:
        path = io.FINAL / "requests/payloads" / f"{row['request_id']}.json"
        material = io.read_seal(path)
        verify_opaque_seal(path, material["fingerprint"])
        e.audit_payload(material)
        wire = material["wire_payload"]
        task = io._json(wire["input"][1]["content"].encode())["task"]
        semantic = row["target_rule_id"].startswith("ARCH2")
        if (
            digest(wire) != row["request_fingerprint"]
            or digest(material["context"]) != row["context_fingerprint"]
            or e.visible_tokens(wire) != (row["input_estimate"], row["input_upper"])
            or task["request_id"] != row["request_id"]
            or task["target_rule_id"] != row["target_rule_id"]
            or task["target_question"]
            != base["semantic_questions" if semantic else "structural_questions"][
                row["target_rule_id"]
            ]
            or wire["input"][0]["content"]
            != base["semantic_system" if semantic else "structural_system"]
            or wire["text"]["format"]["schema"] != base["response_schema"]
            or row["context_chars"] > 20000
            or row["input_upper"] > 32768
        ):
            raise io.ReviewBlocked("P024_FINAL_EXACT_REQUEST_DRIFT")
    verify_opaque_seal(PRICING, "2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b")
    pricing = PricingAssumption.model_validate_json(PRICING.read_bytes())
    facts = dict(
        cases=300,
        JAVA=150,
        TYPESCRIPT=150,
        normative=100,
        graph=100,
        semantic=100,
        rules=15,
        cases_per_rule=20,
        Static_rows=300,
        Graph_rows=300,
        missing=0,
        duplicates=0,
        development_requests=0,
        development_final_overlap=0,
        separation_certificate_fingerprint=cert["fingerprint"],
        cohort_certificate_fingerprint=cohort["fingerprint"],
        static_fingerprint=evidence["static_output_fingerprint"],
        graph_fingerprint=evidence["graph_output_fingerprint"],
        common_evidence_fingerprint=registry["final_evidence"],
        request_manifest_fingerprint=requests["fingerprint"],
        context_manifest_fingerprint=contexts["fingerprint"],
        response_schema_fingerprint=digest(base["response_schema"]),
        forbidden_mounts=0,
        forbidden_payload_metadata=0,
        final_truth_reads=0,
    )
    return requests, base, pricing, facts


def prepare(*, verify: bool = False) -> dict[str, Any]:
    with offline_scope():
        git_gate()
        lock = model_gate()
        requests, base, pricing, facts = source_gate()
        rows = requests["rows"]
        config = e.protocol(base)
        cost = e.costs(rows, pricing)
        old = io.read_seal(
            io.BASE / "p020-cost-preflight-v1.json",
            "1eaea1ed1c51e80eb6eebb2370ebc1a0f3a11e5a010e17e7e375af27c717673d",
        )
        reconciliation = {}
        for key, oldkey in [
            ("expected_usd", "expected_usd"),
            ("conservative_usd", "conservative_usd"),
            ("configured_two_full_retries_usd", "absolute_with_retries_usd"),
        ]:
            total = Decimal(cost[key]) + Decimal(old["DEVELOPMENT"][oldkey])
            if Decimal(cost[key]) != Decimal(old["FINAL"][oldkey]) or total != Decimal(
                old["TOTAL"][oldkey]
            ):
                raise io.ReviewBlocked("P024_COST_RECONCILIATION_DRIFT")
            reconciliation[key] = dict(
                P020_whole=old["TOTAL"][oldkey],
                completed_development_estimate=old["DEVELOPMENT"][oldkey],
                frozen_final=old["FINAL"][oldkey],
                recombined=str(total),
            )
        if not e.ROOT.exists() and verify:
            raise io.ReviewBlocked("P024_BUNDLE_MISSING")
        if not e.ROOT.exists():

            def build(stage: Path) -> None:
                for name in ("manifest.json", "contexts.json"):
                    (stage / name).write_bytes((io.FINAL / "requests" / name).read_bytes())
                    (stage / name).chmod(0o600)
                for row in rows:
                    name = row["request_id"] + ".json"
                    dest = stage / "payloads" / name
                    dest.parent.mkdir(exist_ok=True, mode=0o700)
                    dest.write_bytes((io.FINAL / "requests/payloads" / name).read_bytes())
                    dest.chmod(0o600)
                for name, payload in [
                    ("protocol.json", config),
                    ("response-schema.json", dict(schema=base["response_schema"])),
                    ("order.json", dict(request_ids=[r["request_id"] for r in rows])),
                    ("cost-preflight.json", cost),
                    ("model-lock.json", lock),
                    (
                        "approval-contract.json",
                        dict(
                            required_fields=sorted(e.APPROVAL_FIELDS),
                            stage="FINAL_300_LLM",
                            paid_execution_approved=False,
                            approved_cap_usd=None,
                        ),
                    ),
                    (
                        "source-bindings.json",
                        dict(files={n: io.sha(Path(n)) for n in (*SOURCES, *SHARED)}),
                    ),
                ]:
                    io.append_seal(stage / name, payload)
                (stage / "pricing.json").write_bytes(PRICING.read_bytes())
                (stage / "pricing.json").chmod(0o600)
                io.append_seal(
                    stage / "bundle-freeze.json",
                    dict(
                        version="p024-final-execution-bundle-v1",
                        files={
                            p.relative_to(stage).as_posix(): io.sha(p)
                            for p in stage.rglob("*")
                            if p.is_file()
                        },
                        provider_calls=0,
                        paid_execution_approved=False,
                    ),
                )

            atomic_directory(e.ROOT, build)
        with e.final_scope(e.ROOT, e.LEDGER):
            manifest, actual, _ = e.load_bundle(e.ROOT)
            if manifest != requests or actual != config | {"fingerprint": digest(config)}:
                raise io.ReviewBlocked("P024_MOUNTED_REQUEST_OR_PROTOCOL_DRIFT")
            bundle = io.read_seal(e.ROOT / "bundle-freeze.json")
            sources = io.read_seal(e.ROOT / "source-bindings.json")["files"]
            e.prepare_ledger(e.LEDGER, bundle["fingerprint"])
            if {p.name for p in e.LEDGER.iterdir()} != {"ledger-header.json"}:
                raise io.ReviewBlocked("P024_LIVE_ALREADY_STARTED")
            bindings = e.approval_bindings(e.ROOT)
            costfp = io.read_seal(e.ROOT / "cost-preflight.json")["fingerprint"]
            lockfp = io.read_seal(e.ROOT / "model-lock.json")["fingerprint"]
            orderfp = io.read_seal(e.ROOT / "order.json")["fingerprint"]
        if sources != {n: io.sha(Path(n)) for n in (*SOURCES, *SHARED)}:
            raise io.ReviewBlocked("P024_EXECUTION_IMPLEMENTATION_DRIFT")
        for row in rows:
            name = row["request_id"] + ".json"
            if io.sha(e.ROOT / "payloads" / name) != io.sha(io.FINAL / "requests/payloads" / name):
                raise io.ReviewBlocked("P024_BYTE_IDENTITY_DRIFT")
        summary = seal(
            io.BASE / "p024-approval-summary-v1.json",
            dict(
                **bindings,
                paid_execution_approved=False,
                approved_cap_usd=None,
                expected_usd=cost["expected_usd"],
                conservative_usd=cost["conservative_usd"],
                configured_primary_ceiling_usd=cost["configured_primary_ceiling_usd"],
                one_full_retry_usd=cost["configured_one_full_retry_usd"],
                two_full_retries_usd=cost["configured_two_full_retries_usd"],
                recommended_cap_usd=cost["recommended_cap_usd"],
                next_command=(
                    ".venv/bin/python scripts/prompt024_final.py live --approval "
                    "experiments/unified-hybrid/private/unified-hybrid-experiment-v1/"
                    "p024-final-live-approval-v1/explicit-human-approval.json"
                ),
            ),
        )
        seal(io.BASE / "p024-model-lock-v1.json", lock)
        return seal(
            io.BASE / "p024-final-preflight-v1.json",
            dict(
                version="p024-final-preflight-v1",
                status="P024_FINAL_LLM_PREFLIGHT_COMPLETE",
                lineage=ANCHORS,
                hybrid_lock=lock,
                facts=facts,
                config=config,
                cost=cost,
                pricing_fingerprint=pricing.fingerprint,
                reconciliation=reconciliation,
                material_discrepancy=False,
                fingerprints=dict(
                    request_manifest=requests["fingerprint"],
                    context_manifest=requests["context_manifest_fingerprint"],
                    execution_order=orderfp,
                    protocol=digest(config),
                    bundle=bundle["fingerprint"],
                    cost_preflight=costfp,
                    approval_summary=summary["fingerprint"],
                    model_lock=lockfp,
                ),
                provider_invocations=0,
                connectivity_calls=0,
                credential_value_accessed=False,
                actual_spend_usd=0,
                invoice=None,
                paid_execution_approved=False,
                approved_hard_cap=None,
                live_started=False,
                hybrid_retraining=False,
                hybrid_predictions=0,
                final_evaluation=False,
                security=False,
            ),
        )
