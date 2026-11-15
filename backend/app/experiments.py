from contextlib import contextmanager
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field


DATABASE_PATH = Path(
    os.getenv(
        "EARTHSIGNAL_SENSOR_DB",
        str(Path(__file__).resolve().parents[1] / "earthsignal_sensors.sqlite3"),
    )
)
router = APIRouter()


class ExperimentGroupIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    treatment: str = Field(min_length=1, max_length=300)
    watering_plan: str | None = Field(default=None, max_length=500)


class ExperimentIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=120)
    crop: str = Field(min_length=1, max_length=80)
    variety: str | None = Field(default=None, max_length=120)
    location: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date | None = None
    research_objective: str = Field(min_length=1, max_length=2000)
    groups: list[ExperimentGroupIn] = Field(min_length=1, max_length=20)


class ExperimentReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    group_id: int | None = Field(default=None, gt=0)
    source_type: Literal["manual", "esp32", "other"] = "manual"
    source_id: str = Field(min_length=1, max_length=100)
    recorded_at: datetime | None = None
    air_temperature_c: float | None = Field(default=None, ge=-40, le=80, allow_inf_nan=False)
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    light_lux: float | None = Field(default=None, ge=0, le=300000, allow_inf_nan=False)
    medium_moisture_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    water_added_l: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    notes: str | None = Field(default=None, max_length=1000)


class PlantObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    group_id: int = Field(gt=0)
    plant_id: str = Field(min_length=1, max_length=80)
    observed_at: datetime | None = None
    height_cm: float | None = Field(default=None, ge=0, le=10000, allow_inf_nan=False)
    leaf_count: int | None = Field(default=None, ge=0, le=100000)
    visible_stress: str | None = Field(default=None, max_length=500)
    notes: str | None = Field(default=None, max_length=1000)
    image_reference: str | None = Field(default=None, max_length=1000)


class HarvestIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    group_id: int = Field(gt=0)
    harvested_at: datetime | None = None
    plant_count: int = Field(ge=1, le=100000)
    fresh_mass_g: float = Field(ge=0, le=100000000, allow_inf_nan=False)
    dry_mass_g: float | None = Field(default=None, ge=0, le=100000000, allow_inf_nan=False)
    notes: str | None = Field(default=None, max_length=1000)


class HabitatReadingIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    experiment_id: int | None = Field(default=None, gt=0)
    group_id: int | None = Field(default=None, gt=0)
    source_type: Literal["manual", "esp32", "other"] = "esp32"
    recorded_at: datetime | None = None
    air_temperature_c: float | None = Field(default=None, ge=-40, le=80, allow_inf_nan=False)
    relative_humidity_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    light_lux: float | None = Field(default=None, ge=0, le=300000, allow_inf_nan=False)
    medium_moisture_pct: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    water_added_l: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    reservoir_level_l: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    co2_ppm: float | None = Field(default=None, ge=0, le=100000, allow_inf_nan=False)
    nutrient_ph: float | None = Field(default=None, ge=0, le=14, allow_inf_nan=False)
    nutrient_ec_ms_cm: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)


class CropProfileIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=80)
    scientific_name: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    nutrition: dict[str, Any] = Field(default_factory=dict)
    references: list[dict[str, str]] = Field(default_factory=list, max_length=20)


