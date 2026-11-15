"""
Tests for City Pulse hotspots API (P3-F5).

Target coverage:
- 401 unauthenticated
- 400 validation: missing lat/lng, malformed floats, out of range coordinates, invalid radius_m / top_n
- Empty area: hotspots=[] + parent-cell weather context present
- Empty area without weather: weather=null
- Ordering & z-score math & unusually_busy flag (z >= 2.0 and sample_count >= 3)
- Anomaly rules: stddev=0 -> z=null, sample_count < 3 -> z=null
- Spatial filtering: distant cell outside radius excluded
- top_n parameter capping
- hour_total sum over last 12 buckets
- Polygon structure (6 [lng, lat] vertices) and center
"""

from datetime import datetime, timedelta
from decimal import Decimal
import zoneinfo

import h3
import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.factories import UserFactory
from apps.activity.factories import ActivityAggregateFactory, HistoricalBaselineFactory
from apps.geo.factories import WeatherDataFactory

PULSE_URL = "/api/v1/activity/pulse/"
IST = zoneinfo.ZoneInfo("Asia/Kolkata")
ANCHOR_LAT = 18.9400
ANCHOR_LNG = 72.8350


def assert_error_envelope(data):
    assert data["error"] is True
    assert isinstance(data["message"], str) and data["message"]
    assert isinstance(data["code"], str) and data["code"]
    assert "details" in data
    assert "correlation_id" in data


@pytest.fixture
def auth_client():
    user = UserFactory(location_sharing_consent=True)
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.mark.django_db
class TestPulseAuthenticationAndValidation:
    """Test auth gate and query parameter validation."""

    def test_unauthenticated_returns_401(self):
        client = APIClient()
        response = client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert_error_envelope(response.json())

    def test_missing_lat_lng_400(self, auth_client):
        response = auth_client.get(PULSE_URL)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert_error_envelope(data)
        assert "lat" in data["details"]
        assert "lng" in data["details"]

    def test_malformed_lat_lng_400(self, auth_client):
        response = auth_client.get(f"{PULSE_URL}?lat=abc&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng=xyz")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())

    def test_out_of_range_lat_lng_400(self, auth_client):
        response = auth_client.get(f"{PULSE_URL}?lat=95.0&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng=185.0")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())

    def test_malformed_radius_and_top_n_400(self, auth_client):
        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&radius_m=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&top_n=invalid")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert_error_envelope(response.json())


