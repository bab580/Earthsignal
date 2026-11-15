# Project File Structure

```text
earthsignal_mvp_starter/
├── README.md
├── MASTER_BUILD_PROMPT.md
├── requirements.txt
├── package.json
├── .env.example
├── .gitignore
├── backend/
│   ├── __init__.py
│   ├── earthsignal_sensors.sqlite3 (runtime database; ignored)
│   ├── tests/
│   │   ├── test_analysis.py
│   │   ├── test_appeears.py
│   │   ├── test_experiments.py
│   │   ├── test_sensors.py
│   │   ├── test_validation_notes.py
│   │   └── test_weather.py
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── analysis.py
│       ├── appeears.py
│       ├── weather.py
│       └── experiments.py
├── esp32/
│   └── SoilSense_v1/
│       ├── SoilSense_v1.ino
│       └── README.md
├── frontend/
│   ├── index.html
│   ├── styles.css
│   ├── app.js
│   ├── farmer.js
│   └── experiments.js
└── docs/
    ├── PRODUCT_BRIEF.md
    ├── DATA_SOURCES_AND_METHOD.md
    ├── ARCHITECTURE.md
    ├── API_CONTRACT.md
    ├── DEMO_RUNBOOK.md
    ├── TEST_PLAN.md
    └── experiment-protocol.md
```

The implementation is a single FastAPI app serving static Research, Farmer Dashboard and Space Crop Research views. Sensor, habitat and experiment records are stored in a runtime SQLite database, which is not committed.