class SensorDeviceIn(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    sensor_types: list[str] = Field(min_length=1, max_length=30)
    calibration: dict[str, Any] = Field(default_factory=dict)
    units: dict[str, str] = Field(default_factory=dict)


def init_experiment_db(db_path: Path) -> None:
    global DATABASE_PATH
    DATABASE_PATH = Path(db_path)
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DATABASE_PATH) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                crop TEXT NOT NULL,
                variety TEXT,
                location TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT,
                research_objective TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS experiment_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                treatment TEXT NOT NULL,
                watering_plan TEXT,
                UNIQUE(experiment_id, name)
            );
            CREATE TABLE IF NOT EXISTS experiment_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                group_id INTEGER REFERENCES experiment_groups(id) ON DELETE SET NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                air_temperature_c REAL,
                relative_humidity_pct REAL,
                light_lux REAL,
                medium_moisture_pct REAL,
                water_added_l REAL,
                notes TEXT,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_experiment_readings_time
                ON experiment_readings(experiment_id, recorded_at DESC);
            CREATE TABLE IF NOT EXISTS plant_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                group_id INTEGER NOT NULL REFERENCES experiment_groups(id) ON DELETE CASCADE,
                plant_id TEXT NOT NULL,
                observed_at TEXT NOT NULL,
                height_cm REAL,
                leaf_count INTEGER,
                visible_stress TEXT,
                notes TEXT,
                image_reference TEXT,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_plant_observations_time
                ON plant_observations(experiment_id, plant_id, observed_at);
            CREATE TABLE IF NOT EXISTS harvest_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL REFERENCES experiments(id) ON DELETE CASCADE,
                group_id INTEGER NOT NULL REFERENCES experiment_groups(id) ON DELETE CASCADE,
                harvested_at TEXT NOT NULL,
                plant_count INTEGER NOT NULL,
                fresh_mass_g REAL NOT NULL,
                dry_mass_g REAL,
                notes TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS crop_profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                scientific_name TEXT,
                description TEXT,
                nutrition_json TEXT NOT NULL,
                references_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS sensor_devices (
                device_id TEXT PRIMARY KEY,
                sensor_types_json TEXT NOT NULL,
                calibration_json TEXT NOT NULL,
                units_json TEXT NOT NULL,
                registered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS habitat_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL REFERENCES sensor_devices(device_id),
                experiment_id INTEGER REFERENCES experiments(id) ON DELETE SET NULL,
                group_id INTEGER REFERENCES experiment_groups(id) ON DELETE SET NULL,
                source_type TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                air_temperature_c REAL,
                relative_humidity_pct REAL,
                light_lux REAL,
                medium_moisture_pct REAL,
                water_added_l REAL,
                reservoir_level_l REAL,
                co2_ppm REAL,
                nutrient_ph REAL,
                nutrient_ec_ms_cm REAL,
                received_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_habitat_readings_device_time
                ON habitat_readings(device_id, recorded_at DESC);
            """
        )


@contextmanager
def _connection():
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_text(value: datetime | None) -> str:
    timestamp = value or _now()
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc).isoformat()


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="Metadata must contain valid JSON values.") from exc


def _json_value(value: str) -> Any:
    return json.loads(value)


def _require_measurement(model: BaseModel, fields: tuple[str, ...]) -> None:
    if not any(getattr(model, field) is not None for field in fields):
        raise HTTPException(status_code=422, detail="At least one measurement value is required.")


def _require_experiment(connection: sqlite3.Connection, experiment_id: int) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM experiments WHERE id = ?", (experiment_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Experiment not found.")
    return row


def _require_group(
    connection: sqlite3.Connection, experiment_id: int, group_id: int
) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM experiment_groups WHERE id = ? AND experiment_id = ?",
        (group_id, experiment_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=422, detail="Group does not belong to this experiment.")
    return row


def _experiment_payload(connection: sqlite3.Connection, row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    groups = connection.execute(
        "SELECT id, name, treatment, watering_plan FROM experiment_groups "
        "WHERE experiment_id = ? ORDER BY id",
        (row["id"],),
    ).fetchall()
    result["groups"] = [dict(group) for group in groups]
    return result


def _dict_rows(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


@router.post("/api/experiments", status_code=201)
async def create_experiment(experiment: ExperimentIn):
    if experiment.end_date and experiment.end_date < experiment.start_date:
        raise HTTPException(status_code=422, detail="End date must be on or after start date.")
    now = _now().isoformat()
    try:
        with _connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO experiments
                    (name, crop, variety, location, start_date, end_date, research_objective, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    experiment.name.strip(),
                    experiment.crop.strip(),
                    experiment.variety.strip() if experiment.variety else None,
                    experiment.location.strip(),
                    experiment.start_date.isoformat(),
                    experiment.end_date.isoformat() if experiment.end_date else None,
                    experiment.research_objective.strip(),
                    now,
                    now,
                ),
            )
            experiment_id = cursor.lastrowid
            for group in experiment.groups:
                connection.execute(
                    "INSERT INTO experiment_groups (experiment_id, name, treatment, watering_plan) "
                    "VALUES (?, ?, ?, ?)",
                    (
                        experiment_id,
                        group.name.strip(),
                        group.treatment.strip(),
                        group.watering_plan.strip() if group.watering_plan else None,
                    ),
                )
            row = _require_experiment(connection, experiment_id)
            return _experiment_payload(connection, row)
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Group names must be unique within an experiment.") from exc


@router.get("/api/experiments")
async def list_experiments():
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM experiments ORDER BY created_at DESC, id DESC").fetchall()
        return [_experiment_payload(connection, row) for row in rows]


@router.get("/api/experiments/{experiment_id}")
async def get_experiment(experiment_id: int):
    with _connection() as connection:
        return _experiment_payload(connection, _require_experiment(connection, experiment_id))


@router.post("/api/experiments/{experiment_id}/readings", status_code=201)
async def add_experiment_reading(
    experiment_id: int,
    reading: ExperimentReadingIn,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    if reading.source_type == "esp32":
        from .main import verify_sensor_token

        verify_sensor_token(x_device_token)
    fields = (
        "air_temperature_c",
        "relative_humidity_pct",
        "light_lux",
        "medium_moisture_pct",
        "water_added_l",
    )
    _require_measurement(reading, fields)
    recorded_at = _utc_text(reading.recorded_at)
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        if reading.group_id is not None:
            _require_group(connection, experiment_id, reading.group_id)
        cursor = connection.execute(
            """
            INSERT INTO experiment_readings
                (experiment_id, group_id, source_type, source_id, recorded_at,
                 air_temperature_c, relative_humidity_pct, light_lux, medium_moisture_pct,
                 water_added_l, notes, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                reading.group_id,
                reading.source_type,
                reading.source_id.strip(),
                recorded_at,
                reading.air_temperature_c,
                reading.relative_humidity_pct,
                reading.light_lux,
                reading.medium_moisture_pct,
                reading.water_added_l,
                reading.notes.strip() if reading.notes else None,
                _now().isoformat(),
            ),
        )
        return {"id": cursor.lastrowid, "experiment_id": experiment_id, "recorded_at": recorded_at}