@pytest.mark.django_db
class TestPulseHotspotsAndWeather:
    """Test hotspot calculation, baselines, z-scores, and weather context."""

    def test_empty_area_with_weather(self, auth_client):
        """Empty area returns empty hotspots list with parent res7 weather context."""
        now = timezone.now()
        origin_res8 = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)
        parent_res7 = h3.cell_to_parent(origin_res8, 7)

        WeatherDataFactory(
            h3_index=parent_res7,
            timestamp=now,
            temperature_c=Decimal("31.20"),
            weather_code=2,
            precipitation_probability=Decimal("10.00"),
            is_forecast=False,
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&radius_m=1000")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data["hotspots"] == []
        assert data["timezone"] == "Asia/Kolkata"
        assert data["radius_m"] == 1000.0
        assert data["weather"] is not None
        assert data["weather"]["temperature_c"] == 31.2
        assert data["weather"]["weather_code"] == 2
        assert data["weather"]["precipitation_probability"] == 10.0
        assert data["weather"]["is_forecast"] is False
        assert "local_time" in data["weather"]

    def test_empty_area_without_weather(self, auth_client):
        """When no WeatherData exists, weather field is null."""
        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["hotspots"] == []
        assert data["weather"] is None

    def test_ordering_and_z_score_and_unusually_busy(self, auth_client):
        """
        Hotspots ordered by active_count desc, z_score desc nulls last.
        Cell A: active=12, avg=4.0, sd=2.0, n=5 -> z=4.0 -> unusually_busy=True
        Cell B: active=10, avg=9.0, sd=2.0, n=5 -> z=0.5 -> unusually_busy=False
        Cell C: active=5, avg=1.0, sd=1.0, n=4 -> z=4.0 -> unusually_busy=True
        """
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)
        dow = bucket_time.weekday()
        minute_slot = bucket_time.hour * 60 + bucket_time.minute

        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)
        disk = list(h3.grid_disk(origin_cell, 1))  # 7 adjacent cells
        cell_a, cell_b, cell_c = disk[0], disk[1], disk[2]

        # Activity aggregates for current bucket
        ActivityAggregateFactory(
            h3_index=cell_a, resolution=8, time_bucket=bucket_time, active_count=12, event_count=20
        )
        ActivityAggregateFactory(
            h3_index=cell_b, resolution=8, time_bucket=bucket_time, active_count=10, event_count=15
        )
        ActivityAggregateFactory(
            h3_index=cell_c, resolution=8, time_bucket=bucket_time, active_count=5, event_count=10
        )

        # Historical baselines
        HistoricalBaselineFactory(
            h3_index=cell_a, resolution=8, day_of_week=dow, time_bucket_minutes=minute_slot,
            avg_active_count=Decimal("4.00"), stddev_active_count=Decimal("2.00"), sample_count=5
        )
        HistoricalBaselineFactory(
            h3_index=cell_b, resolution=8, day_of_week=dow, time_bucket_minutes=minute_slot,
            avg_active_count=Decimal("9.00"), stddev_active_count=Decimal("2.00"), sample_count=5
        )
        HistoricalBaselineFactory(
            h3_index=cell_c, resolution=8, day_of_week=dow, time_bucket_minutes=minute_slot,
            avg_active_count=Decimal("1.00"), stddev_active_count=Decimal("1.00"), sample_count=4
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&radius_m=2000")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        hotspots = data["hotspots"]

        assert len(hotspots) == 3
        # Check order: Cell A (12), Cell B (10), Cell C (5)
        assert hotspots[0]["h3_index"] == cell_a
        assert hotspots[0]["active_count"] == 12
        assert hotspots[0]["z_score"] == 4.0
        assert hotspots[0]["unusually_busy"] is True

        assert hotspots[1]["h3_index"] == cell_b
        assert hotspots[1]["active_count"] == 10
        assert hotspots[1]["z_score"] == 0.5
        assert hotspots[1]["unusually_busy"] is False

        assert hotspots[2]["h3_index"] == cell_c
        assert hotspots[2]["active_count"] == 5
        assert hotspots[2]["z_score"] == 4.0
        assert hotspots[2]["unusually_busy"] is True

    def test_stddev_zero_yields_null_z(self, auth_client):
        """When stddev=0, z_score is null and unusually_busy is False (P3-D6)."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)
        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)

        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time, active_count=10
        )
        HistoricalBaselineFactory(
            h3_index=origin_cell,
            resolution=8,
            day_of_week=bucket_time.weekday(),
            time_bucket_minutes=bucket_time.hour * 60 + bucket_time.minute,
            avg_active_count=Decimal("10.00"),
            stddev_active_count=Decimal("0.00"),
            sample_count=5,
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_200_OK
        hotspot = response.json()["hotspots"][0]
        assert hotspot["z_score"] is None
        assert hotspot["unusually_busy"] is False

    def test_sample_count_less_than_three_yields_null_z(self, auth_client):
        """When sample_count < 3, z_score is null and unusually_busy is False (P3-D6)."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)
        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)

        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time, active_count=20
        )
        HistoricalBaselineFactory(
            h3_index=origin_cell,
            resolution=8,
            day_of_week=bucket_time.weekday(),
            time_bucket_minutes=bucket_time.hour * 60 + bucket_time.minute,
            avg_active_count=Decimal("5.00"),
            stddev_active_count=Decimal("2.00"),
            sample_count=2,  # < 3
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_200_OK
        hotspot = response.json()["hotspots"][0]
        assert hotspot["z_score"] is None
        assert hotspot["unusually_busy"] is False

    def test_distant_cell_outside_radius_excluded(self, auth_client):
        """Cells whose centers exceed radius_m are excluded from response."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)

        # Near cell (~100 m from anchor)
        near_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)
        # Far cell (~15 km away in Mumbai north corridor)
        far_cell = h3.latlng_to_cell(19.05, 72.88, 8)

        ActivityAggregateFactory(
            h3_index=near_cell, resolution=8, time_bucket=bucket_time, active_count=5
        )
        ActivityAggregateFactory(
            h3_index=far_cell, resolution=8, time_bucket=bucket_time, active_count=50
        )

        # Search with 1000m radius
        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&radius_m=1000")
        assert response.status_code == status.HTTP_200_OK
        hotspots = response.json()["hotspots"]
        returned_cells = [h["h3_index"] for h in hotspots]

        assert near_cell in returned_cells
        assert far_cell not in returned_cells

    def test_top_n_cap(self, auth_client):
        """top_n limits hotspot count; capped at 50."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)

        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)
        disk = list(h3.grid_disk(origin_cell, 1))[:5]  # 5 cells

        for i, cell in enumerate(disk):
            ActivityAggregateFactory(
                h3_index=cell, resolution=8, time_bucket=bucket_time, active_count=i + 1
            )

        response = auth_client.get(
            f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}&radius_m=2000&top_n=2"
        )
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["hotspots"]) == 2

    def test_hour_total_math(self, auth_client):
        """hour_total reflects the sum of event_count for the cell over the last 12 buckets."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)
        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)

        # Current bucket: 10 events
        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time,
            active_count=5, event_count=10
        )
        # Bucket 15m ago (within 1 hour): 15 events
        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time - timedelta(minutes=15),
            active_count=3, event_count=15
        )
        # Bucket 45m ago (within 1 hour): 20 events
        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time - timedelta(minutes=45),
            active_count=4, event_count=20
        )
        # Bucket 2 hours ago (outside 1 hour window): 100 events
        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time - timedelta(hours=2),
            active_count=10, event_count=100
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_200_OK
        hotspot = response.json()["hotspots"][0]
        assert hotspot["event_count"] == 10
        # 10 + 15 + 20 = 45
        assert hotspot["hour_total"] == 45

    def test_polygon_format_and_center(self, auth_client):
        """Hotspot contains 6-vertex polygon of [lng, lat] and center dict."""
        now = timezone.now().astimezone(IST)
        bucket_min = (now.minute // 5) * 5
        bucket_time = now.replace(minute=bucket_min, second=0, microsecond=0)
        origin_cell = h3.latlng_to_cell(ANCHOR_LAT, ANCHOR_LNG, 8)

        ActivityAggregateFactory(
            h3_index=origin_cell, resolution=8, time_bucket=bucket_time, active_count=5
        )

        response = auth_client.get(f"{PULSE_URL}?lat={ANCHOR_LAT}&lng={ANCHOR_LNG}")
        assert response.status_code == status.HTTP_200_OK
        hotspot = response.json()["hotspots"][0]

        assert "center" in hotspot
        assert "lat" in hotspot["center"] and "lng" in hotspot["center"]
        assert isinstance(hotspot["center"]["lat"], float)
        assert isinstance(hotspot["center"]["lng"], float)

        assert "polygon" in hotspot
        assert len(hotspot["polygon"]) == 6
        for vertex in hotspot["polygon"]:
            assert len(vertex) == 2
            lng, lat = vertex
            assert -180.0 <= lng <= 180.0
            assert -90.0 <= lat <= 90.0
