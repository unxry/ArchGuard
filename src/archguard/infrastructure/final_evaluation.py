"""P025: separate blind prediction writer, then immutable truth-only evaluation."""

import resource
import subprocess
import sys
from collections import Counter
from pathlib import Path
from time import perf_counter
from typing import Any

from archguard.benchmark import final_evaluation as stats
from archguard.benchmark import unified_hybrid as domain
from archguard.benchmark.oss.models import digest
from archguard.calibration import hybrid_development as selected
from archguard.infrastructure import final_llm_completion as acquisition
from archguard.infrastructure import final_llm_continuation as guard
from archguard.infrastructure import final_llm_preflight as preflight
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure import unified_hybrid as evidence

HEAD = "27c53640b16ed9746cac3cbcb93a3610c847f5c1"
INPUT = io.PRIVATE / "p025-prediction-input-v1"
PRED = io.PRIVATE / "p025-final-predictions-v1"
RECEIPTS = io.PRIVATE / "p025-prediction-receipts-v1"
TRUTH = io.PRIVATE / "p025-authoritative-truth-v1"
JOIN = io.PRIVATE / "p025-final-join-v1"
RESULT = io.BASE / "p025-final-results-v1"
PUBLIC = io.BASE / "p025-final-evaluation-v1.json"
QUALITY = io.BASE / "p025-verification-v1.json"
STRUCTURAL = io.PRIVATE / "coordinator/structural-truth.json"
SEMANTIC = io.PRIVATE / "human-intake/agreement-v1/truth/final-semantic-truth.json"
ROUTING = io.PRIVATE / "coordinator/final-cases.json"
HUMAN_PUBLIC_FP = "12c8da4b469d7068418d083534d777d4b8898813d7e56ec35ba60804c1efac5b"
HUMAN_PUBLIC = io.BASE / "p021-b-human-agreement-v1.json"
COHORT = io.BASE / "p020-final-holdout-freeze-v1.json"
ANALYSIS = io.BASE / "p020-final-analysis-plan-v1.json"
P017 = Path("experiments/semantic-holdout/p017-aggregate-evaluation-v1.json")
P017_FREEZE = Path("experiments/semantic-holdout/p017-evaluation-freeze-v1.json")
P019 = Path("experiments/component-holdout/p019-graph-feature-diagnostic-v1.json")
PINS = {
    "static-output.json": "6fd60e7064fc40ace76f34a488d031efafcdf7d1483a676855d7e1c64a124571",
    "graph-output.json": "37eaacf17d4585c43d8e46b57c64c10e22e93b57e2c6015c6ec46008a0ee63d6",
    "evidence.json": "bcefd040216b64a1d636a155ec2b62b6aeb9d089be92405d9899874c86971633",
}
ACQUISITION_FP = "cfc634fe10a8327322fba61710596d21093910534de19b21a3b5661bee25a737"
HANDOFF_FP = "f15dfd5edd305c308f001fb81f308f60ed79a0cb09b2950a10f2187ec4e2e37e"
MODEL_LOCK_FP = "d424792a985335b0e259a1fbf9478bf140fb371a7112a40f470661f9c7d1bd57"
MODEL_AUX = (
    preflight.P023 / "selected-model-registry.json",
    preflight.P023 / "final-full-hybrid-model.json",
    preflight.P023 / "validation-selection-receipt.json",
)
SOURCES = (
    "src/archguard/benchmark/final_evaluation.py",
    "src/archguard/infrastructure/final_evaluation.py",
    "scripts/prompt025_final_evaluation.py",
    "tests/intelligence/test_final_evaluation.py",
)
PUBLIC_PATHS = (
    str(PUBLIC),
    str(QUALITY),
    "docs/verification/PROMPT_025.md",
    "docs/verification/FINAL_ARCHITECTURE_EXPERIMENT.md",
)


def git_gate() -> None:
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"]
    )
    allowed = SOURCES + PUBLIC_PATHS + tuple(str(p) for p in RESULT.glob("*.json"))
    io.scientific_status(status, allowed)
    chain = [
        "2f596fb57b00a1d8374cdcba50a98ab6ffbe4023",
        "1891fa553218200139f027ed9c3a82d100f61462",
        *preflight.ANCHORS.values(),
        "d609a312bdf5ce2af67026008bf2f055c6898962",
        guard.HEAD,
        "46320397944273c766bd2723d8354773c8a7ccb2",
        acquisition.HEAD,
        "953af56286437a7e75dac9fba62e5260c13a6cd1",
        HEAD,
    ]
    # ANCHORS includes older prerequisite commits: verify ancestry individually.
    for sha in chain:
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", sha, "HEAD"], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P025_BLOCKED_LINEAGE")
    ordered = [
        chain[0],
        chain[1],
        preflight.ANCHORS["P021.B"],
        preflight.ANCHORS["P022"],
        preflight.ANCHORS["P022.LIVE"],
        preflight.ANCHORS["P023"],
        *chain[-7:],
    ]
    for a, b in zip(ordered, ordered[1:], strict=False):
        if subprocess.run(
            ["git", "merge-base", "--is-ancestor", a, b], capture_output=True
        ).returncode:
            raise io.ReviewBlocked("P025_BLOCKED_LINEAGE_ORDER")


