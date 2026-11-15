# Test Plan

## Manual tests
1. Health endpoint returns status ok.
2. Default Lira coordinates return a successful NASA response.
3. Kampala coordinates produce a separate query.
4. Start date after end date returns 400.
5. Latitude outside -90..90 returns 400.
6. Longitude outside -180..180 returns 400.
7. NASA timeout returns a clear 504.
8. NASA non-200 or invalid JSON returns a clear 502.
9. Missing NASA values are shown as gaps, not zero.
10. UI displays units, source, location, date range and retrieval timestamp.
11. Analysis excludes incomplete periods and reports insufficient history rather than inventing a trend.
12. Monthly anomalies compare only earlier complete observations from the same calendar month.
13. Trend output includes complete-year sample size, Mann–Kendall p-value and Sen's slope.
14. MODIS parsing accepts AppEEARS-scaled values, converts Kelvin to Celsius, and rejects failed quality flags.
15. MODIS requests clearly report missing NASA Earthdata credentials without blocking POWER analysis.
16. The text report is readable plain text and includes source provenance, summary statistics, analysis, rainfall-event screens, and point comparisons without dumping all daily observations or including sensor values.
17. A valid SoilSense payload is stored in SQLite and appears on the Farmer Dashboard under the matching device ID.
18. Sensor ingestion rejects missing/wrong tokens unless trusted-LAN demo mode is explicitly enabled.
19. Sensor payload validation rejects out-of-range ADC/moisture values and unsupported status values.
20. The Farmer Dashboard displays an empty state before the first reading and marks stale readings as not recently reporting.
21. The research workspace resolves a global place name and sends its selected coordinates to the live NASA POWER endpoint.
22. A new Farmer Dashboard profile automatically loads live weather for Lira, Uganda; selecting a different farm location updates and saves the weather coordinates.
23. Current conditions, recent 7-day weather and up to 7 forecast days display with Open-Meteo units and attribution.
24. The 12-month rainfall history displays valid-day coverage, and missing days break recent dry-spell runs.
25. Dashboard alerts and crop prompts remain informational and do not claim a precise planting date or irrigation schedule.
26. An experiment and its groups are created transactionally; end dates before start dates and duplicate group names are rejected.
27. Experiment readings, plant observations, harvests and habitat readings retain UTC timestamps, source IDs, units, and nulls for missing fields.
28. Group analysis uses only attributed water and harvest data; fresh and dry water-use metrics are separate, and incomplete dry-mass records do not produce a dry-mass total.
29. Habitat readings marked as ESP32-originated require the configured device token; manual readings remain available through the prototype UI.
30. Crop nutrition values are rejected unless a titled HTTP(S) source reference is provided.
31. Sensor metadata can store sensor types, calibration details and units without silently applying calibration.
32. The Space Crop Research workspace shows group-separated mean height history only when real observations exist and can export a report with methods and limitations.

## Scientific checks
- Check parameter names and units against NASA response metadata.
- Check the time standard is UTC.
- Confirm no missing-value sentinel is treated as a real measurement.
- Confirm monthly aggregation is labelled as calculated by EarthSignal.
- Confirm seasonal anomalies use a same-calendar-month historical baseline.
- Confirm trend interpretation describes historical evidence only and does not imply causation or forecast.
- Confirm the Field Monitor soil values are clearly marked illustrative and no live sensor data is claimed.
- Confirm sensor observations remain separate from NASA data and show the reported status, raw value, timestamp and device ID.
- Confirm device AP+STA connectivity, uploads and retry/offline behavior only after testing with the actual firmware and hardware.
- Confirm additional SHT31, BH1750, flow, CO2, pH or EC sensors only after wiring, calibration, firmware integration and hardware tests.
- Confirm deterministic explanations are not described as generative AI.
- Confirm experiment results are based on recorded measurements, and no placeholder or simulated plant results are presented as actual research.
- Confirm group-level water totals exclude readings without an explicit group assignment.
- Confirm lux is not labelled PPFD and Earth-based experiments are not described as microgravity results.

## Release gate
Do not present the app as working until at least one live request succeeds on the presentation machine.
