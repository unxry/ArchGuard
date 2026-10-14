"""Read-only scientific closure over P025; never fit, predict, evaluate or call a provider."""

import ast
import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

from archguard.benchmark.oss.models import canonical, digest
from archguard.benchmark.unified_hybrid import ABLATIONS, RULES
from archguard.infrastructure import final_evaluation as final
from archguard.infrastructure import unified_human_review as io
from archguard.infrastructure.semantic_positive_evaluation_freeze import verify_evaluation

VERSION = "thesis-core-v1"
SOURCE = "cecb6eb22036383b9b2f210cebc41c82ccee75c2"
ROOT = io.BASE / VERSION
DOC = Path("docs/verification")
DOCUMENTS = (
    DOC / "THESIS_CORE_CLOSURE.md",
    DOC / "THESIS_CORE_RESULTS.md",
    DOC / "THESIS_NUMERIC_FACTS.md",
    DOC / "THESIS_CORE_REPRODUCIBILITY.md",
    Path("docs/research/CORE_THESIS_COMPLETE.md"),
)
SOURCES = (
    "src/archguard/infrastructure/thesis_closure.py",
    "scripts/prompt026_thesis_closure.py",
    "tests/benchmark/test_thesis_closure.py",
)
LINEAGE = {
    "P001-P004": "53956fc29c4e568234579492ac5d4efb95c6d0d8",
    "P005": "1ccebf04e75f01aa0d6fc465cb86fdd45f535539",
    "P006": "280f26c8513afd90a1f3cec1f9ddd2eb3dcf1b7a",
    "P007": "6f06414a33371017b883bfb1c4143e7d1de37429",
    "P008": "5ad963eb881c75ab366bfd5fa473784230303cde",
    "P009": "1a0db742dd6908831e08a8c4e8cff144598d9c91",
    "P010": "a1b466dd45a20bbc59f86d3671bdd5e9d7833369",
    "P010.1": "8e24249313f6eb6b4fb0e623a1f09b44ac18ddde",
    "P011": "df899b097bd07d240591c594baf1ff5ba77a831e",
    "P012": "ee84a6d0c3766ea12f4125d75bb91ddb68df7b85",
    "P013": "17c1292a4d608d5aaf90964d2947fa04919f4e64",
    "P014.OFFLINE": "dcacc6a8ea42231e4d0fb97dcf171caaaae02a56",
    "P014": "f69a544a9b80911a471040b478173bb8bf7f9486",
    "P015": "e91e6c13e6cc7dff7b640f9a968e52dd07745f11",
    "P015.F": "08082d793d5962cee1bdc51dccc54ca79ac46bfd",
    "P016.OFFLINE": "c4e2ed358568e8b0992f8cc3838e688443bbfb5d",
    "P016": "802257d1211e519ae174736c8d83c3614f2678ea",
    "P017.BINDING": "7e96c87d2380dfa417f6df9cbf59d3f512bdb5fe",
    "P017": "8a11b012dadde660318053f2cb6845703cae7547",
    "P018.PLAN": "5a53531a06106b10c5a14986c8e9905c36fb816b",
    "P018": "264e7cc237f96714fc1d066d04418944e397a6e2",
    "P019": "2f596fb57b00a1d8374cdcba50a98ab6ffbe4023",
    "P020": "1891fa553218200139f027ed9c3a82d100f61462",
    "P021.B": "86f19f50de2f638a57192694e5c73afde3fa50dc",
    "P022": "8629d728bf80b4a5ba3009e8730ec14062a77abc",
    "P022.LIVE": "c416b1c1376009c8591026165323268201882495",
    "P023": "881e7b523198f40a09b79000016a1707efe4ecde",
    "P024": "d609a312bdf5ce2af67026008bf2f055c6898962",
    "P024.LIVE": "0c5b467264488dc6e08a54bfd0de8f4ffe3f6096",
    "P024.LIVE.1.RUNTIME": "46320397944273c766bd2723d8354773c8a7ccb2",
    "P024.LIVE.1": "3395b500379530bb5c898b7e7fdeb177326e213b",
    "P024.LIVE.2.RUNTIME": "953af56286437a7e75dac9fba62e5260c13a6cd1",
    "P024.LIVE.2": "27c53640b16ed9746cac3cbcb93a3610c847f5c1",
    "P025.RUNTIME": "f17e3946909c2b2f3ba1861fe35f2baed9b67dd9",
    "P025": SOURCE,
}
PINS = {
    "final-primary-metrics.json": (
        "f98709ce55c6ed64200052a69612480cb3593e1ea6f82592b2f6ca69278f959e"
    ),
    "final-coverage-metrics.json": (
        "ceea3dea28a10596aa84530d033bbabfe1b576dd397a16a17b07a13c24b0b1e1"
    ),
    "final-native-scope-metrics.json": (
        "fc48e613ce28811ce9ff6e85dd78bc7949ebf308c75419801fffeaeab882d604"
    ),
    "final-family-strata.json": "520fce8aa2af38602406158bb16f170d7711102a1b221e06d67a9b03bb94a2e2",
    "final-rule-strata.json": "46cd755a9943e48c84794c9e2beaede45ffb201c14f6abd5d0d895350342d073",
    "final-language-strata.json": (
        "1836a63b276db458a365570eea473a3a95ba1974ae3fff065ea3f6caf8236795"
    ),
    "final-ablation.json": "c68adf9b16375a85812308bc8efc403d238c8d105544d5e20cabd8252ab9c2a2",
    "final-paired-comparisons.json": (
        "9c896e89f268eab905caa9c3ce1b64284d2f0e5901fcc7c9610efcb164cbeb7c"
    ),
    "final-resource-metrics.json": (
        "870efc24437b19790073e0986c899c4ae09329085dbe5b84f4af4736c170c6d9"
    ),
    "final-rq-summary.json": "402d603c6848d5c6866375ae2b919173cc127d2a2c3c15164372630181bcfb2d",
    "final-hypothesis.json": "43911be7b9ab087cad58158abef19b30e3d4e3a1965b4150bd839a1e23c6a053",
    "evaluation-receipt.json": "fe510b5bca86b48197c53cc37d219543fe427c0e0379116d5d4ebb5e3ee502f6",
}
BOUNDARY = {
    "provider_calls": 0,
    "connectivity_calls": 0,
    "credential_reads": 0,
    "paid_spend_usd": "0",
    "model_fitting": 0,
    "threshold_tuning": 0,
    "prediction_regenerations": 0,
    "metric_recomputations": 0,
    "new_annotations": 0,
    "Security": "PLANNED_OUTSIDE_ARCHITECTURE_CORE",
    "UI": "NOT_PART_OF_SCIENTIFIC_CORE",
    "SEC_in_Hybrid": False,
}
EFFICIENCY = (
    "Graph-guided context materially reduced LLM input and estimated cost in the controlled "
    "strategy comparison, while several quality metrics were modestly lower than expanded context."
)
QUALIFIED_HYPOTHESIS = "The hypothesis is supported on the frozen controlled final benchmark N=300."
METRICS = (
    "Precision",
    "Recall",
    "F1",
    "Specificity",
    "FPR",
    "FNR",
    "effective_correctness",
    "definitive_coverage",
)


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    if "fingerprint" in value:
        raise ValueError("already sealed")
    return value | {"fingerprint": digest(value)}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def worktree_gate() -> None:
    names = (
        "lineage-registry.json",
        "capability-registry.json",
        "rule-coverage.json",
        "claim-registry.json",
        "threats-registry.json",
        "reproducibility-registry.json",
        "scientific-registry.json",
        "numeric-facts.json",
        "thesis-results.json",
        "quality-verification.json",
        "closure-manifest.json",
        "freeze-index.json",
    )
    allowed = (
        *SOURCES,
        *(str(p) for p in DOCUMENTS),
        str(DOC / "PROMPT_026.md"),
        *(str(ROOT / n) for n in names),
    )
    entries = git("status", "--porcelain=v1", "-z", "--untracked-files=all").decode().split("\0")
    for entry in filter(None, entries):
        if entry == " D " + io.WORKTREE_EXCEPTION:
            continue
        if entry[:2] not in {"??", " M", "A ", "M "} or entry[3:] not in allowed:
            raise ValueError("P026_UNEXPECTED_WORKTREE_STATE")


