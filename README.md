# EarthSignal MVP — Texora Tech Solutions

A runnable, Uganda-first food-security and crop-research prototype with farmer weather context, SoilSense readings, and controlled Earth-based plant-growth experiments. NASA environmental data and space-crop studies provide supporting research context without treating Earth and space environments as equivalent.

The Farmer Dashboard includes an offline project Q&A guide, language choices for English, Luganda, Luo, Acholi, Lusoga, Runyankole, Lugisu (Lumasaba) and Kiswahili, and an opt-in daily SMS workflow. Local-language copy is an initial draft and must be reviewed by fluent speakers before operational use.

## What this MVP does

- Positions EarthSignal around Uganda food-security research and farmer support, with NASA data as supporting context.
- Lets a user select a Uganda quick location or search global cities and regions, then sends the selected coordinates to NASA POWER.
- Fetches real daily precipitation and air-temperature data from NASA POWER.
- Calculates historical seasonal anomalies and exploratory trends, then explains the evidence in plain language.
- Compares selected Uganda points for the same dates; these are point samples, not district or region-wide averages.
- Explores high-rainfall days and extended dry spells with transparent, period-specific screening thresholds, without treating them as proof of flooding or drought.
- Optionally retrieves quality-screened MODIS NDVI and daytime land-surface temperature through NASA AppEEARS.
- Displays a human-readable research brief, source attribution, data coverage and a downloadable plain-text evidence report with event and comparison details.
- Provides the Farmer Dashboard with Open-Meteo current conditions, recent 7-day weather, a 7-day forecast, and 12 complete months of rainfall history for the farm location.
- Combines forecast context with the selected crop and SoilSense state for cautious planting and irrigation prompts; dashboard alerts are informational, not automated instructions.
- Provides a controlled-growing research workspace for experiment groups, timestamped environmental readings, plant observations, harvest records, growth summaries and measured water-use calculations.
- Provides habitat/resource reading storage for temperature, humidity, light, medium moisture, water, reservoir level, optional CO2, nutrient pH and EC.
- Stores crop profiles and requires a titled URL reference when nutrition values are entered.
- Keeps observed NASA data separate from optional soil-sensor telemetry.
- Includes a Farmer Dashboard backed by SQLite sensor storage and a token-protected ESP32 ingestion API.
- Keeps sensor measurements separate from NASA observations and labels the moisture percentage as firmware-reported.
- Provides a clear path to add GPM IMERG precipitation grids later.

**Important:** NASA POWER is a NASA analysis-ready solar and meteorological data service. Do not describe every POWER variable as a direct satellite measurement. Identify the product and variable in the UI and methodology. The initial MVP does not claim to forecast drought, floods or crop yield.

## Fastest way to run

Requirements: Python 3.10+, `uv`, and `pnpm`.

```bash
pnpm install
pnpm start
```

Open http://127.0.0.1:3000. Use `pnpm dev` to enable backend auto-reload during development.

The app calls NASA POWER live when you press **Load NASA data**. Internet access is required. If NASA's service is unavailable, the app reports an error rather than silently substituting fake data.

MODIS is optional and requires a free NASA Earthdata Login. Copy `.env.example` to `.env` and set `NASA_EARTHDATA_USERNAME` and `NASA_EARTHDATA_PASSWORD` to enable it. Without credentials, POWER remains available and the dashboard explains that MODIS is not configured.

## Deploying to Render

The repository includes a Render Blueprint in `render.yaml`. In Render, create a **Blueprint** from this repository and apply the `earthsignal` web service. Render installs `requirements.txt`, runs the FastAPI app, serves the frontend and API from the same origin, checks `/api/health`, and mounts a persistent disk at `/var/data` for SQLite sensor and experiment records.

The Blueprint uses a paid Starter web service because the daily SMS dispatcher needs a continuously running process and the SQLite database needs a persistent disk. After deployment, open the service URL and check `/api/health`. Render generates `EARTHSIGNAL_DEVICE_TOKEN`; copy its value from the service's environment settings into the ESP32 configuration as `DEVICE_TOKEN`. Never expose this token in frontend code.

**Public-deployment limitation:** the current experiment, crop, and sensor read APIs do not require user authentication. Do not use this deployment for private or sensitive records, or treat it as production-ready, until application-level authentication and authorization have been added. Configure the sensor token only on the backend and ESP32; never put it in frontend code or public settings.

## ESP32 SoilSense integration

The Farmer Dashboard is available from the **Farmer Dashboard** navigation tab (or `/#farmer`). Farm details are stored in the browser. Sensor readings are stored in SQLite at `backend/earthsignal_sensors.sqlite3` by default; the path can be changed with `EARTHSIGNAL_SENSOR_DB`.

The Farmer Dashboard's project chat uses curated, built-in answers; it does not call an AI service or provide personalized farm advice. The language selector changes the dashboard labels, chat answers and SMS language. Translations are drafts and require review by fluent speakers of each language before farmers rely on them.

### Daily SMS for remote farmers

The Africa's Talking integration sends one opt-in daily information message with the farm's seven-day rainfall outlook, current temperature and latest available SoilSense reading. It is not a planting or irrigation instruction. A phone number must be in international format (for example `+256...`) and is verified by a one-time code before subscribing. Farmers can use a second verification code to unsubscribe in the dashboard.

Configure these variables on the **long-running FastAPI backend only**:

