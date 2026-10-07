"""
Hermetic unit and integration tests for air-quality ingestion pipeline (P2-F5).
Probed live: the Open-Meteo AQ API rejects the combined multi-variable request
with HTTP 400, and `sulfur_dioxide` is unsupported (400) — so the service
issues one request per supported variable and merges arrays by timestamp.
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.geo.models import AirQualityData
from apps.geo.services import AQ_VARIABLES, fetch_air_quality_for_city
from apps.geo.tasks import refresh_air_quality
from apps.places.models import Place

TIMES = ["2026-10-06T12:00:00", "2026-10-06T13:00:00"]
CELL = "87608b032ffffff"

# Per-variable sample series for the two hours in TIMES.
VALUES = {
    "us_aqi": [52, 55],
    "pm2_5": [12.5, 13.1],
    "pm10": [30.0, 31.5],
    "ozone": [40.0, 41.0],
    "nitrogen_dioxide": [25.0, 26.0],
    "carbon_monoxide": [0.5, 0.6],
}


def aq_payload(var: str, values: list | None = None) -> dict:
    return {"hourly": {"time": TIMES, var: values if values is not None else VALUES[var]}}


def make_session(payloads: dict[str, list]) -> MagicMock:
    """Session mock that answers each per-variable GET with its payload."""

    def _get(url, params=None, timeout=None):
        resp = MagicMock()
        resp.json.return_value = aq_payload(params["hourly"], payloads.get(params["hourly"]))
        return resp

    session = MagicMock()
    session.get.side_effect = _get
    return session


@pytest.fixture
def mumbai_place(db):
    p = Place.objects.create(
        name="A Place",
        city="Mumbai",
        location=Point(72.835, 18.940, srid=4326),
        is_active=True,
    )
    p.fill_derived_fields()
    p.save()
    return p


@pytest.mark.django_db
class TestFetchAirQuality:
    def test_merges_variables_per_cell(self, mumbai_place):
        session = make_session({})
        res = fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)

        assert res["cells"] == 1
        assert res["rows"] == 2
        assert res["upserted"] == 2
        assert AirQualityData.objects.count() == 2

        rows = {r.timestamp: r for r in AirQualityData.objects.all()}
        first = rows[datetime(2026, 10, 6, 12, 0, tzinfo=dt_timezone.utc)]
        assert first.h3_index == CELL
        assert first.us_aqi == 52
        assert first.pm2_5 == Decimal("12.50")
        assert first.pm10 == Decimal("30.00")
        assert first.ozone == Decimal("40.00")
        assert first.nitrogen_dioxide == Decimal("25.00")
        assert first.carbon_monoxide == Decimal("0.50")
        second = rows[datetime(2026, 10, 6, 13, 0, tzinfo=dt_timezone.utc)]
        assert second.us_aqi == 55

    def test_one_request_per_variable(self, mumbai_place):
        session = make_session({})
        fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)
        assert session.get.call_count == len(AQ_VARIABLES)
        asked = {c.kwargs["params"]["hourly"] for c in session.get.call_args_list}
        assert asked == set(AQ_VARIABLES)

    def test_all_null_rows_dropped(self, mumbai_place):
        """A cell outside model coverage returns all-NULL series -> no rows."""
        session = make_session({var: [None, None] for var in AQ_VARIABLES})
        res = fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)
        assert res["rows"] == 0
        assert AirQualityData.objects.count() == 0

    def test_partial_nulls_kept(self, mumbai_place):
        """Keep the row when at least one pollutant is present; keep NULLs for the rest."""
        payloads = {var: [None, None] for var in AQ_VARIABLES}
        payloads["us_aqi"] = [40, None]
        session = make_session(payloads)
        res = fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)
        assert res["rows"] == 1  # hour 2 all-null -> dropped
        row = AirQualityData.objects.get()
        assert row.us_aqi == 40
        assert row.pm2_5 is None

    def test_upsert_idempotent(self, mumbai_place):
        session = make_session({})
        first = fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)
        second = fetch_air_quality_for_city("Mumbai", hours_ahead=48, session=session)
        assert first["rows"] == second["rows"] == 2
        assert AirQualityData.objects.count() == 2

    def test_prunes_old_rows(self, mumbai_place):
        now = timezone.now()
        old_time = now - timedelta(days=15)
        AirQualityData.objects.create(
            h3_index=CELL,
            timestamp=old_time,
            us_aqi=99,
            source="open_meteo_aq",
        )
        session = make_session({})
        res = fetch_air_quality_for_city("Mumbai", hours_ahead=48, now=now, session=session)
        assert res["pruned"] >= 1
        assert not AirQualityData.objects.filter(timestamp=old_time).exists()

    def test_empty_city_no_http(self):
        session = MagicMock()
        res = fetch_air_quality_for_city("Nowhere", session=session)
        assert res == {"cells": 0, "rows": 0, "upserted": 0, "pruned": 0}
        session.get.assert_not_called()

    def test_network_failure_propagates(self, mumbai_place):
        session = MagicMock()
        session.get.side_effect = requests.RequestException("AQ API down")
        with pytest.raises(requests.RequestException):
            fetch_air_quality_for_city("Mumbai", hours_ahead=24, session=session)

    def test_batching_multiple_cells(self):
        """600 cells -> 2 batches, 2 requests per variable (14 total)."""
        fake_cells = [f"{CELL}_{i}" for i in range(600)]
        payloads = {var: [] for var in AQ_VARIABLES}
        session = make_session(payloads)
        with patch("apps.geo.services.city_weather_cells", return_value=fake_cells):
            with patch("h3.cell_to_latlng", return_value=(18.94, 72.83)):
                res = fetch_air_quality_for_city("Mumbai", hours_ahead=24, session=session)
        assert session.get.call_count == 2 * len(AQ_VARIABLES)
        assert res["cells"] == 600


@pytest.mark.django_db
class TestRefreshAirQualityTask:
    def test_task_wrapper(self, mumbai_place):
        with patch("requests.Session") as mock_session_cls:
            session = mock_session_cls.return_value
            session.get.side_effect = lambda url, params=None, timeout=None: MagicMock(
                json=lambda: aq_payload(params["hourly"])
            )
            summaries = refresh_air_quality()
        assert "Mumbai" in summaries
        assert summaries["Mumbai"]["cells"] == 1
        assert AirQualityData.objects.count() == 2
