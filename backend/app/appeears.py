import asyncio
import csv
from datetime import date, datetime, timezone
from io import StringIO
import os
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from .analysis import analyze_series


APPEEARS_API = "https://appeears.earthdatacloud.nasa.gov/api/"
NDVI_LAYER = "_250m_16_days_NDVI"
NDVI_QUALITY_LAYER = "_250m_16_days_VI_Quality"
LST_LAYER = "LST_Day_1km"
LST_QUALITY_LAYER = "QC_Day"


class AppEEARSError(ValueError):
    pass


class EarthdataNotConfigured(AppEEARSError):
    pass


def _column(fields: list[str], layer_name: str) -> str | None:
    target = layer_name.casefold()
    return next((field for field in fields if target in field.casefold()), None)


def _parse_sample_csv(content: str) -> dict[str, dict[str, Any]]:
    reader = csv.DictReader(StringIO(content))
    fields = reader.fieldnames or []
    date_field = next((field for field in fields if field.strip().casefold() == "date"), None)
    ndvi_field = _column(fields, NDVI_LAYER)
    ndvi_quality_field = _column(fields, NDVI_QUALITY_LAYER)
    lst_field = _column(fields, LST_LAYER)
    lst_quality_field = _column(fields, LST_QUALITY_LAYER)
    if not date_field:
        raise AppEEARSError("NASA AppEEARS point results did not contain a Date column.")
    if not any((ndvi_field, lst_field)):
        raise AppEEARSError("NASA AppEEARS point results did not contain the requested NDVI or land-surface temperature layers.")

    observations: dict[str, dict[str, Any]] = {}
    for row in reader:
        raw_date = (row.get(date_field) or "").strip()[:10]
        try:
            observed_date = date.fromisoformat(raw_date).isoformat()
        except ValueError:
            continue
        record = observations.setdefault(observed_date, {"date": observed_date, "NDVI": None, "LST_DAY_C": None})

        if ndvi_field and ndvi_quality_field:
            try:
                raw_ndvi = float(row[ndvi_field])
                quality = int(float(row[ndvi_quality_field]))
            except (KeyError, TypeError, ValueError):
                raw_ndvi = None
                quality = -1
            if raw_ndvi is not None and quality & 0b11 == 0 and -0.2 <= raw_ndvi <= 1.0:
                record["NDVI"] = round(raw_ndvi, 4)

        if lst_field and lst_quality_field:
            try:
                raw_lst = float(row[lst_field])
                quality = int(float(row[lst_quality_field]))
            except (KeyError, TypeError, ValueError):
                raw_lst = None
                quality = -1
            if raw_lst is not None and quality & 0b11 == 0 and 150 <= raw_lst <= 1310.7:
                record["LST_DAY_C"] = round(raw_lst - 273.15, 2)

    return observations


def _matches_task_request(task: dict[str, Any], request: dict[str, Any]) -> bool:
    if task.get("task_name") != request["task_name"] or task.get("task_type") != request["task_type"]:
        return False

    params = task.get("params") or {}
    requested_params = request["params"]
    if params.get("dates") != requested_params["dates"] or params.get("layers") != requested_params["layers"]:
        return False

    coordinates = params.get("coordinates") or []
    requested_coordinates = requested_params["coordinates"]
    if len(coordinates) != 1 or len(requested_coordinates) != 1:
        return False

    try:
        return (
            float(coordinates[0]["latitude"]) == float(requested_coordinates[0]["latitude"])
            and float(coordinates[0]["longitude"]) == float(requested_coordinates[0]["longitude"])
        )
    except (KeyError, TypeError, ValueError):
        return False


async def _json(response: httpx.Response, operation: str) -> Any:
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        raise AppEEARSError(f"NASA AppEEARS {operation} failed with HTTP {response.status_code}.") from exc
    except ValueError as exc:
        raise AppEEARSError(f"NASA AppEEARS {operation} returned invalid JSON.") from exc


async def _find_existing_task(
    client: httpx.AsyncClient, request: dict[str, Any], headers: dict[str, str]
) -> str | None:
    task_list = await _json(await client.get(f"{APPEEARS_API}task", headers=headers), "task lookup")
    if not isinstance(task_list, list):
        raise AppEEARSError("NASA AppEEARS task lookup returned an unexpected response.")

    expected_params = request["params"]
    for candidate in task_list:
        if not isinstance(candidate, dict) or candidate.get("task_name") != request["task_name"]:
            continue
        if candidate.get("task_type") != request["task_type"]:
            continue
        candidate_params = candidate.get("params") or {}
        if candidate_params.get("dates") != expected_params["dates"] or candidate_params.get("layers") != expected_params["layers"]:
            continue
        task_id = candidate.get("task_id")
        if not task_id:
            continue

        details = await _json(await client.get(f"{APPEEARS_API}task/{task_id}", headers=headers), "task details")
        if not isinstance(details, dict) or details.get("status") in {"error", "crashed"}:
            continue
        if _matches_task_request(details, request):
            return task_id
    return None


async def _download_bundle_file(
    client: httpx.AsyncClient, task_id: str, file_id: str, headers: dict[str, str]
) -> str:
    response = await client.get(f"{APPEEARS_API}bundle/{task_id}/{file_id}", headers=headers)
    if response.is_redirect:
        signed_url = response.headers.get("location")
        if not signed_url:
            raise AppEEARSError("NASA AppEEARS returned a bundle redirect without a download URL.")
        response = await client.get(urljoin(str(response.url), signed_url))
    try:
        response.raise_for_status()
        return response.text
    except httpx.HTTPStatusError as exc:
        raise AppEEARSError(f"NASA AppEEARS could not download result file {file_id}.") from exc


