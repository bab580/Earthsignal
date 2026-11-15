from fastapi.testclient import TestClient

from backend.app import main as app_module


def configure_sensor_app(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SENSOR_DB", tmp_path / "sensor-test.sqlite3")
    monkeypatch.setattr(app_module, "SENSOR_DEVICE_TOKEN", "test-device-token")
    monkeypatch.setattr(app_module, "ALLOW_UNAUTHENTICATED_SENSOR_INGESTION", False)
    return TestClient(app_module.app)


def test_sensor_reading_round_trip(tmp_path, monkeypatch):
    with configure_sensor_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/sensors/readings",
            headers={"X-Device-Token": "test-device-token"},
            json={
                "device_id": "soilsense-01",
                "raw": 2300,
                "moisture": 42.5,
                "status": "MOIST",
                "recorded_at": "2026-11-12T18:35:00Z",
            },
        )
        assert response.status_code == 200
        assert response.json()["accepted"] is True

        latest = client.get("/api/sensors/latest", params={"device_id": "soilsense-01"})
        assert latest.status_code == 200
        assert latest.json()["reading"]["raw"] == 2300
        assert latest.json()["reading"]["moisture"] == 42.5
        assert latest.json()["reading"]["status"] == "MOIST"

        recent = client.get(
            "/api/sensors/recent",
            params={"device_id": "soilsense-01", "limit": 1},
        )
        assert recent.status_code == 200
        assert recent.json()["count"] == 1


def test_sensor_ingestion_requires_configured_token(tmp_path, monkeypatch):
    with configure_sensor_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/sensors/readings",
            json={"device_id": "soilsense-01", "raw": 2300, "moisture": 42.5, "status": "MOIST"},
        )
        assert response.status_code == 401
        response = client.post(
            "/api/sensors/readings",
            headers={"X-Device-Token": "wrong-token"},
            json={"device_id": "soilsense-01", "raw": 2300, "moisture": 42.5, "status": "MOIST"},
        )
        assert response.status_code == 401


def test_unauthenticated_ingestion_requires_explicit_demo_setting(tmp_path, monkeypatch):
    with configure_sensor_app(tmp_path, monkeypatch) as client:
        monkeypatch.setattr(app_module, "SENSOR_DEVICE_TOKEN", "")
        response = client.post(
            "/api/sensors/readings",
            json={"device_id": "soilsense-01", "raw": 2300, "moisture": 42.5, "status": "MOIST"},
        )
        assert response.status_code == 503

        monkeypatch.setattr(app_module, "ALLOW_UNAUTHENTICATED_SENSOR_INGESTION", True)
        response = client.post(
            "/api/sensors/readings",
            json={"device_id": "soilsense-01", "raw": 2300, "moisture": 42.5, "status": "MOIST"},
        )
        assert response.status_code == 200


def test_sensor_reading_rejects_out_of_range_or_unknown_values(tmp_path, monkeypatch):
    with configure_sensor_app(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/sensors/readings",
            headers={"X-Device-Token": "test-device-token"},
            json={"device_id": "soilsense-01", "raw": 5000, "moisture": 42.5, "status": "MOIST"},
        )
        assert response.status_code == 422

        response = client.post(
            "/api/sensors/readings",
            headers={"X-Device-Token": "test-device-token"},
            json={"device_id": "soilsense-01", "raw": 2300, "moisture": 42.5, "status": "UNKNOWN"},
        )
        assert response.status_code == 422


def test_sensor_latest_is_empty_for_unknown_device(tmp_path, monkeypatch):
    with configure_sensor_app(tmp_path, monkeypatch) as client:
        response = client.get("/api/sensors/latest", params={"device_id": "unknown"})
        assert response.status_code == 200
        assert response.json()["reading"] is None
