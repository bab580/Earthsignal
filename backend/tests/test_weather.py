import asyncio
from datetime import date, datetime, timezone

from fastapi.testclient import TestClient

from backend.app import main as app_module
from backend.app.weather import (
    ARCHIVE_URL,
    FORECAST_URL,
    WeatherServiceError,
    fetch_weather,
    normalize_weather_response,
    rainfall_history_period,
    summarize_monthly_rainfall,
    trailing_dry_spell,
)
from backend.app import weather as weather_module


def test_rainfall_history_uses_twelve_complete_calendar_months():
    start, end = rainfall_history_period(date(2026, 11, 13))

    assert start == date(2025, 11, 1)
    assert end == date(2026, 10, 31)


def test_health_route_supports_get_and_head(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SENSOR_DB", tmp_path / "health-test.sqlite3")

    with TestClient(app_module.app) as client:
        get_response = client.get("/api/health")
        head_response = client.head("/api/health")

    assert get_response.status_code == 200
    assert get_response.json() == {"status": "ok", "service": "earthsignal"}
    assert head_response.status_code == 200
    assert head_response.content == b""


def test_monthly_rainfall_reports_valid_coverage():
    result = summarize_monthly_rainfall(
        {
            "time": ["2025-11-01", "2025-11-02", "2025-11-03"],
            "precipitation_sum": [3.2, None, 0.8],
        },
        date(2025, 11, 1),
        date(2025, 11, 30),
    )

    assert result == [{
        "month": "2025-11",
        "precipitation_mm": 4.0,
        "valid_days": 2,
        "days_in_month": 30,
    }]


def test_trailing_dry_spell_stops_at_missing_day():
    result = trailing_dry_spell(
        ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04", "2026-01-05"],
        [0.2, 0.0, 3.0, None, 0.4],
        date(2026, 1, 6),
    )

    assert result == {
        "days": 1,
        "start": "2026-01-05",
        "as_of": "2026-01-05",
        "threshold_mm_per_day": 1.0,
    }


def test_weather_response_separates_forecast_from_recent_rainfall():
    forecast_dates = [f"2026-01-{day:02d}" for day in range(1, 11)]
    forecast = {
        "timezone": "Africa/Kampala",
        "current": {
            "time": "2026-01-03T10:00",
            "temperature_2m": 27,
            "relative_humidity_2m": 70,
            "apparent_temperature": 29,
            "precipitation": 0.2,
            "weather_code": 2,
            "is_day": 1,
            "wind_speed_10m": 8,
        },
        "current_units": {
            "temperature_2m": "°C",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
        },
        "daily": {
            "time": forecast_dates,
            "weather_code": [0] * 10,
            "temperature_2m_max": [30] * 10,
            "temperature_2m_min": [20] * 10,
            "precipitation_sum": [0.2, 0.1, 1.5, 0, 0, 0, 0, 0, 0, 0],
            "precipitation_probability_max": [30] * 10,
            "wind_speed_10m_max": [10] * 10,
        },
    }
    archive = {
        "daily": {
            "time": ["2025-12-31"],
            "precipitation_sum": [4.5],
        },
    }

    result = normalize_weather_response(
        forecast,
        archive,
        0.3476,
        32.5825,
        date(2026, 1, 3),
    )

    assert len(result["forecast"]) == 7
    assert result["forecast"][0]["date"] == "2026-01-03"
    assert [day["date"] for day in result["recent_days"]] == ["2026-01-01", "2026-01-02"]
    assert len(result["rainfall_history"]) == 12
    assert result["recent_dry_spell"]["days"] == 2
    assert result["recent_dry_spell"]["as_of"] == "2026-01-02"


def test_weather_route_passes_global_coordinates_to_provider(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SENSOR_DB", tmp_path / "weather-test.sqlite3")

    async def fake_fetch_weather(latitude, longitude):
        return {
            "source": "Open-Meteo",
            "location": {"latitude": latitude, "longitude": longitude},
        }

    monkeypatch.setattr(app_module, "fetch_weather", fake_fetch_weather)

    with TestClient(app_module.app) as client:
        response = client.get(
            "/api/weather",
            params={"latitude": -33.8688, "longitude": 151.2093},
        )

    assert response.status_code == 200
    assert response.json()["location"] == {"latitude": -33.8688, "longitude": 151.2093}


def test_weather_location_route_returns_global_search_results(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "SENSOR_DB", tmp_path / "weather-location-test.sqlite3")

    async def fake_search(query):
        assert query == "Lira, Uganda"
        return [{"name": "Lira", "country": "Uganda", "latitude": 2.2499, "longitude": 32.8998}]

    monkeypatch.setattr(app_module, "search_weather_locations", fake_search)

    with TestClient(app_module.app) as client:
        response = client.get("/api/weather/locations", params={"query": "Lira, Uganda"})

    assert response.status_code == 200
    assert response.json()["results"][0]["name"] == "Lira"


def test_weather_still_returns_forecast_when_archive_is_unavailable(monkeypatch):
    today = datetime.now(timezone.utc).date()
    forecast_payload = {
        "timezone": "Africa/Kampala",
        "current": {"time": today.isoformat(), "temperature_2m": 27},
        "current_units": {},
        "daily": {
            "time": [today.isoformat()],
            "weather_code": [0],
            "temperature_2m_max": [30],
            "temperature_2m_min": [20],
            "precipitation_sum": [0],
            "precipitation_probability_max": [0],
            "wind_speed_10m_max": [10],
        },
    }

    async def fake_get_json(_client, url, _params):
        if url == FORECAST_URL:
            return forecast_payload
        if url == ARCHIVE_URL:
            raise WeatherServiceError("Archive is unavailable.")
        raise AssertionError(f"Unexpected weather URL: {url}")

    monkeypatch.setattr(weather_module, "_get_json", fake_get_json)
    result = asyncio.run(fetch_weather(2.2499, 32.8998))

    assert result["current"]["temperature"] == 27
    assert len(result["forecast"]) == 1
    assert result["warnings"] == ["historical_rainfall_unavailable"]
    assert len(result["rainfall_history"]) == 12
    assert all(month["precipitation_mm"] is None for month in result["rainfall_history"])
