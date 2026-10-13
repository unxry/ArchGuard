"""Offline coordinator gates and manifest-bound development-only execution packaging."""

import hashlib
import subprocess
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_preflight import PricingAssumption
from archguard.infrastructure import development_llm_executor as executor
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.oss_review import atomic_directory
from archguard.infrastructure.semantic_adjudication_acceptance import verify_opaque_seal

DEV = io.PRIVATE / "development"
ROOT = io.PRIVATE / "p022-development-execution-v1"
LEDGER = io.PRIVATE / "p022-development-live-ledger-v1"
PRICING = Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json")
SOURCE_FILES = (
    "src/archguard/infrastructure/development_llm_executor.py",
    "src/archguard/infrastructure/development_llm_preflight.py",
    "scripts/prompt022_development.py",
    "tests/intelligence/test_development_llm_executor.py",
)
ADAPTER_FILES = (
    "src/archguard/infrastructure/semantic_positive_live.py",
    "src/archguard/infrastructure/llm_provider.py",
)
PUBLIC_FILES = (
    *SOURCE_FILES,
    "docs/verification/PROMPT_022.md",
    (io.BASE / "p022-development-preflight-v1.json").as_posix(),
    (io.BASE / "p022-paid-approval-summary-v1.json").as_posix(),
    (io.BASE / "p022-verification-v1.json").as_posix(),
)
ANCHORS = {
    "P009": "1a0db742dd6908831e08a8c4e8cff144598d9c91",
    "P011.1": "df899b097bd07d240591c594baf1ff5ba77a831e",
    "P015.F": "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
    "P016": "802257d1211e519ae174736c8d83c3614f2678ea",
    **io.COMMITS,
    "P021.A": "e82de9d0efc8e7e4dda444626aae86ce7f851628",
    "P021.B.1": "4a51a302c0b58ce148797aed14013803bf2a8488",
    "P021.B": "86f19f50de2f638a57192694e5c73afde3fa50dc",
}


