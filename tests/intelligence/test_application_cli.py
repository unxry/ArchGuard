import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from archguard.application.analyze_architecture_semantics import AnalyzeArchitectureSemantics
from archguard.architecture.intelligence.models import (
    AIAnalysisConfig,
    TargetSelectionConfig,
)
from archguard.cli import main
from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import RepositorySourceType
from archguard.repository.models import RepositoryInput
from tests.helpers.scripted_llm import ScriptedLLMProvider, assessment
from tests.intelligence.conftest import building

ROOT = Path(__file__).parents[1]
FIXTURES = ROOT / "fixtures/discovery"


def test_application_builds_iam_graph_discovery_once_for_multiple_targets(chain):
    root = chain[2]
    application = AnalyzeArchitectureSemantics(building())
    config = AIAnalysisConfig(targets=TargetSelectionConfig(explicit_targets=("A", "B", "C")))
    with (
        create_discovery().open(
            RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(root))
        ) as repo,
        patch.object(application.building, "execute", wraps=application.building.execute) as iam,
        patch.object(application.graph, "analyze", wraps=application.graph.analyze) as graph,
        patch.object(
            application.discovery, "analyze", wraps=application.discovery.analyze
        ) as discovery,
    ):
        result = application.execute(repo.snapshot, repo.workspace, config, ScriptedLLMProvider())
    assert result.calls == 3 and iam.call_count == graph.call_count == discovery.call_count == 1


@pytest.mark.parametrize(
    "fixture,target",
    [
        ("java-layered", "UserController"),
        ("typescript-layered", "UserController"),
        ("conflict", "PaymentController"),
    ],
)
def test_real_language_pipeline_dry_run(fixture, target, capsys):
    assert (
        main(["ai", "analyze", str(FIXTURES / fixture), "--target", target, "--dry-run", "--json"])
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "DRY_RUN" and result["calls"] == 0
    assert result["manifests"] and result["request_metadata"]
    assert "PRIVATE_DECORATOR_ARGUMENT" not in json.dumps(result)


def test_offline_supported_not_supported_insufficient_pipeline(chain):
    provider = ScriptedLLMProvider(
        [
            lambda r: assessment(r, "SUPPORTED"),
            lambda r: assessment(r, "NOT_SUPPORTED"),
            lambda r: assessment(r, "INSUFFICIENT_CONTEXT"),
        ]
    )
    with create_discovery().open(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(chain[2]))
    ) as repo:
        result = AnalyzeArchitectureSemantics(building()).execute(
            repo.snapshot,
            repo.workspace,
            AIAnalysisConfig(targets=TargetSelectionConfig(explicit_targets=("A", "B", "C"))),
            provider,
        )
    assert {c.assessment.decision for c in result.candidates} == {
        "SUPPORTED",
        "NOT_SUPPORTED",
        "INSUFFICIENT_CONTEXT",
    }


def test_cli_context_source_is_explicit_and_output_canonical(chain, tmp_path, capsys):
    path = tmp_path / "manifest.json"
    arguments = ["ai", "context", str(chain[2]), "--node", "B", "--json", "--output", str(path)]
    assert main(arguments) == 0
    first = capsys.readouterr()
    assert first.out == path.read_text() and "PRIVATE_SOURCE_MARKER" not in first.out + first.err
    assert main(arguments) == 0 and capsys.readouterr().out == first.out
    assert main([*arguments, "--show-source"]) == 0
    source = capsys.readouterr()
    assert "PRIVATE_SOURCE_MARKER" in source.out and "PRIVATE_SOURCE_MARKER" not in source.err


@pytest.mark.parametrize("dry_run", [True, False])
def test_configured_credentials_never_trigger_implicit_network(chain, monkeypatch, capsys, dry_run):
    monkeypatch.setenv("ARCHGUARD_AI_PROVIDER", "openai")
    monkeypatch.setenv("ARCHGUARD_AI_MODEL", "offline-placeholder-model")
    monkeypatch.setenv("ARCHGUARD_AI_API_KEY", "synthetic-placeholder-key")
    arguments = ["ai", "analyze", str(chain[2]), "--target", "B", "--json"]
    if dry_run:
        arguments.append("--dry-run")
    assert main(arguments) == (0 if dry_run else 3)
    result = json.loads(capsys.readouterr().out)
    assert result["calls"] == 0
    assert result["status"] == ("DRY_RUN" if dry_run else "UNAVAILABLE")
    assert "synthetic-placeholder-key" not in json.dumps(result)


