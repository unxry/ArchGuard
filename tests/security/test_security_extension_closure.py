import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from archguard.benchmark.oss.models import canonical
from archguard.infrastructure import security_extension_closure as c
from archguard.infrastructure import unified_human_review as io


@pytest.fixture(scope="module")
def bundle():
    return c.build()


@pytest.fixture
def quality():
    return c.seal(
        dict(
            status="PASS",
            implementation_commit=c.BASE,
            make_check=dict(returncode=0, passed=1, skipped=0, coverage_percent=81, warnings=[]),
            **dict.fromkeys(
                (
                    "Ruff",
                    "format",
                    "strict_mypy",
                    "privacy",
                    "secret_audit",
                    "determinism",
                    "diff_check",
                ),
                "PASS",
            ),
        )
    )


@pytest.mark.parametrize("stage", [f"P{i:03d}" for i in range(27, 36)])
def test_frozen_stage_pin_and_ancestry(stage, bundle):
    entry = bundle["security-history-receipt.json"]["stages"][stage]
    assert io.read_seal(Path(entry["index"]), entry["index_fingerprint"])
    assert c.git("merge-base", entry["closure_commit"], "HEAD") == entry["closure_commit"]
    with pytest.raises(io.ReviewBlocked):
        io.read_seal(Path(entry["index"]), "0" * 64)


def test_architecture_and_research_separation(bundle):
    h = bundle["security-history-receipt.json"]
    assert (
        h["architecture"]["scientific_registry"]
        == "53420d0aa167ebb99814adb498f3b84597b096f73fe1f77c5c467dc7882a8db1"
    )
    assert h["architecture"]["CORE_THESIS_COMPLETE"] is True
    assert h["import_firewall"] == "PASS"
    assert bundle["security-scientific-claims.json"]["architecture_RQ_rewrite"] is False
    assert set(bundle["security-scientific-claims.json"]["security_questions"]) == {
        f"Q_SEC_{x}" for x in "ABCDE"
    }


def test_historical_v2_identity(bundle):
    pins = bundle["security-history-receipt.json"]["stages"]["P029"]["scientific_pins"]
    assert (
        pins["summary-protocol.json"]
        == "d7df5af8fa93344b62c2fc54927a15a2b5b49aef0ffb358643556422f24d0388"
    )
    assert (
        pins["security-analysis-v2.json"]
        == "c74ab979768cd597ffaa91567a7e6424a1ec4e28938a32889f8fd4572c35e2c7"
    )
    assert bundle["security-history-receipt.json"]["P030_inventory"]["expected"] == 927


@pytest.mark.parametrize("number", range(1, 11))
def test_exact_catalog_and_capability(number, bundle):
    rule = f"SEC{number:03d}"
    catalog = bundle["security-rule-catalog.json"]
    assert catalog["rules"][number - 1] == dict(rule_id=rule, name=c.NAMES[number - 1])
    cells = [
        r for r in bundle["security-final-capability-matrix.json"]["cells"] if r["rule"] == rule
    ]
    assert len(cells) == 2
    for cell in cells:
        expected = "IMPLEMENTED_V3" if number == 1 else "PARTIAL_V3"
        if (number, cell["language"]) == (5, "TYPESCRIPT"):
            expected = "CONTRACT_ONLY"
        assert cell["capability_status"] == expected
        assert all(
            k in cell
            for k in (
                "positive_path_status",
                "negative_completeness_status",
                "interprocedural_scope",
                "known_limitation",
            )
        )
        assert not {"precision", "recall", "TP", "FP"}.intersection(cell)


def test_registry_complete_and_serialization_deterministic(bundle, monkeypatch):
    registry = bundle["security-scientific-registry.json"]
    assert len(registry["stages"]) == 9
    assert set(registry["artifacts"]) == set(bundle) - {"security-scientific-registry.json"}
    monkeypatch.setattr(c, "historical_audit", lambda: bundle["security-history-receipt.json"])
    assert canonical(bundle) == canonical(c.build())
    assert canonical(bundle) == canonical(dict(reversed(list(bundle.items()))))
    for artifact in bundle.values():
        assert artifact == c.seal({k: v for k, v in artifact.items() if k != "fingerprint"})


