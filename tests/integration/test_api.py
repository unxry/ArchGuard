from importlib.metadata import version

from fastapi.testclient import TestClient

from archguard import __version__


def test_health_without_database(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_system_information(client: TestClient) -> None:
    response = client.get("/api/v1/system/info")
    assert response.status_code == 200
    assert response.json() == {
        "name": "ArchGuard AI",
        "version": "0.1.0",
        "status": "foundation",
        "iam_schema_version": "1.0",
        "finding_schema_version": "1.0",
    }
    assert version("archguard-ai") == __version__


def test_no_fake_analysis_endpoint(client: TestClient) -> None:
    assert client.post("/analyze").status_code == 404
    assert client.post("/api/v1/analyze").status_code == 404
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health", "/api/v1/system/info"}