async def fetch_modis_point(latitude: float, longitude: float, start: date, end: date) -> dict[str, Any]:
    username = os.getenv("NASA_EARTHDATA_USERNAME")
    password = os.getenv("NASA_EARTHDATA_PASSWORD")
    request_timeout = float(os.getenv("NASA_APPEEARS_TIMEOUT_SECONDS", "30"))
    task_timeout = float(os.getenv("NASA_APPEEARS_TASK_TIMEOUT_SECONDS", "180"))
    if not username or not password:
        raise EarthdataNotConfigured(
            "MODIS data needs a free NASA Earthdata Login. Set NASA_EARTHDATA_USERNAME and NASA_EARTHDATA_PASSWORD in .env."
        )

    timeout = httpx.Timeout(request_timeout)
    async with httpx.AsyncClient(timeout=timeout) as client:
        login = await client.post(f"{APPEEARS_API}login", auth=(username, password))
        token_data = await _json(login, "Earthdata login")
        token = token_data.get("token") if isinstance(token_data, dict) else None
        if not token:
            raise AppEEARSError("NASA AppEEARS login did not return an access token.")
        headers = {"Authorization": f"Bearer {token}"}

        task = {
            "task_type": "point",
            "task_name": "EarthSignal point analysis",
            "params": {
                "dates": [{
                    "startDate": start.strftime("%m-%d-%Y"),
                    "endDate": end.strftime("%m-%d-%Y"),
                }],
                "layers": [
                    {"product": "MOD13Q1.061", "layer": NDVI_LAYER},
                    {"product": "MOD13Q1.061", "layer": NDVI_QUALITY_LAYER},
                    {"product": "MOD11A2.061", "layer": LST_LAYER},
                    {"product": "MOD11A2.061", "layer": LST_QUALITY_LAYER},
                ],
                "coordinates": [{"latitude": latitude, "longitude": longitude}],
            },
        }
        task_id = await _find_existing_task(client, task, headers)
        if task_id is None:
            submit = await client.post(f"{APPEEARS_API}task", json=task, headers=headers)
            task_data = await _json(submit, "point task submission")
            task_id = task_data.get("task_id") if isinstance(task_data, dict) else None
        if not task_id:
            raise AppEEARSError("NASA AppEEARS did not return a point task ID.")

        deadline = time.monotonic() + task_timeout
        while time.monotonic() < deadline:
            status_response = await client.get(f"{APPEEARS_API}status/{task_id}", headers=headers)
            if status_response.status_code == 303:
                location = status_response.headers.get("location")
                if not location:
                    raise AppEEARSError("NASA AppEEARS completed the task without a result location.")
                status_response = await client.get(urljoin(str(status_response.url), location), headers=headers)
            status_data = await _json(status_response, "task status")
            if isinstance(status_data, list):
                status_data = status_data[0] if status_data else {}
            status = status_data.get("status")
            if status == "done":
                break
            if status == "error":
                raise AppEEARSError("NASA AppEEARS could not process the MODIS point request.")
            await asyncio.sleep(2)
        else:
            raise TimeoutError(
                "NASA AppEEARS is still processing this location and date range. Retry the same request later; "
                "EarthSignal will reuse the existing task."
            )

        bundle_response = await client.get(f"{APPEEARS_API}bundle/{task_id}", headers=headers)
        bundle = await _json(bundle_response, "result bundle")
        files = bundle.get("files", []) if isinstance(bundle, dict) else []
        csv_files = [item for item in files if str(item.get("file_type", "")).casefold() == "csv"]
        if not csv_files:
            raise AppEEARSError("NASA AppEEARS completed the task but returned no CSV point results.")

        merged: dict[str, dict[str, Any]] = {}
        for item in csv_files:
            content = await _download_bundle_file(client, task_id, item["file_id"], headers)
            for observed_date, row in _parse_sample_csv(content).items():
                record = merged.setdefault(observed_date, {"date": observed_date, "NDVI": None, "LST_DAY_C": None})
                for parameter in ("NDVI", "LST_DAY_C"):
                    if row[parameter] is not None:
                        record[parameter] = row[parameter]

    observations = [merged[key] for key in sorted(merged)]
    if not observations or not any(row["NDVI"] is not None for row in observations) or not any(row["LST_DAY_C"] is not None for row in observations):
        raise AppEEARSError("NASA AppEEARS results did not contain valid, quality-screened values for both requested layers.")

    return {
        "source": "NASA AppEEARS point sample",
        "source_url": APPEEARS_API,
        "products": {
            "NDVI": {"product": "MOD13Q1.061", "layer": NDVI_LAYER, "unit": "NDVI", "scale_factor": 0.0001, "temporal_resolution": "16-day composite"},
            "LST_DAY_C": {"product": "MOD11A2.061", "layer": LST_LAYER, "unit": "°C", "scale_factor": 0.02, "temporal_resolution": "8-day composite"},
        },
        "parameters": {
            "NDVI": {"unit": "NDVI", "long_name": "16-day normalized difference vegetation index"},
            "LST_DAY_C": {"unit": "°C", "long_name": "8-day daytime land-surface temperature"},
        },
        "location": {"latitude": latitude, "longitude": longitude},
        "period": {"start": start.isoformat(), "end": end.isoformat()},
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "observations": observations,
        "analysis": {
            "NDVI": analyze_series(observations, "NDVI", start, end, cadence_days=16),
            "LST_DAY_C": analyze_series(observations, "LST_DAY_C", start, end, cadence_days=8),
        },
        "method_note": (
            "MODIS point samples from NASA AppEEARS. AppEEARS returns the product values with scale factors applied; "
            "EarthSignal converts daytime land-surface temperature from Kelvin to Celsius and retains only accepted "
            "quality values. These grid samples are not field measurements."
        ),
    }