def test_final_and_experiment_arithmetic(bundle):
    c.metric_audit()
    s = bundle["security-experiment-summary.json"]
    m = s["P035_V3_FINAL"]
    assert m["truth_distribution"] == dict(POSITIVE=85, NEGATIVE=106, UNCERTAIN=9, OUT_OF_SCOPE=0)
    assert m["binary_eligible"] == 191
    assert sum(m["outcomes"].values()) == m["N"] == 200
    assert m["positive_nondefinitive"] == 47
    assert m["negative_nondefinitive"] == 103
    assert m["FP"] == 3 and m["TN"] == 0 and m["outcomes"]["DEFINITIVE_NEGATIVE"] == 0
    assert sum(r["TP"] for r in s["rules"].values()) == 38
    assert sum(r["FP"] for r in s["rules"].values()) == 3
    assert s["rules"]["SEC001"]["FP"] == 3
    assert s["P029_V2_DEV"]["TP"] == 7 and s["P033_V3_DEV"]["TP"] == 21
    assert s["DEV_USED_FOR_REFINEMENT"] is True
    assert s["P029_FINAL_EFFECTIVENESS"] == "NOT_EVALUATED"
    g = s["generalization"]
    for key, delta in g["deltas_percentage_points"].items():
        assert delta == pytest.approx(100 * (m[key] - g["DEV"][key]))


@pytest.mark.parametrize(
    "text",
    [
        "Recall=1.0 and F1=0.9620",
        "100% recall",
        "high accuracy",
        "detects vulnerabilities accurately",
        "fully supports SEC001–SEC010",
        "zero false negatives",
    ],
)
def test_overclaim_and_conditional_wording_guard(text):
    with pytest.raises(ValueError, match="OVERCLAIM"):
        c.wording_guard(text)
    c.wording_guard(c.INTERPRETATION)


@pytest.mark.parametrize(
    "relative",
    [
        "security-human-review-v1/private/truth/FINAL/truth.json",
        "security-human-review-v1/private/truth/DEV/truth.json",
        "security-human-review-v1/private/response.json",
        "security-human-review-v1/private/adjudication.json",
        "security-benchmark-v1/private/coordinator/intent.json",
        "security-benchmark-v1/private/prediction/FINAL/sources/input.java",
        "security-dev-baseline-v1/private/joined.json",
        "security-dev-refinement-v3/private/iteration/result.json",
        "security-final-prediction-v1/private/output/registry.json",
        "security-final-evaluation-v1/private/truth-source.json",
        "security-final-evaluation-v1/private/joined-final.json",
        "security-final-evaluation-v1/private/error-inventory.json",
    ],
)
def test_protected_open_denied_without_read(relative):
    root = Path.cwd()
    assert c.guard_reason("open", (str(root / "experiments/security" / relative), "r", 0), root)


def test_offline_credentials_and_frozen_write_guard():
    root = Path.cwd()
    assert c.guard_reason("socket.connect", (), root)
    assert c.guard_reason("open", (str(root / ".env"), "r", 0), root)
    assert c.guard_reason(
        "open",
        (
            str(
                root
                / "experiments/security/security-final-evaluation-v1/public"
                / "security-final-metrics.json"
            ),
            "w",
            1,
        ),
        root,
    )
    assert (
        c.guard_reason(
            "open",
            (
                str(root / "experiments/security/security-benchmark-v1/private/freeze-index.json"),
                "r",
                0,
            ),
            root,
        )
        is None
    )
    assert (
        c.guard_reason("open", (str(root / c.PUBLIC / "security-limitations.json"), "r", 0), root)
        is None
    )
    with pytest.raises(PermissionError, match="PROCESS_DENIED"):
        c.access_guard("subprocess.Popen", ("python",))


def test_analyzer_calls_blocked():
    frame = SimpleNamespace(
        f_code=SimpleNamespace(co_name="analyze"),
        f_globals={"__name__": "archguard.security.analyzer_v3"},
    )
    with pytest.raises(PermissionError, match="ANALYZER_EXECUTION_DENIED"):
        c.deny_analyzer(frame, "call", None)


