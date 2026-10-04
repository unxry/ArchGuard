from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from archguard.infrastructure.repository.factory import create_discovery
from archguard.repository.enums import HashStatus, RepositorySourceType
from archguard.repository.models import RepositoryInput, RepositorySnapshot
from archguard.repository.policy import RepositoryScanPolicy


def test_snapshot_roundtrip_without_materialization_paths(tmp_path: Path) -> None:
    (tmp_path / "App.java").write_text("class App {}")
    snapshot = create_discovery().execute(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    )
    assert RepositorySnapshot.model_validate_json(snapshot.model_dump_json()) == snapshot
    assert snapshot.root == "."
    assert str(tmp_path) not in snapshot.model_dump_json()
    assert snapshot.created_at.tzinfo is not None
    assert snapshot.files[0].hash_status == HashStatus.HASHED
    with pytest.raises(ValidationError, match="frozen"):
        snapshot.root = "/other"


@pytest.mark.parametrize(
    "changes",
    [
        {"repository_schema_version": "2.0"},
        {"root": "/absolute"},
        {"created_at": datetime(2026, 1, 1)},
        {"supported_for_analysis": False},
        {"manifests": ["missing.json"]},
        {"detected_languages": []},
        {"revision": "a" * 40},
        {"fingerprint": "0" * 64},
        {"snapshot_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"},
    ],
)
def test_snapshot_invariants(changes: dict[str, object], tmp_path: Path) -> None:
    (tmp_path / "App.java").write_text("class App {}")
    snapshot = create_discovery().execute(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    )
    with pytest.raises(ValidationError):
        RepositorySnapshot.model_validate(snapshot.model_dump() | changes)


def test_statistics_and_unique_order_invariants(tmp_path: Path) -> None:
    (tmp_path / "b.ts").write_text("export const b=1")
    (tmp_path / "a.ts").write_text("export const a=1")
    snapshot = create_discovery().execute(
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=str(tmp_path))
    )
    for files in [snapshot.files[::-1], snapshot.files + snapshot.files[:1]]:
        with pytest.raises(ValidationError, match="unique and sorted"):
            RepositorySnapshot.model_validate(snapshot.model_dump() | {"files": files})
    data = snapshot.model_dump(mode="json")
    data["statistics"]["total_files"] = 100
    with pytest.raises(ValidationError, match="statistics"):
        RepositorySnapshot.model_validate(data)


@pytest.mark.parametrize(
    "field",
    [
        "max_files",
        "max_entries",
        "max_source_file_bytes",
        "max_single_file_bytes",
        "max_total_uncompressed_bytes",
        "git_timeout_seconds",
    ],
)
def test_policy_rejects_invalid_limits(field: str) -> None:
    with pytest.raises(ValidationError):
        RepositoryScanPolicy.model_validate({field: 0})


@pytest.mark.parametrize("ref", ["--upload-pack=evil", "name;command", "../bad\x00ref"])
def test_input_ref_rejects_option_and_command_injection(ref: str) -> None:
    with pytest.raises(ValidationError):
        RepositoryInput(
            source_type=RepositorySourceType.GIT, location="https://example.invalid/repo", ref=ref
        )


def test_local_input_cannot_select_git_ref() -> None:
    with pytest.raises(ValidationError):
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location=".", ref="main")


def test_input_rejects_nul_location() -> None:
    with pytest.raises(ValidationError):
        RepositoryInput(source_type=RepositorySourceType.LOCAL, location="bad\x00path")
