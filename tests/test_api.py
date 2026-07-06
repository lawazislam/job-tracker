"""End-to-end API tests. Run with: pytest tests/ -v

Uses a temporary database per test session so tests never touch real data.
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    import backend.database as database
    test_db = tmp_path / "test.db"
    monkeypatch.setattr(database, "DB_PATH", test_db)
    database.init_db(test_db)
    from backend.main import app
    return TestClient(app)


def _make(client, **overrides):
    payload = {"company": "Acme", "role": "Analyst", "status": "applied",
               "date_applied": "2026-07-01"}
    payload.update(overrides)
    return client.post("/api/applications", json=payload)


def test_full_lifecycle(client):
    # create
    r = _make(client)
    assert r.status_code == 201
    app_id = r.json()["id"]

    # read: initial status is in history
    r = client.get(f"/api/applications/{app_id}")
    assert r.status_code == 200
    assert [h["new_status"] for h in r.json()["history"]] == ["applied"]

    # update
    r = client.put(f"/api/applications/{app_id}", json={"notes": "phone screen booked"})
    assert r.status_code == 200
    assert r.json()["notes"] == "phone screen booked"

    # status change writes history
    r = client.patch(f"/api/applications/{app_id}/status", json={"status": "interview"})
    assert r.status_code == 200
    trail = [(h["old_status"], h["new_status"]) for h in r.json()["history"]]
    assert trail == [(None, "applied"), ("applied", "interview")]

    # same-status change is a no-op, no duplicate history row
    r = client.patch(f"/api/applications/{app_id}/status", json={"status": "interview"})
    assert len(r.json()["history"]) == 2

    # delete cascades
    assert client.delete(f"/api/applications/{app_id}").status_code == 204
    assert client.get(f"/api/applications/{app_id}").status_code == 404


def test_validation_rejections(client):
    assert _make(client, status="partying").status_code == 422
    assert _make(client, date_applied="2026-13-45").status_code == 422
    assert _make(client, company="   ").status_code == 422
    assert client.post("/api/applications", json={"role": "no company"}).status_code == 422
    # follow-up before applied
    assert _make(client, follow_up_date="2026-06-01").status_code == 422


def test_duplicate_detection(client):
    assert _make(client).status_code == 201
    # case-insensitive duplicate blocked
    r = _make(client, company="ACME", role="analyst")
    assert r.status_code == 409
    # explicit override allowed
    r = client.post("/api/applications?allow_duplicate=true",
                    json={"company": "Acme", "role": "Analyst"})
    assert r.status_code == 201


def test_reapply_after_rejection_is_allowed(client):
    r = _make(client)
    client.patch(f"/api/applications/{r.json()['id']}/status", json={"status": "rejected"})
    assert _make(client).status_code == 201


def test_list_filters_validated(client):
    _make(client)
    assert client.get("/api/applications?status=banana").status_code == 422
    assert client.get("/api/applications?sort=evil").status_code == 422
    r = client.get("/api/applications?status=applied")
    assert r.status_code == 200 and len(r.json()) == 1


def test_404s(client):
    assert client.get("/api/applications/999").status_code == 404
    assert client.put("/api/applications/999", json={"notes": "x"}).status_code == 404
    assert client.patch("/api/applications/999/status", json={"status": "applied"}).status_code == 404
    assert client.delete("/api/applications/999").status_code == 404


def test_stats(client):
    _make(client)
    _make(client, company="Beta", role="Dev", status="interview")
    r = client.get("/api/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2
    assert body["by_status"] == {"applied": 1, "interview": 1}
