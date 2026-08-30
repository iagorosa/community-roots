"""Tests for `GET /health` (backend/app/api/routes/health.py).

Only the happy path is covered. Simulating a database outage safely — without
tearing down the shared `community_roots_test` connection other tests rely
on — would need either a second, separately-controllable engine or fault
injection into the driver; both add real complexity for one status code, so
that case is left out here (see the issue #5 report for the same note).
"""

from fastapi.testclient import TestClient


def test_health_returns_ok_when_database_is_reachable(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