@router.get("/api/experiments/{experiment_id}/readings")
async def list_experiment_readings(
    experiment_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
):
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        rows = connection.execute(
            "SELECT * FROM experiment_readings WHERE experiment_id = ? "
            "ORDER BY recorded_at DESC, id DESC LIMIT ?",
            (experiment_id, limit),
        ).fetchall()
        return {"experiment_id": experiment_id, "readings": _dict_rows(rows)}


@router.post("/api/experiments/{experiment_id}/observations", status_code=201)
async def add_plant_observation(experiment_id: int, observation: PlantObservationIn):
    if (
        observation.height_cm is None
        and observation.leaf_count is None
        and not (observation.visible_stress and observation.visible_stress.strip())
    ):
        raise HTTPException(
            status_code=422,
            detail="Provide plant height, leaf count, or a visible-stress observation.",
        )
    recorded_at = _utc_text(observation.observed_at)
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        _require_group(connection, experiment_id, observation.group_id)
        cursor = connection.execute(
            """
            INSERT INTO plant_observations
                (experiment_id, group_id, plant_id, observed_at, height_cm, leaf_count,
                 visible_stress, notes, image_reference, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                observation.group_id,
                observation.plant_id.strip(),
                recorded_at,
                observation.height_cm,
                observation.leaf_count,
                observation.visible_stress.strip() if observation.visible_stress else None,
                observation.notes.strip() if observation.notes else None,
                observation.image_reference.strip() if observation.image_reference else None,
                _now().isoformat(),
            ),
        )
        return {"id": cursor.lastrowid, "experiment_id": experiment_id, "observed_at": recorded_at}


@router.get("/api/experiments/{experiment_id}/observations")
async def list_plant_observations(
    experiment_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
):
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        rows = connection.execute(
            "SELECT * FROM plant_observations WHERE experiment_id = ? "
            "ORDER BY observed_at DESC, id DESC LIMIT ?",
            (experiment_id, limit),
        ).fetchall()
        return {"experiment_id": experiment_id, "observations": _dict_rows(rows)}


@router.post("/api/experiments/{experiment_id}/harvests", status_code=201)
async def add_harvest(experiment_id: int, harvest: HarvestIn):
    harvested_at = _utc_text(harvest.harvested_at)
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        _require_group(connection, experiment_id, harvest.group_id)
        if harvest.dry_mass_g is not None and harvest.dry_mass_g > harvest.fresh_mass_g:
            raise HTTPException(status_code=422, detail="Dry mass cannot exceed fresh mass.")
        cursor = connection.execute(
            """
            INSERT INTO harvest_records
                (experiment_id, group_id, harvested_at, plant_count, fresh_mass_g,
                 dry_mass_g, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                experiment_id,
                harvest.group_id,
                harvested_at,
                harvest.plant_count,
                harvest.fresh_mass_g,
                harvest.dry_mass_g,
                harvest.notes.strip() if harvest.notes else None,
                _now().isoformat(),
            ),
        )
        return {"id": cursor.lastrowid, "experiment_id": experiment_id, "harvested_at": harvested_at}