def inventory(root: Path) -> dict[str, str]:
    return {p.relative_to(root).as_posix(): io.sha(p) for p in root.rglob("*") if p.is_file()}


def freeze_directory(root: Path, parts: dict[str, Any]) -> dict[str, Any]:
    for name, value in parts.items():
        preflight.seal(root / name, value)
    return preflight.seal(
        root / "freeze-receipt.json",
        dict(
            files={name: io.sha(root / name) for name in parts},
            fingerprints={name: io.read_seal(root / name)["fingerprint"] for name in parts},
        ),
    )


def verify_directory(root: Path) -> dict[str, Any]:
    receipt = io.read_seal(root / "freeze-receipt.json")
    io.verify_files(
        root, receipt["files"] | {"freeze-receipt.json": io.sha(root / "freeze-receipt.json")}
    )
    for name, fp in receipt["fingerprints"].items():
        io.read_seal(root / name, fp)
    return receipt


def models() -> dict[str, Path]:
    return {method: preflight.P023 / "selected" / f"{method}.json" for method in stats.METHODS[3:]}


def verify_acquisition() -> dict[str, Any]:
    with preflight.offline_scope():
        model = preflight.model_gate()
        preflight.source_gate()
    if digest(model) != MODEL_LOCK_FP:
        raise io.ReviewBlocked("P025_BLOCKED_MODEL_LOCK")
    with guard.scope(
        (
            *acquisition.READS,
            acquisition.PUBLIC,
            acquisition.HANDOFF,
            acquisition.FREEZE,
            acquisition.COMPOSITE,
            acquisition.QUALITY,
        )
    ):
        acquisition.history()
        pub = io.read_seal(acquisition.PUBLIC, ACQUISITION_FP)
        handoff = io.read_seal(acquisition.HANDOFF, HANDOFF_FP)
        acquisition.verify_snapshot(
            acquisition.FREEZE,
            "1f7c0e4824cd0f827fe889b136be6fcafa6df1f9326648f898f1d7a0b27b284e",
            acquisition.LEDGER,
        )
        acquisition.verify_snapshot(
            acquisition.COMPOSITE,
            "27bdc88a34165a7c08b394971d63d28abc012e084c0abf67bb86be6d162b17b7",
        )
        if (
            not handoff["ready"]
            or pub["technical_status_counts"]
            != dict(
                ACCEPTED=298,
                TERMINAL_INVALID_REQUEST_ID_MISMATCH=1,
                AMBIGUOUS_TRANSPORT_NO_CAPTURE=1,
            )
            or pub["unexecuted"]
            or pub["accepted_duplicates"]
            or pub["active_unresolved_execution_stops"]
        ):
            raise io.ReviewBlocked("P025_BLOCKED_FINAL_ACQUISITION_DRIFT")
    return model


