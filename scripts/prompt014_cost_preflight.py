"""PROMPT 014 offline-only preparation; never execute or evaluate a provider response."""

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from archguard.benchmark.oss.models import digest, seal
from archguard.benchmark.oss.review import (
    AnnotationReviewReport,
    ReviewedFreeze,
    ReviewStore,
    RevisionCatalog,
    freeze_reviews,
    review_report,
)
from archguard.benchmark.semantic_preflight import PricingAssumption, experiment_manifest
from archguard.infrastructure.oss_benchmark import load_corpus, write_new
from archguard.infrastructure.semantic_preflight import prepare_contexts, publish_preflight
from archguard.oss_cli import load_sample


def verify_baseline_head(baseline="17c1292a4d608d5aaf90964d2947fa04919f4e64"):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.run(["git", "merge-base", "--is-ancestor", baseline, head]).returncode:
        raise ValueError("HEAD must descend from the frozen P013 baseline")
    return head


def verify_frozen_lineage():
    root = Path("experiments/oss/annotation-results/prompt013-f")
    b = load_corpus(
        Path("experiments/oss/oss-corpus-v1.json"),
        Path("experiments/oss/selection-protocol-v1.json"),
        Path("experiments/oss/corpus-freeze.json"),
    )
    s = load_sample(
        Path("experiments/oss/annotation/sample-v1.json"),
        Path("experiments/oss/annotation/sample-freeze-v1.json"),
    )
    c = RevisionCatalog.model_validate_json(
        Path("experiments/oss/annotation/review-packet-revisions-final-v1.json").read_text()
    )
    private = Path("experiments/oss/blinded/prompt013-e/import-adjudicated")
    store = ReviewStore.model_validate_json((private / "reviews.json").read_text())
    report = AnnotationReviewReport.model_validate_json(
        (private / "review-report.json").read_text()
    )
    assert report == review_report(s, store)
    native = ReviewedFreeze.model_validate_json(
        (root / "protocol-freeze/annotation-freeze.json").read_text()
    )
    assert native == freeze_reviews(s, c, store)

    def verified(name):
        raw = json.loads((root / name).read_text())
        assert raw["fingerprint"] == digest({k: v for k, v in raw.items() if k != "fingerprint"}), (
            name
        )
        return raw

    gt = verified("ground-truth.json")
    f = verified("annotation-freeze.json")
    m = verified("freeze-manifest.json")
    ready = verified("scientific-readiness.json")
    for path, expected in m["files"]:
        assert hashlib.sha256((root / path).read_bytes()).hexdigest() == expected, path
    expected = {
        "sample": "3fd3619f74509ae4334f174a6e4472c48bb55c0b64e7a49e077cf1f4713359b9",
        "catalog": "9d5e3aad6ce60a5d65ed0b1b34976066301be539c220bd8379325884985c0443",
        "store": "684577a73716e15792e04cee77c8220bd4bd5e6c4363cbd1880b886f50eb957b",
        "report": "d77b39c7a05899460ec2c7c5b86da428e3ea66ba29a01ae09803bc7daa9868f6",
        "truth": "14e8de64c7b0d1ccaa11dc6d0fed247ea723abc6bca2a1445f8f8298895ca0e4",
        "freeze": "6ed86e0806de70b797fff5d28a0d9a6417f65ba9cbcb85c131621aba73653a5f",
    }
    actual = dict(
        sample=s.fingerprint,
        catalog=c.fingerprint,
        store=store.fingerprint,
        report=report.fingerprint,
        truth=gt["fingerprint"],
        freeze=f["fingerprint"],
    )
    assert actual == expected
    for key, value in {
        "sample_fingerprint": s.fingerprint,
        "final_catalog_fingerprint": c.fingerprint,
        "adjudicated_store_fingerprint": store.fingerprint,
        "final_ground_truth_fingerprint": gt["fingerprint"],
        "final_review_report_fingerprint": report.fingerprint,
        "protocol_freeze_fingerprint": native.fingerprint,
        "corpus_fingerprint": b.corpus.fingerprint,
        "corpus_freeze_fingerprint": b.freeze.fingerprint,
    }.items():
        assert f[key] == value, key
    assert tuple(row["annotation_case_id"] for row in gt["cases"]) == tuple(
        p.annotation_case_id for p in s.packets
    )
    cases = {row.annotation_case_id: row for row in store.cases}
    latest = {p.annotation_case_id: p for p in c.packets}
    for row, packet in zip(gt["cases"], s.packets, strict=True):
        case = cases[row["annotation_case_id"]]
        rev = latest[case.annotation_case_id]
        assert (row["human_status"], row["final_human_label"], row["binary_eligible"]) == (
            case.status,
            case.final_label,
            case.binary_eligible,
        )
        assert (row["repository_id"], row["rule_id"], row["language"]) == (
            packet.repository_id,
            packet.rule_id,
            packet.subject.language.value,
        )
        assert (row["packet_revision"], row["packet_fingerprint"]) == (
            rev.revision,
            rev.fingerprint,
        )
    assert Counter(row["final_human_label"] for row in gt["cases"]) == {
        "NEGATIVE": 32,
        "OUT_OF_SCOPE": 8,
    }
    assert Counter(row["human_status"] for row in gt["cases"]) == {
        "DOUBLE_REVIEW": 39,
        "ADJUDICATED": 1,
    }
    assert ready["ANNOTATION_VALID"] is ready["REAL_AI_EXECUTION_READY"] is True
    assert (
        ready["POSITIVE_CLASS_PRESENT"]
        is ready["PRIMARY_SEMANTIC_EFFECTIVENESS_READY"]
        is ready["evaluation_started"]
        is False
    )
    assert f["contamination_audit"]["live_ai_calls_during_annotation"] == 0
    assert not any(
        f["contamination_audit"][key]
        for key in (
            "structural_v2_evaluation",
            "hybrid_evaluation",
            "model_predictions_used_to_change_truth",
            "detector_predictions_used_to_change_truth",
        )
    )
    return actual | {
        "corpus": b.corpus.fingerprint,
        "corpus_freeze": b.freeze.fingerprint,
        "native_freeze": native.fingerprint,
        "all_frozen_p013_fingerprints_verified": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--graph-inputs", type=Path, required=True)
    parser.add_argument(
        "--private-output", type=Path, default=Path("experiments/ai/private/semantic-context-v1")
    )
    parser.add_argument("--output", type=Path, default=Path("experiments/ai/semantic-context-v1"))
    parser.add_argument(
        "--accounting-output", type=Path, default=Path("experiments/preflight/semantic-context-v1")
    )
    parser.add_argument(
        "--pricing-output",
        type=Path,
        default=Path("experiments/pricing/gpt-6-luna-standard-user-assumption-2026-10-06-v1.json"),
    )
    args = parser.parse_args()
    head = verify_baseline_head()
    for path in (args.private_output, args.output, args.accounting_output, args.pricing_output):
        if path.exists():
            raise ValueError("immutable preflight output already exists: " + str(path))
    with ExitStack() as guards:
        for name in (
            "socket.socket",
            "archguard.infrastructure.llm_provider._post",
            "archguard.infrastructure.llm_provider.create_llm_provider",
            "archguard.infrastructure.llm_provider.AIProviderSettings",
        ):
            guards.enter_context(
                patch(
                    name,
                    side_effect=AssertionError(
                        "offline preflight forbids networking and credentials"
                    ),
                )
            )
        lineage = verify_frozen_lineage()
        bound = load_corpus(
            Path("experiments/oss/oss-corpus-v1.json"),
            Path("experiments/oss/selection-protocol-v1.json"),
            Path("experiments/oss/corpus-freeze.json"),
        )
        sample = load_sample(
            Path("experiments/oss/annotation/sample-v1.json"),
            Path("experiments/oss/annotation/sample-freeze-v1.json"),
        )
        manifest = experiment_manifest(
            bound.corpus.fingerprint,
            bound.freeze.fingerprint,
            sample.fingerprint,
            tuple(p.annotation_case_id for p in sample.packets),
        )
        pricing = seal(PricingAssumption)
        rows, contexts = prepare_contexts(
            bound, sample, args.cache, args.graph_inputs, manifest, args.private_output
        )
        report = publish_preflight(manifest, rows, contexts, pricing, args.output)
        if lineage != verify_frozen_lineage():
            raise ValueError("P013 lineage changed during preparation")
        args.pricing_output.parent.mkdir(parents=True, exist_ok=True)
        write_new(args.pricing_output, pricing)
        args.accounting_output.mkdir(parents=True)
        write_new(args.accounting_output / "cost-preflight-v1.json", report)
        write_new(
            args.accounting_output / "p013-lineage-verification-v1.json",
            lineage | {"head": head, "live_api_calls": 0},
        )
        print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
