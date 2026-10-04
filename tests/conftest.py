import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from archguard.api.app import create_app
from archguard.core.findings.model import Finding
from archguard.iam.model import ArchitectureModel
from archguard.infrastructure.settings import Settings

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in tuple(os.environ):
        if key.startswith("ARCHGUARD_"):
            monkeypatch.delenv(key)


@pytest.fixture
def synthetic_iam() -> ArchitectureModel:
    return ArchitectureModel.model_validate_json((FIXTURES / "synthetic_iam.json").read_text())


@pytest.fixture
def synthetic_arch_finding() -> Finding:
    return Finding.model_validate_json((FIXTURES / "synthetic_arch_finding.json").read_text())


@pytest.fixture
def synthetic_sec_finding(synthetic_arch_finding: Finding) -> Finding:
    data = synthetic_arch_finding.model_dump(mode="json")
    data.update(
        namespace="SEC",
        rule_id="SEC001",
        category="secrets",
        title="Synthetic future security contract fixture",
        detector={"source": "SECURITY_STATIC", "name": "synthetic-fixture", "version": "test"},
    )
    for evidence in data["evidence"]:
        evidence.update(namespace="SEC", type="SECRET_PATTERN")
    return Finding.model_validate(data)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(_env_file=None))) as test_client:
        yield test_client