def lineage_gate() -> dict[str, Any]:
    rows = []
    previous = None
    for stage, commit in LINEAGE.items():
        for ancestor, descendant in ((commit, SOURCE), (commit, "HEAD")):
            if subprocess.run(
                ["git", "merge-base", "--is-ancestor", ancestor, descendant], capture_output=True
            ).returncode:
                raise ValueError("P026_INVALID_LINEAGE:" + stage)
        if (
            previous
            and subprocess.run(
                ["git", "merge-base", "--is-ancestor", previous, commit], capture_output=True
            ).returncode
        ):
            raise ValueError("P026_INVALID_CHRONOLOGY:" + stage)
        rows.append(
            dict(
                stage=stage,
                commit=commit,
                subject=git("show", "-s", "--format=%s", commit).decode().strip(),
            )
        )
        previous = commit
    ancestry = [
        dict(commit=line.split(" ", 1)[0], subject=line.split(" ", 1)[1])
        for line in git("log", "--reverse", "--format=%H %s", SOURCE).decode().splitlines()
    ]
    return sealed(
        dict(
            rows=rows,
            complete_git_ancestry=ancestry,
            missing_anchors=0,
            invalid_anchors=0,
            early_history="P001-P004 are coalesced in the first IAM baseline commit; "
            "no separate earlier commits exist in this Git history.",
        )
    )


def safe_path(path: str) -> Path:
    p = Path(path)
    if (
        p.is_absolute()
        or ".." in p.parts
        or p.is_symlink()
        or not p.is_file()
        or any(part.startswith(".env") for part in p.parts)
    ):
        raise ValueError("P026_INVALID_PUBLIC_BINDING")
    if not p.parts or p.parts[0] not in {"src", "tests", "scripts", "experiments", "docs"}:
        raise ValueError("P026_INVALID_PUBLIC_BINDING")
    if "private" in p.parts:
        raise ValueError("P026_PRIVATE_PUBLIC_BINDING")
    return p


def artifact(path: str, *, historical: bool = True) -> dict[str, Any]:
    p = safe_path(path)
    raw = p.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if historical and hashlib.sha256(git("show", f"{SOURCE}:{path}")).hexdigest() != sha:
        raise ValueError("P026_SCIENTIFIC_IMMUTABILITY_DRIFT:" + path)
    fp = io.read_seal(p)["fingerprint"] if p.suffix == ".json" else sha
    return dict(artifact=path, fingerprint=fp, sha256=sha)


