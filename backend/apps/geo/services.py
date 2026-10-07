"""
Geo domain services: weather ingestion (P2-F4).
"""

from datetime import datetime, timedelta, timezone as dt_timezone
import math
from typing import Optional

import h3
import requests
from django.utils import timezone

from apps.geo.models import WeatherData
from apps.places.models import Place

OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_RETENTION_DAYS = 14
METRIC_UPDATE_FIELDS = [
    "temperature_c",
    "humidity_pct",
    "precipitation_probability",
    "precipitation_mm",
    "wind_speed_kmh",
    "weather_code",
]


def city_weather_cells(city: str) -> list[str]:
    """
    Derive canonical weather grid cells (H3 res7) from active places in the city (P2-D6).
    """
    res8 = set(
        Place.objects.filter(city=city, is_active=True, h3_index_res8__gt="")
        .values_list("h3_index_res8", flat=True)
    )
    return sorted({h3.cell_to_parent(c, 7) for c in res8})


def _chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def _map_weather_response(
    data: dict | list,
    batch: list[tuple[float, float, str]],
    now: datetime,
) -> list[WeatherData]:
    """
    Map Open-Meteo response into WeatherData model instances.
    Normalizes single-point (dict) and multi-point (list) responses.
    Drops rows with any NULL metrics.
    """
    locations_data = data if isinstance(data, list) else [data]
    rows: list[WeatherData] = []

    for loc_idx, loc_data in enumerate(locations_data):
        if loc_idx >= len(batch):
            break
        _, _, cell = batch[loc_idx]
        hourly = loc_data.get("hourly") or {}
        times = hourly.get("time") or []
        temps = hourly.get("temperature_2m") or []
        humidities = hourly.get("relative_humidity_2m") or []
        precip_probs = hourly.get("precipitation_probability") or []
        precips = hourly.get("precipitation") or []
        weather_codes = hourly.get("weather_code") or []
        wind_speeds = hourly.get("wind_speed_10m") or []

        num_entries = len(times)
        for i in range(num_entries):
            # If any metric is None, skip row (P2-F4: never store NULL metrics)
            t = temps[i] if i < len(temps) else None
            h = humidities[i] if i < len(humidities) else None
            pp = precip_probs[i] if i < len(precip_probs) else None
            p = precips[i] if i < len(precips) else None
            wc = weather_codes[i] if i < len(weather_codes) else None
            ws = wind_speeds[i] if i < len(wind_speeds) else None

            if any(val is None for val in (t, h, pp, p, wc, ws)):
                continue

            time_str = times[i]
            dt = datetime.fromisoformat(time_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=dt_timezone.utc)

            is_forecast = dt > now

            rows.append(
                WeatherData(
                    h3_index=cell,
                    timestamp=dt,
                    temperature_c=t,
                    humidity_pct=h,
                    precipitation_probability=pp,
                    precipitation_mm=p,
                    wind_speed_kmh=ws,
                    weather_code=int(wc),
                    is_forecast=is_forecast,
                    source="open_meteo",
                )
            )

    return rows


def fetch_weather_for_city(
    city: str,
    hours_ahead: int = 48,
    now: Optional[datetime] = None,
    session: Optional[requests.Session] = None,
) -> dict:
    """
    Fetch and store weather forecast for city's H3 res7 cells.
    Idempotent upsert via unique constraint, and prunes records > 14 days old.
    """
    now = now or timezone.now()
    session = session or requests.Session()
    cells = city_weather_cells(city)
    if not cells:
        return {"cells": 0, "rows": 0, "upserted": 0, "pruned": 0}

    points = [(h3.cell_to_latlng(c)[0], h3.cell_to_latlng(c)[1], c) for c in cells]
    forecast_days = max(1, math.ceil(hours_ahead / 24))
    all_rows: list[WeatherData] = []

    for batch in _chunks(points, 500):
        lats = ",".join(str(round(p[0], 4)) for p in batch)
        lngs = ",".join(str(round(p[1], 4)) for p in batch)
        params = {
            "latitude": lats,
            "longitude": lngs,
            "hourly": "temperature_2m,relative_humidity_2m,precipitation_probability,precipitation,weather_code,wind_speed_10m",
            "forecast_days": forecast_days,
            "timezone": "UTC",
        }
        resp = session.get(OPEN_METEO_FORECAST_URL, params=params, timeout=30)
        resp.raise_for_status()
        mapped = _map_weather_response(resp.json(), batch, now)
        all_rows.extend(mapped)

    created = 0
    if all_rows:
        WeatherData.objects.bulk_create(
            all_rows,
            batch_size=500,
            update_conflicts=True,
            update_fields=METRIC_UPDATE_FIELDS,
            unique_fields=["h3_index", "timestamp", "source", "is_forecast"],
        )
        created = len(all_rows)

    cutoff = now - timedelta(days=WEATHER_RETENTION_DAYS)
    pruned = WeatherData.objects.filter(timestamp__lt=cutoff).delete()[0]

    return {
        "cells": len(cells),
        "rows": len(all_rows),
        "upserted": created,
        "pruned": pruned,
    }
