from datetime import datetime, timezone

from fastapi.testclient import TestClient

from backend.app import main as app_module


def experiment_client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SENSOR_DB", tmp_path / "experiments.sqlite3")
    monkeypatch.setattr(app_module, "SENSOR_DEVICE_TOKEN", "test-device-token")
    monkeypatch.setattr(app_module, "ALLOW_UNAUTHENTICATED_SENSOR_INGESTION", False)
    return TestClient(app_module.app)


def create_experiment(client):
    response = client.post(
        "/api/experiments",
        json={
            "name": "Lettuce water-use pilot",
            "crop": "Lettuce",
            "variety": "Test variety",
            "location": "Indoor chamber",
            "start_date": "2026-11-01",
            "research_objective": "Measure growth and supplied water.",
            "groups": [
                {"name": "Control", "treatment": "Adequate water"},
                {"name": "Reduced water", "treatment": "Reduced water supply"},
            ],
        },
    )
    assert response.status_code == 201
    return response.json()


def test_experiment_records_and_group_efficiency_use_measured_data(tmp_path, monkeypatch):
    with experiment_client(tmp_path, monkeypatch) as client:
        experiment = create_experiment(client)
        experiment_id = experiment["id"]
        control, reduced = experiment["groups"]

        reading = client.post(
            f"/api/experiments/{experiment_id}/readings",
            json={
                "group_id": control["id"],
                "source_type": "manual",
                "source_id": "daily-log",
                "recorded_at": "2026-11-01T08:00:00Z",
                "air_temperature_c": 24.5,
                "water_added_l": 1.0,
            },
        )
        assert reading.status_code == 201

        observation_a = client.post(
            f"/api/experiments/{experiment_id}/observations",
            json={
                "group_id": control["id"],
                "plant_id": "plant-01",
                "observed_at": "2026-11-01T08:00:00Z",
                "height_cm": 3,
            },
        )
        observation_b = client.post(
            f"/api/experiments/{experiment_id}/observations",
            json={
                "group_id": control["id"],
                "plant_id": "plant-01",
                "observed_at": "2026-11-11T08:00:00Z",
                "height_cm": 5,
                "leaf_count": 4,
            },
        )
        assert observation_a.status_code == observation_b.status_code == 201

        harvest = client.post(
            f"/api/experiments/{experiment_id}/harvests",
            json={
                "group_id": control["id"],
                "harvested_at": "2026-11-11T08:00:00Z",
                "plant_count": 2,
                "fresh_mass_g": 20,
                "dry_mass_g": 5,
            },
        )
        assert harvest.status_code == 201

        habitat = client.post(
            "/api/habitat/readings",
            json={
                "device_id": "chamber-01",
                "experiment_id": experiment_id,
                "group_id": control["id"],
                "source_type": "manual",
                "water_added_l": 1.5,
                "light_lux": 1200,
            },
        )
        assert habitat.status_code == 201

        analysis = client.get(f"/api/analysis/experiments/{experiment_id}")
        assert analysis.status_code == 200
        control_result = analysis.json()["groups"][0]
        assert control_result["measurements"]["water_added_l"] == 2.5
        assert control_result["measurements"]["fresh_water_use_efficiency_g_per_l"] == 8.0
        assert control_result["measurements"]["dry_water_use_efficiency_g_per_l"] == 2.0
        assert control_result["growth"]["mean_height_change_cm_per_day"] == 0.2
        assert analysis.json()["groups"][1]["measurements"]["fresh_water_use_efficiency_g_per_l"] is None


