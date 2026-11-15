from contextlib import asynccontextmanager
import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal
import math
import os
import secrets
import sqlite3

import httpx
from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

from .analysis import analyze_observations, analyze_rainfall_events
from .appeears import AppEEARSError, EarthdataNotConfigured, fetch_modis_point
from .communications import daily_sms_dispatch_loop, init_communications_db, router as communications_router
from .experiments import init_experiment_db, router as experiments_router
from .weather import WeatherServiceError, WeatherServiceTimeout, fetch_weather, search_weather_locations

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
FRONTEND_DIR = BASE_DIR / "frontend"
NASA_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"
TIMEOUT = float(os.getenv("NASA_POWER_TIMEOUT_SECONDS", "30"))
SENSOR_DB = Path(
    os.getenv("EARTHSIGNAL_SENSOR_DB", str(BASE_DIR / "backend" / "earthsignal_sensors.sqlite3"))
)
SENSOR_DEVICE_TOKEN = os.getenv("EARTHSIGNAL_DEVICE_TOKEN", "").strip()
ALLOW_UNAUTHENTICATED_SENSOR_INGESTION = (
    os.getenv("EARTHSIGNAL_ALLOW_UNAUTHENTICATED_SENSOR_INGESTION", "false").strip().lower() == "true"
)


class SensorReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    raw: int = Field(ge=0, le=4095)
    moisture: float = Field(ge=0, le=100, allow_inf_nan=False)
    status: Literal["DRY", "MOIST", "WET"]
    recorded_at: datetime | None = None


def init_sensor_db() -> None:
    SENSOR_DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(SENSOR_DB) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                raw INTEGER NOT NULL,
                moisture REAL NOT NULL,
                status TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                received_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_sensor_device_time "
            "ON sensor_readings(device_id, recorded_at DESC)"
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_sensor_db()
    init_experiment_db(SENSOR_DB)
    init_communications_db(SENSOR_DB)
    app.state.sensor_db = SENSOR_DB
    sms_task = asyncio.create_task(daily_sms_dispatch_loop(SENSOR_DB))
    try:
        yield
    finally:
        sms_task.cancel()
        try:
            await sms_task
        except asyncio.CancelledError:
            pass


def verify_sensor_token(x_device_token: str | None) -> None:
    if SENSOR_DEVICE_TOKEN:
        if not x_device_token or not secrets.compare_digest(x_device_token, SENSOR_DEVICE_TOKEN):
            raise HTTPException(status_code=401, detail="Invalid or missing device token.")
        return
    if not ALLOW_UNAUTHENTICATED_SENSOR_INGESTION:
        raise HTTPException(
            status_code=503,
            detail="Sensor ingestion is not configured. Set a device token or explicitly enable trusted-LAN demo mode.",
        )


app = FastAPI(title="EarthSignal MVP", version="0.1.0", lifespan=lifespan)
cors_origins = [
    origin.strip().rstrip("/")
    for origin in os.getenv("EARTHSIGNAL_CORS_ORIGINS", "").split(",")
    if origin.strip()
]
if cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
app.include_router(experiments_router)
app.include_router(communications_router)


@app.get("/")
async def home():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "earthsignal"}


@app.get("/api/weather/locations")
async def weather_locations(query: str = Query(..., min_length=2, max_length=120)):
    try:
        return {"results": await search_weather_locations(query)}
    except WeatherServiceTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/weather")
async def weather(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
):
    try:
        return await fetch_weather(latitude, longitude)
    except WeatherServiceTimeout as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except WeatherServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.post("/api/sensors/readings")