def freeze(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if path.exists():
        v = io.read_seal(path)
        if v != payload | {"fingerprint": digest(payload)}:
            raise io.ReviewBlocked("P022_FROZEN_PREFLIGHT_DRIFT")
        return v
    return io.append_seal(path, payload)


def human_gate() -> dict[str, Any]:
    """Orchestrator only; human case-level content is hashed, never passed to worker."""
    summary = io.read_seal(io.BASE / "p021-b-human-agreement-v1.json")
    verification = io.read_seal(io.BASE / "p021-b-verification-v1.json")
    committed = subprocess.check_output(
        ["git", "show", f"{ANCHORS['P021.B']}:{io.BASE / 'p021-b-verification-v1.json'}"]
    )
    if (
        committed != (io.BASE / "p021-b-verification-v1.json").read_bytes()
        or summary["fingerprint"] != verification["summary_fingerprint"]
    ):
        raise io.ReviewBlocked("P022_P021_B_FREEZE_DRIFT")
    if (
        summary["agreement"]["primary"]["n"] != 100
        or summary["agreement"]["primary"]["exact_agreement"] != 100
        or summary["conflict_summary"]["conflict_count"] != 0
        or not summary["final_semantic_truth_frozen"]
        or summary["truth_categories"]
        != {"POSITIVE": 50, "NEGATIVE": 50, "UNCERTAIN": 0, "OUT_OF_SCOPE": 0}
    ):
        raise io.ReviewBlocked("P022_P021_B_FREEZE_DRIFT")
    agreement_root = io.PRIVATE / "human-intake/agreement-v1"
    receipt = io.read_seal(agreement_root / "agreement-freeze-receipt.json")
    if receipt["agreement_fingerprint"] != verification["agreement_fingerprint"] or receipt[
        "accepted_receipts"
    ] != {role: summary["accepted"][role]["receipt_fingerprint"] for role in io.ROLES}:
        raise io.ReviewBlocked("P022_P021_B_FREEZE_DRIFT")
    verify_opaque_seal(agreement_root / "agreement.json", verification["agreement_fingerprint"])
    verify_opaque_seal(
        agreement_root / "conflicts.json", verification["conflict_manifest_fingerprint"]
    )
    for role in io.ROLES:
        row = summary["accepted"][role]
        folder = io.PRIVATE / f"human-intake/accepted/{role}/v0001"
        receipt = io.read_seal(folder / "acceptance-receipt.json", row["receipt_fingerprint"])
        if (
            io.sha(folder / "completed-response.json") != row["raw_sha256"]
            or io.sha(folder / "canonical-response.json") != receipt["canonical_sha256"]
        ):
            raise io.ReviewBlocked("P022_P021_B_FREEZE_DRIFT")
        if (
            hashlib.sha256(
                (folder / "canonical-response.json").read_bytes().rstrip(b"\n")
            ).hexdigest()
            != row["canonical_fingerprint"]
        ):
            raise io.ReviewBlocked("P022_P021_B_FREEZE_DRIFT")
    truth = io.PRIVATE / "human-intake/agreement-v1/truth"
    verify_opaque_seal(truth / "final-semantic-truth.json", summary["truth_fingerprint"])
    verify_opaque_seal(truth / "lineage.json", summary["truth_lineage_fingerprint"])
    verify_opaque_seal(truth / "freeze-receipt.json", summary["truth_receipt_fingerprint"])
    return dict(
        A_frozen=True,
        B_frozen=True,
        agreement_frozen=True,
        joined=100,
        conflicts=0,
        final_semantic_truth_frozen=True,
        distribution=summary["truth_categories"],
        public_freeze_fingerprint=summary["fingerprint"],
        executor_access=False,
        role="FINAL_HOLDOUT_ONLY; NOT_DEVELOPMENT_LABELS; NOT_NATURAL_PREVALENCE",
    )


def scientific_gate() -> tuple[dict[str, Any], dict[str, Any], PricingAssumption]:
    for sha in ANCHORS.values():
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P022_LINEAGE_DRIFT")
    chain = (
        "P009",
        "P011.1",
        "P015.F",
        "P016",
        "P017",
        "P018",
        "P019",
        "P020_CLOSURE",
        "P021.A",
        "P021.B.1",
        "P021.B",
    )
    for a, b in zip(chain, chain[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", ANCHORS[a], ANCHORS[b]], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P022_LINEAGE_ORDER_DRIFT")
    registry = io.read_seal(
        io.BASE / "p020-registry-v2.json", io.PINS[io.BASE / "p020-registry-v2.json"]
    )
    plan = io.read_seal(
        io.BASE / "p020-plan-v1.json",
        "6d8610eac7b147b45cd3fcfbdbc3f30df22a300dbadf3a15be86741dc0eda4ac",
    )
    base = plan["protocol"]
    expected = dict(
        provider="openai",
        model="gpt-6-luna",
        processing="STANDARD",
        concurrency=1,
        max_technical_retries=2,
        max_input_tokens=32768,
        max_output_tokens=2000,
        expected_output_tokens=600,
        timeout_seconds=90,
        context_strategy="GRAPH_GUIDED",
        hops=1,
        max_context_chars=20000,
    )
    if any(base[k] != v for k, v in expected.items()):
        raise io.ReviewBlocked("P022_FROZEN_PROVIDER_CONFIG_MISMATCH")
    manifest = io.read_seal(DEV / "requests/manifest.json", registry["development_requests"])
    contexts = io.read_seal(
        DEV / "requests/contexts.json", manifest["context_manifest_fingerprint"]
    )
    dev = io.read_seal(io.BASE / "p020-development-freeze-v1.json", registry["development_freeze"])
    inputs = io.read_seal(DEV / "inputs/manifest.json", dev["manifest_fingerprint"])
    split = io.read_seal(
        io.PRIVATE / "coordinator/development-split.json", registry["development_split"]
    )
    final = io.read_seal(io.FINAL / "inputs/manifest.json", registry["execution_manifest"])
    train = {r["project_id"] for r in split["rows"] if r["split"] == "TRAIN"}
    val = {r["project_id"] for r in split["rows"] if r["split"] == "VALIDATION"}
    project_by_case = {
        r["execution_id"]: str(
            io.read_seal(DEV / "inputs/iam" / r["iam_file"])["iam"]["project"]["id"]
        )
        for r in inputs["rows"]
    }
    final_projects = {
        str(io.read_seal(io.FINAL / "inputs/iam" / r["iam_file"])["iam"]["project"]["id"])
        for r in final["rows"]
    }
    projects = set(project_by_case.values())
    if (
        len(train) != 196
        or len(val) != 84
        or train & val
        or (train | val) != projects
        or projects & final_projects
        or len(inputs["rows"]) != 280
        or len(split["rows"]) != 280
        or any(
            project_by_case.get(r["scientific_case_id"]) != r["project_id"] for r in split["rows"]
        )
    ):
        raise io.ReviewBlocked("P022_SPLIT_ISOLATION_DRIFT")
    evidence = io.read_seal(DEV / "evidence/evidence.json", registry["development_evidence"])
    evrows = evidence["records"]
    if evidence["alignment_version"] != "evidence-alignment-v2":
        raise io.ReviewBlocked("P022_ALIGNMENT_DRIFT")
    if (
        len(evrows) != 280
        or len({r["execution_id"] for r in evrows}) != 280
        or {r["execution_id"] for r in evrows} != {r["execution_id"] for r in inputs["rows"]}
    ):
        raise io.ReviewBlocked("P022_EVIDENCE_DRIFT")
    for name, key in (
        ("static-output.json", "static_output_fingerprint"),
        ("graph-output.json", "graph_output_fingerprint"),
    ):
        verify_opaque_seal(DEV / "evidence" / name, evidence[key])
    reuse = io.read_seal(
        io.PRIVATE / "coordinator/development-semantic-reuse.json", registry["semantic_reuse"]
    )
    semantic_ids = {
        r["scientific_case_id"] for r in split["rows"] if r["target_rule_id"].startswith("ARCH2")
    }
    if (
        len(reuse["rows"]) != 100
        or {r["scientific_case_id"] for r in reuse["rows"]} != semantic_ids
    ):
        raise io.ReviewBlocked("P022_SEMANTIC_REUSE_DRIFT")
    if len({r["accepted_assessment"]["execution_case_id"] for r in reuse["rows"]}) != 100 or any(
        r["accepted_assessment"]["strategy"] != "GRAPH_GUIDED"
        or r["accepted_assessment"]["assessment"]["judgment"]
        not in {"SUPPORTED", "NOT_SUPPORTED", "INSUFFICIENT_CONTEXT", "NOT_APPLICABLE"}
        or r["normalized_fingerprint"]
        != "a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273"
        for r in reuse["rows"]
    ):
        raise io.ReviewBlocked("P022_SEMANTIC_REUSE_DRIFT")
    normalized = Path(
        "experiments/semantic-holdout/private/p016-live-v1/normalized-assessments.json"
    )
    verify_opaque_seal(
        normalized, "a76a29dc72a543f741683a8c5641ddf469e147e074d4aa9979c33027beeff273"
    )
    structural = {
        r["execution_id"] for r in inputs["rows"] if not r["target_rule_id"].startswith("ARCH2")
    }
    rows = manifest["rows"]
    if (
        len(rows) != 180
        or len({r["request_id"] for r in rows}) != 180
        or {r["execution_id"] for r in rows} != structural
        or len(structural) != 180
    ):
        raise io.ReviewBlocked("P022_BLOCKED_DEVELOPMENT_REQUEST_DRIFT")
    if (
        manifest["protocol_fingerprint"] != digest(base)
        or manifest["stream"] != "DEVELOPMENT"
        or len(contexts["rows"]) != 180
    ):
        raise io.ReviewBlocked("P022_BLOCKED_DEVELOPMENT_REQUEST_DRIFT")
    expected_prompt = digest(
        dict(
            system=base["structural_system"],
            questions=base["structural_questions"],
            schema=base["response_schema"],
        )
    )
    if expected_prompt != registry["structural_prompt"]:
        raise io.ReviewBlocked("P022_PROMPT_DRIFT")
    paths = {f"{r['request_id']}.json" for r in rows}
    if {p.name for p in (DEV / "requests/payloads").iterdir()} != paths:
        raise io.ReviewBlocked("P022_PAYLOAD_INVENTORY_DRIFT")
    for row in rows:
        material = io.read_seal(DEV / "requests/payloads" / f"{row['request_id']}.json")
        wire = material["wire_payload"]
        executor.audit_payload(material)
        task = io._json(wire["input"][1]["content"].encode())["task"]
        if (
            digest(wire) != row["request_fingerprint"]
            or digest(material["context"]) != row["context_fingerprint"]
            or executor.visible_tokens(wire) != (row["input_estimate"], row["input_upper"])
            or wire["input"][0]["content"] != base["structural_system"]
            or wire["text"]["format"]["schema"] != base["response_schema"]
            or task["target_question"] != base["structural_questions"][row["target_rule_id"]]
            or task["request_id"] != row["request_id"]
            or task["target_rule_id"] != row["target_rule_id"]
            or wire["model"] != base["model"]
            or wire["max_output_tokens"] != 2000
            or row["context_chars"] > 20000
            or row["input_upper"] > 32768
        ):
            raise io.ReviewBlocked("P022_BLOCKED_DEVELOPMENT_REQUEST_DRIFT")
    verify_opaque_seal(PRICING, "2fbb2424cdb8865d4c68d0d910e64ae9430d5e99eefe501caef8f6a051f3ea5b")
    pricing = PricingAssumption.model_validate_json(PRICING.read_bytes())
    facts = dict(
        development_cases=280,
        structural=180,
        semantic=100,
        TRAIN_cases=196,
        TRAIN_projects=196,
        VALIDATION_cases=84,
        VALIDATION_projects=84,
        TRAIN_VAL_project_overlap=0,
        DEVELOPMENT_FINAL_overlap=0,
        split_fingerprint=split["fingerprint"],
        evidence_records=280,
        evidence_fingerprint=evidence["fingerprint"],
        alignment_version=evidence["alignment_version"],
        semantic_reuse=100,
        semantic_missing=0,
        semantic_paid_repeats=0,
        request_manifest_fingerprint=manifest["fingerprint"],
        context_manifest_fingerprint=contexts["fingerprint"],
        prompt_fingerprint=expected_prompt,
        response_schema_fingerprint=digest(base["response_schema"]),
        execution_order_fingerprint=digest([r["request_id"] for r in rows]),
        missing=0,
        duplicates=0,
        final_requests=0,
        semantic_requests=0,
        payload_leakage=0,
        development_freeze_fingerprint=dev["fingerprint"],
    )
    return facts, base, pricing


def prepare(*, verify: bool = False) -> dict[str, Any]:
    io.verify_lineage(Path.cwd(), allowed=PUBLIC_FILES)
    human = human_gate()
    facts, base, pricing = scientific_gate()
    manifest = io.read_seal(DEV / "requests/manifest.json")
    rows = manifest["rows"]
    config = executor.protocol(base)
    if not ROOT.exists() and verify:
        raise io.ReviewBlocked("P022_EXECUTION_BUNDLE_MISSING")
    if not ROOT.exists():

        def build(stage: Path) -> None:
            stage.chmod(0o700)
            (stage / "payloads").mkdir(mode=0o700)
            for row in rows:
                name = f"{row['request_id']}.json"
                raw = (DEV / "requests/payloads" / name).read_bytes()
                (stage / "payloads" / name).write_bytes(raw)
                (stage / "payloads" / name).chmod(0o600)
            for name, payload in (
                (
                    "manifest.json",
                    dict(
                        version="p022-development-only-manifest-v1",
                        rows=rows,
                        source_manifest_fingerprint=manifest["fingerprint"],
                    ),
                ),
                ("protocol.json", config),
                ("response-schema.json", dict(schema=base["response_schema"])),
                ("order.json", dict(request_ids=[r["request_id"] for r in rows])),
            ):
                io.append_seal(stage / name, payload)
            (stage / "pricing.json").write_bytes(PRICING.read_bytes())
            (stage / "pricing.json").chmod(0o600)
            io.append_seal(
                stage / "source-bindings.json",
                dict(files={p: io.sha(Path(p)) for p in (*SOURCE_FILES, *ADAPTER_FILES)}),
            )
            inventory = {
                p.relative_to(stage).as_posix(): io.sha(p) for p in stage.rglob("*") if p.is_file()
            }
            io.append_seal(
                stage / "bundle-freeze.json",
                dict(
                    version="p022-execution-bundle-v1",
                    files=inventory,
                    request_manifest_fingerprint=manifest["fingerprint"],
                    protocol_fingerprint=digest(config),
                    paid_execution_approved=False,
                    provider_calls=0,
                ),
            )

        atomic_directory(ROOT, build)
    with executor.executor_scope(ROOT, LEDGER):
        mounted, actual, _ = executor.load_bundle(ROOT)
        if mounted["rows"] != rows or actual != {**config, "fingerprint": digest(config)}:
            raise io.ReviewBlocked("P022_EXECUTION_BUNDLE_DRIFT")
        bundle = io.read_seal(ROOT / "bundle-freeze.json")
        executor.prepare_ledger(LEDGER, bundle["fingerprint"])
        if any(p.name != "ledger-header.json" for p in LEDGER.iterdir()):
            raise io.ReviewBlocked("P022_LIVE_EXECUTION_ALREADY_STARTED")
    measured = executor.costs(rows, pricing)
    old = io.read_seal(
        io.BASE / "p020-cost-preflight-v1.json",
        io.read_seal(io.BASE / "p020-registry-v2.json")["cost_preflight"],
    )
    if (
        measured["expected_usd"] != old["DEVELOPMENT"]["expected_usd"]
        or measured["conservative_usd"] != old["DEVELOPMENT"]["conservative_usd"]
        or measured["configured_two_full_retries_usd"]
        != old["DEVELOPMENT"]["absolute_with_retries_usd"]
    ):
        raise io.ReviewBlocked("P022_P020_COST_RECONCILIATION_DRIFT")
    result = dict(
        version="p022-development-preflight-v1",
        status="P022_DEVELOPMENT_LLM_PREFLIGHT_COMPLETE",
        lineage=ANCHORS,
        human_freeze=human,
        development=facts,
        config=config,
        cost=measured,
        pricing_fingerprint=pricing.fingerprint,
        bundle_fingerprint=bundle["fingerprint"],
        protocol_fingerprint=digest(config),
        source_bindings={p: io.sha(Path(p)) for p in (*SOURCE_FILES, *ADAPTER_FILES)},
        reconciliation=dict(
            P020_total_calls=480,
            P020_expected_usd=old["TOTAL"]["expected_usd"],
            final_300_expected_usd=old["FINAL"]["expected_usd"],
            material_discrepancy=False,
            estimated_primary_vs_configured_ceiling=(
                "P022_PRIMARY_USES_ESTIMATED_INPUT; P020_ABSOLUTE_RESERVES_32768_PER_CALL"
            ),
        ),
        forbidden_mounts=0,
        provider_invocations=0,
        connectivity_calls=0,
        actual_spend_usd=0,
        invoice=None,
        paid_execution_approved=False,
        user_approved_cap_usd=None,
        live_started=False,
        final_calls_authorized=False,
        hybrid_training_started=False,
        security_started=False,
        final_evaluation=False,
    )
    freeze(io.BASE / "p022-development-preflight-v1.json", result)
    summary = dict(
        stage="DEVELOPMENT_STRUCTURAL_LLM",
        logical_calls=180,
        provider=config["provider"],
        model=config["model"],
        expected_usd=measured["expected_usd"],
        conservative_usd=measured["conservative_usd"],
        primary_max_usd=measured["primary_max_estimated_input_usd"],
        one_full_retry_usd=measured["one_full_retry_estimated_input_usd"],
        two_full_retries_usd=measured["two_full_retries_estimated_input_usd"],
        configured_two_full_retries_usd=measured["configured_two_full_retries_usd"],
        recommended_cap_usd=measured["recommended_cap_usd"],
        bundle_fingerprint=bundle["fingerprint"],
        protocol_fingerprint=digest(config),
        paid_execution_approved=False,
        approved_cap_usd=None,
        final_calls_authorized=False,
        hybrid_training_authorized=False,
        next_command=(
            ".venv/bin/python scripts/prompt022_development.py live "
            "--approval <explicit-human-approval.json>"
        ),
    )
    freeze(io.BASE / "p022-paid-approval-summary-v1.json", summary)
    return result
