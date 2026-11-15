# Data Sources and Method

## 1. NASA POWER — initial live integration

Service: NASA POWER Daily API, point endpoint.

Endpoint:
`https://power.larc.nasa.gov/api/temporal/daily/point`

Initial variables:
- `PRECTOTCORR`: corrected precipitation parameter; verify exact unit and metadata returned by the API.
- `T2M`: 2-metre air temperature; verify exact unit and metadata returned by the API.

Community:
- `AG` (Agroclimatology)

Output:
- JSON

Time standard:
- UTC explicitly requested.

The daily API supports point time series and JSON responses. NASA POWER documentation states daily data extends from 1981 to near real time, subject to parameter availability and product latency.

Important wording:
NASA POWER is an analysis-ready data service for solar and meteorological variables. Do not label all its values as direct satellite measurements. Cite NASA POWER and the specific variable/product in reports.

## 2. Open-Meteo — farmer weather context

The Farmer Dashboard uses Open-Meteo's forecast API for current conditions, up to seven recent daily summaries and up to seven forecast days, its archive API for the prior 12 complete calendar months of daily precipitation, and its geocoding API for farm locations. No API key is required.

Recent daily summaries and the forecast are weather-model products, not measurements from a farm weather station. The dashboard refreshes its current conditions and forecast every 30 minutes while open; provider outages are shown as errors rather than replaced with sample values.

Monthly rainfall totals sum valid daily values and report the count of valid days in each month. The recent dry-spell screen counts consecutive available days below 1 mm/day; missing days break the sequence. Weather codes are presented as provider condition labels.

Forecasts, rainfall summaries and dashboard alerts provide context only. They are not official warnings, crop-specific planting calendars, diagnoses of crop-water stress or irrigation schedules. Check local forecasts, crop calendars, extension guidance and field conditions.

## 3. NASA AppEEARS / MODIS — optional vegetation and land-surface indicators

The point-sampling integration uses the NASA AppEEARS API and requires a free NASA Earthdata Login configured in the backend `.env` file. Credentials stay server-side.

Products and layers:
- `MOD13Q1.061` / `_250m_16_days_NDVI`: 16-day, 250 m vegetation index; product scale factor `0.0001`.
- `MOD11A2.061` / `LST_Day_1km`: 8-day, 1 km daytime land-surface temperature; product scale factor `0.02` yields Kelvin, then EarthSignal converts to Celsius.

AppEEARS returns these layer values with product scale factors already applied. EarthSignal applies quality screening to the associated QA layers and converts daytime LST from Kelvin to Celsius. Missing or rejected observations remain missing, never zero. These point samples represent MODIS grid cells, not farm-level crop health or soil conditions.

Official metadata endpoints:
- https://appeears.earthdatacloud.nasa.gov/api/product/MOD13Q1.061
- https://appeears.earthdatacloud.nasa.gov/api/product/MOD11A2.061
- https://appeears.earthdatacloud.nasa.gov/api/

## 4. GPM IMERG — planned rainfall enhancement

NASA GPM IMERG combines precipitation information from the GPM satellite constellation and provides a long historical record. NASA's current directory describes V07B coverage from January 1998 to present and approximately 0.1-degree / 10 km resolution.

Use cases:
- Regional rainfall grids.
- Spatial comparisons across districts.
- Historical precipitation analysis.

This integration is not part of the first runnable MVP because robust gridded data access, processing and spatial aggregation add complexity. It can be added after the live POWER path works.

Official references:
- https://gpm.nasa.gov/data/imerg
- https://gpm.nasa.gov/data/directory
- https://gpm.nasa.gov/resources/documents

## 5. Ground sensors — separate source

Initial hardware concept:
- ESP32 microcontroller
- Capacitive soil-moisture probe
- DS18B20 waterproof temperature probe
- Wi-Fi/phone hotspot for the first test

The website accepts a device ID, raw ADC value, firmware-calculated moisture percentage, DRY/MOIST/WET status and optional timestamp. It stores these separately from NASA observations. An integration sketch copy is in `esp32/SoilSense_v1/SoilSense_v1.ino`; a live reading has been observed from connected hardware. Coordinates, probe depth, sensor model and calibration metadata are not currently accepted by this endpoint.

A low-cost capacitive probe is not automatically a calibrated volumetric water-content instrument. Do not report a percentage as scientifically calibrated unless the sensor has been calibrated against the soil type and a reference method. The dashboard identifies it as the firmware-reported value.

## 6. Combining satellite and ground observations

