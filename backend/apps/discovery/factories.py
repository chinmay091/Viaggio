"""
Factory-boy factories for the discovery app (P3-F2).
"""

import factory
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.places.factories import PlaceFactory

from .models import PlaceView, SavedPlace


class SavedPlaceFactory(factory.django.DjangoModelFactory):
    """User bookmarked place factory."""

    class Meta:
        model = SavedPlace

    user = factory.SubFactory(UserFactory)
    place = factory.SubFactory(PlaceFactory)
    saved_at = factory.LazyFunction(timezone.now)


class PlaceViewFactory(factory.django.DjangoModelFactory):
    """Place view tracking factory (supports both authenticated and anonymous)."""

    class Meta:
        model = PlaceView

    user = factory.SubFactory(UserFactory)
    place = factory.SubFactory(PlaceFactory)
    session_id = ""
    duration_seconds = 0
    source = PlaceView.SOURCE_DIRECT
    created_at = factory.LazyFunction(timezone.now)
