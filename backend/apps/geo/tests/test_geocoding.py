"""
Tests for local reverse geocoding over cached City boundaries and the
ingestion job assignment hook (P2-F6, P2-D3). No live egress required.
"""

import random
import time

import h3
import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command

from apps.geo.geocoding import reverse_geocode_city
from apps.geo.services import assign_cities
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


@pytest.mark.django_db
class TestGeocodingSmoke:
    """P2-F7 hardening: 10k-point smoke over the dev bbox.

    The plan targets 100k; this dev box runs the 10k sample the plan allows
    when PostGIS memory is a constraint. The live 100k seed is covered by the
    egress-machine runbook (F7-3) instead.
    """

    COUNT = 10_000
    W, S, E, N = 72.805, 18.905, 72.895, 19.015

    def test_10k_points_assign_and_reverse_geocode(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")

        rng = random.Random(20261008)
        places = []
        for i in range(self.COUNT):
            lng = rng.uniform(self.W, self.E)
            lat = rng.uniform(self.S, self.N)
            places.append(
                Place(
                    name=f"Smoke {i}",
                    normalized_name=f"smoke {i}",
                    slug=f"smoke-{i}",
                    category="restaurant",
                    city="",
                    is_active=True,
                    location=Point(lng, lat, srid=4326),
                    h3_index_res8=h3.latlng_to_cell(lat, lng, 8),
                    h3_index_res9=h3.latlng_to_cell(lat, lng, 9),
                )
            )
        Place.objects.bulk_create(places, batch_size=1000)
        assert Place.objects.count() == self.COUNT

        start = time.monotonic()
        results = assign_cities()
        elapsed = time.monotonic() - start

        assert results == [{"city": "Mumbai", "assigned": self.COUNT}]
        assert elapsed < 120, f"assign_cities over 10k points took {elapsed:.1f}s (budget 120s)"
        assert Place.objects.filter(city="Mumbai").count() == self.COUNT
        assert Place.objects.filter(city="").count() == 0

        # Spot-check reverse geocoding on 100 fresh random points inside the bbox.
        for _ in range(100):
            lng = rng.uniform(self.W, self.E)
            lat = rng.uniform(self.S, self.N)
            assert reverse_geocode_city(lat, lng).name == "Mumbai"
        # And outside the boundary.
        assert reverse_geocode_city(19.50, 73.50) is None
