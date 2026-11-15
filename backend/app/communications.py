import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
import os
import secrets
import sqlite3
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from dotenv import load_dotenv

from .weather import fetch_weather


load_dotenv(Path(__file__).resolve().parents[2] / ".env")
logger = logging.getLogger(__name__)
router = APIRouter()

AFRICASTALKING_USERNAME = os.getenv("AFRICASTALKING_USERNAME", "").strip()
AFRICASTALKING_API_KEY = os.getenv("AFRICASTALKING_API_KEY", "").strip()
AFRICASTALKING_SANDBOX = os.getenv("AFRICASTALKING_SANDBOX", "false").strip().lower() == "true"
SMS_SEND_HOUR_UTC = int(os.getenv("EARTHSIGNAL_SMS_SEND_HOUR_UTC", "5"))
SMS_API_URL = (
    "https://api.sandbox.africastalking.com/version1/messaging"
    if AFRICASTALKING_SANDBOX
    else "https://api.africastalking.com/version1/messaging"
)
OTP_LIFETIME = timedelta(minutes=10)
OTP_RESEND_DELAY = timedelta(seconds=60)
OTP_MAX_ATTEMPTS = 5
OTP_MAX_PER_IP_PER_HOUR = 20


class SubscribeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")
    language: str = Field(pattern=r"^(en|lg|luo|ach|xog|nyn|myx|sw)$")
    device_id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    location_name: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    consent: Literal[True]


class PhoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phone: str = Field(pattern=r"^\+[1-9]\d{7,14}$")


class ConfirmRequest(PhoneRequest):
    code: str = Field(pattern=r"^\d{6}$")