Keep two separate data streams:
- `remote_observation`
- `ground_sensor_observation`

They can be compared by time and location, but they are not interchangeable. A satellite/grid value represents an area or modelled grid cell; a soil probe measures a small volume of soil at a specific depth.

## 7. Analysis methods in the MVP

- Valid and missing observation counts; mean, minimum and maximum.
- Monthly values are averages of valid source observations; only complete months meeting coverage requirements are included.
- A latest-month anomaly screen compares a complete calendar month's mean against the median and median absolute deviation of earlier complete values for that same calendar month. At least three earlier years are required; the robust-score threshold is 3.5.
- A trend test uses complete calendar-year means with at least 80% daily coverage for POWER and documented sample-coverage thresholds for MODIS composites. It reports the Mann–Kendall test and Sen's slope; p-values are exploratory and do not correct for serial autocorrelation.
- High-rainfall screening uses the 95th percentile of positive wet-day totals when at least 20 positive observations are available. Extended dry spells require at least 14 consecutive valid days below 1 mm/day; missing dates break a spell.
- Location comparisons use the selected NASA POWER point samples over the same dates. They are not district or region-wide spatial averages.
- Plain-language explanations are deterministic and generated from these calculations. They are not produced by a generative AI service.

Clearly label EarthSignal-calculated summaries. Do not imply these are NASA-published statistics, causal explanations, forecasts or farm-level recommendations.

## 8. Analysis limitations

The analysis is exploratory. The point sample does not represent a full district; vegetation and surface temperature can be affected by clouds, mixed land cover and product quality. An anomaly, rainfall screen or historical trend is a signal for further investigation, not proof of drought, flood, crop stress or a cause. Daily gridded rainfall does not establish short-duration intensity or local impacts.

## 9. Controlled-growing and habitat measurements

Experiment and habitat records are physical or manually entered measurements, not NASA observations or weather-provider data. Each record stores its source identifier, UTC-normalized timestamp, and values in named units: air temperature (°C), relative humidity (%), light (lux), medium moisture (%), water/reservoir volume (L), CO2 (ppm), nutrient pH, and electrical conductivity (mS/cm). Missing values remain null.

The current ESP32 sketch supplies soil moisture only. Additional habitat values can be entered manually or sent to the API, but the additional sensor drivers, calibration, wiring and reliability have not been implemented or verified. Lux is not PPFD. Calibration details may be attached to a sensor device, but the backend does not transform or correct readings using that metadata.

EarthSignal's controlled-growing calculations are descriptive:

- Per-plant height change is calculated from first and last recorded heights divided by elapsed days; the group value is the mean of available per-plant rates.
- Yield per plant is recorded fresh harvest mass divided by recorded harvested plant count.
- Fresh-mass and dry-mass water-use efficiency use the corresponding recorded biomass divided by group-attributed recorded water.
- Dry-mass metrics are omitted unless every harvest entry for that group has a dry-mass value.

The calculations do not account for evaporation, drainage, initial plant-size differences, or all confounders. They are not validated standard crop-water-productivity metrics and do not establish causality. Nutrition values are not inferred from sensors; crop-profile nutrition requires a reference. Cite NASA Veggie or Advanced Plant Habitat research when discussing space-crop relevance, and do not present Earth chamber experiments as microgravity evidence.

## 10. Published ISS crop research

The Space Crop Research workspace includes a literature-review summary based on the NASA Technical Reports Server record “Veggie: Space Vegetables for the International Space Station and Beyond” (Massa et al., 2016): https://ntrs.nasa.gov/citations/20160004060. The NASA record describes the VEG-01 ‘Outredgeous’ red romaine lettuce crop grown in the Veggie system aboard the ISS for 33 days, and reports watering challenges, food-safety analysis, and returned plant samples analyzed for chemistry. It does not provide directly comparable plant-height, leaf-count, or harvest-mass figures in its summary.

The review labels those unavailable measures rather than estimating them. The 33-day flight interval is study context, not a directly comparable growth result. EarthSignal's experiment records remain separate evidence; the workspace does not infer a Mars or microgravity outcome from Earth-grown plants.

A second, related source is Haveman et al. (2021), “Evaluating the lettuce metatranscriptome with MinION sequencing for future spaceflight food production applications,” *npj Microgravity*: https://doi.org/10.1038/s41526-021-00151-x. This work describes lettuce grown under ISS-like conditions and investigates a microbial-transcript monitoring method; it should not be mislabelled as an in-orbit crop result.
