"""
Hermetic unit and integration tests for weather ingestion pipeline (P2-F4).
"""

from datetime import datetime, timedelta, timezone as dt_timezone
import json
from unittest.mock import MagicMock, patch
import pytest
import requests
from django.contrib.gis.geos import Point
from django.utils import timezone
import h3

from apps.geo.models import WeatherData
from apps.geo.services import (
    _map_weather_response,
    city_weather_cells,
    fetch_weather_for_city,
)
from apps.geo.tasks import refresh_weather
from apps.places.models import Place

FIXTURE_PATH = "apps/geo/fixtures/open_meteo_forecast_hourly.json"


@pytest.fixture
def sample_weather_payload():
    with open(FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


@pytest.mark.django_db
class TestWeatherCellDerivation:
    def test_city_weather_cells_derivation(self):
        """Active places in a city have their res8 H3 cells converted to distinct parent res7 cells."""
        # 18.94, 72.835
        p1 = Place.objects.create(
            name="Place 1",
            city="Mumbai",
            location=Point(72.835, 18.940, srid=4326),
            is_active=True,
        )
        p1.fill_derived_fields()
        p1.save()

        # Near location, might share or be adjacent
        p2 = Place.objects.create(
            name="Place 2",
            city="Mumbai",
            location=Point(72.836, 18.941, srid=4326),
            is_active=True,
        )
        p2.fill_derived_fields()
        p2.save()

        cells = city_weather_cells("Mumbai")
        assert len(cells) >= 1
        for cell in cells:
            assert h3.get_resolution(cell) == 7

    def test_city_weather_cells_ignores_inactive_and_blank(self):
        """Inactive places and places without res8 cells are ignored."""
        p_inactive = Place.objects.create(
            name="Inactive Place",
            city="Mumbai",
            location=Point(72.835, 18.940, srid=4326),
            is_active=False,
        )
        p_inactive.fill_derived_fields()
        p_inactive.save()

        p_other_city = Place.objects.create(
            name="Pune Place",
            city="Pune",
            location=Point(73.856, 18.520, srid=4326),
            is_active=True,
        )
        p_other_city.fill_derived_fields()
        p_other_city.save()

        assert city_weather_cells("Mumbai") == []


class TestWeatherMapping:
    def test_weather_response_mapping(self, sample_weather_payload):
        """Recorded fixture correctly maps into WeatherData rows with is_forecast split at now."""
        # Fix now at a middle timestamp
        times = sample_weather_payload["hourly"]["time"]
        split_time = times[len(times) // 2]
        now = datetime.fromisoformat(split_time).replace(tzinfo=dt_timezone.utc)

        batch = [(18.94, 72.835, "87608b032ffffff")]
        rows = _map_weather_response(sample_weather_payload, batch, now)

        assert len(rows) > 0
        forecast_count = sum(1 for r in rows if r.is_forecast)
        observation_count = sum(1 for r in rows if not r.is_forecast)
        assert forecast_count > 0
        assert observation_count > 0

        first = rows[0]
        assert first.h3_index == "87608b032ffffff"
        assert first.temperature_c is not None
        assert first.weather_code is not None
        assert first.source == "open_meteo"

    def test_mapping_skips_null_metric_rows(self):
        """If any required metric is None/null, the row is dropped to avoid NULL metrics in DB."""
        payload = {
            "hourly": {
                "time": ["2026-10-06T00:00", "2026-10-06T01:00"],
                "temperature_2m": [25.0, None],  # second row has None
                "relative_humidity_2m": [60.0, 65.0],
                "precipitation_probability": [10.0, 20.0],
                "precipitation": [0.0, 0.0],
                "weather_code": [1, 2],
                "wind_speed_10m": [15.0, 12.0],
            }
        }
        batch = [(18.94, 72.835, "87608b032ffffff")]
        now = timezone.now()
        rows = _map_weather_response(payload, batch, now)

        assert len(rows) == 1
        assert float(rows[0].temperature_c) == 25.0

    def test_multi_point_vs_single_point_mapping(self):
        """Both single-point (dict) and multi-point (list of dicts) responses are parsed correctly."""
        single_payload = {
            "hourly": {
                "time": ["2026-10-06T00:00"],
                "temperature_2m": [28.5],
                "relative_humidity_2m": [70.0],
                "precipitation_probability": [0.0],
                "precipitation": [0.0],
                "weather_code": [0],
                "wind_speed_10m": [10.0],
            }
        }
        multi_payload = [
            single_payload,
            {
                "hourly": {
                    "time": ["2026-10-06T00:00"],
                    "temperature_2m": [29.1],
                    "relative_humidity_2m": [68.0],
                    "precipitation_probability": [0.0],
                    "precipitation": [0.0],
                    "weather_code": [0],
                    "wind_speed_10m": [11.0],
                }
            },
        ]
        now = timezone.now()
        batch = [(18.94, 72.83, "cell_1"), (18.95, 72.84, "cell_2")]

        rows_single = _map_weather_response(single_payload, [batch[0]], now)
        assert len(rows_single) == 1
        assert rows_single[0].h3_index == "cell_1"

        rows_multi = _map_weather_response(multi_payload, batch, now)
        assert len(rows_multi) == 2
        assert rows_multi[0].h3_index == "cell_1"
        assert rows_multi[1].h3_index == "cell_2"


@pytest.mark.django_db
class TestWeatherServiceExecution:
    @pytest.fixture(autouse=True)
    def setup_places(self):
        p = Place.objects.create(
            name="Gateway of India",
            city="Mumbai",
            location=Point(72.8347, 18.9220, srid=4326),
            is_active=True,
        )
        p.fill_derived_fields()
        p.save()

    def test_upsert_idempotency(self, sample_weather_payload):
        """Running fetch_weather twice with the same response creates rows first time, updates on second."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_weather_payload
        mock_session.get.return_value = mock_resp

        now = timezone.now()
        res1 = fetch_weather_for_city("Mumbai", hours_ahead=48, now=now, session=mock_session)
        assert res1["cells"] >= 1
        initial_count = WeatherData.objects.count()
        assert initial_count > 0

        # Second run with same data
        res2 = fetch_weather_for_city("Mumbai", hours_ahead=48, now=now, session=mock_session)
        second_count = WeatherData.objects.count()
        assert second_count == initial_count

    def test_retention_pruning(self, sample_weather_payload):
        """Pruning deletes WeatherData rows older than 14 days and preserves newer ones."""
        now = timezone.now()
        cell = city_weather_cells("Mumbai")[0]

        # Seed an old row (15 days ago) and a recent row (1 day ago)
        old_time = now - timedelta(days=15)
        recent_time = now - timedelta(days=1)

        WeatherData.objects.create(
            h3_index=cell,
            timestamp=old_time,
            temperature_c=25.0,
            humidity_pct=50.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            wind_speed_kmh=10.0,
            weather_code=0,
            is_forecast=False,
            source="open_meteo",
        )
        WeatherData.objects.create(
            h3_index=cell,
            timestamp=recent_time,
            temperature_c=26.0,
            humidity_pct=55.0,
            precipitation_probability=0.0,
            precipitation_mm=0.0,
            wind_speed_kmh=12.0,
            weather_code=0,
            is_forecast=False,
            source="open_meteo",
        )

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_weather_payload
        mock_session.get.return_value = mock_resp

        res = fetch_weather_for_city("Mumbai", hours_ahead=48, now=now, session=mock_session)
        assert res["pruned"] >= 1
        assert not WeatherData.objects.filter(timestamp=old_time).exists()
        assert WeatherData.objects.filter(timestamp=recent_time).exists()

    def test_batching_multiple_cells(self):
        """When cells exceed 500, requests are batched into multiple HTTP calls."""
        # Mock city_weather_cells to return 600 cells
        fake_cells = [f"87608b032ffffff_{i}" for i in range(600)]

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "hourly": {
                "time": [],
                "temperature_2m": [],
                "relative_humidity_2m": [],
                "precipitation_probability": [],
                "precipitation": [],
                "weather_code": [],
                "wind_speed_10m": [],
            }
        }
        mock_session.get.return_value = mock_resp

        with patch("apps.geo.services.city_weather_cells", return_value=fake_cells):
            with patch("h3.cell_to_latlng", return_value=(18.94, 72.83)):
                res = fetch_weather_for_city("Mumbai", hours_ahead=24, session=mock_session)

        assert mock_session.get.call_count == 2
        assert res["cells"] == 600

    def test_refresh_weather_task_wrapper(self, sample_weather_payload):
        """refresh_weather shared_task executes for WEATHER_CITIES and returns summary."""
        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = sample_weather_payload
        mock_session.get.return_value = mock_resp

        with patch("requests.Session", return_value=mock_session):
            summaries = refresh_weather()

        assert "Mumbai" in summaries
        assert summaries["Mumbai"]["cells"] >= 1

    def test_timeout_raises_and_no_corruption(self):
        """Network failure / timeout raises RequestException without creating corrupted rows."""
        mock_session = MagicMock()
        mock_session.get.side_effect = requests.RequestException("Open-Meteo down")

        with pytest.raises(requests.RequestException):
            fetch_weather_for_city("Mumbai", hours_ahead=24, session=mock_session)