@router.get("/api/experiments/{experiment_id}/harvests")
async def list_harvests(
    experiment_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
):
    with _connection() as connection:
        _require_experiment(connection, experiment_id)
        rows = connection.execute(
            "SELECT * FROM harvest_records WHERE experiment_id = ? "
            "ORDER BY harvested_at DESC, id DESC LIMIT ?",
            (experiment_id, limit),
        ).fetchall()
        return {"experiment_id": experiment_id, "harvests": _dict_rows(rows)}


def _group_analysis(connection: sqlite3.Connection, group: sqlite3.Row) -> dict[str, Any]:
    group_id = group["id"]
    water_row = connection.execute(
        """
        SELECT
            COALESCE((SELECT SUM(water_added_l) FROM experiment_readings WHERE group_id = ?), 0) +
            COALESCE((SELECT SUM(water_added_l) FROM habitat_readings WHERE group_id = ?), 0) AS water_l,
            (SELECT COUNT(water_added_l) FROM experiment_readings WHERE group_id = ?) +
            (SELECT COUNT(water_added_l) FROM habitat_readings WHERE group_id = ?) AS water_records
        """,
        (group_id, group_id, group_id, group_id),
    ).fetchone()
    harvest_row = connection.execute(
        """
        SELECT SUM(plant_count) AS plant_count,
               SUM(fresh_mass_g) AS fresh_mass_g,
               SUM(dry_mass_g) AS measured_dry_mass_g,
               COUNT(dry_mass_g) AS dry_mass_records,
               COUNT(*) AS harvest_count
        FROM harvest_records WHERE group_id = ?
        """,
        (group_id,),
    ).fetchone()
    observations = connection.execute(
        """
        SELECT plant_id, observed_at, height_cm FROM plant_observations
        WHERE group_id = ? AND height_cm IS NOT NULL
        ORDER BY plant_id, observed_at, id
        """,
        (group_id,),
    ).fetchall()
    growth_by_plant: dict[str, list[sqlite3.Row]] = {}
    for row in observations:
        growth_by_plant.setdefault(row["plant_id"], []).append(row)
    growth_rates = []
    for plant_id, points in growth_by_plant.items():
        if len(points) < 2:
            continue
        first = datetime.fromisoformat(points[0]["observed_at"])
        last = datetime.fromisoformat(points[-1]["observed_at"])
        elapsed_days = (last - first).total_seconds() / 86400
        if elapsed_days > 0:
            growth_rates.append(
                (float(points[-1]["height_cm"]) - float(points[0]["height_cm"])) / elapsed_days
            )
    water_l = water_row["water_l"] if water_row["water_records"] else None
    fresh_mass = harvest_row["fresh_mass_g"]
    dry_mass = (
        harvest_row["measured_dry_mass_g"]
        if harvest_row["harvest_count"] > 0
        and harvest_row["dry_mass_records"] == harvest_row["harvest_count"]
        else None
    )
    plant_count = harvest_row["plant_count"]
    return {
        "group_id": group_id,
        "group_name": group["name"],
        "treatment": group["treatment"],
        "measurements": {
            "water_added_l": round(water_l, 3) if water_l is not None else None,
            "harvest_count": harvest_row["harvest_count"],
            "harvested_plants": plant_count,
            "fresh_mass_g": round(fresh_mass, 3) if fresh_mass is not None else None,
            "dry_mass_g": round(dry_mass, 3) if dry_mass is not None else None,
            "fresh_yield_g_per_plant": (
                round(fresh_mass / plant_count, 3) if fresh_mass is not None and plant_count else None
            ),
            "fresh_water_use_efficiency_g_per_l": (
                round(fresh_mass / water_l, 3) if fresh_mass is not None and water_l and water_l > 0 else None
            ),
            "dry_water_use_efficiency_g_per_l": (
                round(dry_mass / water_l, 3) if dry_mass is not None and water_l and water_l > 0 else None
            ),
        },
        "growth": {
            "plants_with_multiple_height_observations": len(growth_rates),
            "mean_height_change_cm_per_day": (
                round(sum(growth_rates) / len(growth_rates), 4) if growth_rates else None
            ),
            "method": "Mean per-plant change between first and last recorded height divided by elapsed days.",
        },
    }