def prepare() -> dict[str, Any]:
    git_gate()
    if TRUTH.exists() or PRED.exists():
        raise PermissionError("P025_PREDICTION_PREPARATION_CLOSED")
    lock = verify_acquisition()
    cohort = io.read_seal(COHORT)
    source_bindings = {name: io.sha(Path(name)) for name in SOURCES}
    source_reads = (
        ROUTING,
        io.FINAL / "evidence",
        io.FINAL / "requests/manifest.json",
        acquisition.COMPOSITE,
        *models().values(),
        *MODEL_AUX,
        ANALYSIS,
        COHORT,
    )
    with guard.scope(source_reads, (INPUT,)):
        routing = io.read_seal(ROUTING, cohort["fingerprints"]["cases"])
        request = io.read_seal(io.FINAL / "requests/manifest.json")
        records = io.read_seal(io.FINAL / "evidence/evidence.json", PINS["evidence.json"])
        static = io.read_seal(io.FINAL / "evidence/static-output.json", PINS["static-output.json"])
        graph = io.read_seal(io.FINAL / "evidence/graph-output.json", PINS["graph-output.json"])
        route = stats.unique(routing["rows"], "execution_safe_id")
        components = stats.unique(records["records"], "execution_id")
        requests = stats.unique(request["rows"], "execution_id")
        statuses = stats.unique(
            io.read_seal(acquisition.COMPOSITE / "technical-status.json")["rows"], "execution_id"
        )
        accepted = stats.unique(
            [
                item | dict(request_id=item["assessment"]["request_id"])
                for item in io.read_seal(acquisition.COMPOSITE / "accepted-assessments.json")[
                    "assessments"
                ]
            ],
            "request_id",
        )
        if len(route) != 300 or any(
            set(group) != set(route)
            for group in (
                components,
                requests,
                statuses,
                stats.unique(static["rows"], "execution_id"),
                stats.unique(graph["rows"], "execution_id"),
            )
        ):
            raise ValueError("P025_COMPONENT_IDENTITY_DRIFT")
        rows = []
        for eid, meta in sorted(
            route.items(), key=lambda pair: digest(pair[1]["scientific_case_id"])
        ):
            comp, req, status = components[eid], requests[eid], statuses[eid]
            rule = meta["target_rule_id"]
            if (
                comp["target_rule_id"] != rule
                or req["target_rule_id"] != rule
                or status["request_id"] != req["request_id"]
            ):
                raise ValueError("P025_CROSS_CASE_RULE_BINDING")
            available = status["llm_evidence_status"] == "ACCEPTED"
            carrier = (
                domain.UnifiedAssessment.model_validate(accepted[req["request_id"]]["assessment"])
                if available
                else None
            )
            if carrier and (
                carrier.request_id != req["request_id"] or carrier.target_rule_id != rule
            ):
                raise ValueError("P025_LLM_CASE_BINDING")
            raw = carrier.decision if carrier else None
            rows.append(
                dict(
                    case_id=meta["scientific_case_id"],
                    execution_id=eid,
                    rule=rule,
                    family={
                        "NORMATIVE_STATIC": "NORMATIVE",
                        "GRAPH_STRUCTURAL": "GRAPH",
                        "SEMANTIC": "SEMANTIC",
                    }[meta["target_rule_family"]],
                    language=meta["language"],
                    llm_decision=raw,
                    llm_technical_status=status["llm_evidence_status"],
                    evidence=dict(
                        STATIC=comp["STATIC"],
                        GRAPH=comp["GRAPH"],
                        LLM="INSUFFICIENT_EVIDENCE"
                        if raw is None or raw == "INSUFFICIENT_CONTEXT"
                        else raw,
                        static_proof=comp["static_proof"],
                        cycle_proof=comp["cycle_proof"],
                    ),
                    values=evidence.candidate_values(comp, carrier, truncated=req["truncated"]),
                )
            )
        parts: dict[str, Any] = {"matrix.json": dict(rows=rows)}
        for method, path in models().items():
            original = io.read_seal(path, lock["selected"][method]["candidate_fingerprint"])
            parts[f"models/{method}.json"] = {
                key: original[key] for key in ("configuration", "method", "artifact")
            } | dict(original_candidate_fingerprint=original["fingerprint"])
        analysis = io.read_seal(
            ANALYSIS, "f5c5b24cf4a9b47eee819c8ca0ca46efc8e9721a3d65bf065ac6bd0090535e91"
        )
        parts["analysis.json"] = {k: v for k, v in analysis.items() if k != "fingerprint"}
        parts["metadata.json"] = dict(
            original_model_hashes={method: io.sha(path) for method, path in models().items()},
            original_aux_hashes={str(path): io.sha(path) for path in MODEL_AUX},
            model_registry_fingerprint=lock["selected_registry_fingerprint"],
            model_lock_fingerprint=digest(lock),
            acquisition_fingerprint=ACQUISITION_FP,
            acquisition_freeze_fingerprint=(
                "27bdc88a34165a7c08b394971d63d28abc012e084c0abf67bb86be6d162b17b7"
            ),
            handoff_fingerprint=HANDOFF_FP,
            cohort_fingerprint=cohort["fingerprint"],
            routing_fingerprint=routing["fingerprint"],
            component_fingerprints=PINS,
            hypothesis_rule=stats.HYPOTHESIS_RULE,
            source_bindings=source_bindings,
            truth_mounted=False,
            final_truth_reads=0,
        )
        result = freeze_directory(INPUT, parts)
    return dict(
        status="P025_BLIND_INPUT_PREPARED",
        cases=300,
        fingerprint=result["fingerprint"],
        final_truth_reads=0,
    )


def model_immutability(metadata: dict[str, Any]) -> None:
    aux = metadata.get("original_aux_hashes", {})
    if set(aux) - {str(path) for path in MODEL_AUX}:
        raise ValueError("P025_OPAQUE_MODEL_ALLOWLIST_DRIFT")
    with guard.scope((*models().values(), *MODEL_AUX)):
        if {key: io.sha(path) for key, path in models().items()} != metadata[
            "original_model_hashes"
        ]:
            raise io.ReviewBlocked("P025_BLOCKED_MODEL_MUTATION")
        if {path: io.sha(Path(path)) for path in aux} != aux:
            raise io.ReviewBlocked("P025_BLOCKED_MODEL_MUTATION")