async def receive_sensor_reading(
    reading: SensorReadingIn,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    verify_sensor_token(x_device_token)
    recorded_at = reading.recorded_at or datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    recorded_text = recorded_at.astimezone(timezone.utc).isoformat()
    received_text = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(SENSOR_DB) as connection:
        cursor = connection.execute(
            """
            INSERT INTO sensor_readings
                (device_id, raw, moisture, status, recorded_at, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                reading.device_id,
                reading.raw,
                reading.moisture,
                reading.status,
                recorded_text,
                received_text,
            ),
        )
        reading_id = cursor.lastrowid

    return {
        "accepted": True,
        "id": reading_id,
        "device_id": reading.device_id,
        "recorded_at": recorded_text,
    }


@app.get("/api/sensors/latest")
async def latest_sensor_reading(
    device_id: str = Query(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
):
    with sqlite3.connect(SENSOR_DB) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            """
            SELECT device_id, raw, moisture, status, recorded_at, received_at
            FROM sensor_readings
            WHERE device_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT 1
            """,
            (device_id,),
        ).fetchone()
    return {"device_id": device_id, "reading": dict(row) if row else None}


@app.get("/api/sensors/recent")
async def recent_sensor_readings(
    device_id: str = Query(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$"),
    limit: int = Query(50, ge=1, le=500),
):
    with sqlite3.connect(SENSOR_DB) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT device_id, raw, moisture, status, recorded_at, received_at
            FROM sensor_readings
            WHERE device_id = ?
            ORDER BY recorded_at DESC, id DESC
            LIMIT ?
            """,
            (device_id, limit),
        ).fetchall()
    return {"device_id": device_id, "count": len(rows), "readings": [dict(row) for row in rows]}


@app.get("/api/modis")
async def modis(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start: date = Query(...),
    end: date = Query(...)
):
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date.")
    if (end - start).days > 365 * 15:
        raise HTTPException(status_code=400, detail="For this demo, select a period of 15 years or less.")
    try:
        return await fetch_modis_point(latitude, longitude, start, end)
    except EarthdataNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except AppEEARSError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="NASA AppEEARS did not respond before the timeout. Please try again.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not retrieve MODIS data from NASA AppEEARS. Please retry.") from exc


def parse_power_response(payload: dict[str, Any], latitude: float, longitude: float,
                         start: date, end: date) -> dict[str, Any]:
    try:
        properties = payload["properties"]
        parameter_data = properties["parameter"]
    except (KeyError, TypeError):
        raise ValueError("NASA POWER response did not contain the expected properties.parameter object.")

    metadata = properties.get("parameter_metadata") or properties.get("parameters") or payload.get("parameters") or {}
    parameter_units = {}
    for code in ("PRECTOTCORR", "T2M"):
        item = metadata.get(code, {}) if isinstance(metadata, dict) else {}
        parameter_units[code] = {
            "unit": item.get("units") or item.get("unit") or "Check NASA metadata",
            "long_name": item.get("longname") or item.get("name") or code
        }

    all_dates = set()
    for code in ("PRECTOTCORR", "T2M"):
        series = parameter_data.get(code, {})
        if isinstance(series, dict):
            all_dates.update(series.keys())

    observations_by_date = {}
    summaries = {}
    for code in ("PRECTOTCORR", "T2M"):
        series = parameter_data.get(code, {})
        valid = []
        for raw_day in sorted(all_dates):
            raw_value = series.get(raw_day) if isinstance(series, dict) else None
            value = None
            if raw_value is not None:
                try:
                    candidate = float(raw_value)
                    # POWER missing-value sentinel commonly appears as -999.
                    if math.isfinite(candidate) and candidate > -900:
                        value = candidate
                        valid.append(candidate)
                except (TypeError, ValueError):
                    pass
            iso_day = f"{raw_day[:4]}-{raw_day[4:6]}-{raw_day[6:8]}"
            row = observations_by_date.setdefault(iso_day, {"date": iso_day})
            row[code] = value

        summaries[code] = {
            "valid_count": len(valid),
            "missing_count": max(0, len(all_dates) - len(valid)),
            "mean": round(sum(valid) / len(valid), 3) if valid else None,
            "min": round(min(valid), 3) if valid else None,
            "max": round(max(valid), 3) if valid else None,
        }

    observations = [observations_by_date[key] for key in sorted(observations_by_date)]
    return {
        "source": "NASA POWER Daily API",
        "source_url": NASA_URL,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "location": {"latitude": latitude, "longitude": longitude},
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "parameters": parameter_units,
        "observations": observations,
        "summary": summaries,
        "analysis": analyze_observations(observations, start, end),
        "rainfall_events": analyze_rainfall_events(observations, start, end),
        "method_note": "Daily NASA POWER values. Summary statistics are calculated by EarthSignal from valid returned observations."
    }


@app.get("/api/earth")
async def earth(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    start: date = Query(...),
    end: date = Query(...)
):
    if start > end:
        raise HTTPException(status_code=400, detail="Start date must be on or before end date.")
    if (end - start).days > 365 * 15:
        raise HTTPException(status_code=400, detail="For this demo, select a period of 15 years or less.")

    params = {
        "parameters": "PRECTOTCORR,T2M",
        "community": "AG",
        "longitude": longitude,
        "latitude": latitude,
        "start": start.strftime("%Y%m%d"),
        "end": end.strftime("%Y%m%d"),
        "format": "JSON",
        "time-standard": "UTC"
    }
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(NASA_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="NASA POWER did not respond before the timeout. Please try again.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Could not retrieve valid data from NASA POWER. Please retry.")
    try:
        return parse_power_response(payload, latitude, longitude, start, end)
    except ValueError as exc:
        raise HTTPException(status_code=502, detail=str(exc))