@router.get("/api/analysis/experiments/{experiment_id}")
async def analyze_experiment(experiment_id: int):
    with _connection() as connection:
        experiment = _require_experiment(connection, experiment_id)
        groups = connection.execute(
            "SELECT * FROM experiment_groups WHERE experiment_id = ? ORDER BY id",
            (experiment_id,),
        ).fetchall()
        return {
            "experiment": {
                "id": experiment["id"],
                "name": experiment["name"],
                "crop": experiment["crop"],
                "variety": experiment["variety"],
                "start_date": experiment["start_date"],
                "end_date": experiment["end_date"],
            },
            "groups": [_group_analysis(connection, group) for group in groups],
            "limitations": [
                "Water-use efficiency uses only water explicitly recorded for the group and harvest mass explicitly recorded.",
                "Fresh-mass and dry-mass efficiency are separate; dry-mass results remain unavailable until measured.",
                "Growth rates summarize first-to-last recorded plant heights and do not establish cause.",
                "These prototype calculations are not a validated standard crop-water-productivity measure.",
            ],
        }


@router.post("/api/habitat/readings", status_code=201)
async def add_habitat_reading(
    reading: HabitatReadingIn,
    x_device_token: str | None = Header(default=None, alias="X-Device-Token"),
):
    if reading.source_type == "esp32":
        from .main import verify_sensor_token

        verify_sensor_token(x_device_token)
    _require_measurement(
        reading,
        (
            "air_temperature_c",
            "relative_humidity_pct",
            "light_lux",
            "medium_moisture_pct",
            "water_added_l",
            "reservoir_level_l",
            "co2_ppm",
            "nutrient_ph",
            "nutrient_ec_ms_cm",
        ),
    )
    recorded_at = _utc_text(reading.recorded_at)
    now = _now().isoformat()
    sensor_types = [
        key
        for key in (
            "air_temperature_c",
            "relative_humidity_pct",
            "light_lux",
            "medium_moisture_pct",
            "water_added_l",
            "reservoir_level_l",
            "co2_ppm",
            "nutrient_ph",
            "nutrient_ec_ms_cm",
        )
        if getattr(reading, key) is not None
    ]
    with _connection() as connection:
        if reading.experiment_id is not None:
            _require_experiment(connection, reading.experiment_id)
        if reading.group_id is not None:
            if reading.experiment_id is None:
                raise HTTPException(status_code=422, detail="A group requires an experiment ID.")
            _require_group(connection, reading.experiment_id, reading.group_id)
        device = connection.execute(
            "SELECT sensor_types_json FROM sensor_devices WHERE device_id = ?",
            (reading.device_id,),
        ).fetchone()
        if device:
            known_types = set(_json_value(device["sensor_types_json"]))
            connection.execute(
                "UPDATE sensor_devices SET sensor_types_json = ?, updated_at = ? WHERE device_id = ?",
                (_json_text(sorted(known_types.union(sensor_types))), now, reading.device_id),
            )
        else:
            connection.execute(
                """
                INSERT INTO sensor_devices
                    (device_id, sensor_types_json, calibration_json, units_json, registered_at, updated_at)
                VALUES (?, ?, '{}', '{}', ?, ?)
                """,
                (reading.device_id, _json_text(sensor_types), now, now),
            )
        cursor = connection.execute(
            """
            INSERT INTO habitat_readings
                (device_id, experiment_id, group_id, source_type, recorded_at, air_temperature_c,
                 relative_humidity_pct, light_lux, medium_moisture_pct, water_added_l,
                 reservoir_level_l, co2_ppm, nutrient_ph, nutrient_ec_ms_cm, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                reading.device_id,
                reading.experiment_id,
                reading.group_id,
                reading.source_type,
                recorded_at,
                reading.air_temperature_c,
                reading.relative_humidity_pct,
                reading.light_lux,
                reading.medium_moisture_pct,
                reading.water_added_l,
                reading.reservoir_level_l,
                reading.co2_ppm,
                reading.nutrient_ph,
                reading.nutrient_ec_ms_cm,
                now,
            ),
        )
        return {"id": cursor.lastrowid, "device_id": reading.device_id, "recorded_at": recorded_at}


@router.get("/api/habitat/latest")
async def latest_habitat_reading(
    device_id: str = Query(..., min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
):
    with _connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM habitat_readings WHERE device_id = ?
            ORDER BY recorded_at DESC, id DESC LIMIT 1
            """,
            (device_id,),
        ).fetchone()
        device = connection.execute(
            "SELECT * FROM sensor_devices WHERE device_id = ?", (device_id,)
        ).fetchone()
    return {
        "device_id": device_id,
        "device": (
            {
                "sensor_types": _json_value(device["sensor_types_json"]),
                "calibration": _json_value(device["calibration_json"]),
                "units": _json_value(device["units_json"]),
            }
            if device
            else None
        ),
        "reading": dict(row) if row else None,
    }


