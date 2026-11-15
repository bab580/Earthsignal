# Controlled Growing Pilot Protocol

## Purpose

The initial EarthSignal experiment is a small, Earth-based pilot to record how different measured water inputs relate to edible-plant growth under otherwise similar indoor conditions. It is not a microgravity experiment, spacecraft habitat test, or validated crop-water-productivity study.

## Research question

How does water availability relate to plant growth and measured water-use efficiency when crop variety, growing medium, light schedule, and growing conditions are kept as similar as practical?

## Suggested pilot

- Select one fast-growing edible crop and record its species and variety.
- Create at least two groups, such as a consistently watered control and a reduced-water comparison.
- Use at least three plants per group when space permits. Assign stable plant IDs and record the actual number of plants.
- Keep seed batch, growing medium, container size, light schedule, and placement as similar as practical. Record unavoidable differences.
- Randomize or rotate container positions where appropriate to reduce position-related light or temperature differences.
- Define the water treatment before starting. Measure and log the water actually supplied to each group; do not substitute the intended amount for a missing measurement.
- Record the start date, location, objective, group treatment, watering plan, sensor source, units, and any calibration details.

## Observations

Record measurements at a consistent time and frequency, preferably daily:

- Air temperature in °C and relative humidity in %.
- Light in lux, with the lighting schedule. Lux is not PPFD and should not be reported as a direct plant-usable-light measurement.
- Growing-medium moisture as a sensor-reported value, with sensor identity and calibration method.
- Water added in litres, attributed to the appropriate experiment group.
- Plant height in centimetres, leaf count, and visible stress notes for each plant.
- At harvest, plant count and fresh mass in grams. Record dry mass only if the material was actually dried and weighed using a stated method.

Use blank/missing values when no measurement was made. Do not enter zero to mean unknown. Note sensor replacement, calibration, missed days, disease, pests, and other events that could affect results.

## Calculations in EarthSignal

- **Mean height change (cm/day):** for each plant with at least two height records, subtract its first recorded height from its last and divide by elapsed days. The group result is the mean of those per-plant rates.
- **Yield per plant (g/plant):** total recorded fresh harvest mass divided by total harvested plant count.
- **Fresh-mass water-use efficiency (g/L):** recorded fresh biomass divided by group-attributed recorded water.
- **Dry-mass water-use efficiency (g/L):** recorded dry biomass divided by group-attributed recorded water; shown only when every harvest record in the group includes dry mass.

These are descriptive pilot calculations. They do not account for unmeasured water losses, initial plant size, drainage, evaporation, environmental differences, or all possible confounders. Do not interpret group differences as proof that water alone caused the result. State whether biomass is fresh or dry and how water was counted in every report.

## Space-food research connection

Use NASA Veggie and Advanced Plant Habitat publications as scientific context and cite the exact source. For the ISS lettuce review, the NASA Technical Reports Server record [“Veggie: Space Vegetables for the International Space Station and Beyond”](https://ntrs.nasa.gov/citations/20160004060) describes the VEG-01 ‘Outredgeous’ red romaine crop grown aboard the ISS for 33 days. It notes watering challenges and analyses of returned samples but does not state directly comparable height, leaf-count or harvest-mass figures in its summary. The workspace explicitly labels those figures unavailable.

The related study [“Evaluating the lettuce metatranscriptome with MinION sequencing for future spaceflight food production applications”](https://doi.org/10.1038/s41526-021-00151-x) used lettuce grown under ISS-like conditions; do not describe it as an in-orbit crop result. Compare research questions and measurement methods, not environmental conditions as if Earth and microgravity were interchangeable. EarthSignal does not measure plant nutrient content; enter nutrition values only with a sourced reference describing units and crop/variety context. Laboratory analysis is needed to establish the nutrition of a harvested sample.

## Current hardware boundary

The current ESP32 sketch reads and uploads soil-moisture values only. The web API accepts additional habitat measurements, and the dashboard supports manual entry, but the SHT31, BH1750, flow meter, CO2, pH, and EC hardware has not been wired or validated by this software change. Lux does not equal PPFD. No experiment measurements or harvest results are preloaded.
