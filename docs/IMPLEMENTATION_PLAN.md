# EarthSignal implementation plan

## Direction from the November 14 meeting

Center EarthSignal on Uganda's food-security needs. NASA environmental data and space-crop research should strengthen the research story, not displace the farmer use case. Preserve the existing workspaces and IoT device; do not make new sensors a prerequisite for the lettuce demonstration.

The initial demonstration should use measured lettuce growth and resource inputs. The meeting notes identify a container demonstration, limited monitoring capacity, soil-moisture sensors as the available hardware, and other measurements as unavailable for now. Record unavailable measurements manually only when actually measured; otherwise leave them blank.

## Current implementation and gaps

| Requirement | Current state | Work still needed |
|---|---|---|
| Farmer Dashboard and Uganda weather context | Implemented in [farmer.js](../frontend/farmer.js), supported by the weather endpoints in [main.py](../backend/app/main.py). | Reframe the product copy around Uganda food security. Current weather prompts are informational, not validated crop-calendar advice. |
| Existing SoilSense device | Soil-moisture ingestion, token validation, storage, and dashboard display exist. The firmware reports soil moisture only. | Keep this hardware path. Do not present temperature, humidity, light, or water flow as live device data until corresponding hardware is installed and tested. |
| Controlled crop study | Experiment groups, environmental readings, plant observations, harvests, analysis, and reports are implemented in [experiments.py](../backend/app/experiments.py) and [experiments.js](../frontend/experiments.js). | Run and record the real lettuce study. Do not add a second experiment system or seed results. |
| Earth and space-crop comparison | A NASA ISS lettuce literature review now appears beside, but separately from, selected Earth experiment measurements in [index.html](../frontend/index.html) and [experiments.js](../frontend/experiments.js). Sources and unavailable values are documented in [Data Sources and Method](./DATA_SOURCES_AND_METHOD.md). | Keep citations current; preserve the distinction between actual ISS-grown crops and separate ground-based ISS-like studies. |
| Dry-/wet-season farmer guidance | Weather and SoilSense context with cautious prompts exists. | Define and source any crop-selection, rotation, soil-fertility, or seasonal guidance before presenting it as actionable advice. |
| SMS updates | Not implemented; notification delivery is explicitly outside the current MVP. | Design rules and consent first, then select a Uganda-supported SMS provider and add delivery history/status. Keep provider credentials server-side. |
| Judge presentation | Existing research and experiment evidence reports are available. | Prepare a demo around actual records and honest empty states. A protected read-only judge mode requires an authentication approach; the current app has no user accounts. |

## Ordered work

### Phase 0 — Align project wording

- Make the Uganda food-security use case primary in the product brief and user-facing introduction.
- Describe NASA and space-crop work as supporting research context.
- Keep the current NASA environmental research workspace and farmer dashboard; do not replace either.
- Keep SMS marked as planned work, not an existing feature.

**Complete when:** project documentation and the first screen describe the same Uganda-first purpose without claiming capabilities that are not implemented.

### Phase 1 — Run the lettuce pilot with available equipment

- Confirm the crop, variety, setup date, treatment, and safe watering range with the team.
- Prefer a control and reduced-water group with the same variety, growing medium, container conditions, and light. If the available plants or monitoring capacity do not support a fair comparison, demonstrate a single-group growth record instead and do not claim a treatment effect.
- Use the existing ESP32 for soil moisture only. Record other readings by hand only when measured; leave unmeasured values blank.
- Record plant IDs, height, leaves, visible stress, water actually supplied, and harvest mass when available. Do not enter expected values as observed results.
- Follow the existing [experiment protocol](./experiment-protocol.md); refine it for the actual container and team capacity before the study starts.

**Complete when:** the team can show a real, timestamped lettuce record in the existing Space Crop Research workspace and explain its method and limitations.

### Phase 2 — Verify the existing research workflow

- Exercise experiment creation, environmental entry, plant observations, harvest records, growth chart, and study report using the pilot's real records.
- Confirm each value retains its source, time, unit, and group; missing measurements remain missing.
- Keep group comparisons descriptive. Do not claim that water alone caused a growth difference.