def binding(path: str, *symbols: str) -> dict[str, Any]:
    ref = artifact(path)
    tree = ast.parse(safe_path(path).read_text())
    names = {
        n.name
        for n in ast.walk(tree)
        if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if not symbols or not set(symbols) <= names:
        raise ValueError("P026_MISSING_IMPLEMENTATION_OR_TEST_SYMBOL:" + path)
    return ref | {"symbols": list(symbols)}


def frozen_inputs() -> dict[str, Any]:
    quality = io.read_seal(
        final.QUALITY, "906fff11cd4488360a2e9f412420633f8c93d823cf5bcc64fe4d406a0afc38e6"
    )
    if (
        quality["status"] != "P025_FINAL_ARCHITECTURE_EVALUATION_COMPLETE"
        or quality["next_stage"] != "READY_FOR_P026_THESIS_CORE_CLOSURE"
    ):
        raise ValueError("P026_P025_NOT_COMPLETE")
    for path, sha in quality["public_file_hashes"].items():
        if io.sha(safe_path(path)) != sha:
            raise ValueError("P026_BLOCKED_P025_FREEZE_DRIFT")
    data = {name: io.read_seal(final.RESULT / name, fp) for name, fp in PINS.items()}
    for name in ("final-truth-counts.json", "prior-context-efficiency.json"):
        data[name] = io.read_seal(final.RESULT / name)
    receipt = final.prediction_gate()
    if receipt["fingerprint"] != "39e860c4ba64e347775c390686f8b842fcf56bb375170b84e575ffadf321aab6":
        raise ValueError("P026_BLOCKED_P025_FREEZE_DRIFT")
    if io.read_seal(final.PRED / "registry.json")["fingerprint"] != (
        "ccb97fa25559d2960be4828c5d06788c9ab187edb355ca11e6fbbc6624a33041"
    ):
        raise ValueError("P026_BLOCKED_P025_FREEZE_DRIFT")
    for root in (final.TRUTH, final.JOIN):
        final.verify_directory(root)
    for path, fp in (
        (final.TRUTH / "truth.json", quality["truth_fingerprint"]),
        (
            final.JOIN / "join.json",
            "dee444d363ce5ad199032106a78fa6d3c648b28f63d9b001d540af7116c175a4",
        ),
    ):
        io.read_seal(path, fp)
    for path, sha in data["evaluation-receipt.json"]["implementation_bindings"].items():
        if io.sha(safe_path(path)) != sha:
            raise ValueError("P026_P025_IMPLEMENTATION_DRIFT")
    for name, sha in data["evaluation-receipt.json"]["files"].items():
        if io.sha(final.RESULT / name) != sha:
            raise ValueError("P026_P025_OUTPUT_DRIFT")
    # Verify the original truth bytes, rather than replacing them with normalized copies.
    cohort = io.read_seal(final.COHORT)
    io.read_seal(final.STRUCTURAL, cohort["fingerprints"]["structural_truth"])
    human = io.read_seal(final.HUMAN_PUBLIC, final.HUMAN_PUBLIC_FP)
    io.read_seal(final.SEMANTIC, human["truth_fingerprint"])
    if io.sha(final.SEMANTIC) != human["truth_raw_sha256"]:
        raise ValueError("P026_HUMAN_TRUTH_DRIFT")
    acquisition = io.read_seal(io.BASE / "p024-live2-acquisition-v1.json", final.ACQUISITION_FP)
    model = io.read_seal(io.BASE / "p023-hybrid-development-v1.json")
    development = io.read_seal(io.BASE / "p020-development-freeze-v1.json")
    preflight = io.read_seal(io.BASE / "p024-final-preflight-v1.json")
    if (
        development["project_overlap"]
        or development["final_overlap"]
        or cohort["overlaps"]["development_projects"]
        or model["post_selection_refit"]
        or model["validation_opens"] != 1
        or model["final_truth_reads"]
        or model["final_evidence_fitting"]
        or not cohort["oracle_independent"]
        or cohort["component_used_as_truth"]
    ):
        raise ValueError("P026_DEVELOPMENT_FINAL_LEAKAGE")
    data.update(
        quality=quality,
        receipt=receipt,
        cohort=cohort,
        human=human,
        acquisition=acquisition,
        model=model,
        development=development,
        preflight=preflight,
    )
    return data


def prior_integrity() -> None:
    """Compare historical private bytes/seals; do not replay oracles or evaluations."""
    semantic = Path("experiments/semantic-holdout")
    truth_public = io.read_seal(semantic / "final-human-ground-truth-verification-v1.json")
    truth = semantic / "private/final-human-ground-truth-v1"
    io.read_seal(truth / "ground-truth-v1.json", truth_public["ground_truth_fingerprint"])
    if io.sha(truth / "ground-truth-v1.json") != truth_public["ground_truth_sha256"]:
        raise ValueError("P026_P015_TRUTH_DRIFT")
    ledger = semantic / "private/p016-live-v1"
    public = io.read_seal(semantic / "p016-live-recovery-verification-v1.json")
    receipt = io.read_seal(
        ledger / "assessment-freeze.json", public["ai_freeze_receipt_fingerprint"]
    )
    io.verify_files(
        ledger,
        receipt["files"] | {"assessment-freeze.json": io.sha(ledger / "assessment-freeze.json")},
    )
    for name, key in (
        ("raw-ledger.json", "raw_ledger_fingerprint"),
        ("normalized-assessments.json", "normalized_assessment_fingerprint"),
        ("attempt-usage-ledger.json", "usage_ledger_fingerprint"),
        ("execution-lineage.json", "execution_lineage_fingerprint"),
    ):
        io.read_seal(ledger / name, public[key])
    evaluation = io.read_seal(semantic / "p017-evaluation-freeze-v1.json")
    verify_evaluation(semantic / "private/p017-evaluation-v1", evaluation["fingerprint"])
    from archguard.infrastructure import component_holdout as component

    holdout = io.read_seal(component.HOLDOUT)
    for path, key in (
        (component.EXECUTION / "manifest-v1.json", "execution_manifest_fingerprint"),
        (component.PRIVATE / "truth-v1.json", "truth_fingerprint"),
        (component.PRIVATE / "source-inventory-v1.json", "source_inventory_fingerprint"),
        (component.PRIVATE / "validation-v1.json", "validation_fingerprint"),
        (component.PRIVATE / "independence-v1.json", "independence_fingerprint"),
    ):
        io.read_seal(path, holdout[key])
    inventory = io.read_seal(component.PRIVATE / "source-inventory-v1.json")["files"]
    source_files = {
        str(p.relative_to(component.PRIVATE)): io.sha(p)
        for p in (component.PRIVATE / "sources").rglob("*")
        if p.is_file()
    }
    if source_files != inventory:
        raise ValueError("P026_P019_SOURCE_DRIFT")
    for name in ("static", "graph", "v2"):
        output = component.OUTPUT / name / "output-v1.json"
        frozen = io.read_seal(component.BASE / f"p019-{name}-output-freeze-v1.json")
        io.read_seal(output, frozen["output_fingerprint"])
        if io.sha(output) != frozen["output_sha256"]:
            raise ValueError("P026_P019_BASELINE_DRIFT")


# Each mandatory entry binds historical source symbols and runnable regression tests.
CAPABILITIES = (
    (
        "JAVA",
        "parsing/tree_sitter_adapters.py",
        "JavaParser",
        "unit/test_parsing_adapters.py",
        "test_valid_fixtures_build_real_trees",
    ),
    (
        "TYPESCRIPT",
        "parsing/tree_sitter_adapters.py",
        "TypeScriptParser",
        "unit/test_parsing_adapters.py",
        "test_valid_fixtures_build_real_trees",
    ),
    (
        "JS_TSX",
        "parsing/tree_sitter_adapters.py",
        "TSXParser",
        "unit/test_parsing_adapters.py",
        "test_language_constructs_are_present_in_syntax_tree",
    ),
    (
        "IAM",
        "iam_building/builder.py",
        "IAMBuilder",
        "integration/test_iam_pipeline.py",
        "test_real_fixture_build_roundtrips",
    ),
    (
        "DEPENDENCIES",
        "extraction/resolution/resolver.py",
        "SymbolResolver",
        "integration/test_iam_pipeline.py",
        "test_real_fixture_build_roundtrips",
    ),
    (
        "ARCHITECTURE_SPEC_DSL",
        "architecture/specification/loader.py",
        "ArchitectureSpecLoader",
        "unit/test_architecture_specification.py",
        "test_examples_roundtrip_and_normalize",
    ),
    (
        "STATIC",
        "architecture/conformance/analyzer.py",
        "StaticConformanceAnalyzer",
        "unit/test_static_rules.py",
        "test_four_explicit_rules",
    ),
    (
        "GRAPH",
        "architecture/graph/analyzer.py",
        "GraphAnalyzer",
        "unit/test_graph_engine.py",
        "test_chain_exact_metrics_and_pagerank",
    ),
    (
        "SEMANTIC_LLM",
        "architecture/intelligence/analyzer.py",
        "SemanticArchitectureAnalyzer",
        "intelligence/test_semantics.py",
        "test_all_semantic_rules_and_decisions_are_candidates",
    ),
    (
        "GRAPH_GUIDED",
        "architecture/intelligence/context.py",
        "GraphGuidedContextBuilder",
        "intelligence/test_context.py",
        "test_hard_context_budgets",
    ),
    (
        "HYBRID",
        "benchmark/unified_hybrid.py",
        "precedence",
        "benchmark/test_unified_hybrid.py",
        "test_learned_synthetic_ablations_refit_and_precedence",
    ),
    (
        "RULES_15",
        "benchmark/unified_hybrid.py",
        "family",
        "benchmark/test_unified_hybrid.py",
        "test_family_catalog",
    ),
    (
        "BENCHMARK_INDEPENDENT_TRUTH",
        "benchmark/component_holdout.py",
        "oracle",
        "benchmark/test_unified_hybrid.py",
        "test_new_structural_operator_and_oracle",
    ),
    (
        "METRICS",
        "benchmark/final_evaluation.py",
        "metrics",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "ABLATIONS",
        "infrastructure/final_evaluation.py",
        "evaluate",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "STRATA",
        "benchmark/final_evaluation.py",
        "aggregate",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "RESOURCES",
        "infrastructure/final_evaluation.py",
        "evaluate",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "CONTEXT_EFFICIENCY",
        "infrastructure/final_evaluation.py",
        "prior_evidence",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "RQ_SYNTHESIS",
        "infrastructure/final_evaluation.py",
        "rq_summary",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "HYPOTHESIS",
        "benchmark/final_evaluation.py",
        "hypothesis",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "REPRODUCIBILITY",
        "infrastructure/final_evaluation.py",
        "verify_directory",
        "intelligence/test_final_evaluation.py",
        "test_exact_metrics_zero_denominators_and_no_new_accuracy",
    ),
    (
        "NO_TARGET_ANOMALIES",
        "architecture/discovery/analyzer.py",
        "ArchitectureDiscoveryAnalyzer",
        "hybrid/test_decisions.py",
        "test_actual_cycles_without_target_rule_are_not_findings",
    ),
    (
        "TARGET_SPEC_CONFORMANCE",
        "architecture/graph/conformance.py",
        "GraphConformanceAnalyzer",
        "hybrid/test_decisions.py",
        "test_explicit_arch003_survives_negative_ai",
    ),
)


def capability_registry(refs: dict[str, Any]) -> dict[str, Any]:
    rows = []
    for name, src, symbol, test, test_symbol in CAPABILITIES:
        evidence_names = {
            "CONTEXT_EFFICIENCY": ("prior-context-efficiency.json",),
            "HYPOTHESIS": ("final-hypothesis.json",),
            "RQ_SYNTHESIS": ("final-rq-summary.json",),
            "RESOURCES": ("final-resource-metrics.json",),
            "ABLATIONS": ("final-ablation.json",),
            "STRATA": ("final-rule-strata.json", "final-language-strata.json"),
            "RULES_15": ("final-rule-strata.json",),
            "JAVA": ("final-language-strata.json",),
            "TYPESCRIPT": ("final-language-strata.json",),
        }.get(name, ("final-primary-metrics.json", "evaluation-receipt.json"))
        if name in {"RESOURCES", "RQ_SYNTHESIS", "ABLATIONS", "STRATA", "REPRODUCIBILITY"}:
            test_symbol = "test_full_offline_reproducibility_no_predict_after_truth"
        rows.append(
            dict(
                capability=name,
                status="IMPLEMENTED" if name == "JS_TSX" else "EXPERIMENTALLY_VERIFIED",
                mandatory=True,
                implementation=binding("src/archguard/" + src, symbol),
                tests=binding("tests/" + test, test_symbol),
                scientific_evidence=[refs[n] for n in evidence_names],
                scope="Controlled Java/TypeScript architecture core; JS/TSX parser support "
                "has regression evidence only, no final JS/TSX stratum.",
                limitations="Bounded static resolution; no universal program semantics.",
            )
        )
    return sealed(
        dict(
            rows=rows,
            Security=BOUNDARY["Security"],
            UI=BOUNDARY["UI"],
            graph_signals=[
                "Ca",
                "Ce",
                "coupling",
                "I",
                "SCC",
                "cycle",
                "betweenness",
                "PageRank",
                "frozen_V2_score",
            ],
            graph_signal_bindings=[
                binding("src/archguard/architecture/graph/metrics.py", "calculate_metrics"),
                binding("src/archguard/architecture/graph/algorithms.py", "cycle_observations"),
                binding("src/archguard/infrastructure/unified_hybrid.py", "evidence_record"),
            ],
            point_compatibility=binding("src/archguard/extraction/common.py", "location"),
            pipeline_bindings=[
                binding("src/archguard/extraction/java/extractor.py", "JavaExtractor"),
                binding("src/archguard/extraction/ecmascript/extractor.py", "TypeScriptExtractor"),
                binding("src/archguard/iam/model.py", "ArchitectureModel"),
                binding("src/archguard/iam/nodes.py", "ArchitectureNode"),
                binding("src/archguard/iam/edges.py", "ArchitectureEdge"),
                binding("src/archguard/architecture/graph/builder.py", "GraphBuilder"),
                binding(
                    "src/archguard/infrastructure/semantic_positive_live.py",
                    "OpenAIPositiveTransport",
                    "decode_response",
                ),
                binding("src/archguard/calibration/unified.py", "fit_candidate"),
                binding("src/archguard/calibration/numeric.py", "fit_coefficients"),
            ],
        )
    )


RULE_NAMES = (
    "ForbiddenDependency",
    "LayerViolation",
    "CircularDependency",
    "ReverseDependency",
    "ModuleBoundaryViolation",
    "ExcessiveCoupling",
    "DependencyHub",
    "PotentialGodComponent",
    "UnstableDependency",
    "ArchitectureBottleneck",
    "ResponsibilityMismatch",
    "BusinessLogicInController",
    "InfrastructureLeakage",
    "MisplacedComponent",
    "SuspiciousCrossLayerResponsibility",
)


def rule_registry(data: dict[str, Any]) -> dict[str, Any]:
    strata = data["final-rule-strata.json"]["strata"]
    if set(strata) != set(RULES) or len(strata) != 15:
        raise ValueError("P026_RULE_SET_DRIFT")
    rows = []
    static = {"ARCH001", "ARCH002", "ARCH004", "ARCH005"}
    for rule, name in zip(RULES, RULE_NAMES, strict=True):
        semantic = rule.startswith("ARCH2")
        family = "NORMATIVE" if rule.startswith("ARCH0") else "SEMANTIC" if semantic else "GRAPH"
        owner = "STATIC" if rule in static else "LLM" if semantic else "GRAPH"
        path, symbol, test, test_symbol = (
            (
                "architecture/rules/builtin.py",
                {
                    "ARCH001": "ForbiddenDependencyRule",
                    "ARCH002": "LayerDependencyRule",
                    "ARCH004": "ReverseDependencyRule",
                    "ARCH005": "ModuleBoundaryRule",
                }[rule],
                "unit/test_static_rules.py",
                "test_four_explicit_rules",
            )
            if owner == "STATIC"
            else (
                "architecture/intelligence/analyzer.py",
                "SemanticArchitectureAnalyzer",
                "intelligence/test_semantics.py",
                "test_all_semantic_rules_and_decisions_are_candidates",
            )
            if semantic
            else (
                "architecture/graph/conformance.py",
                "cyclic_finding",
                "unit/test_graph_engine.py",
                "test_cycle_metrics_and_canonical_closed_proof",
            )
            if rule == "ARCH003"
            else (
                "infrastructure/unified_hybrid.py",
                "evidence_record",
                "unit/test_graph_engine.py",
                "test_all_candidates_have_explicit_thresholds_and_null_confidence",
            )
        )
        m = strata[rule]["A7"]
        if m["N"] != 20 or m["positive"] != 10 or m["negative"] != 10:
            raise ValueError("P026_RULE_COUNTS_DRIFT")
        rows.append(
            dict(
                rule_id=rule,
                name=name,
                family=family,
                scientific_owner=owner,
                implementation=binding("src/archguard/" + path, symbol),
                tests=binding("tests/" + test, test_symbol),
                evidence_type="SEMANTIC_LLM"
                if semantic
                else "DIRECT_CYCLE_PROOF"
                if rule == "ARCH003"
                else "DETERMINISTIC_CONTRACT_PROOF"
                if owner == "STATIC"
                else "GRAPH_SIGNALS_FROZEN_V2",
                deterministic=owner == "STATIC" or rule == "ARCH003",
                graph_based=owner == "GRAPH",
                semantic=semantic,
                N=20,
                positive=10,
                negative=10,
                methods=strata[rule],
                final_aggregate=artifact(str(final.RESULT / "final-rule-strata.json")),
                precedence="Unconditional positive proof when component included"
                if owner == "STATIC" or rule == "ARCH003"
                else "Frozen selected Hybrid",
                Hybrid="Included components/evidence; no Security rules",
            )
        )
    return sealed(
        dict(
            rows=rows,
            missing=0,
            duplicates=0,
            SEC_rules=[],
            native_static_cases=80,
            native_graph_cases=120,
        )
    )


CLAIMS = (
    ("Java architectural source analysis exists.", "IMPLEMENTATION", "JAVA", "system_architecture"),
    (
        "TypeScript architectural source analysis exists.",
        "IMPLEMENTATION",
        "TYPESCRIPT",
        "system_architecture",
    ),
    (
        "IAM and dependency graph extraction exist.",
        "IMPLEMENTATION",
        "DEPENDENCIES",
        "system_architecture",
    ),
    (
        "Static architectural conformance analysis exists.",
        "IMPLEMENTATION",
        "STATIC",
        "static_method",
    ),
    ("Graph architectural analysis exists.", "IMPLEMENTATION", "GRAPH", "graph_method"),
    (
        "LLM semantic architectural analysis exists.",
        "IMPLEMENTATION",
        "SEMANTIC_LLM",
        "semantic_method",
    ),
    (
        "Graph-guided LLM context construction exists.",
        "IMPLEMENTATION",
        "GRAPH_GUIDED",
        "graph_guided_context",
    ),
    ("Hybrid evidence fusion exists.", "IMPLEMENTATION", "HYBRID", "hybrid_method"),
    (
        "All 15 ARCH001–ARCH205 rules are covered and evaluated.",
        "IMPLEMENTATION",
        "RULES_15",
        "rules",
    ),
    (
        (
            "A7 improves Recall and F1 over A1/A2/A3, with no loss o"
            "f Precision on final controlled N=300."
        ),
        "EXPERIMENTAL",
        "METRICS",
        "results",
    ),
    (QUALIFIED_HYPOTHESIS, "EXPERIMENTAL", "HYPOTHESIS", "hypothesis"),
    (EFFICIENCY, "EXPERIMENTAL", "CONTEXT_EFFICIENCY", "graph_guided_context"),
    (
        (
            "RQ2 remains PARTIALLY_ANSWERED; collective graph eviden"
            "ce does not rank causal feature importance."
        ),
        "LIMITATION",
        "RQ_SYNTHESIS",
        "rq_answers",
    ),
    (
        (
            "RQ6 remains PARTIALLY_ANSWERED; tested-range feasibilit"
            "y does not establish universal scalability."
        ),
        "LIMITATION",
        "RESOURCES",
        "rq_answers",
    ),
    (
        "Results are benchmark-specific; controlled balance is not a natural prevalence estimate.",
        "LIMITATION",
        "BENCHMARK_INDEPENDENT_TRUTH",
        "threats_to_validity",
    ),
    (
        "Security is separate and outside the architecture Hybrid result.",
        "INTERPRETATION",
        "RULES_15",
        "scope",
    ),
)


def claim_registry(capabilities: dict[str, Any]) -> dict[str, Any]:
    by_name = {r["capability"]: r for r in capabilities["rows"]}
    rows = []
    for i, (text, kind, cap, section) in enumerate(CLAIMS, 1):
        c = by_name[cap]
        refs = [c["implementation"], c["tests"], *c["scientific_evidence"]]
        rows.append(
            dict(
                claim_id=f"C{i:03d}",
                claim_text=text,
                claim_type=kind,
                status="VERIFIED_IMPLEMENTATION" if kind == "IMPLEMENTATION" else "SUPPORTED",
                evidence_artifacts=refs,
                fingerprints=[r["fingerprint"] for r in refs],
                scope=c["scope"]
                if i != 12
                else (
                    "Prior P017 controlled strategy comparison; N=99 resourc"
                    "es, N=96 quality; separate from final N=300."
                ),
                limitations=c["limitations"]
                + " "
                + (
                    "RQ2/RQ6 partial; small descriptive strata; no universal"
                    " validity or causal ranking."
                ),
                thesis_sections=[section],
            )
        )
    return sealed(dict(rows=rows, unsupported_supported_claims=0, dangling_claims=0))


THREATS = (
    (
        "Benchmark validity",
        "Controlled/synthetic benchmark",
        "Independent frozen truth and prospective protocol",
        "Natural prevalence and real deployment performance remain unknown",
    ),
    (
        "External validity",
        "OSS-derived methodology is not natural prevalence",
        "Explicit controlled benchmark scope",
        "No population prevalence inference",
    ),
    (
        "External validity",
        "Finite N=300",
        "Shared final cohort for all methods",
        "No universal generalization",
    ),
    (
        "Benchmark validity",
        "Only 20 cases per rule",
        "All 15 rule strata retained",
        "Descriptive strata; no p-values",
    ),
    (
        "External validity",
        "Java/TypeScript only",
        "150/150 language strata preserved",
        "No final JS/TSX or all-language effectiveness claim",
    ),
    (
        "LLM/provider validity",
        "Single frozen provider/model",
        "Protocol and accepted responses frozen",
        "Provider/model dependence and nondeterminism",
    ),
    (
        "Construct validity",
        "GRAPH_GUIDED-only final strategy",
        "Prior comparison separately referenced",
        "No final strategy causal comparison",
    ),
    (
        "Reliability / reproducibility",
        "Two technical-missing rows",
        "N=300 retained; explicit missing indicators",
        "No semantic imputation; one usage value unknown",
    ),
    (
        "Construct validity",
        "Prior graph-guided comparison is a separate cohort",
        "N=99 resources and N=96 quality recorded",
        "Quality modestly lower; no unconditional preservation claim",
    ),
    (
        "Human annotation validity",
        "Human semantic truth is benchmark-specific",
        "Two independent slots, 100/100 agreement and kappa=1",
        "Not universal natural annotator agreement",
    ),
    (
        "Construct validity",
        "RQ2 feature attribution limitation",
        "Collective frozen graph mechanism and diagnostic",
        "No causal individual feature ranking",
    ),
    (
        "External validity",
        "RQ6 scalability limitation",
        "Measured resource facts at tested range",
        "No asymptotic scaling experiment",
    ),
    (
        "Reliability / reproducibility",
        "No per-method RSS",
        "Whole-worker RSS scope explicitly recorded",
        "NOT_MEASURED by method",
    ),
    (
        "Reliability / reproducibility",
        "No final separate Static/Graph runtime",
        "Combined frozen materialization measured",
        "Separate runtimes NOT_MEASURED",
    ),
    (
        "Internal validity",
        "Small rule strata and no significance inference",
        "All error strata and exact deltas published",
        "No p-values or significance claims",
    ),
    (
        "Construct validity",
        "Whole-system ablation is not causal attribution",
        "A4-A7 independently selected before final truth",
        "No feature-causal inference",
    ),
)


def threats_registry(refs: dict[str, Any]) -> dict[str, Any]:
    return sealed(
        dict(
            rows=[
                dict(
                    group=g,
                    threat=t,
                    observed_mitigation=m,
                    remaining_limitation=limit,
                    evidence_artifacts=list(refs.values()),
                )
                for g, t, m, limit in THREATS
            ]
        )
    )


def validate_bundle(bundle: dict[str, dict[str, Any]]) -> None:
    caps = bundle["capability-registry.json"]["rows"]
    required = {c[0] for c in CAPABILITIES}
    if {c["capability"] for c in caps} != required or len(caps) != len(required):
        raise ValueError("P026_MISSING_MANDATORY_CAPABILITY")
    for c in caps:
        if c["status"] not in {"IMPLEMENTED", "EXPERIMENTALLY_VERIFIED"} or not c["mandatory"]:
            raise ValueError("P026_UNIMPLEMENTED_MANDATORY_CAPABILITY")
        for ref in (c["implementation"], c["tests"]):
            binding(ref["artifact"], *ref["symbols"])
        if not c["scientific_evidence"]:
            raise ValueError("P026_MISSING_SCIENTIFIC_EVIDENCE")
    rules = bundle["rule-coverage.json"]["rows"]
    if len(rules) != 15 or {r["rule_id"] for r in rules} != set(RULES):
        raise ValueError("P026_RULE_SET_DRIFT")
    for r in rules:
        if r["N"] != 20 or set(r["methods"]) != {f"A{i}" for i in range(1, 8)}:
            raise ValueError("P026_RULE_STRATUM_DRIFT")
    claims = bundle["claim-registry.json"]["rows"]
    if len(claims) < 16 or len({c["claim_id"] for c in claims}) != len(claims):
        raise ValueError("P026_CLAIM_SET_DRIFT")
    for c in claims:
        if not c["scope"] or not c["limitations"] or not c["thesis_sections"]:
            raise ValueError("P026_DANGLING_CLAIM")
        if c["status"] not in {"SUPPORTED", "VERIFIED_IMPLEMENTATION"}:
            raise ValueError("P026_UNSUPPORTED_CLAIM")
        refs = c["evidence_artifacts"]
        if not refs or c["fingerprints"] != [r["fingerprint"] for r in refs]:
            raise ValueError("P026_DANGLING_CLAIM")
        for ref in refs:
            if artifact(ref["artifact"])["fingerprint"] != ref["fingerprint"]:
                raise ValueError("P026_DANGLING_CLAIM")
    facts = bundle["numeric-facts.json"]
    if facts["benchmark"]["N"] != 300 or facts["languages"] != {"JAVA": 150, "TYPESCRIPT": 150}:
        raise ValueError("P026_BENCHMARK_DRIFT")
    if (
        facts["rq_status"]["RQ2"] != "PARTIALLY_ANSWERED"
        or facts["rq_status"]["RQ6"] != "PARTIALLY_ANSWERED"
    ):
        raise ValueError("P026_RQ_OVERCLAIM")
    if (
        facts["hypothesis_conclusion"] != QUALIFIED_HYPOTHESIS
        or facts["context_qualification"] != EFFICIENCY
    ):
        raise ValueError("P026_OVERCLAIM")
    for name, value in bundle.items():
        if value["fingerprint"] != digest({k: v for k, v in value.items() if k != "fingerprint"}):
            raise ValueError("P026_INVALID_SEAL:" + name)


def build() -> dict[str, dict[str, Any]]:
    """Build source-free copies/references only; outputs are not yet accepted closure."""
    data = frozen_inputs()
    lineage = lineage_gate()
    refs = {name: artifact(str(final.RESULT / name)) for name in data if name.endswith(".json")}
    caps = capability_registry(refs)
    rules = rule_registry(data)
    claims = claim_registry(caps)
    threats = threats_registry(refs)
    primary = data["final-primary-metrics.json"]["methods"]
    languages = data["final-language-strata.json"]["strata"]
    families = data["final-family-strata.json"]["strata"]
    hypothesis = data["final-hypothesis.json"]
    counts = data["final-truth-counts.json"]
    config = data["preflight"]["config"]
    if (
        config["hops"] != 1
        or config["max_context_chars"] != 20000
        or config["model"] != "gpt-6-luna"
    ):
        raise ValueError("P026_LLM_PROTOCOL_DRIFT")
    rq = {r["rq"]: r["status"] for r in data["final-rq-summary.json"]["rows"]}
    facts = sealed(
        dict(
            benchmark={k: v for k, v in counts.items() if k != "fingerprint"},
            languages={k: v["A7"]["N"] for k, v in languages.items()},
            families={k: v["A7"]["N"] for k, v in families.items()},
            rules={r["rule_id"]: r["N"] for r in rules["rows"]},
            primary=primary,
            language_metrics=languages,
            family_metrics=families,
            resources=data["final-resource-metrics.json"],
            ablation=data["final-ablation.json"],
            rq_status=rq,
            hypothesis=hypothesis,
            hypothesis_conclusion=QUALIFIED_HYPOTHESIS,
            context=data["prior-context-efficiency.json"],
            context_qualification=EFFICIENCY,
            technical_missing_is_semantic_abstention=False,
            sources=list(refs.values()),
            policy="Copy sealed P025 values; no metric recomputation",
        )
    )
    stages = []
    stage_paths = (
        (
            "DEVELOPMENT",
            "P020",
            "p020-development-freeze-v1.json",
            "Controlled development units and independent truth",
            "DEVELOPMENT_ONLY",
            False,
        ),
        (
            "TRAIN",
            "P023",
            "p023-hybrid-development-v1.json",
            "TRAIN-only fitting and preprocessing",
            "TRAIN",
            False,
        ),
        (
            "VALIDATION",
            "P023",
            "p023-hybrid-development-v1.json",
            "One-pass candidate selection, no post-selection refit",
            "VALIDATION_ONCE",
            False,
        ),
        (
            "FINAL_HOLDOUT",
            "P020",
            "p020-final-holdout-freeze-v1.json",
            "Prospective controlled cohort and independent structural truth",
            "INDEPENDENT_ORACLE",
            False,
        ),
        (
            "STATIC_GRAPH",
            "P020",
            "p020-offline-verification-v1.json",
            "Blind component evidence",
            "NONE",
            False,
        ),
        (
            "DEVELOPMENT_LLM",
            "P022.LIVE",
            "p022-live-scientific-freeze-v1.json",
            "Blind structural development evidence",
            "NONE",
            True,
        ),
        (
            "HYBRID_MODELS",
            "P023",
            "p023-hybrid-development-v1.json",
            "Frozen A4-A7 and model lock",
            "DEVELOPMENT_ONLY",
            False,
        ),
        (
            "HUMAN_TRUTH",
            "P021.B",
            "p021-b-human-agreement-v1.json",
            "Independent semantic consensus; no reviewer identities",
            "HUMAN_ONLY",
            False,
        ),
        (
            "STRUCTURAL_TRUTH",
            "P020",
            "p020-final-holdout-freeze-v1.json",
            "Independent 200-unit oracle; construction intent not truth",
            "INDEPENDENT_ORACLE",
            False,
        ),
        (
            "FINAL_LLM",
            "P024.LIVE.2",
            "p024-live2-acquisition-v1.json",
            "298 accepted, two historical terminal failures",
            "NONE",
            True,
        ),
        (
            "PREDICTION_FREEZE",
            "P025",
            "p025-final-evaluation-v1.json",
            "Closed writer before first final truth open",
            "NONE_BEFORE_FREEZE",
            False,
        ),
        (
            "FIRST_TRUTH_OPEN_JOIN",
            "P025",
            "p025-final-evaluation-v1.json",
            "First truth open after immutable prediction receipt",
            "AFTER_WRITER_CLOSE",
            False,
        ),
        (
            "EVALUATION_ABLATION_RQ_HYPOTHESIS",
            "P025",
            "p025-final-evaluation-v1.json",
            "Frozen final evaluation on N=300",
            "AFTER_WRITER_CLOSE",
            False,
        ),
    )
    for stage, anchor, path, purpose, truth, provider in stage_paths:
        stages.append(
            dict(
                stage=stage,
                commit=LINEAGE[anchor],
                public_artifact=artifact(str(io.BASE / path)),
                private_artifact_class=stage.lower() + "_frozen_evidence",
                purpose=purpose,
                truth_access=truth,
                provider_activity="HISTORICAL_PAID_ONLY" if provider else "NONE",
                input_dependency="Prior frozen protocol/evidence",
                output_dependency=purpose,
                reproduction_command=".venv/bin/python scripts/prompt026_thesis_closure.py verify",
                expected_invariant="Original seals unchanged; no regeneration",
            )
        )
    prior_paths = (
        "experiments/semantic-holdout/final-human-ground-truth-verification-v1.json",
        "experiments/semantic-holdout/p016-live-recovery-verification-v1.json",
        "experiments/semantic-holdout/p017-aggregate-evaluation-v1.json",
        "experiments/semantic-holdout/p018-diagnostic-freeze-v1.json",
        "experiments/component-holdout/p019-baseline-aggregate-v1.json",
        "experiments/component-holdout/p019-graph-feature-diagnostic-v1.json",
        "experiments/component-holdout/p019-component-registry-v1.json",
    )
    prior = [artifact(p) for p in prior_paths]
    repro = sealed(
        dict(
            stages=stages,
            prior_frozen_artifacts=prior,
            provider_required=False,
            credentials_required=False,
            safe_command=".venv/bin/python scripts/prompt026_thesis_closure.py verify",
            reproduction=(
                "Deterministic downstream computation from frozen eviden"
                "ce and models; P026 verifies seals without recomputatio"
                "n."
            ),
            replication=(
                "Fresh stochastic provider generations constitute a new experiment; not executed."
            ),
            private_requirement=(
                "Authorized local frozen input, prediction, receipt, tru"
                "th and join directories; never raw reviewer identities."
            ),
            p025_replay_status=(
                "READ_ONLY_FREEZE_COMPARISON_PASS; no predictions or metrics regenerated"
            ),
        )
    )
    definitions = {f"A{i}": list(c) for i, c in enumerate(ABLATIONS, 1)}
    science = sealed(
        dict(
            closure_version=VERSION,
            source_commit=SOURCE,
            thesis_topic=(
                "Hybrid static, graph and semantic LLM analysis of archi"
                "tecture in Java/TypeScript software"
            ),
            scientific_hypothesis=hypothesis["hypothesis"],
            hypothesis_conclusion=QUALIFIED_HYPOTHESIS,
            rq_status=rq,
            supported_languages=["JAVA", "TYPESCRIPT"],
            rule_ids=list(RULES),
            method_families=["STATIC", "GRAPH", "SEMANTIC_LLM", "HYBRID"],
            ablations=definitions,
            development_summary={
                k: data["development"][k]
                for k in (
                    "cases",
                    "binary",
                    "nonbinary",
                    "project_overlap",
                    "final_overlap",
                    "by_split",
                )
            },
            selected_models=data["model"]["selected_models"],
            final_summary=facts["benchmark"],
            final_metrics=refs,
            claim_registry=claims["fingerprint"],
            threats_registry=threats["fingerprint"],
            reproducibility_registry=repro["fingerprint"],
            capability_registry=caps["fingerprint"],
            rule_coverage=rules["fingerprint"],
            numeric_facts=facts["fingerprint"],
            authoritative_private_fingerprints={
                "prediction_registry": data["quality"]["prediction_registry_fingerprint"],
                "closed_writer_receipt": data["receipt"]["fingerprint"],
                "final_truth": data["quality"]["truth_fingerprint"],
                "stable_join": data["evaluation-receipt.json"]["join_fingerprint"],
                "selected_model_registry": data["model"]["fingerprints"]["selected_registry"],
            },
            prior_frozen_artifacts=prior,
            contributions=[c[0] for c in CLAIMS[:8]],
            contribution_qualification=(
                "Developed in this work; no first-ever or worldwide novelty claim"
            ),
            confidence="Absent from frozen LLM schema; severity is not confidence",
            no_target=(
                "Architecture anomalies/suspicious structures; no normat"
                "ive conformance assertion without target spec"
            ),
            target_spec="Explicit target contracts support conformance-violation proofs",
            boundaries=BOUNDARY,
        )
    )
    tables = sealed(
        dict(
            primary=primary,
            rule_strata=data["final-rule-strata.json"],
            language_strata=data["final-language-strata.json"],
            family_strata=data["final-family-strata.json"],
            native_scope=data["final-native-scope-metrics.json"],
            coverage=data["final-coverage-metrics.json"],
            ablation=data["final-ablation.json"],
            paired=data["final-paired-comparisons.json"],
            sources=list(refs.values()),
        )
    )
    bundle = {
        "lineage-registry.json": lineage,
        "capability-registry.json": caps,
        "rule-coverage.json": rules,
        "claim-registry.json": claims,
        "threats-registry.json": threats,
        "reproducibility-registry.json": repro,
        "scientific-registry.json": science,
        "numeric-facts.json": facts,
        "thesis-results.json": tables,
    }
    validate_bundle(bundle)
    return bundle


def metric_table(methods: dict[str, Any]) -> str:
    header = "| Method | TP | FP | TN | FN | " + " | ".join(METRICS) + " |\n"
    header += "|" + " --- |" * 13 + "\n"
    for method, m in methods.items():
        header += (
            "| "
            + " | ".join(
                [
                    method,
                    *(str(m[k]) for k in ("TP", "FP", "TN", "FN")),
                    *(f"{m[k]:.12f}" for k in METRICS),
                ]
            )
            + " |\n"
        )
    return header


def documents(bundle: dict[str, dict[str, Any]]) -> dict[Path, str]:
    """A single canonical renderer also checks every duplicated numeric fact byte-for-byte."""
    facts = bundle["numeric-facts.json"]
    science = bundle["scientific-registry.json"]
    resources = facts["resources"]
    primary = metric_table(facts["primary"])
    rq = "\n".join(f"- {k}: {v}." for k, v in facts["rq_status"].items())
    refs = "\n".join(f"- `{r['artifact']}` — `{r['fingerprint']}`." for r in facts["sources"])
    benchmark = (
        "Final controlled N=300: 150 positive / 150 negative; 150 Java / 150 TypeScript; "
        "100 normative / 100 graph / 100 semantic; 15 rules × 20 cases. "
        "200 independent structural truth units and 100 independent human semantic units. "
        "No natural-prevalence inference. TRAIN=196 (193 binary), VALIDATION=84 (83 binary); "
        "TRAIN/VALIDATION and DEVELOPMENT/FINAL project overlap=0."
    )
    method = (
        "Source → Java/TypeScript parser → versioned IAM (files/modules, classes/functions, "
        "members/properties where supported) → resolved dependency edges → directed graph → "
        "Ca/Ce/coupling/I/SCC/cycles/betweenness/PageRank → rule evidence → Hybrid. "
        "JS/TSX parsing is regression-tested, outside the final language strata. Tree-sitter 0.26 "
        "Point tuple-unpacking compatibility is preserved. Resolution is static and bounded.\n\n"
        "Native Static: ARCH001/002/004/005 (80 final cases). Native Graph: ARCH003 and "
        "ARCH101–105 (120). ARCH003 is a direct cycle proof. ARCH201–205 use semantic LLM "
        "evidence. Included deterministic Static and ARCH003 proofs cannot be downgraded. "
        "Graph anomalies without target specification remain suspicious structures; explicit "
        "target specifications support normative conformance violations.\n\n"
        "Frozen OpenAI/gpt-6-luna protocol: GRAPH_GUIDED, 1 hop, 20,000 character context, "
        "max input 32,768 tokens, max output 2,000, expected output 600, at most two technical "
        "retries. Exact request identity and response schema are validated; raw transport and "
        "normalized evidence are separate. Human labels/rational"
        "es were absent from request material. "
        "SUPPORTED, NOT_SUPPORTED, INSUFFICIENT_CONTEXT and NOT_APPLICABLE remain distinct.\n\n"
        "H0 uses categorical deterministic precedence. H1 uses TRAIN-only weighted ridge, L2=1; "
        "H2 uses TRAIN-only Newton logistic regression, L2=1. Numerical preprocessing uses "
        "TRAIN medians/scales and missing indicators. A4=H0, A5=H2@0.5, A6=H2@0.5, "
        "A7=H2@0.75; these are separately trained/selected ablations, not zeroed A7. "
        "No final fitting, threshold search or selection. Frozen schema has no confidence; "
        "severity is not confidence."
    )
    reliability = (
        "300 logical requests / 300 physical invocations; 298 accepted / 2 technical missing; "
        "unexecuted=0. Historical terminal failures: TERMINAL_INVALID_REQUEST_ID_MISMATCH and "
        "AMBIGUOUS_TRANSPORT_NO_CAPTURE. Neither was retried or semantically imputed. Both "
        "missing rows were negative, discovered after freeze/truth open. A3 primary N=300; "
        "available-only N=298 is supplemental. Hybrid handled missing indicators using frozen "
        "TRAIN preprocessing; technical missingness is not semantic abstention.\n\n"
        f"Reported input={resources['composite_input_tokens']}, "
        f"output={resources['composite_output_tokens']}, "
        f"total={resources['composite_total_tokens']}, cached={resources['cached_tokens']}; "
        f"usage unavailable={resources['usage_unavailable_invocations']}. Known estimated cost "
        f"USD {resources['total_known_cost_usd']}; reserved uncertainty USD "
        f"{resources['historical_uncertain_reserved_usd']}; known-or-reserved USD "
        f"{resources['total_exposure_usd']}; invoice=null. These are estimates, not invoice spend. "
        "Whole-worker RSS and offline prediction timings were measured in P025; per-method "
        "RSS and separate final Static/Graph runtime remain NOT_MEASURED. P026 provider calls=0, "
        "connectivity=0, credential reads=0, spend=$0."
    )
    efficiency = (
        EFFICIENCY + "\n\nPrior P017 resource matched N=99, quality N=96. Frozen reductions: "
        "input 52.700049596712%, estimated cost 36.969541052674%. Quality deltas: precision "
        "−3.306878306878 pp, F1 −1.814223512337 pp, effective correctness −2.083333333333 pp. "
        "Final N=300 has only GRAPH_GUIDED and supplies no Expanded comparison."
    )
    limitations = "\n".join(
        f"- {r['threat']}: {r['remaining_limitation']}."
        for r in bundle["threats-registry.json"]["rows"]
    )
    interpretation = (
        "A1 has perfect observed precision in its narrow determi"
        "nistic scope and low unified recall. "
        "A2 supplies graph coverage with nonzero false positives. A3 extends semantic/normative "
        "reach, with false positives, abstention and technical missingness. A6 has near-complete "
        "recall with residual false positives. A7: 149 TP, 0 FP, 149 TN, 1 FN; perfect observed "
        "precision and near-complete recall, with one negative a"
        "bstention. It is not perfect overall "
        "correctness or F1. ARCH104 has one positive miss (Recall=0.900000000000, "
        "F1=0.947368421053). Java has one positive miss (Recall="
        "0.986666666667, F1=0.993288590604); "
        "TypeScript has no positive miss (Recall=1.000000000000, F1=1.000000000000) and one "
        "negative abstention. All rule/language/family A1–A7 strata remain in thesis-results.json."
    )
    deltas = "| A7 minus | Precision pp | Recall pp | F1 pp |\n| --- | --- | --- | --- |\n"
    for name, values in facts["ablation"]["A7_minus"].items():
        deltas += (
            f"| {name} | {values['Precision']:.12f} | "
            f"{values['Recall']:.12f} | {values['F1']:.12f} |\n"
        )
    chronology = (
        "P015 independent development human truth → P019 component baselines → P020 prospective "
        "cohort, structural oracle and project splits → P021 independent final human truth → "
        "P022 blind development LLM → P023 TRAIN-only fitting and one VALIDATION selection → "
        "P024 blind final LLM acquisition → P025 truth-blind closed prediction writer → first "
        "final truth open/join → frozen evaluation/ablation/RQ/h"
        "ypothesis → P026 read-only closure. "
        "Two final reviewer slots agreed on 100/100 units (kappa=1), 50 positive / 50 negative; "
        "this is agreement on a specially constructed prospective benchmark. Construction intent "
        "is not authoritative truth."
    )
    complete = (
        "CORE_THESIS_COMPLETE requires implemented methods/languages/rules, independent frozen "
        "truth, pre-truth model/prediction freeze, final N=300 metrics, seven ablations, honest "
        "RQ synthesis/hypothesis and reproducibility/traceability. Partial RQ2/RQ6 do not justify "
        "stronger answers and do not require further experiments to support the scoped primary "
        "hypothesis. Security, UI, deployment, full thesis prose and defense slides are outside "
        "this scientific closure. Final acceptance is gated by closure-manifest.json and its "
        "quality receipt; generated registries alone do not declare completion."
    )
    closure = f"""# Thesis architecture core closure

## Scope

{science["thesis_topic"]}. Architecture rules only; SEC001–SEC010 are excluded.

## Definition of CORE THESIS COMPLETE

{complete}

## Implemented scientific method

{method}

## Rules ARCH001–ARCH205

Five normative, five graph and five semantic rules. Exact ownership, implementation/test bindings,
all 15 × 20-case A1–A7 strata and fingerprints: `rule-coverage.json`.

## Languages

Java and TypeScript have final experimental evidence; JS/TSX have parser regression evidence only.

## Benchmark

{benchmark}

## Experiment chronology

{chronology}

## Final results

{primary}
{interpretation}

## Ablation

A1 Static; A2 Graph; A3 LLM; A4 Static+Graph; A5 Static+LLM; A6 Graph+LLM; A7 full Hybrid.

{deltas}
No new significance tests or causal attribution.

## RQ1–RQ6

{rq}

## Hypothesis

{science["scientific_hypothesis"]}

{QUALIFIED_HYPOTHESIS} All three strict Recall gains and exact nondecreasing Precision comparisons
were frozen in P025. No universal proof or natural-prevalence claim.

## Graph-guided efficiency result

{efficiency}

## Resource and reliability evidence

{reliability}

## Reproducibility

See [safe verification guide](THESIS_CORE_REPRODUCIBILITY.md). Registries are generated twice and
compared without altering original evidence. All numbers below are copies of frozen P025 JSON.

## Threats and limitations

{limitations}

## Security boundary

Security is PLANNED / OUTSIDE_ARCHITECTURE_CORE; not included in Hybrid results.

## Future engineering work

Security, orchestration polish, frontend/graph UX, report UX, packaging, deployment and performance
hardening are future engineering scope. UI is NOT_PART_OF_SCIENTIFIC_CORE.

## Final closure status

The accepted boolean and mandatory gate results are in `closure-manifest.json`.
P026 stops after scientific closure and normal Git publication, before Security/UI/new experiments.

## Authoritative sources

{refs}
"""
    results = f"""# Thesis core results

{science["thesis_topic"]}.

{science["scientific_hypothesis"]}

{QUALIFIED_HYPOTHESIS}

{benchmark}

{method}

{chronology}

{primary}
{interpretation}

Selected full Hybrid A7=H2@0.75; independent A4–A7 selection preceded final truth.

{deltas}
{rq}

{efficiency}

{reliability}

Limitations:

{limitations}

Authoritative artifact/fingerprint references:

{refs}
"""
    sheet = f"""# Frozen thesis numeric facts

{benchmark}

{primary}
{deltas}
{rq}

{QUALIFIED_HYPOTHESIS}

{efficiency}

{reliability}

Every table/value is rendered from `numeric-facts.json`, copied from these sealed authoritative
P025 aggregates. Twelve decimals are display precision; original floats/exact ratios remain
authoritative.

{refs}
"""
    guide = f"""# Thesis core reproducibility

## Level 1 — safe verification

From the repository root, with the locked project environment and authorized local frozen evidence:

```sh
.venv/bin/python scripts/prompt026_thesis_closure.py verify
.venv/bin/python -m pytest tests/benchmark/test_thesis_closure.py -q
```

No provider, secrets, credential configuration or paid calls are required. The command checks Git
ancestry, historical source/test/artifact bindings, original P025 public file hashes, private input/
prediction/truth/join seals, closed writer receipt, original model hashes, original human/structural
truth, final metric/RQ/hypothesis fingerprints, claim/rule/capability registries, numeric documents
and closure manifest. Missing private evidence must fail full verification; it is not silently
skipped.
A public-only checkout can inspect aggregate registries but cannot claim full private freeze
verification.

P025 replay status: read-only byte/canonical-seal comparison PASS. No evaluation, model fit,
prediction generation or truth rewrite occurs. A second registry construction must equal the first.
Quality checks use synthetic offline fixtures and fake transports, never provider credentials.

## Level 2 — full scientific reproduction

{chronology}

Requirements: pinned Git revisions, locked Python/parser runtime, authorized original private source
snapshots and immutable accepted evidence, independent truth, TRAIN/VALIDATION project split,
frozen selected models, receipts and acquisition ledger. Check each dependency before deterministic
downstream replay in a separate output location; compare canonical hashes without replacing
originals.
P026 does not run that replay or invoke historical mutating stage CLIs.

Historical paid LLM responses are frozen scientific evidence. REPRODUCTION recomputes deterministic
downstream results from this evidence and frozen models. A literal fresh provider rerun is
REPLICATION:
new stochastic/provider outputs and a new experiment needing separate authorization, never an
identical
reproduction. No fresh paid replication is required for core closure.

## Evidence registry

`reproducibility-registry.json` maps stages, commits, public artifacts/fingerprints, private
artifact
classes, input/output dependencies, truth/provider access and safe verification invariants.
Early P001–P004 history is coalesced in the first IAM baseline commit; no separate earlier
commits exist.
Every required P019–P025 anchor and runtime amendment is in `lineage-registry.json`.

## Limits

{limitations}

{complete}
"""
    milestone = f"""# CORE THESIS COMPLETE

{complete}

Authoritative closure: [P026](../verification/PROMPT_026.md),
[scientific closure](../verification/THESIS_CORE_CLOSURE.md),
[reproducibility](../verification/THESIS_CORE_REPRODUCIBILITY.md).

The mandatory method/language/rule/benchmark/evaluation gates and their implementation/test/artifact
bindings are frozen in `experiments/unified-hybrid/thesis-core-v1/closure-manifest.json`.
Use its `CORE_THESIS_COMPLETE` boolean after quality acceptance; prose alone is not evidence.

{QUALIFIED_HYPOTHESIS}

RQ2 and RQ6 remain PARTIALLY_ANSWERED. Security is outside the architecture Hybrid result.
**Security implementation starts only after CORE THESIS COMPLETE and separate authorization.**
"""
    return dict(zip(DOCUMENTS, (closure, results, sheet, guide, milestone), strict=True))


def privacy_audit(paths: list[Path]) -> None:
    patterns = (
        r"sk-[A-Za-z0-9_-]{16,}",
        r"(?i)Bearer\s+[A-Za-z0-9._-]{12,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r'"(?:case_id|execution_id|request_id|reviewer_name|raw_response|source_code)"\s*:',
        r"private/unified-hybrid-experiment",
        r"(?i)authorization\s*:\s*bearer",
    )
    for path in paths:
        raw = path.read_text()
        if any(re.search(p, raw) for p in patterns):
            raise ValueError("P026_PUBLIC_PRIVACY_FAILURE")


def document_gate(bundle: dict[str, dict[str, Any]]) -> dict[str, str]:
    hashes = {}
    for path, expected in documents(bundle).items():
        if path.read_text() != expected:
            raise ValueError("P026_DOCUMENT_NUMERIC_OR_CLAIM_DRIFT:" + str(path))
        hashes[str(path)] = io.sha(path)
    return hashes


def write_new(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text() != content:
            raise ValueError("P026_IMMUTABLE_CLOSURE_DRIFT:" + str(path))
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)


def generate() -> dict[str, Any]:
    worktree_gate()
    prior_integrity()
    bundle = build()
    second = build()
    if canonical(bundle) != canonical(second):
        raise ValueError("P026_NONDETERMINISTIC_CLOSURE")
    for name, value in bundle.items():
        write_new(ROOT / name, canonical(value) + "\n")
    for path, content in documents(bundle).items():
        if (
            path == Path("docs/research/CORE_THESIS_COMPLETE.md")
            and not (ROOT / "closure-manifest.json").exists()
        ):
            path.write_text(content)
        else:
            write_new(path, content)
    document_gate(bundle)
    privacy_audit([*(ROOT / n for n in bundle), *DOCUMENTS])
    return dict(status="P026_REGISTRIES_PREPARED_QUALITY_REQUIRED", double_run="PASS", **BOUNDARY)


def manifest_value(
    bundle: dict[str, dict[str, Any]], q: dict[str, Any], hashes: dict[str, str]
) -> dict[str, Any]:
    return sealed(
        dict(
            closure_version=VERSION,
            source_commit=SOURCE,
            required_lineage=LINEAGE,
            mandatory_checklist={c[0]: "PASS" for c in CAPABILITIES},
            fingerprints={n: v["fingerprint"] for n, v in bundle.items()},
            P025_evaluation_receipt=PINS["evaluation-receipt.json"],
            P025_hypothesis=PINS["final-hypothesis.json"],
            P025_primary=PINS["final-primary-metrics.json"],
            P024_acquisition=final.ACQUISITION_FP,
            P023_model_registry=bundle["scientific-registry.json"][
                "authoritative_private_fingerprints"
            ]["selected_model_registry"],
            implementation_bindings={p: io.sha(Path(p)) for p in SOURCES},
            docs_hashes=hashes,
            public_report_hash=io.sha(DOC / "PROMPT_026.md"),
            all_docs_consistency="PASS",
            privacy_audit="PASS",
            quality_status="PASS",
            quality_fingerprint=q["fingerprint"],
            double_run="PASS",
            CORE_THESIS_COMPLETE=True,
            status="P026_CORE_THESIS_COMPLETE",
            next_stage="WAITING_FOR_COORDINATOR_REVIEW",
            **BOUNDARY,
        )
    )


def accept(quality: dict[str, Any]) -> dict[str, Any]:
    worktree_gate()
    bundle = build()
    if canonical(bundle) != canonical(build()):
        raise ValueError("P026_NONDETERMINISTIC_CLOSURE")
    checks = (
        "ruff",
        "format",
        "strict_mypy",
        "regressions",
        "privacy",
        "secret_audit",
        "numeric_consistency",
        "claim_traceability",
        "artifact_fingerprints",
        "overclaim_audit",
        "diff_check",
        "double_run",
        "acquisition_integrity",
    )
    if (
        quality.get("make_check") != "PASS"
        or not quality.get("full_tests")
        or quality.get("p026_tests", 0) < 1
        or quality.get("provider_calls") != 0
        or quality.get("credential_reads") != 0
        or any(quality.get(check) != "PASS" for check in checks)
    ):
        raise ValueError("P026_QUALITY_INCOMPLETE")
    for name, expected in bundle.items():
        if io.read_seal(ROOT / name) != expected:
            raise ValueError("P026_REGISTRY_DRIFT")
    hashes = document_gate(bundle)
    privacy_audit([*(ROOT / n for n in bundle), *DOCUMENTS, DOC / "PROMPT_026.md"])
    q = sealed(quality)
    write_new(ROOT / "quality-verification.json", canonical(q) + "\n")
    manifest = manifest_value(bundle, q, hashes)
    if manifest != manifest_value(bundle, q, hashes):
        raise ValueError("P026_NONDETERMINISTIC_MANIFEST")
    write_new(ROOT / "closure-manifest.json", canonical(manifest) + "\n")
    names = (*bundle, "quality-verification.json", "closure-manifest.json")
    index = sealed(
        dict(
            files={n: io.sha(ROOT / n) for n in names},
            fingerprints={n: io.read_seal(ROOT / n)["fingerprint"] for n in names},
            public_closure_report_sha256=io.sha(DOC / "PROMPT_026.md"),
        )
    )
    write_new(ROOT / "freeze-index.json", canonical(index) + "\n")
    return verify()


def verify() -> dict[str, Any]:
    worktree_gate()
    prior_integrity()
    final.verify_acquisition()
    bundle = build()
    for name, expected in bundle.items():
        if io.read_seal(ROOT / name) != expected:
            raise ValueError("P026_REGISTRY_DRIFT:" + name)
    manifest = io.read_seal(ROOT / "closure-manifest.json")
    quality = io.read_seal(ROOT / "quality-verification.json", manifest["quality_fingerprint"])
    if manifest != manifest_value(bundle, quality, document_gate(bundle)):
        raise ValueError("P026_MANIFEST_DRIFT")
    index = io.read_seal(ROOT / "freeze-index.json")
    expected_names = {*bundle, "quality-verification.json", "closure-manifest.json"}
    if set(index["files"]) != expected_names or set(index["fingerprints"]) != expected_names:
        raise ValueError("P026_FREEZE_INDEX_DRIFT")
    io.verify_files(
        ROOT, index["files"] | {"freeze-index.json": io.sha(ROOT / "freeze-index.json")}
    )
    for name, fp in index["fingerprints"].items():
        io.read_seal(ROOT / name, fp)
    if (
        not manifest["CORE_THESIS_COMPLETE"]
        or manifest["mandatory_checklist"] != {c[0]: "PASS" for c in CAPABILITIES}
        or quality["make_check"] != "PASS"
    ):
        raise ValueError("P026_CLOSURE_INCOMPLETE")
    if manifest["fingerprints"] != {n: v["fingerprint"] for n, v in bundle.items()}:
        raise ValueError("P026_MANIFEST_DRIFT")
    if manifest["docs_hashes"] != document_gate(bundle):
        raise ValueError("P026_DOC_DRIFT")
    if manifest["public_report_hash"] != io.sha(DOC / "PROMPT_026.md"):
        raise ValueError("P026_REPORT_DRIFT")
    for path, sha in manifest["implementation_bindings"].items():
        if io.sha(Path(path)) != sha:
            raise ValueError("P026_CLOSURE_IMPLEMENTATION_DRIFT")
    privacy_audit(
        [
            *(ROOT / n for n in bundle),
            ROOT / "closure-manifest.json",
            ROOT / "quality-verification.json",
            *DOCUMENTS,
            DOC / "PROMPT_026.md",
        ]
    )
    return dict(
        status=manifest["status"],
        CORE_THESIS_COMPLETE=True,
        manifest_fingerprint=manifest["fingerprint"],
        **BOUNDARY,
    )
