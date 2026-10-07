"""Prospective source/engineering freeze only. No provider or human-answer execution."""

import argparse
import json
import secrets
import shutil
import subprocess
from pathlib import Path

from archguard.benchmark.oss.models import digest
from archguard.benchmark.semantic_holdout import RULES, VERSION, operators
from archguard.infrastructure.semantic_holdout import construct_holdout, sealed, verify_file_freeze

P014_COMMIT = "f69a544a9b80911a471040b478173bb8bf7f9486"
PUBLIC = Path("experiments/semantic-holdout/semantic-positive-holdout-v1")
PRIVATE = Path("experiments/semantic-holdout/private/semantic-positive-holdout-v1")
OLD_PATHS = (
    "experiments/oss",
    "experiments/ai",
    "experiments/preflight",
    "experiments/pricing",
    "experiments/calibration",
    "experiments/results",
)


def definitions():
    protocol = sealed(
        {
            "schema_version": "prospective-independent-review-v1",
            "dataset_id": VERSION,
            "reviewer_slots": ["A", "B"],
            "reviewers_must_be_real_distinct_humans": True,
            "allowed_outcomes": ["POSITIVE", "NEGATIVE", "UNCERTAIN", "OUT_OF_SCOPE"],
            "independence": "Each human reviews all 100 cases without seeing the other decisions",
            "required_submission": "Outcome, independent rationale, evidence IDs and real identity",
            "adjudication": (
                "A distinct real human reviews conflicts only; never a third paired reviewer"
            ),
            "reviewer_access": "Own source-only bundle and rubric only; "
            "no generator/operator/catalog, "
            "provenance, pair map, construction intent, model or detector results",
            "intent_is_not_truth": True,
            "post_freeze_replacements": "FORBIDDEN after any human or model outcomes",
            "technical_rejection": "Pre-freeze only: syntax/IAM/graph/span/replay/native failure",
            "status": "WAITING_FOR_HUMAN_REVIEW",
            "auto_review": False,
        }
    )
    guidance = sealed(
        {
            "schema_version": "semantic-review-guidance-v1",
            "general": "Judge source and architectural contract only. Cite evidence IDs. "
            "Do not infer truth from names, expected prevalence or tool predictions. "
            "UNCERTAIN means evidence cannot establish the applicable concern; "
            "OUT_OF_SCOPE means the question is inapplicable.",
            "rules": {
                "ARCH201": "Implementation responsibility contradicts the documented role. "
                "Require material behavior; naming alone is insufficient.",
                "ARCH202": "Applicable to HTTP controller/request components. Business decisions "
                "include pricing, eligibility, allocation or workflow policy. "
                "Routing, validation, mapping and serialization alone are insufficient.",
                "ARCH203": "Direct concrete storage/transport/filesystem responsibility in a "
                "domain/application boundary where its contract forbids that concern. "
                "Using an appropriate boundary abstraction alone is insufficient.",
                "ARCH204": "Coherent implementation belongs to a different architecture slot. "
                "Use behavior, documented ownership and callers; package names alone "
                "are insufficient.",
                "ARCH205": "A component materially owns multiple distinct responsibilities "
                "across documented layers. Delegating orchestration alone is insufficient.",
            },
            "arch201_vs_arch205": "ARCH201 concerns role contradiction, even with a single "
            "implemented concern. ARCH205 requires material ownership of "
            "multiple concerns; semantic rule overlaps remain possible.",
        }
    )
    analysis = sealed(
        {
            "schema_version": "prospective-semantic-analysis-plan-v1",
            "activation_gate": (
                "Independent final human truth freeze, followed by separate authorization"
            ),
            "primary_population": "Final human POSITIVE/NEGATIVE cases only",
            "excluded_from_binary": ["UNCERTAIN", "OUT_OF_SCOPE"],
            "excluded_outcomes_still_reported": True,
            "prediction_mapping": {
                "SUPPORTED": "TP or FP",
                "NOT_SUPPORTED": "FN or TN",
                "INSUFFICIENT_CONTEXT": "ABSTENTION, not a forced negative",
                "NOT_APPLICABLE": "SCOPE_ERROR on eligible cases; scope recognition on OOS",
                "invalid_or_failed": "Execution failure, separate from semantic judgment",
            },
            "primary_metrics": {
                "Precision": "TP/(TP+FP)",
                "Recall": "TP/(TP+FN), definitive positive decisions",
                "F1": "2TP/(2TP+FP+FN), definitive decisions",
                "Specificity": "TN/(TN+FP)",
                "FPR": "FP/(FP+TN)",
                "FNR": "FN/(TP+FN), definitive positive decisions",
                "definitive_coverage": "(TP+TN+FP+FN)/all binary-eligible human cases",
                "abstention": "INSUFFICIENT_CONTEXT/all binary-eligible human cases",
            },
            "mandatory_companions": {
                "effective_positive_correctness": "TP/all human POSITIVE cases",
                "effective_negative_correctness": "TN/all human NEGATIVE cases",
                "coverage_by_human_class": "Definitive cases/class total",
                "scope_errors_and_failures": (
                    "Counts and full-population rates; never silently dropped"
                ),
            },
            "undefined_denominators": "null",
            "secondary": [
                "Per rule",
                "Per language",
                "VALID vs PARTIAL/INVALID",
                "Matched mutation/control pairs",
                "Three context strategies",
                "Actual tokens/latency/cost after separately authorized execution",
            ],
            "paired_missingness": (
                "List incomplete pairs; report full cohort and matched complete pairs"
            ),
            "repositories_are_clusters": True,
            "natural_prevalence_estimate": False,
            "do_not_pool_with_p013_p014": True,
            "construction_balance_is_not_human_balance": True,
            "computed_metrics": "NONE; no human truth exists",
            "no_overall_superiority_from_construction_intent": True,
        }
    )
    return protocol, guidance, analysis