@router.get("/api/sensor-devices")
async def list_sensor_devices():
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM sensor_devices ORDER BY device_id").fetchall()
    return [
        {
            "device_id": row["device_id"],
            "sensor_types": _json_value(row["sensor_types_json"]),
            "calibration": _json_value(row["calibration_json"]),
            "units": _json_value(row["units_json"]),
            "registered_at": row["registered_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]


@router.post("/api/sensor-devices", status_code=201)
async def register_sensor_device(device: SensorDeviceIn):
    now = _now().isoformat()
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO sensor_devices
                (device_id, sensor_types_json, calibration_json, units_json, registered_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(device_id) DO UPDATE SET
                sensor_types_json = excluded.sensor_types_json,
                calibration_json = excluded.calibration_json,
                units_json = excluded.units_json,
                updated_at = excluded.updated_at
            """,
            (
                device.device_id,
                _json_text(device.sensor_types),
                _json_text(device.calibration),
                _json_text(device.units),
                now,
                now,
            ),
        )
    return {"device_id": device.device_id, "updated_at": now}


@router.get("/api/crops")
async def list_crop_profiles():
    with _connection() as connection:
        rows = connection.execute("SELECT * FROM crop_profiles ORDER BY name").fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "scientific_name": row["scientific_name"],
            "description": row["description"],
            "nutrition": _json_value(row["nutrition_json"]),
            "references": _json_value(row["references_json"]),
        }
        for row in rows
    ]


@router.post("/api/crops", status_code=201)
async def create_crop_profile(profile: CropProfileIn):
    if profile.nutrition and not profile.references:
        raise HTTPException(
            status_code=422,
            detail="Nutrition values require at least one source reference.",
        )
    if any(not item.get("title", "").strip() or not item.get("url", "").strip() for item in profile.references):
        raise HTTPException(
            status_code=422,
            detail="Each crop reference must include a title and URL.",
        )
    if any(urlparse(item["url"]).scheme not in {"http", "https"} for item in profile.references):
        raise HTTPException(
            status_code=422,
            detail="Crop reference URLs must use HTTP or HTTPS.",
        )
    now = _now().isoformat()
    try:
        with _connection() as connection:
            cursor = connection.execute(
                """
                INSERT INTO crop_profiles
                    (name, scientific_name, description, nutrition_json, references_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.name.strip(),
                    profile.scientific_name.strip() if profile.scientific_name else None,
                    profile.description.strip() if profile.description else None,
                    _json_text(profile.nutrition),
                    _json_text(profile.references),
                    now,
                ),
            )
            profile_id = cursor.lastrowid
            row = connection.execute("SELECT * FROM crop_profiles WHERE id = ?", (profile_id,)).fetchone()
            return {
                "id": row["id"],
                "name": row["name"],
                "scientific_name": row["scientific_name"],
                "description": row["description"],
                "nutrition": _json_value(row["nutrition_json"]),
                "references": _json_value(row["references_json"]),
            }
    except sqlite3.IntegrityError as exc:
        raise HTTPException(status_code=409, detail="A crop profile with this name already exists.") from exc
