import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.store import store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clear_store():
    store.clear()
    yield
    store.clear()


VALID_PAYLOAD = {
    "site_id": "SITE001",
    "trial_phase": "II",
    "submission_date": "2025-03-15",
    "status": "pending",
    "patient_count": 42,
    "notes": "Initial submission",
}


class TestHealth:
    def test_health_returns_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_health_returns_version(self):
        r = client.get("/health")
        assert "version" in r.json()


class TestCreateRecord:
    def test_create_valid_record(self):
        r = client.post("/records", json=VALID_PAYLOAD)
        assert r.status_code == 201
        body = r.json()
        assert "id" in body
        assert body["site_id"] == "SITE001"
        assert body["trial_phase"] == "II"
        assert body["patient_count"] == 42

    def test_site_id_uppercased(self):
        payload = {**VALID_PAYLOAD, "site_id": "site001"}
        r = client.post("/records", json=payload)
        assert r.status_code == 201
        assert r.json()["site_id"] == "SITE001"

    def test_invalid_status_rejected(self):
        payload = {**VALID_PAYLOAD, "status": "approved"}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_invalid_trial_phase_rejected(self):
        payload = {**VALID_PAYLOAD, "trial_phase": "V"}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_patient_count_below_minimum_rejected(self):
        payload = {**VALID_PAYLOAD, "patient_count": 0}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_patient_count_above_maximum_rejected(self):
        payload = {**VALID_PAYLOAD, "patient_count": 99999}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_non_alphanumeric_site_id_rejected(self):
        payload = {**VALID_PAYLOAD, "site_id": "SITE-001"}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_missing_required_field_rejected(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "site_id"}
        r = client.post("/records", json=payload)
        assert r.status_code == 422

    def test_notes_defaults_to_empty_string(self):
        payload = {k: v for k, v in VALID_PAYLOAD.items() if k != "notes"}
        r = client.post("/records", json=payload)
        assert r.status_code == 201
        assert r.json()["notes"] == ""

    def test_each_record_gets_unique_id(self):
        r1 = client.post("/records", json=VALID_PAYLOAD)
        r2 = client.post("/records", json=VALID_PAYLOAD)
        assert r1.json()["id"] != r2.json()["id"]


class TestGetRecord:
    def test_retrieve_created_record(self):
        created = client.post("/records", json=VALID_PAYLOAD).json()
        r = client.get(f"/records/{created['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == created["id"]

    def test_unknown_id_returns_404(self):
        r = client.get("/records/does-not-exist")
        assert r.status_code == 404
        assert r.json()["detail"] == "Record not found"

    def test_retrieved_record_matches_submitted_data(self):
        created = client.post("/records", json=VALID_PAYLOAD).json()
        fetched = client.get(f"/records/{created['id']}").json()
        assert fetched["patient_count"] == VALID_PAYLOAD["patient_count"]
        assert fetched["trial_phase"] == VALID_PAYLOAD["trial_phase"]
        assert fetched["status"] == VALID_PAYLOAD["status"]
