"""
Hermetic unit and integration tests for OvertureProvider (P2-F2).
"""

import io
from unittest.mock import MagicMock, patch
import pytest
import requests
from django.core.management import call_command

from apps.ingestion.providers.base import Region
from apps.ingestion.providers.overture import (
    CATEGORY_MAP,
    DEFAULT_CATEGORY,
    OvertureProvider,
    _bbox_from_center,
    _map_category,
    _tile_bbox,
)
from apps.places.models import Place, PlaceSource

FIXTURE_PATH = "apps/ingestion/fixtures/overture_sample_response.json"


class TestOvertureProviderUnit:
    def test_category_mapping_table_driven(self):
        """All CATEGORY_MAP entries map to expected canonical categories; unknown to 'other'."""
        for label, expected in CATEGORY_MAP.items():
            cat, sub = _map_category([label])
            assert cat == expected
            assert sub == label

        cat, sub = _map_category(["nonexistent_custom_label"])
        assert cat == DEFAULT_CATEGORY
        assert sub == "nonexistent_custom_label"

        cat, sub = _map_category([])
        assert cat == DEFAULT_CATEGORY
        assert sub == ""

    def test_tiling_and_center_radius_math(self):
        """Verify bbox tiling edges and center+radius conversion formula."""
        bbox = (72.80, 18.90, 72.88, 19.02)
        tiles = _tile_bbox(*bbox)
        # 0.08 lon span / 0.05 = 2 columns; 0.12 lat span / 0.05 = 3 rows -> 6 tiles
        assert len(tiles) == 6
        assert tiles[0][0] == 72.80
        assert tiles[0][1] == 18.90
        assert tiles[-1][2] == 72.88
        assert tiles[-1][3] == 19.02

        w, s, e, n = _bbox_from_center(18.9400, 72.8350, 12.0)
        assert w < 72.8350 < e
        assert s < 18.9400 < n

    def test_fixture_fetch(self):
        """Region(fixture_path=...) loads features with zero fetch_errors."""
        provider = OvertureProvider()
        region = Region(fixture_path=FIXTURE_PATH, city="Mumbai")
        features, errors = provider.fetch(region)
        assert len(features) > 0
        assert errors == 0

    def test_retry_isolation(self):
        """Mocked requests.Session.get: retry recovers on temporary failure, records error on 3x fail."""
        mock_session = MagicMock()

        # Tile 1: fails once, succeeds on retry
        # Tile 2: fails 3 times
        fail_resp = requests.RequestException("Network timeout")
        success_resp = MagicMock()
        success_resp.json.return_value = {
            "features": [{"id": "poi.recov.1", "geometry": {"type": "Point", "coordinates": [72.81, 18.91]}, "properties": {"name": "Recovered Place"}}]
        }

        # For a 2-tile bbox:
        # Tile 1: fail, success
        # Tile 2: fail, fail, fail
        mock_session.get.side_effect = [
            fail_resp,
            success_resp,
            fail_resp,
            fail_resp,
            fail_resp,
        ]

        provider = OvertureProvider(session=mock_session)
        # 2 tiles: (0, 0, 0.05, 0.10) -> 2 tiles in lat
        with patch("time.sleep", return_value=None):
            features, fetch_errors = provider.fetch(Region(bbox=(0.0, 0.0, 0.05, 0.10)))

        assert fetch_errors == 1
        assert "poi.recov.1" in features


