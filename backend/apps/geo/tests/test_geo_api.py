"""
API tests for the public geo read endpoints (P3-F7, P2 carry-over).

Covers: JWT required on all three endpoints, weather/now latest-observation
vs first-forecast fallback + 404 when the cell is uncached, forecast
horizon filtering/clamping, and reverse-geocode inside-boundary (city) vs
outside (city: null). No network I/O — rows come from factories / the
hermetic `load_city --bbox` command.
"""

from datetime import timedelta

import h3
import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.geo.factories import WeatherDataFactory

pytestmark = pytest.mark.django_db

NOW_URL = "/api/v1/geo/weather/now/"
FORECAST_URL = "/api/v1/geo/weather/forecast/"
REVERSE_URL = "/api/v1/geo/reverse-geocode/"

MUMBAI = {"lat": "18.94", "lng": "72.835"}
ANCHOR_CELL = h3.latlng_to_cell(18.94, 72.835, 7)


@pytest.fixture
def authed_client(api_client, user):
    """DRF test client authenticated as a real user (force_authenticate)."""
    api_client.force_authenticate(user=user)
    return api_client


def assert_error_envelope(data):
    assert data["error"] is True
    assert isinstance(data["message"], str) and data["message"]
    assert isinstance(data["code"], str) and data["code"]
    assert "details" in data
    assert "correlation_id" in data


def assert_ist_offset(local_time: str):
    assert local_time.endswith("+05:30")


class TestAuthentication:
    def test_all_endpoints_require_authentication(self, api_client):
        for url in (NOW_URL, FORECAST_URL, REVERSE_URL):
            response = api_client.get(url, MUMBAI)
            assert response.status_code == 401
            assert_error_envelope(response.json())


class TestWeatherNow:
    def test_returns_latest_observation(self, authed_client):
        WeatherDataFactory(
            h3_index=ANCHOR_CELL,
            timestamp=timezone.now() - timedelta(minutes=30),
            temperature_c="31.20",
            is_forecast=False,
        )

        response = authed_client.get(NOW_URL, MUMBAI)

        assert response.status_code == 200
        data = response.json()
        assert data["h3_index"] == ANCHOR_CELL
        assert data["is_forecast"] is False
        assert data["temperature_c"] == 31.2
        assert data["source"] == "open_meteo"
        assert_ist_offset(data["local_time"])

    def test_falls_back_to_first_forecast(self, authed_client):
        WeatherDataFactory(
            h3_index=ANCHOR_CELL,
            timestamp=timezone.now() + timedelta(hours=2),
            is_forecast=True,
        )

        response = authed_client.get(NOW_URL, MUMBAI)

        assert response.status_code == 200
        assert response.json()["is_forecast"] is True

    def test_404_when_cell_has_no_data(self, authed_client):
        # Row in a different cell must not satisfy the anchor lookup.
        WeatherDataFactory()

        response = authed_client.get(NOW_URL, MUMBAI)

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_invalid_lat_400(self, authed_client):
        response = authed_client.get(NOW_URL, {"lat": "95", "lng": "72.835"})

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_missing_params_400(self, authed_client):
        response = authed_client.get(NOW_URL, {})

        assert response.status_code == 400
        assert_error_envelope(response.json())


class TestWeatherForecast:
    def test_returns_future_points_oldest_first(self, authed_client):
        now = timezone.now()
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=5), is_forecast=True)
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=1), is_forecast=True)
        # Outside the default 24 h horizon.
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=30), is_forecast=True)

        response = authed_client.get(FORECAST_URL, MUMBAI)

        assert response.status_code == 200
        data = response.json()
        assert data["h3_index"] == ANCHOR_CELL
        assert data["timezone"] == "Asia/Kolkata"
        assert data["hours"] == 24
        timestamps = [p["timestamp"] for p in data["points"]]
        assert len(timestamps) == 2
        assert timestamps == sorted(timestamps)  # oldest first
        assert_ist_offset(data["points"][0]["local_time"])

    def test_hours_clamped_to_max(self, authed_client):
        now = timezone.now()
        for hour in (1, 5, 30):
            WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=hour), is_forecast=True)

        response = authed_client.get(FORECAST_URL, {**MUMBAI, "hours": "100"})

        assert response.status_code == 200
        data = response.json()
        assert data["hours"] == 48
        assert len(data["points"]) == 3  # the 30 h row is now inside

    def test_hours_clamped_to_min(self, authed_client):
        now = timezone.now()
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=1), is_forecast=True)
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=now + timedelta(hours=5), is_forecast=True)

        response = authed_client.get(FORECAST_URL, {**MUMBAI, "hours": "0"})

        assert response.status_code == 200
        data = response.json()
        assert data["hours"] == 1
        assert len(data["points"]) == 1  # only the 1 h row

    def test_malformed_hours_400(self, authed_client):
        response = authed_client.get(FORECAST_URL, {**MUMBAI, "hours": "abc"})

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_empty_when_no_forecast(self, authed_client):
        # Only an observation (past) — no future rows.
        WeatherDataFactory(h3_index=ANCHOR_CELL, timestamp=timezone.now() - timedelta(hours=1))

        response = authed_client.get(FORECAST_URL, MUMBAI)

        assert response.status_code == 200
        data = response.json()
        assert data["points"] == []


class TestReverseGeocode:
    def test_inside_boundary_returns_city(self, authed_client):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")

        response = authed_client.get(REVERSE_URL, MUMBAI)

        assert response.status_code == 200
        data = response.json()
        assert data["city"] is not None
        assert data["city"]["name"] == "Mumbai"
        assert data["timezone"] == "Asia/Kolkata"

    def test_outside_boundary_returns_null_city(self, authed_client):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")

        response = authed_client.get(REVERSE_URL, {"lat": "40.0", "lng": "75.0"})

        assert response.status_code == 200
        assert response.json()["city"] is None

    def test_no_cities_returns_null_city(self, authed_client):
        response = authed_client.get(REVERSE_URL, MUMBAI)

        assert response.status_code == 200
        assert response.json()["city"] is None

    def test_invalid_lat_400(self, authed_client):
        response = authed_client.get(REVERSE_URL, {"lat": "-95", "lng": "72.835"})

        assert response.status_code == 400
        assert_error_envelope(response.json())