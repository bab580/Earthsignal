import asyncio
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
import math
from typing import Any

import httpx


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_TIMEOUT = 20.0


class WeatherServiceError(RuntimeError):
    pass


class WeatherServiceTimeout(WeatherServiceError):
    pass


def rainfall_history_period(today: date) -> tuple[date, date]:
    end = date(today.year, today.month, 1) - timedelta(days=1)
    start_month_index = end.year * 12 + end.month - 1 - 11
    start = date(start_month_index // 12, start_month_index % 12 + 1, 1)
    return start, end


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_monthly_rainfall(
    daily: dict[str, Any],
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    try:
        dates = daily["time"]
        values = daily["precipitation_sum"]
    except (KeyError, TypeError):
        raise ValueError("Open-Meteo archive response did not contain daily rainfall data.")
    if not isinstance(dates, list) or not isinstance(values, list) or len(dates) != len(values):
        raise ValueError("Open-Meteo archive response contained incomplete daily rainfall data.")

    rainfall_by_date = {
        day: _number(value)
        for day, value in zip(dates, values)
        if isinstance(day, str)
    }
    results = []
    current = start
    while current <= end:
        month_start = date(current.year, current.month, 1)
        last_day = monthrange(current.year, current.month)[1]
        month_end = date(current.year, current.month, last_day)
        day = month_start
        total = 0.0
        valid_days = 0
        while day <= month_end:
            value = rainfall_by_date.get(day.isoformat())
            if value is not None and value >= 0:
                total += value
                valid_days += 1
            day += timedelta(days=1)
        results.append({
            "month": month_start.strftime("%Y-%m"),
            "precipitation_mm": round(total, 1) if valid_days else None,
            "valid_days": valid_days,
            "days_in_month": last_day,
        })
        current = month_end + timedelta(days=1)
    return results


def trailing_dry_spell(dates: list[Any], values: list[Any], today: date) -> dict[str, Any]:
    if len(dates) != len(values):
        raise ValueError("Open-Meteo recent rainfall data contained mismatched dates and values.")
    recent = sorted(
        (
            (date.fromisoformat(day), _number(value))
            for day, value in zip(dates, values)
            if isinstance(day, str) and day < today.isoformat()
        ),
        key=lambda item: item[0],
    )
    as_of = recent[-1][0].isoformat() if recent else None
    days = 0
    start = None
    expected_previous_day = None
    for day, rainfall in reversed(recent):
        if expected_previous_day and day != expected_previous_day:
            break
        if rainfall is None or rainfall < 0 or rainfall >= 1:
            break
        days += 1
        start = day.isoformat()
        expected_previous_day = day - timedelta(days=1)
    return {
        "days": days,
        "start": start,
        "as_of": as_of,
        "threshold_mm_per_day": 1.0,
    }


async def _get_json(client: httpx.AsyncClient, url: str, params: dict[str, Any]) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.TimeoutException as exc:
        raise WeatherServiceTimeout("Open-Meteo did not respond before the timeout. Please try again.") from exc
    except (httpx.HTTPError, ValueError) as exc:
        raise WeatherServiceError("Could not retrieve valid weather data from Open-Meteo. Please retry.") from exc
    if not isinstance(payload, dict) or payload.get("error"):
        raise WeatherServiceError("Open-Meteo returned an invalid weather response. Please retry.")
    return payload


async def search_weather_locations(query: str) -> list[dict[str, Any]]:
    async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT) as client:
        payload = await _get_json(client, GEOCODING_URL, {
            "name": query,
            "count": 8,
            "language": "en",
            "format": "json",
        })
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise WeatherServiceError("Open-Meteo returned invalid location results.")
    locations = []
    for item in results:
        if not isinstance(item, dict):
            continue
        latitude = _number(item.get("latitude"))
        longitude = _number(item.get("longitude"))
        if latitude is None or longitude is None:
            continue
        locations.append({
            "name": item.get("name"),
            "admin1": item.get("admin1"),
            "country": item.get("country"),
            "country_code": item.get("country_code"),
            "latitude": latitude,
            "longitude": longitude,
            "timezone": item.get("timezone"),
        })
    return locations


def _daily_value(daily: dict[str, Any], key: str, index: int) -> Any:
    values = daily.get(key)
    return values[index] if isinstance(values, list) and index < len(values) else None


def normalize_weather_response(
    forecast_payload: dict[str, Any],
    archive_payload: dict[str, Any],
    latitude: float,
    longitude: float,
    today: date,
) -> dict[str, Any]:
    try:
        current = forecast_payload["current"]
        forecast_daily = forecast_payload["daily"]
        archive_daily = archive_payload["daily"]
        dates = forecast_daily["time"]
    except (KeyError, TypeError):
        raise ValueError("Open-Meteo response did not contain expected current, forecast and archive data.")
    if not isinstance(current, dict) or not isinstance(forecast_daily, dict) or not isinstance(dates, list):
        raise ValueError("Open-Meteo response contained invalid current conditions or forecast data.")

    local_today = today
    current_time = current.get("time")
    if isinstance(current_time, str):
        try:
            local_today = date.fromisoformat(current_time[:10])
        except ValueError:
            pass

    forecast = []
    recent_days = []
    for index, day in enumerate(dates):
        if not isinstance(day, str):
            continue
        daily_summary = {
            "date": day,
            "weather_code": _daily_value(forecast_daily, "weather_code", index),
            "temperature_max": _number(_daily_value(forecast_daily, "temperature_2m_max", index)),
            "temperature_min": _number(_daily_value(forecast_daily, "temperature_2m_min", index)),
            "precipitation_mm": _number(_daily_value(forecast_daily, "precipitation_sum", index)),
            "precipitation_probability_max": _number(
                _daily_value(forecast_daily, "precipitation_probability_max", index)
            ),
            "wind_speed_max": _number(_daily_value(forecast_daily, "wind_speed_10m_max", index)),
        }
        if day < local_today.isoformat():
            recent_days.append(daily_summary)
        elif len(forecast) < 7:
            forecast.append(daily_summary)

    history_start, history_end = rainfall_history_period(today)
    return {
        "source": "Open-Meteo",
        "forecast_source_url": "https://open-meteo.com/en/docs",
        "archive_source_url": "https://open-meteo.com/en/docs/historical-weather-api",
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "location": {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": forecast_payload.get("timezone"),
        },
        "units": {
            "temperature": forecast_payload.get("current_units", {}).get("temperature_2m", "°C"),
            "precipitation": forecast_payload.get("current_units", {}).get("precipitation", "mm"),
            "wind_speed": forecast_payload.get("current_units", {}).get("wind_speed_10m", "km/h"),
        },
        "current": {
            "time": current.get("time"),
            "temperature": _number(current.get("temperature_2m")),
            "apparent_temperature": _number(current.get("apparent_temperature")),
            "relative_humidity": _number(current.get("relative_humidity_2m")),
            "precipitation_mm": _number(current.get("precipitation")),
            "weather_code": current.get("weather_code"),
            "is_day": current.get("is_day"),
            "wind_speed": _number(current.get("wind_speed_10m")),
        },
        "recent_days": recent_days[-7:],
        "forecast": forecast,
        "rainfall_history": summarize_monthly_rainfall(archive_daily, history_start, history_end),
        "recent_dry_spell": trailing_dry_spell(
            dates,
            forecast_daily.get("precipitation_sum", []),
            local_today,
        ),
        "history_period": {
            "start": history_start.isoformat(),
            "end": history_end.isoformat(),
        },
        "method_note": (
            "Current conditions and forecast are from Open-Meteo. Monthly rainfall totals sum valid daily "
            "precipitation from the previous 12 complete calendar months; incomplete months show their "
            "valid-day count. The recent dry-spell screen counts consecutive days below 1 mm/day and is "
            "weather context, not crop-water status."
        ),
    }


async def fetch_weather(latitude: float, longitude: float) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    history_start, history_end = rainfall_history_period(today)
    forecast_params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": (
            "temperature_2m,relative_humidity_2m,apparent_temperature,is_day,"
            "precipitation,weather_code,wind_speed_10m"
        ),
        "daily": (
            "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,"
            "precipitation_probability_max,wind_speed_10m_max"
        ),
        "past_days": 30,
        "forecast_days": 7,
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
        "timezone": "auto",
    }
    archive_params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": history_start.isoformat(),
        "end_date": history_end.isoformat(),
        "daily": "precipitation_sum",
        "precipitation_unit": "mm",
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=WEATHER_TIMEOUT) as client:
        forecast_payload, archive_payload = await asyncio.gather(
            _get_json(client, FORECAST_URL, forecast_params),
            _get_json(client, ARCHIVE_URL, archive_params),
        )
    try:
        return normalize_weather_response(forecast_payload, archive_payload, latitude, longitude, today)
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ValueError) and str(exc).startswith("Open-Meteo response"):
            raise WeatherServiceError(str(exc)) from exc
        raise WeatherServiceError("Open-Meteo returned invalid weather data. Please retry.") from exc