**Complete when:** the UI and report match the recorded data and can be reproduced from the SQLite-backed API.

### Phase 3 — Add the NASA space-crop research reference (implemented)

- Add a small reference section to the existing study workspace rather than building another dashboard.
- Cite specific NASA Veggie and Advanced Plant Habitat publications with title, URL, publication date, and the relevant finding or method.
- Compare research questions and methods, not Earth and Mars environmental conditions as if they were equivalent.
- Show Earth experiment measurements and NASA-published findings in separate, source-labelled sections. Do not invent matching values.
- Do not imply the Earth lettuce study is conducted on Mars, in microgravity, or in a spacecraft.

**Complete:** the experiment workspace cites NASA's VEG-01 ISS lettuce record, summarizes its 33-day flight test and watering challenges, and shows recorded Earth experiment values separately. It marks plant-height and harvest values absent from the NASA summary as unavailable. A separate ISS-like, ground-based lettuce study is labelled as such.

### Phase 4 — Extend farmer guidance, then SMS

- First document and review the weather/soil rules for dry-season reminders and wet-season crop-selection or rotation guidance. Keep prompts advisory and source them to suitable local agronomic guidance.
- Before sending messages, choose an SMS provider that supports Uganda, message languages and timing, consent/opt-out handling, phone validation, and retention requirements.
- Implement server-side alert rules and a notification history with delivery status before connecting provider delivery. Keep credentials off the browser and do not send without recorded consent.
- Add the SMS controls to the Farmer Dashboard only after the backend flow and consent experience are agreed.

**Complete when:** tests cover the alert conditions, consent/opt-out, provider failures, and delivery status, and the app can distinguish queued, sent, failed, and not-consented messages.

### Phase 5 — Judge-ready demonstration

- Use the actual lettuce records, methodology, source references, and a live SoilSense reading if the hardware is connected.
- Show empty states for measurements or SMS delivery that have not happened.
- Do not expose device tokens, credentials, or private farmer details. Do not make the prototype public without authentication for farm and device data.
- Add read-only judge access only after choosing an authentication approach; no such account system currently exists.

## Where changes belong

| Change | Existing location |
|---|---|
| Product positioning and roadmap | [Product brief](./PRODUCT_BRIEF.md), [README](../README.md), and the hero/navigation text in [index.html](../frontend/index.html) |
| Lettuce setup and measurement method | [Experiment protocol](./experiment-protocol.md) and the existing experiment forms in [index.html](../frontend/index.html) |
| Study records, chart, and NASA reference section | [experiments.js](../frontend/experiments.js); only extend [experiments.py](../backend/app/experiments.py) if the reference or study metadata needs persistent fields |
| NASA research provenance | [Data sources and method](./DATA_SOURCES_AND_METHOD.md), [API contract](./API_CONTRACT.md), and the existing research UI in [app.js](../frontend/app.js) |
| Farmer prompts and eventual SMS controls | [farmer.js](../frontend/farmer.js); the weather and sensor APIs in [main.py](../backend/app/main.py); add a dedicated notification module only after provider and consent decisions |
| ESP32 capabilities | [SoilSense_v1.ino](../esp32/SoilSense_v1/SoilSense_v1.ino) and its [README](../esp32/SoilSense_v1/README.md). Keep the current moisture-only path unless new hardware is available and validated. |
| Automated verification | Existing [test_experiments.py](../backend/tests/test_experiments.py), [test_sensors.py](../backend/tests/test_sensors.py), and [test_weather.py](../backend/tests/test_weather.py); add focused notification tests with SMS work |
| Judge flow | [Demo runbook](./DEMO_RUNBOOK.md) and [test plan](./TEST_PLAN.md) |

## Decisions needed before implementation expands

1. Is the lettuce study a two-group comparison, or should the first demonstration be a single-group observation because of plant/monitoring limits?
2. Which Uganda-supported SMS provider, languages, consent wording, and delivery schedule should be used?
3. Should judge access be a local demo-only view or a real read-only account behind authentication?

Until these are decided, do not implement SMS delivery, claim causal crop results, or add hardware-dependent readings.