def blind_matrix(rows: list[dict[str, Any]]) -> None:
    keys = {
        "case_id",
        "execution_id",
        "rule",
        "family",
        "language",
        "llm_decision",
        "llm_technical_status",
        "evidence",
        "values",
    }
    feature_keys = {name for names in domain.FEATURES.values() for name in names}
    if len(rows) != 300 or len(stats.unique(rows, "case_id")) != 300:
        raise ValueError("P025_BLIND_MATRIX_INCOMPLETE")
    for row in rows:
        if (
            set(row) != keys
            or set(row["values"]) != feature_keys
            or set(row["evidence"]) != {"STATIC", "GRAPH", "LLM", "static_proof", "cycle_proof"}
            or row["rule"] not in domain.RULES
            or row["llm_technical_status"] not in ("ACCEPTED", *stats.MISSING)
        ):
            raise ValueError("P025_BLIND_MATRIX_LEAK_OR_SCOPE_DRIFT")
        missing = row["llm_technical_status"] in stats.MISSING
        if missing != (row["llm_decision"] is None) or (
            missing and any(row["values"][name] is not None for name in domain.FEATURES["LLM"])
        ):
            raise ValueError("P025_TECHNICAL_MISSING_SEMANTIC_IMPUTATION")


def prediction_row(
    row: dict[str, Any], method: str, model: dict[str, Any] | None
) -> dict[str, Any]:
    decision = (
        row["evidence"]["STATIC" if method == "A1" else "GRAPH"]
        if method in {"A1", "A2"}
        else row["llm_decision"] or row["llm_technical_status"]
        if method == "A3"
        else selected.prediction(row, model or {})
    )
    return dict(
        case_id=row["case_id"],
        rule=row["rule"],
        family=row["family"],
        language=row["language"],
        decision=decision,
        binary=1 if decision == "SUPPORTED" else 0 if decision == "NOT_SUPPORTED" else None,
        applicable=None if decision in stats.MISSING else decision != "NOT_APPLICABLE",
        nondefinitive=decision not in {"SUPPORTED", "NOT_SUPPORTED"},
        technical_missing=decision in stats.MISSING,
    )


def predict() -> dict[str, Any]:
    if TRUTH.exists() or (RECEIPTS / "truth-blind-receipt.json").exists() or PRED.exists():
        raise PermissionError("P025_PREDICTION_WRITER_CLOSED")
    with guard.scope((INPUT,), (PRED, RECEIPTS)):
        inputs = verify_directory(INPUT)
        metadata = io.read_seal(INPUT / "metadata.json")
        matrix = io.read_seal(INPUT / "matrix.json")["rows"]
        blind_matrix(matrix)
        model_immutability(metadata)
        parts = {}
        measured = {}
        for method in stats.METHODS:
            model = (
                io.read_seal(INPUT / "models" / f"{method}.json")
                if method in stats.METHODS[3:]
                else None
            )
            if model and (
                model["configuration"] != method
                or model["method"] != ("H0" if method == "A4" else "H2")
                or model["artifact"]["threshold"]
                != ({"A4": None, "A5": 0.5, "A6": 0.5, "A7": 0.75}[method])
            ):
                raise ValueError("P025_UNSELECTED_MODEL_PROHIBITED")
            start = perf_counter()
            predictions = [prediction_row(row, method, model) for row in matrix]
            measured[method] = perf_counter() - start
            if len(predictions) != 300 or len(stats.unique(predictions, "case_id")) != 300:
                raise ValueError("P025_PREDICTION_COMPLETENESS")
            parts[f"{method}.json"] = dict(method=method, rows=predictions, truth_available=False)
        parts["registry.json"] = dict(
            methods={method: digest(parts[f"{method}.json"]) for method in stats.METHODS},
            cases=300,
            input_freeze_fingerprint=inputs["fingerprint"],
            model_lock_fingerprint=metadata["model_lock_fingerprint"],
            truth_mounted=False,
            final_truth_reads=0,
        )
        prediction = freeze_directory(PRED, parts)
        preflight.seal(
            RECEIPTS / "resource-measurements.json",
            dict(
                offline_prediction_seconds=measured,
                worker_peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
                * (1 if sys.platform == "darwin" else 1024),
                rss_scope="WHOLE_PREDICTION_WORKER; NOT_METHOD_ATTRIBUTABLE",
            ),
        )
    # This scope has no prediction writer; the receipt is created only after closure.
    model_immutability(metadata)
    with guard.scope((INPUT, PRED), (RECEIPTS,)):
        verify_directory(PRED)
        receipt = preflight.seal(
            RECEIPTS / "truth-blind-receipt.json",
            dict(
                prediction_freeze_fingerprint=prediction["fingerprint"],
                prediction_registry_fingerprint=io.read_seal(PRED / "registry.json")["fingerprint"],
                input_freeze_fingerprint=inputs["fingerprint"],
                model_hashes=metadata["original_model_hashes"],
                writer_closed=True,
                truth_mounted=False,
                final_truth_reads=0,
                unselected_predictions=0,
                model_mutation=False,
                cases_per_method=300,
                methods=list(stats.METHODS),
            ),
        )
    for path in PRED.rglob("*"):
        if path.is_file():
            path.chmod(0o400)
    PRED.chmod(0o500)
    return dict(
        status="FINAL_PREDICTIONS_FROZEN_BEFORE_TRUTH",
        registry_fingerprint=receipt["prediction_registry_fingerprint"],
        receipt_fingerprint=receipt["fingerprint"],
        final_truth_reads=0,
    )


