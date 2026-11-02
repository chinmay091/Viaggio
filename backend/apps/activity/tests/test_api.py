"""
API tests for the activity write endpoints (P3-F3).

Covers the F3 contract: JWT required, the consent hard gate on check-in
(403 + nothing stored), server-side H3 derivation, unknown/malformed/inactive
place 404s via the standard envelope, and the view endpoint's identity split
(consented user vs anonymous session_id) + 10-minute debounce (P3-D3/D9).
"""

import uuid
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.activity.models import UserActivity
from apps.discovery.models import PlaceView
from apps.places.factories import PlaceFactory

pytestmark = pytest.mark.django_db

CHECK_IN_URL = "/api/v1/activity/check-in/"
VIEW_URL = "/api/v1/activity/view/"


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


def consent(user):
    """Flip the user's location sharing consent and return the updated user."""
    user.location_sharing_consent = True
    user.save(update_fields=["location_sharing_consent"])
    return user


def backdate_views(place, minutes):
    """Move a place's PlaceView rows back in time (debounce-window testing)."""
    PlaceView.objects.filter(place=place).update(
        created_at=timezone.now() - timedelta(minutes=minutes)
    )


class TestAuthentication:
    """Both write endpoints are JWT-protected (P3-D8)."""

    def test_check_in_requires_authentication(self, api_client):
        place = PlaceFactory()

        response = api_client.post(CHECK_IN_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 401
        assert_error_envelope(response.json())

    def test_view_requires_authentication(self, api_client):
        place = PlaceFactory()

        response = api_client.post(VIEW_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 401
        assert_error_envelope(response.json())


class TestCheckIn:
    """POST /activity/check-in/ — consent hard gate (P3-D3)."""

    def test_consent_off_rejected_and_nothing_stored(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(CHECK_IN_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 403
        data = response.json()
        assert_error_envelope(data)
        assert data["code"] == "PERMISSION_DENIED"
        assert UserActivity.objects.count() == 0

    def test_consent_on_creates_activity(self, authed_client, user):
        consent(user)
        place = PlaceFactory()

        response = authed_client.post(CHECK_IN_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["place_id"] == str(place.pk)
        assert data["h3_index_res8"] == place.h3_index_res8
        assert data["h3_index_res9"] == place.h3_index_res9
        assert data["timestamp"]

        activity = UserActivity.objects.get()
        assert activity.user == user
        assert activity.place == place
        assert activity.h3_index_res8 == place.h3_index_res8
        assert activity.h3_index_res9 == place.h3_index_res9

    def test_unknown_place_404(self, authed_client, user):
        consent(user)

        response = authed_client.post(
            CHECK_IN_URL, {"place_id": str(uuid.uuid4())}, format="json"
        )

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_malformed_place_id_400(self, authed_client, user):
        consent(user)

        response = authed_client.post(CHECK_IN_URL, {"place_id": "not-a-uuid"}, format="json")

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_inactive_place_404(self, authed_client, user):
        consent(user)
        place = PlaceFactory(is_active=False)

        response = authed_client.post(CHECK_IN_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_missing_place_id_400(self, authed_client, user):
        consent(user)

        response = authed_client.post(CHECK_IN_URL, {}, format="json")

        assert response.status_code == 400
        assert_error_envelope(response.json())


class TestViewIdentity:
    """POST /activity/view/ — consent gates identity (P3-D3)."""

    def test_consent_on_stores_user(self, authed_client, user):
        consent(user)
        place = PlaceFactory()

        response = authed_client.post(VIEW_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "created"
        assert data["place_id"] == str(place.pk)
        assert data["source"] == "direct"
        assert data["duration_seconds"] == 0

        view = PlaceView.objects.get()
        assert view.user == user
        assert view.session_id == ""

    def test_consent_off_stores_anonymous_session(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(
            VIEW_URL,
            {"place_id": str(place.pk), "session_id": "sess-abc123", "duration_seconds": 12},
            format="json",
        )

        assert response.status_code == 201
        view = PlaceView.objects.get()
        assert view.user is None
        assert view.session_id == "sess-abc123"
        assert view.duration_seconds == 12

    def test_consent_off_without_session_id(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(VIEW_URL, {"place_id": str(place.pk)}, format="json")

        assert response.status_code == 201
        view = PlaceView.objects.get()
        assert view.user is None
        assert view.session_id == ""


class TestViewDebounce:
    """Repeated views within 10 minutes merge (P3-D9)."""

    def test_merge_within_window(self, authed_client, user):
        consent(user)
        place = PlaceFactory()

        first = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "duration_seconds": 10}, format="json"
        )
        # Backdate so the second view is 5 minutes later (inside the window).
        backdate_views(place, 5)
        second = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "duration_seconds": 30}, format="json"
        )

        assert first.status_code == 201
        assert second.status_code == 200
        assert PlaceView.objects.filter(place=place).count() == 1
        view = PlaceView.objects.get()
        assert view.duration_seconds == 30  # max(10, 30)
        assert second.json()["id"] == first.json()["id"]

    def test_lower_duration_does_not_shrink(self, authed_client, user):
        consent(user)
        place = PlaceFactory()

        authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "duration_seconds": 30}, format="json"
        )
        backdate_views(place, 5)
        authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "duration_seconds": 5}, format="json"
        )

        assert PlaceView.objects.get().duration_seconds == 30

    def test_new_row_after_window(self, authed_client, user):
        consent(user)
        place = PlaceFactory()

        first = authed_client.post(VIEW_URL, {"place_id": str(place.pk)}, format="json")
        backdate_views(place, 11)  # just outside the 10-minute window
        second = authed_client.post(VIEW_URL, {"place_id": str(place.pk)}, format="json")

        assert first.status_code == 201
        assert second.status_code == 201
        assert PlaceView.objects.filter(place=place).count() == 2

    def test_anonymous_identities_do_not_collapse(self, authed_client, user):
        place = PlaceFactory()

        a = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "session_id": "sess-A"}, format="json"
        )
        b = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "session_id": "sess-B"}, format="json"
        )

        assert a.status_code == 201
        assert b.status_code == 201
        assert PlaceView.objects.filter(place=place).count() == 2


class TestViewValidation:
    """Request validation for POST /activity/view/."""

    def test_unknown_place_404(self, authed_client, user):
        response = authed_client.post(
            VIEW_URL, {"place_id": str(uuid.uuid4())}, format="json"
        )

        assert response.status_code == 404
        assert_error_envelope(response.json())

    def test_malformed_place_id_400(self, authed_client, user):
        response = authed_client.post(VIEW_URL, {"place_id": "nope"}, format="json")

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_invalid_source_400(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "source": "bogus"}, format="json"
        )

        assert response.status_code == 400
        assert_error_envelope(response.json())

    def test_negative_duration_400(self, authed_client, user):
        place = PlaceFactory()

        response = authed_client.post(
            VIEW_URL, {"place_id": str(place.pk), "duration_seconds": -5}, format="json"
        )

        assert response.status_code == 400
        assert_error_envelope(response.json())

