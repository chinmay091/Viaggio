"""
API tests for the place discovery endpoints (P1-F6).

Covers the F4 contract: JWT required, paginated list envelope with
distance_m, the standard JSON error envelope on 400/404, the detail and
nearby endpoints, pagination and radius clamping (decision D5).
"""

import uuid

import pytest

from apps.places.factories import PlaceFactory, SourceFactory, TagFactory
from apps.places.tests.test_geo_queries import offset_point

pytestmark = pytest.mark.django_db

NEAR_URL = "/api/v1/places/near/"
CARD_FIELDS = (
    "id",
    "name",
    "slug",
    "category",
    "subcategory",
    "rating",
    "review_count",
    "price_level",
    "address",
    "phone",
    "website",
    "photos",
    "tags",
    "location",
    "distance_m",
)


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


class TestAuthentication:
    """All places endpoints are JWT-protected (decision D4)."""

    def test_near_requires_authentication(self, api_client):
        response = api_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835"})

        assert response.status_code == 401
        assert_error_envelope(response.json())

    def test_detail_and_nearby_require_authentication(self, api_client):
        place = PlaceFactory()

        detail = api_client.get(f"/api/v1/places/{place.pk}/")
        nearby = api_client.get(f"/api/v1/places/{place.pk}/nearby/")

        assert detail.status_code == 401
        assert nearby.status_code == 401

    def test_malformed_token_is_rejected(self, api_client):
        api_client.credentials(HTTP_AUTHORIZATION="Bearer not-a-real-token")

        response = api_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835"})

        assert response.status_code == 401
        assert_error_envelope(response.json())

class TestNearList:
    """GET /api/v1/places/near/ — paginated envelope, card fields, ordering."""

    def test_list_envelope_with_card_fields_and_distance_ordering(self, authed_client):
        near = PlaceFactory(name="Stop Near", category="cafe", location=offset_point(100, 0))
        mid = PlaceFactory(name="Stop Mid", category="restaurant", location=offset_point(500, 0))
        far = PlaceFactory(name="Stop Far", category="hotel", location=offset_point(1500, 0))

        response = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "radius_m": "2000"})

        assert response.status_code == 200
        data = response.json()
        # ViaggioPagination envelope
        for key in ("count", "total_pages", "current_page", "page_size", "next", "previous", "results"):
            assert key in data
        assert data["count"] == 3
        assert data["total_pages"] == 1
        assert data["current_page"] == 1
        assert data["next"] is None
        assert data["previous"] is None

        results = data["results"]
        assert [r["slug"] for r in results] == [near.slug, mid.slug, far.slug]

        first = results[0]
        for field in CARD_FIELDS:
            assert field in first, f"missing card field: {field}"
        assert first["location"] == {"lat": round(offset_point(100, 0).y, 6), "lng": round(offset_point(100, 0).x, 6)}
        assert first["tags"] == []

        distances = [r["distance_m"] for r in results]
        assert all(isinstance(d, int) for d in distances)
        assert distances == sorted(distances)

    def test_category_and_q_filters(self, authed_client):
        PlaceFactory(name="Seaview Grill", category="restaurant", location=offset_point(100, 0))
        PlaceFactory(name="Seaview Hotel", category="hotel", location=offset_point(120, 0))
        PlaceFactory(name="Hilltop Cafe", category="cafe", location=offset_point(140, 0))

        by_category = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "category": "hotel"}).json()
        assert [r["name"] for r in by_category["results"]] == ["Seaview Hotel"]

        by_q = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "q": "seaview"}).json()
        assert sorted(r["name"] for r in by_q["results"]) == ["Seaview Grill", "Seaview Hotel"]

        combined = authed_client.get(
            NEAR_URL, {"lat": "18.94", "lng": "72.835", "category": "hotel", "q": "seaview"}
        ).json()
        assert [r["name"] for r in combined["results"]] == ["Seaview Hotel"]

    def test_radius_clamped_to_min_and_max(self, authed_client):
        # 50 m away: below the 100 m minimum clamp, inside the clamped window.
        inside_min = PlaceFactory(name="Tiny Radius Stop", location=offset_point(50, 0))

        low = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "radius_m": "10"}).json()
        assert any(r["slug"] == inside_min.slug for r in low["results"])

        huge = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "radius_m": "999999"}).json()
        assert any(r["slug"] == inside_min.slug for r in huge["results"])


class TestNearValidation:
    """lat/lng/radius_m validation -> 400 with the standard error envelope."""

    @pytest.mark.parametrize("params", [
        {"lng": "72.835"},                      # missing lat
        {"lat": "18.94"},                       # missing lng
        {"lat": "abc", "lng": "72.835"},        # non-numeric lat
        {"lat": "18.94", "lng": "abc"},         # non-numeric lng
        {"lat": "95", "lng": "72.835"},         # lat out of range
        {"lat": "18.94", "lng": "-181"},        # lng out of range
        {"lat": "18.94", "lng": "72.835", "radius_m": "xyz"},  # non-numeric radius
    ])
    def test_invalid_params_return_400_envelope(self, authed_client, params):
        response = authed_client.get(NEAR_URL, params)

        assert response.status_code == 400
        data = response.json()
        assert_error_envelope(data)
        assert data["code"] == "INVALID"
        assert data["details"]


