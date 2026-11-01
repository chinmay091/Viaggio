"""
Tests for discovery models (P3-F2).

Covers SavedPlace (AuditModel/UUID PK, unique constraint on user+place, cascades) and
PlaceView (BigAutoField PK, anonymous vs authenticated identity, source choices, cascades).
"""

import uuid
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.discovery.factories import PlaceViewFactory, SavedPlaceFactory
from apps.discovery.models import PlaceView, SavedPlace
from apps.places.factories import PlaceFactory

pytestmark = pytest.mark.django_db


class TestSavedPlaceModel:
    def test_creation_and_defaults(self):
        """SavedPlace uses UUID PK, links user/place, and records saved_at."""
        saved = SavedPlaceFactory()

        assert isinstance(saved.id, uuid.UUID)
        assert saved.user is not None
        assert saved.place is not None
        assert saved.saved_at is not None
        assert saved.created_at is not None
        assert saved.updated_at is not None
        assert str(saved.user_id) in str(saved)
        assert str(saved.place_id) in str(saved)

    def test_unique_user_place_constraint(self):
        """(user, place) is unique — a user cannot bookmark the same place twice."""
        user = UserFactory()
        place = PlaceFactory()
        SavedPlace.objects.create(user=user, place=place)

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                SavedPlace.objects.create(user=user, place=place)

    def test_different_users_can_save_same_place(self):
        """Multiple users can independently save the same place."""
        place = PlaceFactory()
        u1 = UserFactory()
        u2 = UserFactory()

        s1 = SavedPlace.objects.create(user=u1, place=place)
        s2 = SavedPlace.objects.create(user=u2, place=place)

        assert s1.pk != s2.pk
        assert SavedPlace.objects.filter(place=place).count() == 2

    def test_cascade_delete_user(self):
        """Deleting a user removes their saved places."""
        user = UserFactory()
        saved = SavedPlaceFactory(user=user)

        user.delete()
        assert not SavedPlace.objects.filter(pk=saved.pk).exists()

    def test_cascade_delete_place(self):
        """Deleting a place removes its saved place entries."""
        place = PlaceFactory()
        saved = SavedPlaceFactory(place=place)

        place.delete()
        assert not SavedPlace.objects.filter(pk=saved.pk).exists()


class TestPlaceViewModel:
    def test_authenticated_view_creation(self):
        """PlaceView with authenticated user sets user FK and default duration."""
        user = UserFactory()
        place = PlaceFactory()
        view = PlaceViewFactory(user=user, place=place, source=PlaceView.SOURCE_DIRECT)

        assert isinstance(view.id, int)
        assert view.user == user
        assert view.place == place
        assert view.session_id == ""
        assert view.duration_seconds == 0
        assert view.source == PlaceView.SOURCE_DIRECT
        assert view.created_at is not None
        assert str(place.id) in str(view)
        assert str(user.id) in str(view)

    def test_anonymous_view_creation(self):
        """PlaceView supports anonymous views with null user and session_id (P3-D3)."""
        place = PlaceFactory()
        view = PlaceView.objects.create(
            user=None,
            place=place,
            session_id="anon-session-token-12345",
            source=PlaceView.SOURCE_SEARCH,
            duration_seconds=45,
        )

        assert view.user is None
        assert view.session_id == "anon-session-token-12345"
        assert view.source == "search"
        assert view.duration_seconds == 45
        assert "anon-session-token-12345" in str(view)

    def test_source_choices_validation(self):
        """Valid source choices pass full_clean; invalid choice raises ValidationError."""
        place = PlaceFactory()

        for valid_source in ("map_click", "search", "recommendation", "direct"):
            view = PlaceView(place=place, source=valid_source)
            view.full_clean()

        invalid_view = PlaceView(place=place, source="invalid_source")
        with pytest.raises(ValidationError):
            invalid_view.full_clean()

    def test_cascade_delete_place(self):
        """Deleting a place removes all associated place view records."""
        place = PlaceFactory()
        view = PlaceViewFactory(place=place)

        place.delete()
        assert not PlaceView.objects.filter(pk=view.pk).exists()

    def test_set_null_on_user_delete(self):
        """Deleting a user retains the PlaceView record with user set to NULL."""
        user = UserFactory()
        view = PlaceViewFactory(user=user)

        user.delete()
        view.refresh_from_db()
        assert view.user is None
        assert view.place is not None
