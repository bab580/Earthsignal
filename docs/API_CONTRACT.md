# API Contract

## GET /api/health

Response:
```json
{"status":"ok","service":"earthsignal"}
```

## GET /api/earth

Query:
- `latitude`: float, -90 to 90
- `longitude`: float, -180 to 180
- `start`: YYYY-MM-DD
- `end`: YYYY-MM-DD

Example:
`/api/earth?latitude=2.78&longitude=32.30&start=2020-01-01&end=2025-12-31`

Successful response (shape; actual values and units come from NASA):
```json
{
  "source": "NASA POWER Daily API",
  "source_url": "https://power.larc.nasa.gov/api/temporal/daily/point",
  "retrieved_at": "2026-11-10T12:00:00Z",
  "location": {"latitude": 2.78, "longitude": 32.30},
  "period": {"start": "2020-01-01", "end": "2025-12-31"},
  "parameters": {
    "PRECTOTCORR": {"unit": "from NASA response metadata"},
    "T2M": {"unit": "from NASA response metadata"}
  },
  "observations": [
    {"date": "YYYY-MM-DD", "PRECTOTCORR": 0.0, "T2M": 0.0}
  ],
  "summary": {
    "PRECTOTCORR": {"valid_count": 0, "missing_count": 0, "mean": null, "min": null, "max": null},
    "T2M": {"valid_count": 0, "missing_count": 0, "mean": null, "min": null, "max": null}
  },
  "analysis": {
    "PRECTOTCORR": {
      "coverage": {},
      "latest_month_anomaly": {"status": "insufficient_history"},
      "trend": {"status": "insufficient_history"}
    },
    "T2M": {
      "coverage": {},
      "latest_month_anomaly": {"status": "insufficient_history"},
      "trend": {"status": "insufficient_history"}
    }
  },
  "rainfall_events": {
    "threshold": null,
    "wet_day_count": 0,
    "high_rain_days": [],
    "dry_spells": []
  }
}
```

The example is a schema only; it is not measured data.

## GET /api/weather/locations

Query: `query` (2–120 characters). Searches global place names with Open-Meteo geocoding and returns candidate names, countries, coordinates and time zones. The Research workspace uses the selected coordinates for a live NASA POWER request; the Farmer Dashboard uses them to set the farm weather location.

## GET /api/weather

Query:
- `latitude`: float, -90 to 90
- `longitude`: float, -180 to 180

Returns Open-Meteo current conditions, up to 7 recent daily summaries, up to 7 forecast days, monthly rainfall totals for the previous 12 complete calendar months, and a recent dry-spell screen. Monthly values include valid-day coverage:
```json
{
  "source": "Open-Meteo",
  "retrieved_at": "UTC timestamp",
  "location": {"latitude": 2.25, "longitude": 32.90, "timezone": "Africa/Kampala"},
  "units": {"temperature": "°C", "precipitation": "mm", "wind_speed": "km/h"},
  "current": {
    "time": "local timestamp",
    "temperature": 0.0,
    "apparent_temperature": 0.0,
    "relative_humidity": 0,
    "precipitation_mm": 0.0,
    "weather_code": 0,
    "is_day": 1,
    "wind_speed": 0.0
  },
  "recent_days": [
    {
      "date": "YYYY-MM-DD",
      "weather_code": 0,
      "temperature_max": 0.0,
      "temperature_min": 0.0,
      "precipitation_mm": 0.0,
      "precipitation_probability_max": null,
      "wind_speed_max": 0.0
    }
  ],
  "forecast": [
    {
      "date": "YYYY-MM-DD",
      "weather_code": 0,
      "temperature_max": 0.0,
      "temperature_min": 0.0,
      "precipitation_mm": 0.0,
      "precipitation_probability_max": 0,
      "wind_speed_max": 0.0
    }
  ],
  "rainfall_history": [
    {"month": "YYYY-MM", "precipitation_mm": 0.0, "valid_days": 30, "days_in_month": 30}
  ],
  "recent_dry_spell": {
    "days": 0,
    "start": null,
    "as_of": "YYYY-MM-DD",
    "threshold_mm_per_day": 1.0
  },
  "history_period": {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}
}
```

Open-Meteo requires no API key. The Farmer Dashboard displays source attribution. Weather and rainfall context is advisory, not an official alert, crop calendar, crop-water-stress diagnosis or irrigation schedule.

Errors:
- 422: malformed queries or coordinates outside the accepted latitude/longitude ranges.
- 502: Open-Meteo returned an error or invalid response.
- 504: Open-Meteo timed out.