def prediction_gate() -> dict[str, Any]:
    with guard.scope((INPUT, PRED, RECEIPTS)):
        receipt = io.read_seal(RECEIPTS / "truth-blind-receipt.json")
        frozen = verify_directory(PRED)
        metadata = io.read_seal(INPUT / "metadata.json")
        inputs = verify_directory(INPUT)
        if (
            not receipt["writer_closed"]
            or receipt["truth_mounted"]
            or receipt["final_truth_reads"]
            or receipt["prediction_freeze_fingerprint"] != frozen["fingerprint"]
            or receipt["prediction_registry_fingerprint"]
            != io.read_seal(PRED / "registry.json")["fingerprint"]
            or receipt["input_freeze_fingerprint"] != inputs["fingerprint"]
        ):
            raise PermissionError("P025_TRUTH_OPEN_BEFORE_PREDICTION_FREEZE_PROHIBITED")
    model_immutability(metadata)
    return receipt


def open_truth() -> dict[str, Any]:
    receipt = prediction_gate()
    if TRUTH.exists():
        raise PermissionError("P025_FIRST_TRUTH_OPEN_ALREADY_FROZEN")
    with guard.scope((INPUT, COHORT, HUMAN_PUBLIC, STRUCTURAL, SEMANTIC), (TRUTH,)):
        cohort = io.read_seal(COHORT)
        human = io.read_seal(HUMAN_PUBLIC, HUMAN_PUBLIC_FP)
        # Authorization receipt precedes the first label-file open and binds the closed writer.
        preflight.seal(
            TRUTH / "first-truth-open.json",
            dict(
                prediction_receipt_fingerprint=receipt["fingerprint"],
                writer_closed=True,
                truth_open_authorized_after_prediction_freeze=True,
            ),
        )
        structural = io.read_seal(STRUCTURAL, cohort["fingerprints"]["structural_truth"])
        semantic = io.read_seal(SEMANTIC, human["truth_fingerprint"])
        routes = stats.unique(io.read_seal(INPUT / "matrix.json")["rows"], "case_id")
        if any(
            row["scientific_case_id"] not in routes
            or (
                "target_rule" in row
                and (row["target_rule"], row["language"])
                != (
                    routes[row["scientific_case_id"]]["rule"],
                    routes[row["scientific_case_id"]]["language"],
                )
            )
            for row in semantic["cases"]
        ):
            raise ValueError("P025_FINAL_HUMAN_ROUTING_DRIFT")
        if io.sha(SEMANTIC) != human["truth_raw_sha256"]:
            raise ValueError("P025_FINAL_HUMAN_TRUTH_DRIFT")
        labels = [
            dict(case_id=r["scientific_case_id"], category=r["category"], source="P020_STRUCTURAL")
            for r in structural["rows"]
        ] + [
            dict(
                case_id=r["scientific_case_id"], category=r["final_category"], source="P021.B_HUMAN"
            )
            for r in semantic["cases"]
        ]
        counts = Counter(r["category"] for r in labels)
        if (
            len(structural["rows"]) != 200
            or len(semantic["cases"]) != 100
            or len(stats.unique(labels, "case_id")) != 300
            or set(counts) - {"POSITIVE", "NEGATIVE"}
        ):
            raise ValueError("P025_FINAL_TRUTH_CONTRACT_DISCREPANCY")
        if counts != {"POSITIVE": 150, "NEGATIVE": 150}:
            raise ValueError("P025_FINAL_TRUTH_BALANCE_DISCREPANCY")
        parts = dict(
            **{
                "truth.json": dict(
                    rows=sorted(
                        [r | dict(label=int(r["category"] == "POSITIVE")) for r in labels],
                        key=lambda r: digest(r["case_id"]),
                    ),
                    structural_fingerprint=structural["fingerprint"],
                    semantic_fingerprint=semantic["fingerprint"],
                    prediction_receipt_fingerprint=receipt["fingerprint"],
                    counts=dict(counts),
                )
            }
        )
        freeze = freeze_directory(
            TRUTH,
            parts
            | {
                "first-truth-open.json": {
                    k: v
                    for k, v in io.read_seal(TRUTH / "first-truth-open.json").items()
                    if k != "fingerprint"
                }
            },
        )
    return dict(
        status="FINAL_TRUTH_OPENED_AFTER_PREDICTION_FREEZE",
        fingerprint=freeze["fingerprint"],
        counts=dict(counts),
    )


