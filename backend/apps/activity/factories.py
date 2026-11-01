"""
Factory-boy factories for the activity app (P3-F1).

``UserActivityFactory`` derives H3 cells from ``place.location`` via
``post_generation`` and ``LazyAttribute`` so the denormalization invariant
can never be violated in tests.
"""

import factory
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.places.factories import PlaceFactory

from .models import ActivityAggregate, HistoricalBaseline, UserActivity


class UserActivityFactory(factory.django.DjangoModelFactory):
    """
    Activity event (check-in).

    H3 cells are derived from the place's location in post_generation,
    matching the API-layer behaviour (P3-D3: server-side derivation).
    """

    class Meta:
        model = UserActivity

    user = factory.SubFactory(UserFactory)
    place = factory.SubFactory(PlaceFactory)
    timestamp = factory.LazyFunction(timezone.now)
    h3_index_res8 = factory.LazyAttribute(lambda o: o.place.h3_index_res8 if o.place else "")
    h3_index_res9 = factory.LazyAttribute(lambda o: o.place.h3_index_res9 if o.place else "")

    @factory.post_generation
    def derive_h3(self, create, extracted, **kwargs):
        """Derive H3 cells from the place's precomputed fields."""
        if self.place:
            self.h3_index_res8 = self.place.h3_index_res8
            self.h3_index_res9 = self.place.h3_index_res9
            if create:
                self.save(update_fields=["h3_index_res8", "h3_index_res9"])


class ActivityAggregateFactory(factory.django.DjangoModelFactory):
    """5-minute bucket aggregate for a single H3 cell."""

    class Meta:
        model = ActivityAggregate

    h3_index = "886a1080d3fffff"
    resolution = 8
    time_bucket = factory.LazyFunction(timezone.now)
    active_count = 5
    event_count = 10


class HistoricalBaselineFactory(factory.django.DjangoModelFactory):
    """
    Historical baseline for known-z tests.

    Defaults: avg=10, stddev=2, sample_count=10 → a cell with active_count=14
    yields z = (14 − 10) / 2 = 2.0 (exactly on the ``unusually_busy`` threshold).
    """

    class Meta:
        model = HistoricalBaseline

    h3_index = "886a1080d3fffff"
    resolution = 8
    day_of_week = 0
    time_bucket_minutes = 0
    avg_active_count = 10
    stddev_active_count = 2
    sample_count = 10
