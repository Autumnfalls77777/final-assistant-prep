"""HTTP memory endpoint tests."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _create_memory(client: TestClient) -> dict[str, object]:
    response = client.post(
        "/memory",
        json={
            "kind": "personal",
            "content": "My preferred editor is VS Code.",
            "source": "user",
            "confidence": 0.9,
            "project": "jarvis",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_list_and_get_memory(client: TestClient) -> None:
    created = _create_memory(client)
    memory = created["memory"]
    assert created["deduplicated"] is False
    assert memory["content"] == "My preferred editor is VS Code."

    response = client.get("/memory")
    assert response.status_code == 200
    assert len(response.json()) == 1

    response = client.get(f"/memory/{memory['id']}")
    assert response.status_code == 200
    assert response.json()["id"] == memory["id"]


def test_memory_search_and_stats(client: TestClient) -> None:
    _create_memory(client)

    response = client.get("/memory/search", params={"q": "preferred editor"})
    assert response.status_code == 200
    results = response.json()
    assert results
    assert results[0]["content"] == "My preferred editor is VS Code."

    response = client.get("/memory/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_active"] == 1
    assert stats["by_kind"]["personal"] == 1


def test_memory_update_and_delete(client: TestClient) -> None:
    created = _create_memory(client)
    memory_id = created["memory"]["id"]

    response = client.patch(
        f"/memory/{memory_id}",
        json={"content": "My preferred editor is Neovim.", "confidence": 0.99},
    )
    assert response.status_code == 200
    assert response.json()["content"] == "My preferred editor is Neovim."
    assert response.json()["confidence"] == 0.99

    response = client.delete(f"/memory/{memory_id}")
    assert response.status_code == 204
    assert client.get(f"/memory/{memory_id}").status_code == 404


def test_duplicate_memory_is_deduplicated(client: TestClient) -> None:
    first = _create_memory(client)
    second = _create_memory(client)

    assert second["deduplicated"] is True
    assert second["memory"]["id"] == first["memory"]["id"]
    assert len(client.get("/memory").json()) == 1


def test_memory_events_are_available(client: TestClient) -> None:
    created = _create_memory(client)
    response = client.get("/memory/events")

    assert response.status_code == 200
    events = response.json()
    assert events
    assert events[0]["memory_id"] == created["memory"]["id"]
    assert events[0]["action"] == "created"


def test_memory_export_contains_records(client: TestClient) -> None:
    _create_memory(client)

    response = client.get("/memory/export")

    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert len(body["memories"]) == 1
    assert body["memories"][0]["content"] == "My preferred editor is VS Code."


def test_memory_validation_and_not_found(client: TestClient) -> None:
    assert client.post("/memory", json={"kind": "personal", "content": "   "}).status_code == 422
    assert client.get("/memory/missing").status_code == 404
    assert client.patch("/memory/missing", json={"content": "x"}).status_code == 404
    assert client.delete("/memory/missing").status_code == 404
    assert client.get("/memory/search", params={"q": ""}).status_code == 422
