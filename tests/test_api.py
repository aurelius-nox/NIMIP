import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.app import app
def test_get_services():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/services")

    assert response.status_code == 200
    assert isinstance(response.json, list)

def test_missing_incident_events():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.get("/api/incidents/999999/events")

    assert response.status_code == 404
    assert response.json["error"] == "Incident not found"

def test_create_incident_rejects_invalid_service_id():
    app.config["TESTING"] = True
    client = app.test_client()

    response = client.post(
        "/api/incidents",
        json={"service_id": -1}
    )

    assert response.status_code == 400