def old_trees():
    return {
        p: subprocess.check_output(["git", "rev-parse", f"{P014_COMMIT}:{p}"], text=True).strip()
        for p in OLD_PATHS
    }


def verify_old_state():
    assert (
        subprocess.run(["git", "merge-base", "--is-ancestor", P014_COMMIT, "HEAD"]).returncode == 0
    )
    assert (
        subprocess.check_output(
            ["git", "diff", "--name-only", P014_COMMIT, "--", *OLD_PATHS], text=True
        )
        == ""
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    verify_old_state()
    if args.verify:
        freeze = json.loads((PUBLIC / "sample-freeze-v1.json").read_text())
        private_freeze = json.loads((PRIVATE / "private-freeze-v1.json").read_text())
        verify_file_freeze(PUBLIC, freeze)
        verify_file_freeze(PRIVATE, private_freeze)
        assert private_freeze["fingerprint"] == freeze["private_freeze_fingerprint"]
        print(json.dumps({"status": "FROZEN_ARTIFACTS_VERIFIED", "freeze": freeze["fingerprint"]}))
        return
    assert (
        subprocess.run(
            ["git", "check-ignore", "-q", str(PRIVATE / "provenance-v1.json")]
        ).returncode
        == 0
    )
    p013 = json.loads(Path("experiments/oss/annotation/sample-v1.json").read_text())
    excluded = {p["annotation_case_id"] for p in p013["packets"]}
    protocol, guidance, analysis = definitions()
    node = shutil.which("node")
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    node_path = Path(node) if node else bundled if bundled.is_file() else None
    javac = shutil.which("javac")
    javac_path = Path(javac) if javac else None
    if javac_path and subprocess.run([str(javac_path), "-version"], capture_output=True).returncode:
        javac_path = None
    lineage = sealed(
        {
            "dataset_id": VERSION,
            "p014_commit": P014_COMMIT,
            "p014_push_status": "FAILED_AUTH_USERNAME_UNAVAILABLE; normal push only attempted",
            "prior_artifact_git_trees": old_trees(),
            "p013_excluded_case_ids_sha256": digest(sorted(excluded)),
            "source_units": "100 new original fixture instances across 10 original projects",
            "case_selection": "Exhaustive fixed recipe matrix; no prediction-based ranking",
            "case_reuse_count": 0,
            "live_ai_calls": 0,
            "human_answers": "NONE",
            "operators": [o.model_dump(mode="json") for o in operators()],
            "operator_counts": {r: 10 for r in RULES},
            "construction_cli_fingerprint": digest(Path(__file__).read_text()),
            "native_node_version": subprocess.check_output(
                [str(node_path), "--version"], text=True
            ).strip()
            if node_path
            else "UNAVAILABLE",
        }
    )
    frozen = construct_holdout(
        PUBLIC,
        PRIVATE,
        secrets.token_bytes(32),
        P014_COMMIT,
        excluded,
        protocol,
        guidance,
        analysis,
        node_path,
        javac_path,
        construction_lineage=lineage,
    )
    verify_old_state()
    print(json.dumps(frozen, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, AssertionError, OSError) as error:
        raise SystemExit(f"PROMPT_015_BLOCKED: {type(error).__name__}: {error}") from None
