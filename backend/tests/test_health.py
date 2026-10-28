"""Health endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "jarvis-backend"
    assert body["version"] == "0.1.0"
    assert body["environment"] == "test"


def test_health_requires_no_credentials(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/does-not-exist")

    assert response.status_code == 404