- `AFRICASTALKING_USERNAME`
- `AFRICASTALKING_API_KEY`
- `AFRICASTALKING_SANDBOX=true` with sandbox credentials during testing; use `false` with production credentials.
- `EARTHSIGNAL_SMS_SEND_HOUR_UTC=5` for the default 08:00 Uganda time. The background dispatcher checks every minute after the configured UTC hour and records each daily send to avoid routine duplicates.

Add the Africa's Talking username and API key to the Render service's environment settings when ready to enable SMS. Never put the SMS API key in frontend code. SMS provider charges may apply. The scheduler runs inside the FastAPI process, so keep the service continuously running and the SQLite database on persistent storage. The dashboard currently provides verified unsubscribe; inbound SMS `STOP` processing is not implemented.

Farmer weather uses the Open-Meteo forecast, archive and geocoding APIs; no API key is required. New profiles start with live weather for Lira, Uganda. Find a different farm location in Farm details to update the forecast. Weather refreshes automatically, and forecasts and weather-derived alerts are contextual, not an official warning or irrigation schedule. The location is saved with the farm profile in this browser.

Set a unique `EARTHSIGNAL_DEVICE_TOKEN` in `.env`. The ESP32 must POST to `/api/sensors/readings` using the JSON contract in [docs/API_CONTRACT.md](docs/API_CONTRACT.md) and send the token in the `X-Device-Token` header. The dashboard device ID must match the JSON `device_id`.

For a trusted local-network demo only, unauthenticated ingestion can be enabled explicitly with `EARTHSIGNAL_ALLOW_UNAUTHENTICATED_SENSOR_INGESTION=true`. Do not expose that setting on a public server. Read endpoints are also intended for the local prototype and need user authorization before public deployment.

An integration sketch copy is in [esp32/SoilSense_v1/SoilSense_v1.ino](esp32/SoilSense_v1/SoilSense_v1.ino). It preserves the supplied local dashboard and `/api`, adds AP+STA mode and sends readings every 10 seconds when configured. A live reading has been received from the connected ESP32. Follow [esp32/SoilSense_v1/README.md](esp32/SoilSense_v1/README.md) for setup details; calibration and offline buffering are not validated or implemented.

## Controlled growing research

Open **Space Crop Research** to create a study with control/comparison groups, record environmental measurements, track individual plant height/leaf observations, enter harvest masses, review a group-comparison growth chart and water-use calculations, and download an evidence report. Habitat readings can be entered manually or submitted through `/api/habitat/readings`. The API also supports crop profiles and sensor calibration/unit metadata; nutrition values require a titled URL reference.

Results use only values actually recorded. Missing values remain null, not zero. Fresh-mass and dry-mass water-use efficiency are reported separately, and dry-mass results remain unavailable unless every recorded harvest in the group includes dry mass. The calculation is an exploratory prototype measure, not a validated standard crop-water-productivity metric. See [docs/experiment-protocol.md](docs/experiment-protocol.md) for a repeatable pilot method.

**Hardware boundary:** the current ESP32 sketch still reads only its analog soil-moisture probe and uploads the existing SoilSense payload. Temperature/humidity, light, water-flow, CO2, pH and EC readings are supported by the backend/manual habitat form but are not yet wired or implemented in the sketch. Lux is not PPFD. No physical experiment or harvest result is included by default, and Earth-based tests do not reproduce microgravity.

## Suggested hackathon demo

1. Open the dashboard.
2. Select a Uganda quick location or search for a place anywhere in the world.
3. Select a date range, e.g. 2020-01-01 to 2025-12-31.
4. Load NASA data.
5. Show the source, variables, units, data coverage and chart.
6. Compare a second location.
7. Open **Space Crop Research**, define a control and comparison group, and show that measured water and harvest data are needed before WUE appears. Do not present an empty state as a completed experiment.
8. Open the Farmer Dashboard and explain the reported sensor value, status and last-seen time. Until the integration sketch is configured and uploaded to an ESP32, demonstrate the no-reading state rather than treating sample values as live.

## Data integrity rules

- Never fabricate or interpolate missing NASA observations without explicitly labelling the method.
- Preserve the NASA POWER parameter name, units, coordinates, date range and retrieval timestamp.
- POWER's daily endpoint supports time series and JSON responses. Confirm parameter availability and units from the response metadata/API documentation.
- The current frontend labels precipitation as `PRECTOTCORR` and temperature as `T2M`; display the returned units from the API response where available.
- A satellite/reanalysis grid cell is not a farm-level soil measurement.
- Point comparisons are not administrative-boundary or district-wide averages.
- The rainfall event explorer screens daily positive rainfall at or above the selected period's 95th percentile when at least 20 positive wet days are available. An extended dry spell is at least 14 consecutive valid days below 1 mm/day. These are exploratory screens, not observed flood or drought impacts; daily data do not establish short-duration rainfall intensity or causality.
- A soil sensor reading is not a NASA observation.
- Do not call historical trend detection a forecast.
- Treat anomalies and historical trends as exploratory evidence for further investigation, not predictions, causal findings or farm-level advice.
- Plain-language explanations are deterministic statistical summaries, not generative-AI output.

## Project status

This package contains a runnable environmental-data prototype with historical statistical analysis, rainfall-event screening, point comparisons, farmer weather context, sensor ingestion, controlled-growing experiment records and an ESP32 integration sketch. MODIS access requires local NASA Earthdata credentials. The new experiment calculations need real, carefully collected data before they can support research conclusions. Earth-based tests do not reproduce microgravity, and the platform is not a validated operational climate-risk or agricultural advisory service.
