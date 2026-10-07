"""
Hermetic tests for cached City boundaries: load_city command + city
assignment (P2-F6). Nominatim is mocked; no live egress required.
"""

from unittest.mock import MagicMock, patch

import pytest
import requests
from django.contrib.gis.geos import Point
from django.core.management import CommandError, call_command

from apps.geo.models import City
from apps.geo.services import assign_cities
from apps.places.factories import PlaceFactory
from apps.places.models import Place

GEOJSON_FIXTURE = "apps/geo/fixtures/city_bbox_sample.geojson"
INSIDE = Point(72.835, 18.940, srid=4326)
OUTSIDE = Point(73.50, 19.50, srid=4326)
CMD = "apps.geo.management.commands.load_city"

NOMINATIM_HIT = {
    "osm_type": "relation",
    "osm_id": 3165948,
    "address": {"country": "India"},
    "geojson": {
        "type": "Polygon",
        "coordinates": [
            [
                [72.80, 18.90],
                [72.90, 18.90],
                [72.90, 19.02],
                [72.80, 19.02],
                [72.80, 18.90],
            ]
        ],
    },
}


def boundary_gist_indexes():
    """Introspect pg_indexes: exactly the GistIndex on City.boundary."""
    from django.db import connection

    with connection.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes "
            "WHERE tablename = 'geo_cities' AND indexdef ILIKE '%%boundary%%'"
        )
        return [row[0] for row in cur.fetchall()]


@pytest.mark.django_db
class TestLoadCity:
    def test_bbox_creates_city_with_single_gist(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.88,19.02")
        city = City.objects.get(name="Mumbai")
        assert city.boundary.valid
        assert city.centroid is not None
        assert city.source == "bbox"
        assert city.slug == "mumbai"
        assert boundary_gist_indexes() == ["idx_geocity_boundary_gist"]

    def test_geojson_file_creates_city(self):
        call_command("load_city", name="Mumbai", geojson=GEOJSON_FIXTURE)
        city = City.objects.get(name="Mumbai")
        assert city.source == "geojson"
        assert city.source_id == "city_bbox_sample.geojson"
        assert city.boundary.valid
        assert boundary_gist_indexes() == ["idx_geocity_boundary_gist"]

    def test_nominatim_success(self):
        resp = MagicMock(status_code=200)
        resp.json.return_value = [NOMINATIM_HIT]
        session = MagicMock()
        session.get.return_value = resp
        with patch(f"{CMD}.requests.Session", return_value=session):
            call_command("load_city", name="Mumbai", source="nominatim")

        city = City.objects.get(name="Mumbai")
        assert city.source == "nominatim"
        assert city.source_id == "relation/3165948"
        assert city.country == "India"
        assert city.boundary.valid
        assert city.centroid is not None
        _, kwargs = session.get.call_args
        assert kwargs["headers"]["User-Agent"].startswith("Viaggio/2.0")
        assert kwargs["params"]["polygon_geojson"] == 1

    def test_nominatim_retry_sleeps_at_most_per_second(self):
        bad = MagicMock(status_code=503)
        good = MagicMock(status_code=200)
        good.json.return_value = [NOMINATIM_HIT]
        session = MagicMock()
        session.get.side_effect = [bad, good]
        with patch(f"{CMD}.requests.Session", return_value=session), patch(
            f"{CMD}.time.sleep"
        ) as mock_sleep:
            call_command("load_city", name="Mumbai", source="nominatim")
        mock_sleep.assert_called_once_with(1.1)
        assert City.objects.get(name="Mumbai").source == "nominatim"

    def test_nominatim_unreachable_no_row_written(self):
        session = MagicMock()
        session.get.side_effect = requests.RequestException("egress down")
        with patch(f"{CMD}.requests.Session", return_value=session), patch(
            f"{CMD}.time.sleep"
        ):
            with pytest.raises(CommandError):
                call_command("load_city", name="Mumbai", source="nominatim")
        assert not City.objects.exists()

    def test_nominatim_http_errors_twice_commanderror(self):
        session = MagicMock()
        session.get.return_value = MagicMock(status_code=503)
        with patch(f"{CMD}.requests.Session", return_value=session), patch(
            f"{CMD}.time.sleep"
        ):
            with pytest.raises(CommandError):
                call_command("load_city", name="Mumbai", source="nominatim")
        assert not City.objects.exists()

    def test_idempotent_reload_updates_not_duplicates(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.88,19.02")
        call_command("load_city", name="Mumbai", bbox="72.81,18.91,72.87,19.01")
        assert City.objects.count() == 1
        minx, miny, maxx, maxy = City.objects.get(name="Mumbai").boundary.extent
        assert minx == pytest.approx(72.81)
        assert maxx == pytest.approx(72.87)
        assert maxy == pytest.approx(19.01)

    def test_invalid_bbox_rejected(self):
        with pytest.raises(CommandError):
            call_command("load_city", name="Mumbai", bbox="72.90,18.90,72.80,19.02")
        with pytest.raises(CommandError):
            call_command("load_city", name="Mumbai", bbox="not,a,valid,box")
        assert not City.objects.exists()


@pytest.mark.django_db
class TestAssignCities:
    @pytest.fixture
    def city(self):
        call_command("load_city", name="Mumbai", bbox="72.80,18.90,72.90,19.02")
        return City.objects.get(name="Mumbai")

    def test_fills_blank_city_for_places_inside(self, city):
        PlaceFactory(city="", location=INSIDE)
        res = assign_cities()
        assert res == [{"city": "Mumbai", "assigned": 1}]
        assert Place.objects.get().city == "Mumbai"

    def test_places_outside_untouched(self, city):
        PlaceFactory(city="", location=OUTSIDE)
        assert assign_cities() == [{"city": "Mumbai", "assigned": 0}]
        assert Place.objects.get().city == ""

    def test_provider_locality_wins(self, city):
        """A provider-supplied city is never overwritten by assignment."""
        PlaceFactory(city="Bandra", location=INSIDE)
        assert assign_cities() == [{"city": "Mumbai", "assigned": 0}]
        assert Place.objects.get().city == "Bandra"

    def test_inactive_places_untouched(self, city):
        PlaceFactory(city="", is_active=False, location=INSIDE)
        assert assign_cities() == [{"city": "Mumbai", "assigned": 0}]
        assert Place.objects.get().city == ""

    def test_city_name_filter_skips_other_cities(self, city):
        PlaceFactory(city="", location=INSIDE)
        assert assign_cities(city_name="Nope") == []
        assert Place.objects.get().city == ""
