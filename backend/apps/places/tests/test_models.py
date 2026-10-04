"""
Model-level tests for the places app (P1-F6).

Covers derived-field maintenance (normalized_name, slug, H3 cells),
provenance constraints and audit timestamps.
"""

import math

import h3
import pytest
from django.contrib.gis.geos import Point
from django.db import IntegrityError, transaction

from apps.places.factories import (
    ANCHOR_LAT,
    ANCHOR_LNG,
    PlaceFactory,
    PlaceCategoryFactory,
    SourceFactory,
    TagFactory,
)
from apps.places.models import Place, PlaceSource

pytestmark = pytest.mark.django_db


def haversine_m(lat1, lng1, lat2, lng2):
    """Great-circle distance in metres (WGS84 mean-radius sphere)."""
    r = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# Maximum distance from an H3 cell centre to a vertex (circumradius):
# res 8 ~393 m, res 9 ~117 m. Assertions use conservative ceilings.
H3_RES8_CEILING_M = 450.0
H3_RES9_CEILING_M = 150.0


class TestDerivedFields:
    """save() derives normalized_name, a unique slug and H3 cells (D1/D3)."""

    def test_save_sets_normalized_name(self):
        place = PlaceFactory(name="  Grand Old Cafe  ")

        assert place.normalized_name == "grand old cafe"

    def test_slug_auto_generated_from_name(self):
        place = PlaceFactory(name="Blue Mountain Cafe")

        assert place.slug == "blue-mountain-cafe"

    def test_slug_globally_unique_for_same_name(self):
        first = PlaceFactory(name="Blue Mountain Cafe")
        second = PlaceFactory(name="Blue Mountain Cafe")
        third = PlaceFactory(name="Blue Mountain Cafe")

        assert [p.slug for p in (first, second, third)] == [
            "blue-mountain-cafe",
            "blue-mountain-cafe-2",
            "blue-mountain-cafe-3",
        ]

    def test_h3_cells_valid_and_consistent_with_location(self):
        place = PlaceFactory(location=Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326))
        place.refresh_from_db()

        assert h3.is_valid_cell(place.h3_index_res8)
        assert h3.is_valid_cell(place.h3_index_res9)

        for cell, ceiling in (
            (place.h3_index_res8, H3_RES8_CEILING_M),
            (place.h3_index_res9, H3_RES9_CEILING_M),
        ):
            center_lat, center_lng = h3.cell_to_latlng(cell)
            distance = haversine_m(ANCHOR_LAT, ANCHOR_LNG, center_lat, center_lng)
            assert distance < ceiling

    def test_h3_cells_identical_for_same_point(self):
        location = Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326)
        first = PlaceFactory(location=location)
        second = PlaceFactory(location=location)

        assert first.h3_index_res8 == second.h3_index_res8
        assert first.h3_index_res9 == second.h3_index_res9

    def test_h3_cells_differ_for_far_apart_points(self):
        near = PlaceFactory(location=Point(ANCHOR_LNG, ANCHOR_LAT, srid=4326))
        far = PlaceFactory(
            location=Point(ANCHOR_LNG + 0.01, ANCHOR_LAT + 0.01, srid=4326)
        )  # ~1.5 km away

        assert near.h3_index_res8 != far.h3_index_res8
        assert near.h3_index_res9 != far.h3_index_res9


class TestPlaceSource:
    """Provenance records carry a globally unique (provider, provider_id)."""

    def test_source_defaults(self):
        source = SourceFactory()

        assert source.provider == PlaceSource.OVERTURE
        assert float(source.confidence) == 1.00
        assert source.last_synced_at is None
        assert source.place is not None

    def test_duplicate_provider_id_raises_integrity_error(self):
        first = SourceFactory(provider="OVERTURE", provider_id="poi.duplicate.1")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SourceFactory(place=PlaceFactory(), provider="OVERTURE", provider_id="poi.duplicate.1")

    def test_same_provider_id_allowed_for_different_providers(self):
        SourceFactory(provider="OVERTURE", provider_id="poi.shared.1")

        second = SourceFactory(provider="FOURSQUARE", provider_id="poi.shared.1")

        assert second.pk is not None


class TestAuditModel:
    """Timestamps inherited from AuditModel (UUIDModel + TimeStampedModel)."""

    def test_created_and_updated_at_populated_on_save(self):
        place = PlaceFactory()

        assert place.created_at is not None
        assert place.updated_at is not None
        assert place.created_at <= place.updated_at

    def test_updated_at_moves_forward_on_update(self):
        place = PlaceFactory()
        before = place.updated_at

        place.description = "Updated by test."
        place.save()
        place.refresh_from_db()

        assert place.updated_at >= before

    def test_uuid_primary_key_unique(self):
        first, second = PlaceFactory(), PlaceFactory()

        assert first.pk != second.pk


class TestCategoryAndTag:
    """Small companion models exercised by the factories."""

    def test_category_hierarchy(self):
        parent = PlaceCategoryFactory()
        child = PlaceCategoryFactory(parent=parent)

        assert child.parent == parent
        assert child in parent.children.all()

    def test_tag_links_to_places(self):
        place = PlaceFactory()
        tag = TagFactory()
        tag.places.add(place)

        assert tag in place.tags.all()