def _db(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def init_communications_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with _db(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS sms_subscriptions (
                phone TEXT PRIMARY KEY,
                language TEXT NOT NULL,
                device_id TEXT NOT NULL,
                location_name TEXT NOT NULL DEFAULT 'your farm',
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                consented_at TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS sms_verifications (
                phone TEXT PRIMARY KEY,
                purpose TEXT NOT NULL,
                code_digest TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                last_sent_at TEXT NOT NULL,
                window_started_at TEXT NOT NULL,
                sends_in_window INTEGER NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0,
                language TEXT,
                device_id TEXT,
                location_name TEXT,
                latitude REAL,
                longitude REAL
            );
            CREATE TABLE IF NOT EXISTS sms_daily_sends (
                phone TEXT NOT NULL,
                send_date TEXT NOT NULL,
                status TEXT NOT NULL,
                attempted_at TEXT NOT NULL,
                sent_at TEXT,
                error TEXT,
                PRIMARY KEY (phone, send_date)
            );
            CREATE TABLE IF NOT EXISTS sms_request_limits (
                source_digest TEXT PRIMARY KEY,
                window_started_at TEXT NOT NULL,
                sends INTEGER NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sms_subscriptions_active
                ON sms_subscriptions(active);
            """
        )


def _require_sms_configuration() -> None:
    if not AFRICASTALKING_USERNAME or not AFRICASTALKING_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="SMS is not configured. Set AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY on the backend.",
        )


def _digest_code(phone: str, code: str) -> str:
    key = AFRICASTALKING_API_KEY.encode("utf-8")
    return hmac.new(key, f"{phone}:{code}".encode("utf-8"), hashlib.sha256).hexdigest()


def _verification_message(language: str, code: str, purpose: str) -> str:
    messages = {
        "en": "Your EarthSignal verification code is {code}. It expires in 10 minutes.",
        "sw": "Namba ya uthibitisho ya EarthSignal ni {code}. Inaisha baada ya dakika 10.",
        "lg": "Koodi yo ey'okukakasa eya EarthSignal eri {code}. Ewaako oluvannyuma lw'eddakiika 10.",
        "luo": "Koodi mar yie mar EarthSignal en {code}. Tho bang dakika 10.",
        "ach": "Code me moko pa EarthSignal en {code}. Tye ne dakika 10.",
        "xog": "Koodi ey'okukakasa eya EarthSignal eri {code}. Ewaako oluvannyuma lw'eddakiika 10.",
        "nyn": "Koodi y'okuhamya eya EarthSignal ni {code}. Neeyitira omu dakiika 10.",
        "myx": "Koodi ey'okukakasa eya EarthSignal eri {code}. Ewaako oluvannyuma lw'eddakiika 10.",
    }
    actions = {
        "subscribe": {
            "en": "Use it to confirm your daily SMS subscription.",
            "sw": "Itumie kuthibitisha ujumbe wako wa kila siku.",
            "lg": "Kikozese okukakasa obubaka bwo obwa buli lunaku.",
            "luo": "Tii kode ni mondo iyie SMS mar pile pile.",
            "ach": "Tii ki code ni me moko SMS me nino ki nino.",
            "xog": "Kikozese okukakasa obubaka bwo obwa buli lunaku.",
            "nyn": "Kozesa koodi kuhamya obutumwa bwa buri izooba.",
            "myx": "Kikozese okukakasa obubaka bwo obwa buli lunaku.",
        },
        "unsubscribe": {
            "en": "Use it to confirm your unsubscribe request.",
            "sw": "Itumie kuthibitisha kujiondoa.",
            "lg": "Kikozese okukakasa okwesazamu.",
            "luo": "Tii kode ni mondo iyie mar weko.",
            "ach": "Tii ki code ni me moko weko.",
            "xog": "Kikozese okukakasa okwesazamu.",
            "nyn": "Kozesa koodi kuhamya okwehakanisa.",
            "myx": "Kikozese okukakasa okwesazamu.",
        },
    }
    template = messages.get(language, messages["en"])
    return f"{template.format(code=code)} {actions[purpose].get(language, actions[purpose]['en'])}"


async def send_sms(phone: str, message: str) -> None:
    _require_sms_configuration()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(
                SMS_API_URL,
                headers={
                    "apiKey": AFRICASTALKING_API_KEY,
                    "Accept": "application/json",
                },
                data={
                    "username": AFRICASTALKING_USERNAME,
                    "to": phone,
                    "message": message,
                },
            )
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise RuntimeError("Africa's Talking did not accept the SMS request.") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Africa's Talking returned an invalid SMS response.")
    message_data = payload.get("SMSMessageData")
    recipients = message_data.get("Recipients") if isinstance(message_data, dict) else None
    if not isinstance(recipients, list):
        raise RuntimeError("Africa's Talking returned an invalid SMS recipient response.")
    accepted = any(
        isinstance(recipient, dict) and recipient.get("statusCode") in (101, 102, "101", "102")
        for recipient in recipients
    )
    if not accepted:
        raise RuntimeError("Africa's Talking did not accept the SMS recipient.")


def _verification_error(connection: sqlite3.Connection, phone: str, purpose: str) -> HTTPException | None:
    row = connection.execute(
        "SELECT expires_at, attempts FROM sms_verifications WHERE phone = ? AND purpose = ?",
        (phone, purpose),
    ).fetchone()
    if row is None:
        return HTTPException(status_code=400, detail="Request a new verification code first.")
    if row["attempts"] >= OTP_MAX_ATTEMPTS:
        return HTTPException(status_code=429, detail="Too many incorrect codes. Request a new code.")
    if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
        return HTTPException(status_code=400, detail="The verification code expired. Request a new one.")
    return None


async def _start_verification(
    db_path: Path,
    phone: str,
    source_ip: str,
    purpose: str,
    language: str,
    device_id: str | None = None,
    location_name: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> None:
    _require_sms_configuration()
    now = datetime.now(timezone.utc)
    with _db(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        source_digest = _digest_code(source_ip, "rate-limit")
        ip_window = connection.execute(
            "SELECT window_started_at, sends FROM sms_request_limits WHERE source_digest = ?",
            (source_digest,),
        ).fetchone()
        if ip_window and now - datetime.fromisoformat(ip_window["window_started_at"]) < timedelta(hours=1):
            if ip_window["sends"] >= OTP_MAX_PER_IP_PER_HOUR:
                raise HTTPException(status_code=429, detail="Too many verification requests. Try again later.")
            connection.execute(
                "UPDATE sms_request_limits SET sends = sends + 1 WHERE source_digest = ?",
                (source_digest,),
            )
        else:
            connection.execute(
                """
                INSERT INTO sms_request_limits (source_digest, window_started_at, sends)
                VALUES (?, ?, 1)
                ON CONFLICT(source_digest) DO UPDATE SET
                    window_started_at = excluded.window_started_at,
                    sends = 1
                """,
                (source_digest, now.isoformat()),
            )
        previous = connection.execute(
            "SELECT last_sent_at, window_started_at, sends_in_window "
            "FROM sms_verifications WHERE phone = ?",
            (phone,),
        ).fetchone()
        if previous:
            last_sent = datetime.fromisoformat(previous["last_sent_at"])
            if now - last_sent < OTP_RESEND_DELAY:
                raise HTTPException(status_code=429, detail="Wait one minute before requesting another code.")
            window_started = datetime.fromisoformat(previous["window_started_at"])
            if now - window_started < timedelta(hours=1) and previous["sends_in_window"] >= 3:
                raise HTTPException(status_code=429, detail="Too many codes requested for this number. Try again later.")

        code = f"{secrets.randbelow(1_000_000):06d}"
        digest = _digest_code(phone, code)
        sends = previous["sends_in_window"] + 1 if previous and now - datetime.fromisoformat(
            previous["window_started_at"]
        ) < timedelta(hours=1) else 1
        window_start = previous["window_started_at"] if previous and sends > 1 else now.isoformat()
        connection.execute(
            """
            INSERT INTO sms_verifications
                (phone, purpose, code_digest, expires_at, last_sent_at, window_started_at,
                 sends_in_window, attempts, language, device_id, location_name, latitude, longitude)
            VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?)
            ON CONFLICT(phone) DO UPDATE SET
                purpose = excluded.purpose,
                code_digest = excluded.code_digest,
                expires_at = excluded.expires_at,
                last_sent_at = excluded.last_sent_at,
                window_started_at = excluded.window_started_at,
                sends_in_window = excluded.sends_in_window,
                attempts = 0,
                language = excluded.language,
                device_id = excluded.device_id,
                location_name = excluded.location_name,
                latitude = excluded.latitude,
                longitude = excluded.longitude
            """,
            (
                phone,
                purpose,
                digest,
                (now + OTP_LIFETIME).isoformat(),
                now.isoformat(),
                window_start,
                sends,
                language,
                device_id,
                location_name,
                latitude,
                longitude,
            ),
        )
    try:
        await send_sms(phone, _verification_message(language, code, purpose))
    except RuntimeError as exc:
        with _db(db_path) as connection:
            connection.execute("DELETE FROM sms_verifications WHERE phone = ?", (phone,))
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/sms/subscribe")
async def request_subscription_code(payload: SubscribeRequest, request: Request):
    await _start_verification(
        request.app.state.sensor_db,
        payload.phone,
        request.client.host if request.client else "unknown",
        "subscribe",
        payload.language,
        payload.device_id,
        payload.location_name,
        payload.latitude,
        payload.longitude,
    )
    return {"accepted": True, "message": "A verification code was sent to the phone number."}


@router.post("/api/sms/subscribe/confirm")
async def confirm_subscription(payload: ConfirmRequest, request: Request):
    db_path = request.app.state.sensor_db
    with _db(db_path) as connection:
        error = _verification_error(connection, payload.phone, "subscribe")
        if error:
            raise error
        row = connection.execute(
            "SELECT * FROM sms_verifications WHERE phone = ? AND purpose = 'subscribe'",
            (payload.phone,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=400, detail="Request a new verification code first.")
        if not hmac.compare_digest(row["code_digest"], _digest_code(payload.phone, payload.code)):
            connection.execute(
                "UPDATE sms_verifications SET attempts = attempts + 1 WHERE phone = ?",
                (payload.phone,),
            )
            connection.commit()
            raise HTTPException(status_code=400, detail="That code is not valid.")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            connection.execute("DELETE FROM sms_verifications WHERE phone = ?", (payload.phone,))
            connection.commit()
            raise HTTPException(status_code=400, detail="The verification code expired. Request a new one.")
        if not row["device_id"] or not row["location_name"] or row["latitude"] is None or row["longitude"] is None:
            raise HTTPException(status_code=400, detail="The subscription details are incomplete. Start again.")
        connection.execute(
            """
            INSERT INTO sms_subscriptions
                (phone, language, device_id, location_name, latitude, longitude, consented_at, active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            ON CONFLICT(phone) DO UPDATE SET
                language = excluded.language,
                device_id = excluded.device_id,
                location_name = excluded.location_name,
                latitude = excluded.latitude,
                longitude = excluded.longitude,
                consented_at = excluded.consented_at,
                active = 1
            """,
            (
                payload.phone,
                row["language"],
                row["device_id"],
                row["location_name"],
                row["latitude"],
                row["longitude"],
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        connection.execute("DELETE FROM sms_verifications WHERE phone = ?", (payload.phone,))
    return {"subscribed": True, "message": "Daily EarthSignal SMS updates are enabled. Unsubscribe from the dashboard at any time."}


@router.post("/api/sms/unsubscribe")
async def request_unsubscribe_code(payload: PhoneRequest, request: Request):
    db_path = request.app.state.sensor_db
    with _db(db_path) as connection:
        subscription = connection.execute(
            "SELECT language FROM sms_subscriptions WHERE phone = ? AND active = 1",
            (payload.phone,),
        ).fetchone()
    if subscription is None:
        raise HTTPException(status_code=404, detail="No active SMS subscription was found for this number.")
    await _start_verification(
        db_path,
        payload.phone,
        request.client.host if request.client else "unknown",
        "unsubscribe",
        subscription["language"],
    )
    return {"accepted": True, "message": "A verification code was sent to confirm unsubscribe."}


@router.post("/api/sms/unsubscribe/confirm")
async def confirm_unsubscribe(payload: ConfirmRequest, request: Request):
    db_path = request.app.state.sensor_db
    with _db(db_path) as connection:
        error = _verification_error(connection, payload.phone, "unsubscribe")
        if error:
            raise error
        row = connection.execute(
            "SELECT code_digest, expires_at FROM sms_verifications WHERE phone = ? AND purpose = 'unsubscribe'",
            (payload.phone,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=400, detail="Request a new verification code first.")
        if not hmac.compare_digest(row["code_digest"], _digest_code(payload.phone, payload.code)):
            connection.execute(
                "UPDATE sms_verifications SET attempts = attempts + 1 WHERE phone = ?",
                (payload.phone,),
            )
            connection.commit()
            raise HTTPException(status_code=400, detail="That code is not valid.")
        if datetime.fromisoformat(row["expires_at"]) < datetime.now(timezone.utc):
            connection.execute("DELETE FROM sms_verifications WHERE phone = ?", (payload.phone,))
            connection.commit()
            raise HTTPException(status_code=400, detail="The verification code expired. Request a new one.")
        connection.execute(
            "UPDATE sms_subscriptions SET active = 0 WHERE phone = ?",
            (payload.phone,),
        )
        connection.execute("DELETE FROM sms_verifications WHERE phone = ?", (payload.phone,))
    return {"unsubscribed": True, "message": "Daily EarthSignal SMS updates are disabled."}


def _sms_message(language: str, location: str, rain_mm: float | None, temperature: float | None, reading) -> str:
    opening = {
        "en": "EarthSignal",
        "sw": "EarthSignal",
        "lg": "EarthSignal",
        "luo": "EarthSignal",
        "ach": "EarthSignal",
        "xog": "EarthSignal",
        "nyn": "EarthSignal",
        "myx": "EarthSignal",
    }.get(language, "EarthSignal")
    rain_labels = {
        "en": "7-day rain",
        "sw": "Mvua ya siku 7",
        "lg": "Enkuba mu nnaku 7",
        "luo": "Koth mar odiechien 7",
        "ach": "Koth pa nino 7",
        "xog": "Enkuba mu nnaku 7",
        "nyn": "Enkuba y'eizooba 7",
        "myx": "Enkuba mu nnaku 7",
    }
    temperature_labels = {
        "en": "Temp",
        "sw": "Joto",
        "lg": "Ebbugumu",
        "luo": "Koth mar chieng'",
        "ach": "Koth me nino",
        "xog": "Ebbugumu",
        "nyn": "Obutagasi",
        "myx": "Obutagasi",
    }
    soil_labels = {
        "en": "Soil",
        "sw": "Udongo",
        "lg": "Ettaka",
        "luo": "Pur",
        "ach": "Pur",
        "xog": "Ettaka",
        "nyn": "Eitaka",
        "myx": "Eitaka",
    }
    caveats = {
        "en": "Context only; check the field.",
        "sw": "Ni taarifa tu; kagua shamba.",
        "lg": "Bubaka; kebera ennimiro.",
        "luo": "Kony mar ngeyo; ne pur.",
        "ach": "Kony me ngeyo; nen pur.",
        "xog": "Bubaka; kebera ennimiro.",
        "nyn": "N'obuhabuzi; reeba omusiri.",
        "myx": "N'obuhabuzi; reeba omusiri.",
    }
    parts = [f"{opening}: {location}"]
    if rain_mm is not None:
        parts.append(f"{rain_labels.get(language, rain_labels['en'])} ~{rain_mm:.0f} mm")
    if temperature is not None:
        parts.append(f"{temperature_labels.get(language, temperature_labels['en'])} {temperature:.0f}C")
    if reading:
        parts.append(
            f"{soil_labels.get(language, soil_labels['en'])} {reading['status']} "
            f"{reading['moisture']:.0f}% ({reading['recorded_at'][:16].replace('T', ' ')} UTC)"
        )
    return ". ".join(parts) + f". {caveats.get(language, caveats['en'])}"


async def _send_daily_to_subscriber(db_path: Path, subscription: sqlite3.Row, send_date: str) -> None:
    phone = subscription["phone"]
    now = datetime.now(timezone.utc)
    with _db(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status, attempted_at FROM sms_daily_sends WHERE phone = ? AND send_date = ?",
            (phone, send_date),
        ).fetchone()
        if row and row["status"] == "sent":
            return
        if row and now - datetime.fromisoformat(row["attempted_at"]) < timedelta(minutes=10):
            return
        if row:
            connection.execute(
                "UPDATE sms_daily_sends SET status = 'sending', attempted_at = ?, error = NULL "
                "WHERE phone = ? AND send_date = ?",
                (now.isoformat(), phone, send_date),
            )
        else:
            connection.execute(
                "INSERT INTO sms_daily_sends (phone, send_date, status, attempted_at) "
                "VALUES (?, ?, 'sending', ?)",
                (phone, send_date, now.isoformat()),
            )

    try:
        weather = await fetch_weather(subscription["latitude"], subscription["longitude"])
        rain_total = sum(
            float(day["precipitation_mm"])
            for day in weather["forecast"]
            if day.get("precipitation_mm") is not None
        )
        current_temp = weather["current"].get("temperature")
        with _db(db_path) as connection:
            reading = connection.execute(
                """
                SELECT status, moisture, recorded_at FROM sensor_readings
                WHERE device_id = ?
                ORDER BY recorded_at DESC, id DESC LIMIT 1
                """,
                (subscription["device_id"],),
            ).fetchone()
        message = _sms_message(
            subscription["language"],
            subscription["location_name"],
            rain_total,
            float(current_temp) if current_temp is not None else None,
            reading,
        )
        await send_sms(phone, message)
    except Exception as exc:
        with _db(db_path) as connection:
            connection.execute(
                "UPDATE sms_daily_sends SET status = 'failed', error = ? WHERE phone = ? AND send_date = ?",
                (str(exc)[:500], phone, send_date),
            )
        logger.exception("Could not send EarthSignal daily SMS to a subscribed number.")
        return

    with _db(db_path) as connection:
        connection.execute(
            "UPDATE sms_daily_sends SET status = 'sent', sent_at = ?, error = NULL "
            "WHERE phone = ? AND send_date = ?",
            (datetime.now(timezone.utc).isoformat(), phone, send_date),
        )


async def daily_sms_dispatch_loop(db_path: Path) -> None:
    if SMS_SEND_HOUR_UTC not in range(24):
        raise ValueError("EARTHSIGNAL_SMS_SEND_HOUR_UTC must be between 0 and 23.")
    if not AFRICASTALKING_USERNAME or not AFRICASTALKING_API_KEY:
        logger.info("Daily SMS is inactive until Africa's Talking credentials are configured.")
    while True:
        now = datetime.now(timezone.utc)
        if now.hour >= SMS_SEND_HOUR_UTC and AFRICASTALKING_USERNAME and AFRICASTALKING_API_KEY:
            with _db(db_path) as connection:
                subscribers = connection.execute(
                    "SELECT * FROM sms_subscriptions WHERE active = 1"
                ).fetchall()
            for subscription in subscribers:
                await _send_daily_to_subscriber(db_path, subscription, now.date().isoformat())
        await asyncio.sleep(60)