## Error responses
- 400: start date is after end date or the selected period exceeds 15 years.
- 422: malformed query values or coordinates outside the accepted latitude/longitude ranges.
- 502: NASA upstream returned an error or unexpected response.
- 504: NASA upstream timed out.

## GET /api/modis

Query parameters match `/api/earth`. Returns quality-screened point samples from NASA AppEEARS for MODIS NDVI (`MOD13Q1.061`) and daytime land-surface temperature (`MOD11A2.061`), including the retrieval time, provenance and historical analysis.

NASA Earthdata Login is free but required. Configure `NASA_EARTHDATA_USERNAME` and `NASA_EARTHDATA_PASSWORD` in the local `.env`; credentials are never sent to the browser.

Errors:
- 400: start date is after end date or the selected period exceeds 15 years.
- 422: malformed query values or coordinates outside the accepted latitude/longitude ranges.
- 502: AppEEARS authentication, task or response failure.
- 503: Earthdata credentials are not configured.
- 504: AppEEARS request or processing timed out.

## Sensor endpoints

### POST `/api/sensors/readings`

Accepts one ESP32 SoilSense observation and persists it in the local SQLite database. The firmware-calculated moisture percentage and status are stored as reported; EarthSignal does not calibrate or reinterpret them.

Request:
```json
{
  "device_id": "soilsense-01",
  "raw": 2380,
  "moisture": 41.5,
  "status": "MOIST",
  "recorded_at": "2026-11-12T18:35:00Z"
}
```

`recorded_at` is optional; if omitted, the server receive time is used. When supplied, timestamps without a timezone are treated as UTC. `device_id` is limited to letters, digits, dot, underscore and hyphen; `raw` must be 0–4095; `moisture` must be finite and 0–100; `status` must be `DRY`, `MOIST` or `WET`.

The endpoint requires the `X-Device-Token` header matching `EARTHSIGNAL_DEVICE_TOKEN`. If no token is configured, ingestion is disabled unless `EARTHSIGNAL_ALLOW_UNAUTHENTICATED_SENSOR_INGESTION=true` is explicitly set for a trusted local demo network.

Success response:
```json
{"accepted": true, "id": 1, "device_id": "soilsense-01", "recorded_at": "2026-11-12T18:35:00+00:00"}
```

Errors: 401 for a missing/incorrect configured token; 503 when ingestion is not configured; 422 for invalid payloads.

### GET `/api/sensors/latest`

Query: `device_id` (required). Returns the latest stored reading or `reading: null` if none exists.

### GET `/api/sensors/recent`

Query: `device_id` (required), `limit` (optional, 1–500; default 50). Returns recent readings in descending timestamp order.

The read endpoints are intended for the local prototype dashboard. Add user authorization before exposing farm data on a public deployment.

## Farmer SMS subscription

SMS delivery uses Africa's Talking, configured only on the backend with `AFRICASTALKING_USERNAME`, `AFRICASTALKING_API_KEY`, and `AFRICASTALKING_SANDBOX`. Provider credentials are never returned to the browser.

### POST `/api/sms/subscribe`

Requests a one-time verification code. Requires explicit consent and a phone number in E.164 format:
```json
{
  "phone": "+256700123456",
  "language": "en",
  "device_id": "soilsense-01",
  "location_name": "Lira, Uganda",
  "latitude": 2.2499,
  "longitude": 32.8998,
  "consent": true
}
```

Supported `language` codes are `en`, `lg`, `luo`, `ach`, `xog`, `nyn`, `myx` and `sw`. The language codes represent English, Luganda, Luo, Acholi, Lusoga, Runyankole, Lugisu/Lumasaba and Kiswahili. `consent` must be `true`. Codes expire after 10 minutes; requests are rate-limited per number and source address.

### POST `/api/sms/subscribe/confirm`

Confirms the phone number and enables daily SMS:
```json
{"phone": "+256700123456", "code": "123456"}
```

The background dispatcher sends one daily message containing the selected farm's next-seven-day rainfall total, current temperature and latest stored SoilSense status/moisture when available. It runs in the long-lived FastAPI process at `EARTHSIGNAL_SMS_SEND_HOUR_UTC` (default `5`, or 08:00 in Uganda). A persistent database and continuously running backend are required.

### POST `/api/sms/unsubscribe` and POST `/api/sms/unsubscribe/confirm`

The first endpoint sends a confirmation code to an active subscriber. The second accepts `{"phone": "+256700123456", "code": "123456"}` and disables daily delivery. Incoming `STOP` SMS handling is not implemented.