def test_profiler_cleanup(monkeypatch):
    monkeypatch.setattr(c.sys, "addaudithook", lambda f: None)
    monkeypatch.setattr(c.sys, "argv", ["closure", "invalid"])
    with pytest.raises(ValueError, match="UNKNOWN_ACTION"):
        c.main()
    assert sys.getprofile() is None


def test_public_privacy_and_private_git_exclusion(bundle):
    c.privacy(list(c.PUBLIC.glob("*.json")))
    assert not c.git("ls-files", "--", "experiments/security/*/private/*")
    ignored = c.git("check-ignore", str(c.ROOT / "private/quality/untracked.log"))
    assert ignored.endswith("untracked.log")
    receipt = bundle["security-privacy-custody-receipt.json"]
    assert all(receipt[k] == 0 for k in c.ZERO)


@pytest.mark.parametrize("value", ["sc-" + "a" * 24, "/Us" + "ers/person/file", "sk-" + "a" * 20])
def test_private_or_secret_publication_rejected(value, tmp_path):
    p = tmp_path / "public.txt"
    p.write_text(value)
    with pytest.raises(ValueError, match="PRIVACY_PUBLICATION_VIOLATION"):
        c.privacy([p])


def test_reproducibility_and_limitations(bundle):
    r = bundle["security-reproducibility-manifest.json"]
    assert len(r["levels"]) == 3
    assert "replication" in r["levels"]["LEVEL_3_EXPERIMENT_REEXECUTION"]
    assert "Not performed by P036" in r["levels"]["LEVEL_2_AUTHORIZED_SCIENTIFIC_REPLAY"]
    assert len(bundle["security-limitations.json"]["limitations"]) == 22
    assert "47" in bundle["security-limitations.json"]["interpretation"]


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "Ruff",
        "format",
        "strict_mypy",
        "privacy",
        "secret_audit",
        "determinism",
        "diff_check",
        "make_check",
    ],
)
def test_completion_requires_quality(field, quality, bundle):
    broken = copy.deepcopy(quality)
    broken.pop(field)
    with pytest.raises(ValueError, match="QUALITY_INCOMPLETE"):
        c.completion(broken, bundle)


def test_closure_fingerprint_determinism_and_scope(quality, bundle):
    first, second = c.completion(quality, bundle), c.completion(quality, bundle)
    assert canonical(first) == canonical(second)
    assert first["SECURITY_EXTENSION_COMPLETE"] == "YES"
    assert first["SECURITY_PRODUCTION_READINESS"] == "NOT_CLAIMED"
    assert first["UI_UX_STATUS"] == "OUT_OF_SCOPE_FOR_P036"
    assert all(first[k] == 0 for k in c.ZERO)
    assert "timestamp" not in json.dumps(first)


def test_freeze_index_binds_outputs_and_closes_writer(tmp_path, quality, bundle, monkeypatch):
    inputs = io.read_seal(c.PUBLIC / "security-closure-inputs.json")
    document = tmp_path / "report.md"
    document.write_text(c.INTERPRETATION)
    monkeypatch.setattr(c, "PUBLIC", tmp_path)
    monkeypatch.setattr(c, "DOC", document)
    monkeypatch.setattr(c, "SOURCES", ())
    monkeypatch.setattr(c, "verify", lambda: {"status": "PASS"})
    for name, value in bundle.items():
        c.write(tmp_path / name, value)
    c.write(tmp_path / "security-closure-inputs.json", inputs)
    c.write(tmp_path / "quality-verification.json", quality)
    frozen = c.freeze()
    index = io.read_seal(tmp_path / "freeze-index.json")
    assert index["fingerprint"] == frozen["fingerprint"]
    assert index["SECURITY_EXTENSION_COMPLETE"] == "YES"
    assert len(index["fingerprints"]) == 11
    for name, expected in index["files"].items():
        assert io.sha(tmp_path / name) == expected
    assert index["documents"][str(document)] == io.sha(document)
    with pytest.raises(ValueError, match="ALREADY_FROZEN"):
        c.freeze()