def join_predictions(
    truth: list[dict[str, Any]], predictions: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    labels = stats.unique(truth, "case_id")
    indexed = {method: stats.unique(predictions[method], "case_id") for method in stats.METHODS}
    if any(set(group) != set(labels) for group in indexed.values()):
        raise ValueError("P025_PREDICTION_TRUTH_JOIN_INCOMPLETE")
    rows = []
    for cid in sorted(labels, key=digest):
        meta = indexed["A1"][cid]
        if any(
            (group[cid]["rule"], group[cid]["language"], group[cid]["family"])
            != (meta["rule"], meta["language"], meta["family"])
            for group in indexed.values()
        ):
            raise ValueError("P025_CROSS_CASE_ROUTING_MISMATCH")
        rows.append(
            dict(
                case_id=cid,
                label=labels[cid]["label"],
                rule=meta["rule"],
                family=meta["family"],
                language=meta["language"],
                predictions={method: group[cid] for method, group in indexed.items()},
            )
        )
    return rows


def prior_evidence() -> dict[str, Any]:
    with guard.scope(
        (
            P017,
            P017_FREEZE,
            P019,
            acquisition.PUBLIC,
            io.FINAL / "evidence/evidence.json",
            guard.PARTIAL,
            guard.FREEZE,
            acquisition.FREEZE,
            RECEIPTS,
        )
    ):
        prior = io.read_seal(
            P017, "992fc16900a456e2678e4a258b55aee251d04923ed090db1b8dbedeab823b091"
        )
        frozen = io.read_seal(
            P017_FREEZE, "3e506e13ea5cdc20f57da4d5f420687c5bde87d5dcc23e1c1a003c49defe4d02"
        )
        if frozen["aggregate_fingerprint"] != prior["fingerprint"]:
            raise ValueError("P025_PRIOR_RQ5_FREEZE_DRIFT")
        graph_prior = io.read_seal(
            P019, "e39c64ec464c10fc18572f8b74827141b7e957ccd6ac6a851c9cb4d1b59c12b3"
        )
        acquisition_pub = io.read_seal(acquisition.PUBLIC, ACQUISITION_FP)
        combined = io.read_seal(io.FINAL / "evidence/evidence.json", PINS["evidence.json"])
        latency = []
        for root in (guard.PARTIAL, guard.FREEZE, acquisition.FREEZE):
            for path in (root / "ledger").glob("*.outcome.json"):
                latency.append(io.read_seal(path)["latency_seconds"])
        measured = io.read_seal(RECEIPTS / "resource-measurements.json")
        return dict(
            rq5=prior["RQ5"]["GRAPH_GUIDED_VS_EXPANDED_BASELINE"]["primary_prospective_paired"],
            rq5_fingerprint=prior["fingerprint"],
            graph_prior_fingerprint=graph_prior["fingerprint"],
            graph_prior_interpretation=graph_prior["interpretation"],
            resource=dict(
                **{
                    key: acquisition_pub[key]
                    for key in (
                        "logical_benchmark_cases",
                        "total_provider_invocations",
                        "total_accepted",
                        "technical_missing",
                        "composite_input_tokens",
                        "composite_output_tokens",
                        "composite_total_tokens",
                        "cached_tokens",
                        "usage_unavailable_invocations",
                        "total_known_cost_usd",
                        "historical_uncertain_reserved_usd",
                        "total_exposure_usd",
                        "invoice",
                    )
                },
                provider_transport_seconds=dict(
                    measured_invocations=len(latency),
                    sum=sum(latency),
                    mean=sum(latency) / len(latency) if latency else None,
                    missing_invocations=300 - len(latency),
                ),
                frozen_combined_component_materialization_seconds=sum(
                    r["seconds"] for r in combined["records"]
                ),
                individual_static_runtime="NOT_MEASURED",
                individual_graph_runtime="NOT_MEASURED",
                method_memory={method: "NOT_MEASURED" for method in stats.METHODS},
                offline_prediction_seconds=measured["offline_prediction_seconds"],
                worker_peak_rss_bytes=measured["worker_peak_rss_bytes"],
                rss_scope=measured["rss_scope"],
                acquisition_fingerprint=ACQUISITION_FP,
                provider_calls_this_stage=0,
                spend_this_stage_usd="0",
            ),
        )


def rq_summary(
    primary: dict[str, Any], outputs: dict[str, Any], prior: dict[str, Any]
) -> dict[str, Any]:
    source = {name: digest(value) for name, value in outputs.items()}
    native = outputs["final-native-scope-metrics.json"]["methods"]
    graph = prior["rq5"]
    rows = [
        dict(
            rq="RQ1",
            question=(
                "Какова эффективность статического анализа при выявлении архитектурных нарушений?"
            ),
            status="ANSWERED",
            evidence=[
                "final-primary-metrics.json#A1",
                "final-native-scope-metrics.json#A1_STATIC_NATIVE",
                "final-rule-strata.json",
                "final-language-strata.json",
            ],
            answer=(
                f"Static primary Precision={primary['A1']['Precision']}, "
                f"Recall={primary['A1']['Recall']}; native "
                f"N={native['A1_STATIC_NATIVE']['N']}, "
                f"F1={native['A1_STATIC_NATIVE']['F1']}. Native explicit-contract rules "
                f"do not provide universal architecture coverage."
            ),
            limitations=(
                "Controlled benchmark; native rules ARCH001/002/004/005; unified "
                "results retain unsupported cases."
            ),
        ),
        dict(
            rq="RQ2",
            question=(
                "Какие графовые характеристики наиболее полезны для обнаружения "
                "архитектурных аномалий?"
            ),
            status="PARTIALLY_ANSWERED",
            evidence=[
                "final-primary-metrics.json#A2",
                "final-rule-strata.json#ARCH003_ARCH101_ARCH105",
                prior["graph_prior_fingerprint"],
            ],
            answer=(
                f"Frozen direct-cycle plus collective V2 model: primary "
                f"Recall={primary['A2']['Recall']}, native "
                f"F1={native['A2_GRAPH_NATIVE']['F1']}. SCC/cycle proof and the "
                f"collective Ca/Ce/coupling/I/betweenness/PageRank feature mechanism "
                f"were preserved. No final per-feature selection or ranking was "
                f"performed."
            ),
            limitations=(
                "Aggregate model evidence does not isolate or rank individual graph features."
            ),
        ),
        dict(
            rq="RQ3",
            question="Какие архитектурные нарушения требуют семантического анализа?",
            status="ANSWERED",
            evidence=[
                "final-primary-metrics.json#A3",
                "final-family-strata.json#SEMANTIC",
                "final-rule-strata.json#ARCH201_ARCH205",
                "final-coverage-metrics.json",
                "final-native-scope-metrics.json#A3_AVAILABLE_ONLY",
            ],
            answer=(
                f"A3 primary Precision={primary['A3']['Precision']}, "
                f"Recall={primary['A3']['Recall']}; semantic-family "
                f"F1={outputs['final-family-strata.json']['strata']['SEMANTIC']['A3']['F1']}; "
                f"accepted acquisition 298/300, with two transport-missing outcomes "
                f"separate from semantic decisions."
            ),
            limitations=(
                "Benchmark-specific human semantic truth; classification quality and "
                "transport availability are distinct."
            ),
        ),
        dict(
            rq="RQ4",
            question="Повышает ли Hybrid качество относительно отдельных методов?",
            status="ANSWERED",
            evidence=[
                "final-primary-metrics.json",
                "final-ablation.json",
                "final-paired-comparisons.json",
                "final-hypothesis.json",
            ],
            answer=(
                f"Selected A7 Precision={primary['A7']['Precision']}, "
                f"Recall={primary['A7']['Recall']}, F1={primary['A7']['F1']}, effective "
                f"correctness={primary['A7']['effective_correctness']}. Exact "
                f"individual and ablation deltas and paired N=300 counts determine the "
                f"observed trade-offs."
            ),
            limitations=(
                "Descriptive whole-system comparison; no p-values or causal feature attribution."
            ),
        ),
        dict(
            rq="RQ5",
            question="Снижает ли graph-guided context объём LLM-контекста без снижения качества?",
            status="ANSWERED",
            evidence=[prior["rq5_fingerprint"], "prior-context-efficiency.json"],
            answer=(
                f"Prior matched input N={graph['input_tokens']['paired_N']}: "
                f"reduction={graph['input_tokens']['relative_reduction_first_vs_second']}; "
                f"cost "
                f"reduction={graph['cost_usd']['relative_reduction_first_vs_second']}. "
                f"Precision "
                f"delta={100 * graph['effectiveness_difference']['precision']} pp; F1 "
                f"delta={100 * graph['effectiveness_difference']['F1_definitive']} pp. "
                f"Quality preservation is not supported without qualification."
            ),
            limitations=(
                "Prior controlled P017 strategy comparison; final N=300 used "
                "GRAPH_GUIDED only and cannot establish an Expanded-vs-Graph causal "
                "comparison."
            ),
        ),
        dict(
            rq="RQ6",
            question="Как масштабируется разработанный метод с ростом программной системы?",
            status="PARTIALLY_ANSWERED",
            evidence=["final-resource-metrics.json"],
            answer=(
                "Demonstrated within the evaluated benchmark range: frozen component "
                "materialization, 300 final logical requests, reported token/cost "
                "totals and measured offline prediction times. Missing resource "
                "measurements are NOT_MEASURED."
            ),
            limitations=(
                "No asymptotic or universal scalability claim; finite controlled "
                "cohort; memory was not systematically measured per method."
            ),
        ),
    ]
    return dict(
        rows=rows,
        input_result_fingerprints=source,
        prior_rq5_fingerprint=prior["rq5_fingerprint"],
        graph_prior_fingerprint=prior["graph_prior_fingerprint"],
    )


def evaluate() -> dict[str, Any]:
    prediction_receipt = prediction_gate()
    before = inventory(PRED)
    prior = prior_evidence()
    with guard.scope((INPUT, PRED, TRUTH), (JOIN, RESULT)):
        truth_receipt = verify_directory(TRUTH)
        truth = io.read_seal(TRUTH / "truth.json")
        if truth["prediction_receipt_fingerprint"] != prediction_receipt["fingerprint"]:
            raise PermissionError("P025_TRUTH_CHRONOLOGY_DRIFT")
        predictions = {
            method: io.read_seal(PRED / f"{method}.json")["rows"] for method in stats.METHODS
        }
        rows = join_predictions(truth["rows"], predictions)
        if (
            len(rows) != 300
            or Counter(r["rule"] for r in rows) != {r: 20 for r in domain.RULES}
            or Counter(r["family"] for r in rows)
            != {"NORMATIVE": 100, "GRAPH": 100, "SEMANTIC": 100}
            or Counter(r["language"] for r in rows) != {"JAVA": 150, "TYPESCRIPT": 150}
        ):
            raise ValueError("P025_STRATA_ACCOUNTING_DRIFT")
        joined = freeze_directory(
            JOIN,
            {
                "join.json": dict(
                    rows=rows,
                    truth_fingerprint=truth["fingerprint"],
                    prediction_registry_fingerprint=prediction_receipt[
                        "prediction_registry_fingerprint"
                    ],
                    join="STABLE_SCIENTIFIC_ID; NOT_ARRAY_ORDER",
                )
            },
        )
        analysis = io.read_seal(INPUT / "analysis.json")
        outputs = stats.aggregate(
            rows, analysis["scope_conditional"]["STATIC"], analysis["scope_conditional"]["GRAPH"]
        )
        outputs["final-resource-metrics.json"] = prior["resource"]
        outputs["prior-context-efficiency.json"] = dict(
            view="PRIOR CONTROLLED CONTEXT-EFFICIENCY EXPERIMENT — NOT FINAL N=300",
            source_fingerprint=prior["rq5_fingerprint"],
            comparison=prior["rq5"],
        )
        outputs["final-truth-counts.json"] = dict(
            N=300,
            structural=200,
            semantic=100,
            categories=truth["counts"],
            uncertain=0,
            out_of_scope=0,
            missing=0,
            duplicates=0,
            truth_fingerprint=truth["fingerprint"],
        )
        # Numerical scientific results are sealed before narrative synthesis.
        for name, value in outputs.items():
            preflight.seal(RESULT / name, value)
        outputs["final-rq-summary.json"] = rq_summary(
            outputs["final-primary-metrics.json"]["methods"], outputs, prior
        )
        preflight.seal(RESULT / "final-rq-summary.json", outputs["final-rq-summary.json"])
        receipt = preflight.seal(
            RESULT / "evaluation-receipt.json",
            dict(
                status="P025_FINAL_ARCHITECTURE_EVALUATION_COMPLETE",
                prediction_registry_fingerprint=prediction_receipt[
                    "prediction_registry_fingerprint"
                ],
                prediction_receipt_fingerprint=prediction_receipt["fingerprint"],
                truth_fingerprint=truth["fingerprint"],
                truth_freeze_fingerprint=truth_receipt["fingerprint"],
                join_fingerprint=joined["fingerprints"]["join.json"],
                outputs={name: io.read_seal(RESULT / name)["fingerprint"] for name in outputs},
                files={name: io.sha(RESULT / name) for name in outputs},
                input_freeze_fingerprint=verify_directory(INPUT)["fingerprint"],
                metric_definition_fingerprint=analysis["fingerprint"],
                implementation_bindings=io.read_seal(INPUT / "metadata.json")["source_bindings"],
                model_mutation=False,
                prediction_mutation=False,
                model_fitting=0,
                threshold_tuning=0,
                provider_calls=0,
                credential_reads=0,
                security=False,
            ),
        )
    if inventory(PRED) != before:
        raise io.ReviewBlocked("P025_PREDICTION_MUTATION_AFTER_TRUTH")
    model_immutability(io.read_seal(INPUT / "metadata.json"))
    summary = dict(
        status=receipt["status"],
        next_stage="READY_FOR_P026_THESIS_CORE_CLOSURE",
        cases=300,
        accepted_llm=298,
        technical_missing_llm=2,
        predictions_before_truth=True,
        final_truth_join_complete=True,
        prediction_registry_fingerprint=receipt["prediction_registry_fingerprint"],
        prediction_receipt_fingerprint=receipt["prediction_receipt_fingerprint"],
        truth_fingerprint=receipt["truth_fingerprint"],
        join_fingerprint=receipt["join_fingerprint"],
        aggregate_fingerprints=receipt["outputs"],
        evaluation_receipt_fingerprint=receipt["fingerprint"],
        hypothesis_status=outputs["final-hypothesis.json"]["final_status"],
        provider_calls=0,
        credential_reads=0,
        paid_spend_usd="0",
        model_fitting=0,
        threshold_tuning=0,
        unselected_final_predictions=0,
        prediction_mutation_after_truth=False,
        security=False,
    )
    return preflight.seal(PUBLIC, summary)
