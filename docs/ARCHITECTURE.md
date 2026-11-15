# Architecture

```text
Browser
  |
  | HTTPS / local HTTP during demo
  v
FastAPI application
  |-- / or /#experiments  Space Crop Research workspace
  |-- /#research         Environmental research dashboard
  |-- /#farmer           Farmer Dashboard
  |-- /api/health       health check
  |-- /api/earth        validates query and requests NASA POWER
  |-- /api/modis        authenticates with NASA Earthdata and samples MODIS via AppEEARS
  |-- /api/weather      requests current conditions, forecast and rainfall history from Open-Meteo
  |-- Farmer weather falls back to direct browser requests if the weather API fails
  |-- /api/weather/locations  searches global place names through Open-Meteo geocoding
  |-- /api/sensors/readings  validates and stores ESP32 readings in SQLite
  |-- /api/sensors/latest    retrieves the latest reading for a device
  |-- /api/sensors/recent    retrieves recent readings for a device
  |-- /api/experiments       creates and lists controlled-growing studies
  |-- /api/experiments/{id}/readings     stores experiment measurements
  |-- /api/experiments/{id}/observations stores plant-growth observations
  |-- /api/experiments/{id}/harvests     stores measured harvests
  |-- /api/analysis/experiments/{id}     calculates descriptive growth and WUE metrics
  |-- /api/habitat/readings              stores habitat/resource measurements
  |-- /api/habitat/latest                retrieves latest habitat reading
  |-- /api/sensor-devices                stores sensor types, calibration and units
  |-- /api/crops                         stores crop profiles and sourced nutrition
  |
  +--> NASA POWER Daily Point API
  |
  +--> NASA AppEEARS --> MOD13Q1 NDVI + MOD11A2 daytime LST
  |
  +--> Open-Meteo --> forecast, historical rainfall and geocoding
  |
  +--> SQLite --> experiments, groups, readings, plant observations, harvests,
                  habitat readings, sensor metadata and crop profiles
  |
  v
Normalized response
  |-- location and period
  |-- parameter names and units
  |-- daily observations
  |-- EarthSignal anomaly/trend analysis
  |-- retrieval timestamp and source
  |
  +--> Browser charts + historical signals + downloadable plain-text report

Separate sensor path:
ESP32 + calibrated soil probes
  |
  | POST JSON with X-Device-Token
  v
/api/sensors/readings
  |
  +--> SQLite sensor_readings table
          |
          +--> Farmer Dashboard polling /api/sensors/latest
          +--> Farmer Dashboard weather context and informational alerts

Controlled experiment path:
Manual measurements or supported sensor clients
  |
  | timestamped values with source and units
  v
/api/experiments/... or /api/habitat/readings
  |
  +--> SQLite experiment/habitat tables
          |
          +--> Space Crop Research workspace and descriptive analysis
```

If `/api/weather` fails, the Farmer Dashboard retries the public Open-Meteo forecast and archive APIs directly from the browser; no API key is required.

## Design choices
- A single FastAPI service keeps the first release simple.
- NASA calls and NASA Earthdata credentials stay server-side.
- The browser receives normalized JSON, not raw upstream response internals.
- Sensor telemetry remains separate from NASA environmental data and is stored in SQLite.
- An integration sketch copy at `esp32/SoilSense_v1/SoilSense_v1.ino` preserves the supplied dashboard and local `/api`, and adds AP+STA plus periodic HTTP uploads. A live reading has been observed from connected hardware; offline queueing is not implemented.
- Configure `EARTHSIGNAL_DEVICE_TOKEN` to protect sensor ingestion. Unauthenticated ingestion is disabled by default; enable it only for a trusted local demo network.
- The Farmer Dashboard farm profile is saved in browser local storage. It is not a user account or server-side farm record.
- Earthdata credentials are free to obtain but must be configured locally; MODIS data is explicitly unavailable until configured.
- Open-Meteo weather data is separate from sensor readings; forecast-based guidance is informational and not a locally validated crop calendar or irrigation schedule.
- Statistical explanations use deterministic methods without a paid generative-AI endpoint. A no-cost model is not assumed to be installed or available.
- SQLite is used for the current prototype sensor readings. A production deployment should use managed storage, backups, retention policies and authenticated user access.
- Experiment and habitat measurements are stored separately from NASA and farmer sensor records. Blank measurements remain null; the service does not infer a value from another source.
- Group-level fresh/dry water-use calculations require measured harvest mass and group-attributed water additions. They are exploratory metrics, not validated crop-water-productivity standards.
- Manual habitat logging is implemented. The current ESP32 firmware still reports only soil moisture; additional sensors require wiring, calibration, firmware drivers and on-device validation.
- Crop nutrition is not inferred by sensors. Nutrition data entered in a crop profile must have a titled URL reference.
