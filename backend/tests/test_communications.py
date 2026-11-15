import asyncio
import re
import sqlite3
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.app import communications
from backend.app import main as app_module


def configure_communications(tmp_path, monkeypatch):
    database = tmp_path / "communications.sqlite3"
    monkeypatch.setattr(app_module, "SENSOR_DB", database)
    monkeypatch.setattr(communications, "AFRICASTALKING_USERNAME", "test-user")
    monkeypatch.setattr(communications, "AFRICASTALKING_API_KEY", "test-api-key")
    return database


def test_sms_subscription_requires_verified_opt_in_and_supports_unsubscribe(
    tmp_path, monkeypatch
):
    configure_communications(tmp_path, monkeypatch)
    monkeypatch.setattr(communications, "OTP_RESEND_DELAY", timedelta(0))
    monkeypatch.setattr(communications.secrets, "randbelow", lambda _: 123456)
    sent_messages = []

    async def fake_send_sms(phone, message):
        sent_messages.append((phone, message))

    monkeypatch.setattr(communications, "send_sms", fake_send_sms)
    payload = {
        "phone": "+256700123456",
        "language": "sw",
        "device_id": "soilsense-01",
        "location_name": "Lira, Uganda",
        "latitude": 2.2499,
        "longitude": 32.8998,
        "consent": True,
    }

    with TestClient(app_module.app) as client:
        response = client.post("/api/sms/subscribe", json=payload)
        assert response.status_code == 200
        subscribe_code = re.search(r"\b\d{6}\b", sent_messages[-1][1]).group()

        response = client.post(
            "/api/sms/subscribe/confirm",
            json={"phone": payload["phone"], "code": "000000"},
        )
        assert response.status_code == 400

        response = client.post(
            "/api/sms/subscribe/confirm",
            json={"phone": payload["phone"], "code": subscribe_code},
        )
        assert response.status_code == 200
        assert response.json()["subscribed"] is True

        with sqlite3.connect(tmp_path / "communications.sqlite3") as connection:
            row = connection.execute(
                "SELECT language, device_id, location_name, active FROM sms_subscriptions WHERE phone = ?",
                (payload["phone"],),
            ).fetchone()
        assert row == ("sw", "soilsense-01", "Lira, Uganda", 1)

        response = client.post("/api/sms/unsubscribe", json={"phone": payload["phone"]})
        assert response.status_code == 200
        unsubscribe_code = re.search(r"\b\d{6}\b", sent_messages[-1][1]).group()

        response = client.post(
            "/api/sms/unsubscribe/confirm",
            json={"phone": payload["phone"], "code": unsubscribe_code},
        )
        assert response.status_code == 200
        assert response.json()["unsubscribed"] is True

        with sqlite3.connect(tmp_path / "communications.sqlite3") as connection:
            active = connection.execute(
                "SELECT active FROM sms_subscriptions WHERE phone = ?",
                (payload["phone"],),
            ).fetchone()[0]
        assert active == 0


def test_sms_subscription_requires_consent_and_configured_provider(tmp_path, monkeypatch):
    configure_communications(tmp_path, monkeypatch)
    monkeypatch.setattr(communications, "AFRICASTALKING_USERNAME", "")
    with TestClient(app_module.app) as client:
        payload = {
            "phone": "+256700123456",
            "language": "en",
            "device_id": "soilsense-01",
            "location_name": "Lira, Uganda",
            "latitude": 2.2499,
            "longitude": 32.8998,
            "consent": False,
        }
        response = client.post("/api/sms/subscribe", json=payload)
        assert response.status_code == 422

        payload["consent"] = True
        response = client.post("/api/sms/subscribe", json=payload)
        assert response.status_code == 503


def test_daily_sms_uses_weather_and_latest_sensor_only_once(tmp_path, monkeypatch):
    database = tmp_path / "daily-sms.sqlite3"
    communications.init_communications_db(database)
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            CREATE TABLE sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                device_id TEXT NOT NULL,
                raw INTEGER NOT NULL,
                moisture REAL NOT NULL,
                status TEXT NOT NULL,
                recorded_at TEXT NOT NULL,
                received_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "INSERT INTO sms_subscriptions "
            "(phone, language, device_id, location_name, latitude, longitude, consented_at, active) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
            ("+256700123456", "en", "soilsense-01", "Lira, Uganda", 2.2499, 32.8998, "now"),
        )
        connection.execute(
            "INSERT INTO sensor_readings "
            "(device_id, raw, moisture, status, recorded_at, received_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("soilsense-01", 2300, 42.5, "MOIST", "2026-11-15T08:00:00+00:00", "now"),
        )
    with sqlite3.connect(database) as connection:
        connection.row_factory = sqlite3.Row
        subscription = connection.execute("SELECT * FROM sms_subscriptions").fetchone()

    async def fake_weather(latitude, longitude):
        return {
            "forecast": [{"precipitation_mm": 1.0}, {"precipitation_mm": 2.0}],
            "current": {"temperature": 25},
        }

    sent = []

    async def fake_send_sms(phone, message):
        sent.append((phone, message))

    monkeypatch.setattr(communications, "fetch_weather", fake_weather)
    monkeypatch.setattr(communications, "send_sms", fake_send_sms)
    asyncio.run(communications._send_daily_to_subscriber(database, subscription, "2026-11-15"))
    asyncio.run(communications._send_daily_to_subscriber(database, subscription, "2026-11-15"))

    assert len(sent) == 1
    assert "Lira, Uganda" in sent[0][1]
    assert "3 mm" in sent[0][1]
    assert "25C" in sent[0][1]
    assert "MOIST 42%" in sent[0][1]
    with sqlite3.connect(database) as connection:
        status = connection.execute("SELECT status FROM sms_daily_sends").fetchone()[0]
    assert status == "sent"
