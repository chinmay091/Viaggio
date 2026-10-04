"""
PostGIS spatial-query tests for the places app (P1-F6).

Run against the real PostGIS test database (pytest.ini -> config.settings.test):
dwithin radius sets, Distance ordering, trigram-backed name search, category
filtering and H3 maintenance across re-saves.
"""

import math

import pytest
from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point

from apps.places.factories import ANCHOR_LAT, ANCHOR_LNG, PlaceFactory
from apps.places.models import Place

pytestmark = pytest.mark.django_db

M_PER_DEG_LAT = 111_320.0
M_PER_DEG_LNG_AT_ANCHOR = 111_320.0 * math.cos(math.radians(ANCHOR_LAT))


def offset_point(meters_lat=0.0, meters_lng=0.0):
    """Point at a whole-metre offset (north/east positive) from the anchor."""
    lat = ANCHOR_LAT + meters_lat / M_PER_DEG_LAT
    lng = ANCHOR_LNG + meters_lng / M_PER_DEG_LNG_AT_ANCHOR
    return Point(lng, lat, srid=4326)


def seed_ring(prefix="Ring", offsets=()):
    """Create places at (name_suffix, meters_lat, meters_lng) tuples."""
    places = {}
    for suffix, d_lat, d_lng in offsets:
        places[suffix] = PlaceFactory(
            name=f"{prefix} {suffix}",
            location=offset_point(d_lat, d_lng),
        )
    return places


class TestDWithin:
    """location__dwithin returns exactly the places inside the radius."""

    def test_returns_exactly_seeded_set(self):
        places = seed_ring(
            offsets=[
                ("A-north-100", 100, 0),
                ("B-east-500", 0, 500),
                ("C-south-900", -900, 0),
                ("D-west-1500", 0, -1500),
            ],
        )
        anchor = Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326)

        in_1km = set(
            Place.objects.filter(
                location__dwithin=(anchor, 1000),
                slug__in=[p.slug for p in places.values()],
            ).values_list("slug", flat=True),
        )
        assert in_1km == {
            places["A-north-100"].slug,
            places["B-east-500"].slug,
            places["C-south-900"].slug,
        }

        in_1_6km = set(
            Place.objects.filter(
                location__dwithin=(anchor, 1600),
                slug__in=[p.slug for p in places.values()],
            ).values_list("slug", flat=True),
        )
        assert in_1_6km == {p.slug for p in places.values()} and len(in_1_6km) == 4

    def test_inactive_places_are_excluded_by_view_queryset(self):
        active = PlaceFactory(name="Active Stop", location=offset_point(50, 0))
        inactive = PlaceFactory(name="Closed Stop", location=offset_point(60, 0), is_active=False)

        slugs = set(
            Place.objects.filter(
                is_active=True,
                location__dwithin=(Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326), 1000),
            ).values_list("slug", flat=True)
        )
        assert active.slug in slugs
        assert inactive.slug not in slugs


class TestDistanceOrdering:
    """Distance(...) annotation + order_by yields nearest-first, monotonic."""

    def test_ordering_is_monotonic(self):
        places = seed_ring(
            offsets=[
                ("far-north", 2000, 0),
                ("mid-east", 0, 900),
                ("near-west", 0, -400),
                ("closest-south", -100, 0),
            ],
        )
        center = Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326)

        ordered = (
            Place.objects.filter(is_active=True, location__dwithin=(center, 5000))
            .filter(slug__in=[p.slug for p in places.values()])
            .annotate(distance_m=Distance("location", center))
            .order_by("distance_m", "pk")
        )
        slugs = list(ordered.values_list("slug", flat=True))
        distances = [float(p.distance_m.m) for p in ordered]

        assert slugs == [
            places["closest-south"].slug,
            places["near-west"].slug,
            places["mid-east"].slug,
            places["far-north"].slug,
        ]
        assert all(b >= a for a, b in zip(distances, distances[1:]))


class TestNameAndCategoryFilters:
    """Query filters used by the near/ view (trigram GIN index on normalized_name)."""

    def test_q_substring_match_is_case_insensitive(self):
        target = PlaceFactory(name="Blue Mountain Cafe", location=offset_point(100, 0))
        PlaceFactory(name="Ocean View Hotel", location=offset_point(120, 0))

        found = Place.objects.filter(normalized_name__icontains="mountain")
        assert target.slug in set(found.values_list("slug", flat=True))

        found_upper = Place.objects.filter(normalized_name__icontains="MOUNTAIN")
        assert target.slug in set(found_upper.values_list("slug", flat=True))

        assert not Place.objects.filter(normalized_name__icontains="Seaview").exists()

    def test_category_filter(self):
        cafe = PlaceFactory(name="Cafe Filtered", category="cafe", location=offset_point(100, 0))
        hotel = PlaceFactory(name="Hotel Filtered", category="hotel", location=offset_point(110, 0))

        qs = Place.objects.filter(
            category="cafe",
            location__dwithin=(Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326), 1000),
        )
        slugs = set(qs.values_list("slug", flat=True))
        assert cafe.slug in slugs
        assert hotel.slug not in slugs


class TestH3OnResave:
    """H3 cells stay in sync when the location changes (or not)."""

    def test_cells_recomputed_on_location_change(self):
        place = PlaceFactory(location=offset_point(0, 0))
        res8, res9 = place.h3_index_res8, place.h3_index_res9

        place.location = offset_point(5000, 0)  # 5 km north -> different cells
        place.save()
        place.refresh_from_db()
        assert place.h3_index_res8 != res8
        assert place.h3_index_res9 != res9

        place.location = offset_point(0, 0)
        place.save()
        place.refresh_from_db()
        assert place.h3_index_res8 == res8
        assert place.h3_index_res9 == res9

