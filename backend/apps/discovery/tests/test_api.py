"""
API tests for the saved-places endpoints (P3-F6).

Covers the F6 contract: JWT required, per-user scoping, the idempotent
save upsert (201 created / 200 re-saved with ``saved_at`` refresh), list
ordering + pagination envelope, delete (204 / 404), and the standard JSON
error envelope for unknown / inactive / malformed places and validation.
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.discovery.factories import SavedPlaceFactory
from apps.discovery.models import SavedPlace
from apps.places.factories import PlaceFactory

pytestmark = pytest.mark.django_db

SAVED_URL = "/api/v1/discovery/saved/"


@pytest.fixture
def authed_client(api_client, user):
    """DRF test client authenticated as a real user (force_authenticate)."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def other_user(db):
    from apps.accounts.factories import UserFactory

    return UserFactory()


def assert_error_envelope(data):
    assert data["error"] is True
    assert isinstance(data["message"], str) and data["message"]
    assert isinstance(data["code"], str) and data["code"]
    assert "details" in data
    assert "correlation_id" in data


def saved_url(place):
    return f"{SAVED_URL}{place.pk}/"


class TestAuthentication:
    """All saved-places endpoints are JWT-protected."""

    def test_list_requires_authentication(self, api_client):
        response = api_client.get(SAVED_URL)

        assert response.status_code == 401
        assert_error_envelope(response.json())

    def test_create_requires_authentication(self, api_client):
        place = PlaceFactory()

        response = api_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 401
        assert_error_envelope(response.json())

    def test_delete_requires_authentication(self, api_client):
        place = PlaceFactory()

        response = api_client.delete(saved_url(place))

        assert response.status_code == 401
        assert_error_envelope(response.json())


class TestSave:
    """POST /discovery/saved/ — idempotent upsert."""

    def test_create_returns_201_with_card(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["place"]["id"] == str(place.pk)
        assert data["place"]["name"] == place.name
        assert data["saved_at"]
        assert SavedPlace.objects.filter(user=user, place=place).count() == 1

    def test_resave_is_idempotent_and_refreshes_saved_at(self, authed_client, user):
        place = PlaceFactory()

        first = authed_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")
        SavedPlace.objects.filter(user=user).update(
            saved_at=timezone.now() - timedelta(hours=1)
        )
        second = authed_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")

        assert first.status_code == 201
        assert second.status_code == 200
        assert SavedPlace.objects.filter(user=user).count() == 1
        saved = SavedPlace.objects.get(user=user)
        # refreshed to "now" (much later than the backdated stamp)
        assert saved.saved_at > timezone.now() - timedelta(minutes=1)

    def test_unknown_place_404(self, authed_client, user):
        response = authed_client.post(
            SAVED_URL, {"place_id": str(uuid.uuid4())}, format="json"
        )

        assert response.status_code == 404
        assert_error_envelope(response.json())
        assert SavedPlace.objects.count() == 0

    def test_inactive_place_404(self, authed_client, user):
        place = PlaceFactory(is_active=False)

        response = authed_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 404
        assert_error_envelope(response.json())
        assert SavedPlace.objects.count() == 0

    def test_malformed_place_id_400(self, authed_client, user):
        response = authed_client.post(SAVED_URL, {"place_id": "not-a-uuid"}, format="json")

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_missing_place_id_400(self, authed_client, user):
        response = authed_client.post(SAVED_URL, {}, format="json")

        assert response.status_code == 400
        assert_error_envelope(response.json())


class TestList:
    """GET /discovery/saved/ — per-user scoping + ordering."""

    def test_list_orders_saved_at_desc(self, authed_client, user):
        recent = PlaceFactory()
        older = PlaceFactory()
        SavedPlaceFactory(user=user, place=older, saved_at=timezone.now() - timedelta(days=1))
        SavedPlaceFactory(user=user, place=recent, saved_at=timezone.now())

        response = authed_client.get(SAVED_URL)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert [item["place"]["id"] for item in data["results"]] == [
            str(recent.pk),
            str(older.pk),
        ]

    def test_other_users_saves_invisible(self, authed_client, user, other_user):
        mine = PlaceFactory()
        theirs = PlaceFactory()
        SavedPlaceFactory(user=user, place=mine)
        SavedPlaceFactory(user=other_user, place=theirs)

        response = authed_client.get(SAVED_URL)

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["place"]["id"] == str(mine.pk)


class TestDelete:
    """DELETE /discovery/saved/{place_id}/"""

    def test_delete_round_trip(self, authed_client, user):
        place = PlaceFactory()
        authed_client.post(SAVED_URL, {"place_id": str(place.pk)}, format="json")

        response = authed_client.delete(saved_url(place))

        assert response.status_code == 204
        assert SavedPlace.objects.count() == 0
        assert authed_client.get(SAVED_URL).json()["count"] == 0

    def test_delete_not_saved_by_user_404(self, authed_client, user, other_user):
        place = PlaceFactory()
        SavedPlaceFactory(user=other_user, place=place)

        response = authed_client.delete(saved_url(place))

        assert response.status_code == 404
        assert_error_envelope(response.json())
        # the other user's bookmark is untouched
        assert SavedPlace.objects.count() == 1

    def test_delete_malformed_place_id_404(self, authed_client, user):
        response = authed_client.delete(f"{SAVED_URL}not-a-uuid/")

        assert response.status_code == 404
        assert_error_envelope(response.json())


class TestIsolationAtScale:
    """P3-F9: cross-user isolation under bulk saves (10 users x 5 places)."""

    def test_each_user_sees_only_their_own_saves(self, api_client):
        from apps.accounts.factories import UserFactory

        users = UserFactory.create_batch(10)
        places = PlaceFactory.create_batch(5)
        for user in users:
            for place in places:
                SavedPlaceFactory(user=user, place=place)
        assert SavedPlace.objects.count() == 50

        for user in users:
            api_client.force_authenticate(user=user)
            response = api_client.get(SAVED_URL)

            assert response.status_code == 200
            data = response.json()
            assert data["count"] == 5
            assert {r["place"]["id"] for r in data["results"]} == {
                str(p.pk) for p in places
            }

    def test_delete_across_users_at_scale(self, api_client):
        from apps.accounts.factories import UserFactory

        users = UserFactory.create_batch(10)
        places = PlaceFactory.create_batch(5)
        for user in users:
            SavedPlaceFactory(user=user, place=places[0])

        # Every user deletes the same place: each succeeds (their own row)...
        for user in users:
            api_client.force_authenticate(user=user)
            response = api_client.delete(f"{SAVED_URL}{places[0].pk}/")
            assert response.status_code == 204

        assert SavedPlace.objects.count() == 0
        # ...and an 11th delete finds nothing.
        api_client.force_authenticate(user=users[0])
        assert api_client.delete(f"{SAVED_URL}{places[0].pk}/").status_code == 404
