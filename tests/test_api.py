"""
tests/test_api.py — Tests for the FastAPI API routes.
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_storage):
    from api.main import app
    return TestClient(app)


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "AI Scribe" in r.json()["service"]


def test_create_encounter(client):
    r = client.post("/encounters", json={
        "provider_id": "dr_test",
        "patient_id": "p123",
        "visit_type": "follow_up",
        "mode": "dictation",
    })
    assert r.status_code == 201
    data = r.json()
    assert "encounter_id" in data
    assert data["status"] == "pending"


def test_list_encounters(client):
    # Create one
    client.post("/encounters", json={"provider_id": "dr_test", "mode": "dictation"})
    r = client.get("/encounters")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_encounter_not_found(client):
    r = client.get("/encounters/nonexistent")
    assert r.status_code == 404


def test_encounter_status(client):
    r = client.post("/encounters", json={"provider_id": "dr_test"})
    eid = r.json()["encounter_id"]
    r2 = client.get(f"/encounters/{eid}/status")
    assert r2.status_code == 200
    assert r2.json()["status"] == "pending"


def test_upload_no_encounter(client):
    r = client.post("/encounters/fake/upload", files={"audio": ("test.mp3", b"\x00" * 2048, "audio/mpeg")})
    assert r.status_code == 404


def test_upload_empty_audio(client):
    r = client.post("/encounters", json={"provider_id": "dr_test"})
    eid = r.json()["encounter_id"]
    r2 = client.post(f"/encounters/{eid}/upload", files={"audio": ("test.mp3", b"\x00" * 100, "audio/mpeg")})
    assert r2.status_code == 400  # Too small


def test_get_note_not_available(client):
    r = client.post("/encounters", json={"provider_id": "dr_test"})
    eid = r.json()["encounter_id"]
    r2 = client.get(f"/encounters/{eid}/note")
    assert r2.status_code == 404


def test_providers_crud(client):
    # Create
    r = client.post("/providers", json={
        "provider_id": "dr_smith",
        "name": "Dr. Smith",
        "specialty": "orthopedic",
    })
    assert r.status_code == 201

    # List
    r = client.get("/providers")
    assert r.status_code == 200

    # Get
    r = client.get("/providers/dr_smith")
    assert r.status_code == 200

    # Delete
    r = client.delete("/providers/dr_smith")
    assert r.status_code == 204


def test_provider_duplicate(client):
    client.post("/providers", json={"provider_id": "dr_dup", "name": "A"})
    r = client.post("/providers", json={"provider_id": "dr_dup", "name": "B"})
    assert r.status_code == 409


def test_mt_queue_empty(client):
    r = client.get("/mt/queue")
    assert r.status_code == 200
    assert r.json() == []


def test_note_approve_no_encounter(client):
    r = client.post("/notes/fake/approve", json={"approved_by": "doc"})
    assert r.status_code == 404
