"""
Tests for local reverse geocoding over cached City boundaries and the
ingestion job assignment hook (P2-F6, P2-D3). No live egress required.
"""

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command

from apps.geo.geocoding import reverse_geocode_city
from apps.ingestion.models import IngestionJob
from apps.ingestion.tasks import run_ingestion_job
from apps.places.factories import PlaceFactory
from apps.places.models import Place, PlaceSource

OVERTURE_FIXTURE = "apps/ingestion/fixtures/overture_sample_response.json"


@pytest.mark.django_db
class TestReverseGeocodeCity:
    def test_point_inside_returns_city(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")
        city = reverse_geocode_city(18.94, 72.835)
        assert city is not None
        assert city.name == "Mumbai"

    def test_point_outside_returns_none(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")
        assert reverse_geocode_city(19.50, 73.50) is None

    def test_no_cities_returns_none(self):
        assert reverse_geocode_city(18.94, 72.835) is None

    def test_overlapping_boundaries_deterministic_by_name(self):
        """Two overlapping rectangles: alphabetically-first city wins."""
        call_command("load_city", name="Zeta", bbox="72.80,18.90,72.90,19.02")
        call_command("load_city", name="Alpha", bbox="72.82,18.92,72.88,19.00")
        assert reverse_geocode_city(18.94, 72.835).name == "Alpha"


@pytest.mark.django_db
class TestJobAssignmentHook:
    def test_job_summary_reports_assignment(self):
        """F3 hook: a completed fixture job assigns blank-city places inside
        the region's cached city boundary and reports the count in the summary."""
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")
        PlaceFactory(city="", location=Point(72.835, 18.940, srid=4326))

        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region=f"fixture:{OVERTURE_FIXTURE}|city:Mumbai",
            status="pending",
        )
        result = run_ingestion_job(str(job.pk))

        assert result["status"] == "completed"
        assert any(
            entry["city"] == "Mumbai" and entry["assigned"] >= 1
            for entry in result["city_assignment"]
        )
        assert Place.objects.filter(city="Mumbai").count() >= 1

    def test_job_without_city_region_skips_assignment(self):
        """A bbox-only region has no city to assign against -> hook is a no-op."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region=f"fixture:{OVERTURE_FIXTURE}",
            status="pending",
        )
        result = run_ingestion_job(str(job.pk))
        assert result["status"] == "completed"
        assert result["city_assignment"] is None
