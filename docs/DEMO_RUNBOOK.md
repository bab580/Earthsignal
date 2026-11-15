# Hackathon Demo Runbook

## 3-minute demo

### 0:00–0:30 — Research problem
“Food production depends on environmental conditions and efficient resource use. EarthSignal connects environmental evidence with controlled plant-growth research, without treating Earth farms as microgravity environments.”

### 0:30–1:20 — Space Crop Research
- Start on **Space Crop Research**, the primary demonstration page.
- Show how to define a crop study and control/reduced-water groups.
- Explain the required measurements: group-attributed water, per-plant growth, and measured harvest mass.
- Use the honest empty state unless an actual experiment has supplied data.

### 1:20–2:00 — Live NASA data
- Open **Research**.
- Open EarthSignal.
- Select Lira.
- Set a date range.
- Click Load NASA data.
- Point out the live source label, coordinates, variable codes, units and retrieval timestamp.

### 2:00–2:25 — Farmer and habitat monitoring
- Show the Farmer Dashboard and its separate SoilSense/weather data.
- Show the habitat entry form; distinguish manual entries from actual connected sensors.

### 2:25–3:00 — Evidence and limits
- Switch to Kampala or Gulu.
- Load again.
- Compare the returned time series and explain that NASA POWER values are grid data and summaries are calculated by EarthSignal.
- If an updated ESP32 is available, show its actual reported raw and moisture values; troubleshoot router/backend/token if none arrive.
- State that the app supports investigation, not an official forecast, automated farm advisory, completed experiment result, or microgravity experiment.

## Before presenting
- Test the NASA API from the actual demo network.
- Test two locations.
- Confirm data units in metadata.
- Confirm the displayed retrieval time is recent.
- Keep a backup screenshot of a previously retrieved real response, labelled with its original retrieval date. Never label a screenshot as live.
- Do not use sample/mock values in the live data path.
- Use a unique `EARTHSIGNAL_DEVICE_TOKEN` and keep unauthenticated ingestion disabled except on a trusted local demo network.
- If the physical growing experiment has not completed, demonstrate study setup and the no-harvest state instead of claiming completed results.
- The current ESP32 sketch reports soil moisture only. Do not present temperature, humidity, light, water-flow, CO2, pH or EC as live hardware readings unless the corresponding sensor and firmware have been tested.
