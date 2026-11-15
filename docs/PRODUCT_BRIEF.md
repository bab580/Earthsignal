# Product Brief — EarthSignal Uganda Food Security MVP

## Name
EarthSignal — Uganda Food Security and Earth–Space Crop Research

## One-line description
EarthSignal supports Uganda food-security research and farmer decision support with local weather, SoilSense readings, and recorded crop experiments. NASA environmental data and space-crop research add supporting context.

## Problem
Farmers and research teams need accessible, locally relevant context for food-security challenges, including changing weather and crop resource use. Environmental datasets can be difficult for non-specialists to locate and interpret, while field observations need to be recorded with clear sources, units and limitations.

## Target users
- Ugandan farmers and agricultural extension organisations
- Food-security and agricultural research teams
- Environmental NGOs
- Universities and student researchers
- Local planning teams

## Initial use case
A farmer or researcher views weather context and the existing SoilSense moisture reading, then records actual crop-study measurements in the Space Crop Research workspace. A Uganda location can also be selected in the Research workspace to retrieve NASA POWER rainfall and air-temperature data; optional MODIS samples provide separate environmental context. A small Earth-based lettuce study can compare recorded growth and water inputs when the team has enough plants and measurements. NASA space-crop publications support the research framing but are not treated as measurements of the Earth experiment.

The existing Space Crop Research workspace records experiment groups, environmental readings, plant observations, harvest mass, descriptive growth and water-use calculations, habitat readings and sourced crop profiles. It supports research on resource-efficient food production while keeping Earth-based evidence distinct from actual microgravity research.

## MVP scope
Included:
- Five preset Ugandan locations
- Global place search using geocoded coordinates
- Date range selection
- Live NASA POWER request
- Precipitation and temperature time series
- Optional NASA AppEEARS MODIS NDVI and land-surface temperature point samples
- Historical same-month anomaly screening
- Mann–Kendall trend test and Sen's slope on complete calendar years
- Plain-language, rule-based evidence explanations
- Downloadable plain-text evidence report with methods, event screens and point comparisons
- Source and metadata display
- Farmer Dashboard with browser-local farm details
- Live current weather, recent 7-day weather, a 7-day forecast and 12 complete months of rainfall for the saved farm location through Open-Meteo
- Contextual planting/irrigation prompts and dashboard alerts based on forecast and live SoilSense status
- SoilSense-compatible sensor ingestion and SQLite persistence
- Latest sensor reading and connection status
- Controlled-growing experiments with treatment groups, readings, plant observations and harvest records
- Habitat/resource measurements with source, timestamp and units
- Crop profiles that require references for nutrition values
- Group-level descriptive growth and fresh/dry water-use calculations
- Group-comparison plant-height chart and downloadable experiment evidence report
- Error handling

Not implemented in the current MVP:
- Drought/flood forecasting
- Crop-yield prediction
- Automated irrigation recommendations
- Production-grade soil-sensor network
- Verified SHT31, BH1750, flow, CO2, pH or EC wiring and calibration
- Completed physical plant-growth study or harvest outcome
- Microgravity or spacecraft life-support testing
- Offline queueing, production device provisioning and hardware validation
- User accounts and payments
- SMS or national-scale notification delivery (planned follow-up; SMS consent, provider and delivery workflow must be designed first)
- Generative AI service; the no-cost MVP uses transparent deterministic explanations instead

Weather-based prompts are advisory only. They do not determine exact planting dates, diagnose crop-water stress or control irrigation; consult local crop calendars, extension services and field conditions.
Experimental metrics are exploratory, depend on complete real measurements, and are not validated agronomic standards. Earth-based chamber results do not reproduce microgravity.

## Value proposition
An Uganda-first food-security research and farmer-support platform that keeps local observations, weather context and NASA research traceable and separate.

## Success criteria
- The product presents Uganda food security as the primary goal and NASA/space-crop research as supporting context.
- The team can record and explain a real lettuce pilot without presenting missing or simulated values as results.
- A judge can retrieve real data live during the demo.
- Every chart has source, variable, unit, location and date range.
- Switching locations changes the upstream query and results.
- API failures are visible and do not create fake values.
- Anomaly and trend results expose their baseline, method, sample size and limitations.
- MODIS indicators are unavailable rather than fabricated when Earthdata credentials are not configured.
- The team can explain what the data does and does not establish.

See the [implementation plan](./IMPLEMENTATION_PLAN.md) for the ordered work, current gaps, and file-level change map.