class TestPagination:
    """page=2 behaviour with more than one page of results (page_size 20)."""

    def test_second_page_returns_remainder(self, authed_client):
        for i in range(1, 26):  # 25 places, 100 m..2500 m north of the anchor
            PlaceFactory(name=f"Page Stop {i:02d}", location=offset_point(i * 100, 0))

        response = authed_client.get(NEAR_URL, {"lat": "18.94", "lng": "72.835", "radius_m": "5000", "page": "2"})

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 25
        assert data["total_pages"] == 2
        assert data["current_page"] == 2
        assert len(data["results"]) == 5
        assert data["previous"] is not None
        assert data["next"] is None

        # Ordering is global (nearest first): page 2 holds the five farthest places.
        assert [r["name"] for r in data["results"]] == [
            "Page Stop 21", "Page Stop 22", "Page Stop 23", "Page Stop 24", "Page Stop 25",
        ]


class TestDetail:
    """GET /api/v1/places/{uuid}/ — full detail or JSON 404 envelope."""

    def test_returns_full_detail_with_sources_and_tags(self, authed_client):
        tag = TagFactory()
        place = PlaceFactory(
            name="Full Detail Place",
            description="A place with everything.",
            opening_hours={"monday": [{"open": "09:00", "close": "22:00"}]},
            tags=[tag],
        )
        source = SourceFactory(place=place, provider_url="https://example.com/poi.1")

        response = authed_client.get(f"/api/v1/places/{place.pk}/")

        assert response.status_code == 200
        data = response.json()
        for field in ("id", "name", "slug", "category", "description", "opening_hours",
                      "metadata", "city", "region", "country", "postal_code", "verified",
                      "updated_at", "sources"):
            assert field in data, f"missing detail field: {field}"
        assert data["description"] == "A place with everything."
        assert data["opening_hours"] == {"monday": [{"open": "09:00", "close": "22:00"}]}
        assert data["tags"] == [tag.name]
        assert data["sources"] == [
            {"provider": "OVERTURE", "provider_url": "https://example.com/poi.1"}
        ]
        assert "distance_m" not in data

    # Malformed-but-routable UUIDs reach the view and get the JSON envelope.
    # (An empty pk would build a double-slash URL that never matches a route.)
    @pytest.mark.parametrize("pk", ["not-a-uuid", "12345"])
    def test_invalid_uuid_returns_404_envelope(self, authed_client, pk):
        response = authed_client.get(f"/api/v1/places/{pk}/")

        assert response.status_code == 404
        assert_error_envelope(response.json())
        assert response.json()["code"] == "NOT_FOUND"

    def test_unknown_uuid_returns_404_envelope(self, authed_client):
        response = authed_client.get(f"/api/v1/places/{uuid.uuid4()}/")

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_inactive_place_returns_404(self, authed_client):
        place = PlaceFactory(name="Ghost Place", is_active=False)

        assert authed_client.get(f"/api/v1/places/{place.pk}/").status_code == 404


class TestNearby:
    """GET /api/v1/places/{uuid}/nearby/ — anchor excluded, radius respected."""

    def test_excludes_anchor_and_respects_radius(self, authed_client):
        anchor = PlaceFactory(name="Nearby Anchor", location=offset_point(0, 0))
        close = PlaceFactory(name="Nearby Close", location=offset_point(200, 0))
        far = PlaceFactory(name="Nearby Far", location=offset_point(1200, 0))

        narrow = authed_client.get(f"/api/v1/places/{anchor.pk}/nearby/", {"radius_m": "500"}).json()
        assert [r["slug"] for r in narrow["results"]] == [close.slug]

        wide = authed_client.get(f"/api/v1/places/{anchor.pk}/nearby/", {"radius_m": "5000"}).json()
        assert [r["slug"] for r in wide["results"]] == [close.slug, far.slug]
        assert all(r["slug"] != anchor.slug for r in wide["results"])

        distances = [r["distance_m"] for r in wide["results"]]
        assert distances == sorted(distances)

    def test_category_filter(self, authed_client):
        anchor = PlaceFactory(name="Anchor Cafe", category="cafe", location=offset_point(0, 0))
        PlaceFactory(name="Anchor Cafe Sibling", category="cafe", location=offset_point(200, 0))
        hotel = PlaceFactory(name="Anchor Hotel", category="hotel", location=offset_point(250, 0))

        data = authed_client.get(f"/api/v1/places/{anchor.pk}/nearby/", {"category": "hotel"}).json()
        assert [r["slug"] for r in data["results"]] == [hotel.slug]

    def test_invalid_uuid_returns_404_envelope(self, authed_client):
        response = authed_client.get("/api/v1/places/not-a-uuid/nearby/")

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_unknown_anchor_returns_404(self, authed_client):
        assert authed_client.get(f"/api/v1/places/{uuid.uuid4()}/nearby/").status_code == 404