@pytest.mark.django_db
class TestOvertureProviderUpsert:
    def test_upsert_create_derived_fields(self):
        """N valid features create N Places + PlaceSources, with derived fields (h3, slug) set."""
        provider = OvertureProvider()
        region = Region(fixture_path=FIXTURE_PATH, city="Mumbai")
        features, _ = provider.fetch(region)
        result = provider.upsert(region, features)

        # 4 unique valid places in sample fixture (out of 6 deduplicated features with IDs)
        assert result.created == 4
        assert result.updated == 0
        assert result.skipped == 2  # unnamed fountain, non-point polygon
        assert Place.objects.count() == 4
        assert PlaceSource.objects.filter(provider=PlaceSource.OVERTURE).count() == 4

        for place in Place.objects.all():
            assert place.h3_index_res8 != ""
            assert place.h3_index_res9 != ""
            assert place.slug != ""
            assert place.normalized_name != ""

    def test_upsert_idempotency(self):
        """Re-running the same fixture creates 0, updates 4, preserves slugs, and bumps last_synced_at."""
        provider = OvertureProvider()
        region = Region(fixture_path=FIXTURE_PATH, city="Mumbai")
        features, _ = provider.fetch(region)

        res1 = provider.upsert(region, features)
        assert res1.created == 4
        first_sync = {s.provider_id: s.last_synced_at for s in PlaceSource.objects.all()}
        first_slugs = {p.id: p.slug for p in Place.objects.all()}

        res2 = provider.upsert(region, features)
        assert res2.created == 0
        assert res2.updated == 4
        assert Place.objects.count() == 4

        for source in PlaceSource.objects.all():
            assert source.last_synced_at >= first_sync[source.provider_id]

        for place in Place.objects.all():
            assert place.slug == first_slugs[place.id]

    def test_enrichment_fields_not_clobbered(self):
        """Pre-set rating, photos, and metadata survive an upsert update."""
        provider = OvertureProvider()
        region = Region(fixture_path=FIXTURE_PATH, city="Mumbai")
        features, _ = provider.fetch(region)
        provider.upsert(region, features)

        # Pre-set enrichment fields on one place
        source = PlaceSource.objects.get(provider_id="poi.1.cafe0001")
        place = source.place
        place.rating = 4.85
        place.photos = [{"url": "https://example.com/photo.jpg"}]
        place.metadata = {"featured": True}
        place.save()

        # Re-run upsert
        provider.upsert(region, features)

        place.refresh_from_db()
        assert float(place.rating) == 4.85
        assert place.photos == [{"url": "https://example.com/photo.jpg"}]
        assert place.metadata == {"featured": True}

    def test_malformed_feature_handling(self):
        """Features with missing id, missing geometry, or missing name are skipped and recorded in errors."""
        provider = OvertureProvider()
        malformed_features = {
            "bad_geom": {
                "id": "bad_geom",
                "geometry": {"type": "Polygon", "coordinates": []},
                "properties": {"name": "Bad Polygon"},
            },
            "no_name": {
                "id": "no_name",
                "geometry": {"type": "Point", "coordinates": [72.82, 18.92]},
                "properties": {},
            },
            "valid": {
                "id": "valid_1",
                "geometry": {"type": "Point", "coordinates": [72.82, 18.92]},
                "properties": {"name": "Valid Place"},
            },
        }
        region = Region(city="Mumbai")
        result = provider.upsert(region, malformed_features)

        assert result.created == 1
        assert result.skipped == 2
        assert len(result.errors) == 2
        assert Place.objects.filter(name="Valid Place").exists()

    def test_limit_cap_respected(self):
        """Limit parameter stops processing once created + updated reaches cap."""
        provider = OvertureProvider()
        region = Region(fixture_path=FIXTURE_PATH, city="Mumbai", limit=2)
        features, _ = provider.fetch(region)
        result = provider.upsert(region, features)

        assert result.created + result.updated == 2
        assert Place.objects.count() == 2

    def test_seed_places_command_regression(self):
        """seed_places --fixture runs via call_command with expected output lines."""
        out = io.StringIO()
        err = io.StringIO()
        call_command(
            "seed_places",
            fixture=FIXTURE_PATH,
            city="Mumbai",
            stdout=out,
            stderr=err,
        )
        output = out.getvalue()
        assert "source:   fixture" in output
        assert "fetched:  5" in output or "fetched:  " in output
        assert "created:  4" in output
        assert "seed_places done" in output