def test_experiment_and_readings_reject_invalid_or_unattributed_measurements(tmp_path, monkeypatch):
    with experiment_client(tmp_path, monkeypatch) as client:
        invalid_experiment = client.post(
            "/api/experiments",
            json={
                "name": "Invalid dates",
                "crop": "Lettuce",
                "location": "Chamber",
                "start_date": "2026-11-10",
                "end_date": "2026-11-01",
                "research_objective": "Test",
                "groups": [{"name": "Control", "treatment": "Watered"}],
            },
        )
        assert invalid_experiment.status_code == 422

        experiment = create_experiment(client)
        experiment_id = experiment["id"]
        response = client.post(
            f"/api/experiments/{experiment_id}/readings",
            json={
                "group_id": experiment["groups"][0]["id"],
                "source_id": "empty-log",
                "recorded_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        assert response.status_code == 422

        response = client.post(
            f"/api/experiments/{experiment_id}/readings",
            json={
                "group_id": experiment["groups"][1]["id"] + 100,
                "source_id": "wrong-group",
                "water_added_l": 1,
            },
        )
        assert response.status_code == 422


def test_habitat_device_posts_require_token_and_preserve_missing_values(tmp_path, monkeypatch):
    with experiment_client(tmp_path, monkeypatch) as client:
        experiment = create_experiment(client)
        group_id = experiment["groups"][0]["id"]
        experiment_id = experiment["id"]
        experiment_payload = {
            "group_id": group_id,
            "source_type": "esp32",
            "source_id": "chamber-esp32",
            "medium_moisture_pct": 45,
        }
        assert client.post(
            f"/api/experiments/{experiment_id}/readings",
            json=experiment_payload,
        ).status_code == 401
        assert client.post(
            f"/api/experiments/{experiment_id}/readings",
            headers={"X-Device-Token": "test-device-token"},
            json=experiment_payload,
        ).status_code == 201

        payload = {
            "device_id": "chamber-02",
            "source_type": "esp32",
            "air_temperature_c": 23.5,
        }
        assert client.post("/api/habitat/readings", json=payload).status_code == 401
        response = client.post(
            "/api/habitat/readings",
            headers={"X-Device-Token": "test-device-token"},
            json=payload,
        )
        assert response.status_code == 201

        latest = client.get("/api/habitat/latest", params={"device_id": "chamber-02"})
        assert latest.status_code == 200
        assert latest.json()["reading"]["air_temperature_c"] == 23.5
        assert latest.json()["reading"]["relative_humidity_pct"] is None
        assert latest.json()["device"]["sensor_types"] == ["air_temperature_c"]


def test_crop_nutrition_requires_references_and_unique_names(tmp_path, monkeypatch):
    with experiment_client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/crops",
            json={"name": "Lettuce", "nutrition": {"protein_g_per_100g": 1.2}},
        )
        assert response.status_code == 422

        profile = {
            "name": "Lettuce",
            "nutrition": {"protein_g_per_100g": 1.2},
            "references": [{"title": "Nutrition source", "url": "https://example.test/nutrition"}],
        }
        response = client.post("/api/crops", json=profile)
        assert response.status_code == 201
        assert response.json()["references"] == profile["references"]
        assert client.post("/api/crops", json=profile).status_code == 409


def test_partial_dry_mass_records_do_not_report_dry_mass_efficiency(tmp_path, monkeypatch):
    with experiment_client(tmp_path, monkeypatch) as client:
        experiment = create_experiment(client)
        group_id = experiment["groups"][0]["id"]
        experiment_id = experiment["id"]
        for dry_mass in (5, None):
            response = client.post(
                f"/api/experiments/{experiment_id}/harvests",
                json={
                    "group_id": group_id,
                    "plant_count": 1,
                    "fresh_mass_g": 10,
                    "dry_mass_g": dry_mass,
                },
            )
            assert response.status_code == 201
        client.post(
            f"/api/experiments/{experiment_id}/readings",
            json={
                "group_id": group_id,
                "source_id": "water-log",
                "water_added_l": 1,
            },
        )

        result = client.get(f"/api/analysis/experiments/{experiment_id}").json()
        group = result["groups"][0]
        assert group["measurements"]["fresh_mass_g"] == 20
        assert group["measurements"]["water_added_l"] == 1
        assert group["measurements"]["fresh_water_use_efficiency_g_per_l"] == 20
        assert group["measurements"]["dry_mass_g"] is None
        assert group["measurements"]["dry_water_use_efficiency_g_per_l"] is None