Local-language SMS strings are initial drafts; fluent speakers must review them before operational use. Daily SMS is informational and does not provide a planting calendar or irrigation instruction.

## Controlled-growing experiments

Experiment and habitat data are stored separately from NASA observations and farmer SoilSense readings. Every measurement timestamp is normalized to UTC; omitted timestamps use server receive time. Omitted measurement fields remain null.

### POST `/api/experiments`

Creates an experiment and its comparison groups in one transaction. Required fields: `name`, `crop`, `location`, `start_date`, `research_objective`, and one or more `groups`. Each group has a unique-per-experiment `name` and a `treatment`; `watering_plan` is optional. `variety` and `end_date` are optional.

### GET `/api/experiments` and GET `/api/experiments/{id}`

Lists experiments or returns one experiment with its groups. A missing ID returns 404.

### POST/GET `/api/experiments/{id}/readings`

Stores/retrieves timestamped measurements for an experiment. A reading may include `group_id`, `source_type` (`manual`, `esp32` or `other`), `source_id`, and any of:

| Field | Unit | Valid range |
|---|---|---|
| `air_temperature_c` | °C | -40 to 80 |
| `relative_humidity_pct` | % | 0 to 100 |
| `light_lux` | lux | 0 to 300000 |
| `medium_moisture_pct` | % | 0 to 100 |
| `water_added_l` | L | 0 or greater |

At least one measurement is required. Water must be assigned to an experiment group to be used in group-level water-use calculations.
When `source_type` is `esp32`, the request must include the configured `X-Device-Token` header.

### POST/GET `/api/experiments/{id}/observations`

Stores/retrieves plant-level observations: `group_id`, `plant_id`, optional `observed_at`, `height_cm`, `leaf_count`, `visible_stress`, `notes` and `image_reference`. At least height, leaf count or a non-empty visible-stress note is required. Image references are metadata only; uploaded image storage is not implemented.

### POST/GET `/api/experiments/{id}/harvests`

Stores/retrieves `group_id`, harvest time, `plant_count`, required `fresh_mass_g`, optional `dry_mass_g` and notes. Dry mass cannot exceed fresh mass.

### GET `/api/analysis/experiments/{id}`

Returns per-group water totals, harvest mass, yield per plant, fresh/dry water-use efficiency and first-to-last per-plant height-change rates. Water-use efficiency is `recorded biomass grams / recorded water litres`; it is unavailable if the relevant measurements are missing or water is zero. Dry-mass metrics remain unavailable unless every harvest record in that group has a dry-mass measurement. These are exploratory prototype calculations, not validated crop-water-productivity standards or causal findings.

## Habitat and resource readings

### POST `/api/habitat/readings`

Accepts `device_id`, optional `experiment_id` and `group_id`, `source_type`, optional `recorded_at`, and any measured fields: `air_temperature_c`, `relative_humidity_pct`, `light_lux`, `medium_moisture_pct`, `water_added_l`, `reservoir_level_l`, `co2_ppm`, `nutrient_ph` and `nutrient_ec_ms_cm`. Values have the same units as their field names (`°C`, `%`, `lux`, `L`, `ppm`, `pH`, `mS/cm`). At least one value is required. A group requires a matching experiment ID. Group-attributed water additions contribute to the corresponding experiment analysis.

Manual entries may use `source_type: "manual"`. Sensor submissions use `source_type: "esp32"` and must include the same `X-Device-Token` used by `/api/sensors/readings`. Other source types are recorded as supplied; deploy this prototype only on a trusted network.

### GET `/api/habitat/latest?device_id=...`

Returns the latest reading and registered sensor metadata for the device, or `reading: null` if no readings exist.

### GET/POST `/api/sensor-devices`

Lists or registers device metadata: `device_id`, `sensor_types`, `calibration` and `units`. Calibration values and units must describe the actual installed sensors; the API does not calibrate measurements automatically.

## Crop profiles

### GET/POST `/api/crops`

Lists or creates crop profiles with `name`, optional `scientific_name`, `description`, `nutrition` JSON object and `references` array. Nutrition values require at least one reference containing a `title` and HTTP(S) `url`. The service does not supply or infer nutrition values. Record the value's unit, crop/variety and measurement context in the submitted metadata.

## Device connectivity limits

An integration sketch copy is provided at `esp32/SoilSense_v1/SoilSense_v1.ino`; the original dashboard markup and local `/api` endpoint are preserved. The copy adds AP+STA mode and HTTP uploads, and a live reading has been observed from the connected ESP32. Upload retries are periodic; offline queueing, calibration and long-term reliability remain unverified.