@pytest.mark.parametrize(
    "data", [b"{} trailing", b"x" * 131073, b'{"unexpected":true}', b'{"context":{"max_nodes":0}}']
)
def test_cli_rejects_invalid_configuration(chain, tmp_path, capsys, data):
    path = tmp_path / "config.json"
    path.write_bytes(data)
    assert main(["ai", "analyze", str(chain[2]), "--config", str(path), "--dry-run", "--json"]) == 2
    assert "INVALID_AI_CONFIGURATION" in capsys.readouterr().err


def test_config_cannot_authorize_remote_upload_without_cli_opt_in(
    chain, tmp_path, monkeypatch, capsys
):
    path = tmp_path / "config.json"
    path.write_text('{"allow_remote_source":true,"targets":{"explicit_targets":["B"]}}')
    monkeypatch.setenv("ARCHGUARD_AI_PROVIDER", "openai")
    monkeypatch.setenv("ARCHGUARD_AI_MODEL", "placeholder")
    monkeypatch.setenv("ARCHGUARD_AI_API_KEY", "placeholder")
    assert main(["ai", "analyze", str(chain[2]), "--config", str(path), "--json"]) == 3
    assert json.loads(capsys.readouterr().out)["calls"] == 0


def test_cli_target_and_missing_provider_are_truthful(chain, capsys):
    assert main(["ai", "context", str(chain[2]), "--node", "nonexistent", "--json"]) == 2
    assert "INVALID_AI_TARGET" in capsys.readouterr().err
    assert (
        main(["ai", "analyze", str(chain[2]), "--target", "B", "--provider", "openai", "--json"])
        == 3
    )
    result = json.loads(capsys.readouterr().out)
    assert any(d["code"] == "AI_PROVIDER_CONFIGURATION_REQUIRED" for d in result["diagnostics"])


def test_unrelated_physical_source_change_does_not_change_selected_fingerprint(tmp_path, capsys):
    shutil.copytree(FIXTURES / "java-layered", tmp_path / "repo")
    root = tmp_path / "repo"
    arguments = ["ai", "context", str(root), "--node", "UserController", "--json"]
    assert main(arguments) == 0
    first = json.loads(capsys.readouterr().out)
    unrelated = root / "src/payments/clients/ExternalClient.java"
    unrelated.write_text(unrelated.read_text() + "// unrelated source change\n")
    assert main(arguments) == 0
    second = json.loads(capsys.readouterr().out)
    assert first["context_fingerprint"] == second["context_fingerprint"]


def test_explicit_remote_cli_flag_reaches_real_adapter_with_stubbed_transport(
    chain, monkeypatch, capsys
):
    calls = []

    def transport(data, key, timeout):
        wire = json.loads(data)
        task = json.loads(wire["input"][1]["content"])
        calls.append(task)
        response = {
            "candidate_rule_id": task["task"]["candidate_rule_id"],
            "decision": "INSUFFICIENT_CONTEXT",
            "subject_node_ids": [task["task"]["subject_node_id"]],
            "short_reason": "Offline wire verification.",
            "evidence_refs": [],
            "suggested_role": None,
            "suggested_layer": None,
            "assumptions": [],
            "limitations": [],
            "recommendation": None,
        }
        return json.dumps(
            {
                "id": "resp_offline",
                "model": "offline-model",
                "status": "completed",
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(response)}],
                    }
                ],
            }
        ).encode()

    monkeypatch.setattr("archguard.infrastructure.llm_provider._post", transport)
    monkeypatch.setenv("ARCHGUARD_AI_API_KEY", "synthetic-placeholder")
    assert (
        main(
            [
                "ai",
                "analyze",
                str(chain[2]),
                "--target",
                "B",
                "--provider",
                "openai",
                "--model",
                "offline-model",
                "--allow-remote-ai",
                "--json",
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert len(calls) == result["calls"] == 1
    assert result["candidates"][0]["provider_id"] == "openai"
