"""
Tests for activity models (P3-F1).

Covers UserActivity (AuditModel/UUID PK, foreign keys, cascade deletes, denormalized H3 cells),
ActivityAggregate (BigAutoField PK, resolution choices, unique constraint), and
HistoricalBaseline (BigAutoField PK, unique constraint on h3/res/dow/bucket_minutes).
"""

import uuid
from decimal import Decimal
import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.activity.factories import (
    ActivityAggregateFactory,
    HistoricalBaselineFactory,
    UserActivityFactory,
)
from apps.activity.models import ActivityAggregate, HistoricalBaseline, UserActivity
from apps.places.factories import PlaceFactory

pytestmark = pytest.mark.django_db


class TestUserActivityModel:
    def test_creation_and_defaults(self):
        """UserActivity uses UUID PK and inherits audit timestamps."""
        activity = UserActivityFactory()

        assert isinstance(activity.id, uuid.UUID)
        assert activity.user is not None
        assert activity.place is not None
        assert activity.h3_index_res8 != ""
        assert activity.h3_index_res9 != ""
        assert activity.timestamp is not None
        assert activity.created_at is not None
        assert activity.updated_at is not None
        assert str(activity.user_id) in str(activity)

    def test_h3_indices_match_place(self):
        """H3 cells are denormalized from the place's precomputed fields."""
        place = PlaceFactory()
        activity = UserActivityFactory(place=place)

        assert activity.h3_index_res8 == place.h3_index_res8
        assert activity.h3_index_res9 == place.h3_index_res9

    def test_cascade_delete_user(self):
        """Deleting a user removes all their activity records."""
        user = UserFactory()
        activity = UserActivityFactory(user=user)

        user.delete()
        assert not UserActivity.objects.filter(pk=activity.pk).exists()

    def test_cascade_delete_place(self):
        """Deleting a place removes associated activity records."""
        place = PlaceFactory()
        activity = UserActivityFactory(place=place)

        place.delete()
        assert not UserActivity.objects.filter(pk=activity.pk).exists()


class TestActivityAggregateModel:
    def test_creation_and_fields(self):
        """ActivityAggregate uses BigAutoField and stores 5-minute bucket counts."""
        now = timezone.now()
        agg = ActivityAggregateFactory(
            h3_index="886a1080d3fffff",
            resolution=8,
            time_bucket=now,
            active_count=7,
            event_count=15,
        )

        assert isinstance(agg.id, int)
        assert agg.h3_index == "886a1080d3fffff"
        assert agg.resolution == 8
        assert agg.time_bucket == now
        assert agg.active_count == 7
        assert agg.event_count == 15
        assert agg.created_at is not None
        assert "886a1080d3fffff" in str(agg)

    def test_unique_constraint(self):
        """(h3_index, resolution, time_bucket) is unique."""
        now = timezone.now()
        ActivityAggregate.objects.create(
            h3_index="886a1080d3fffff",
            resolution=8,
            time_bucket=now,
            active_count=5,
            event_count=10,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                ActivityAggregate.objects.create(
                    h3_index="886a1080d3fffff",
                    resolution=8,
                    time_bucket=now,
                    active_count=1,
                    event_count=2,
                )


class TestHistoricalBaselineModel:
    def test_creation_and_defaults(self):
        """HistoricalBaseline uses BigAutoField and stores baseline statistics."""
        baseline = HistoricalBaselineFactory(
            h3_index="886a1080d3fffff",
            resolution=8,
            day_of_week=2,
            time_bucket_minutes=720,
            avg_active_count=Decimal("12.50"),
            stddev_active_count=Decimal("3.25"),
            sample_count=8,
        )

        assert isinstance(baseline.id, int)
        assert baseline.h3_index == "886a1080d3fffff"
        assert baseline.resolution == 8
        assert baseline.day_of_week == 2
        assert baseline.time_bucket_minutes == 720
        assert baseline.avg_active_count == Decimal("12.50")
        assert baseline.stddev_active_count == Decimal("3.25")
        assert baseline.sample_count == 8
        assert baseline.updated_at is not None
        assert "886a1080d3fffff" in str(baseline)

    def test_unique_constraint(self):
        """(h3_index, resolution, day_of_week, time_bucket_minutes) is unique."""
        HistoricalBaseline.objects.create(
            h3_index="886a1080d3fffff",
            resolution=8,
            day_of_week=0,
            time_bucket_minutes=60,
            avg_active_count=Decimal("10.00"),
            stddev_active_count=Decimal("2.00"),
            sample_count=10,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                HistoricalBaseline.objects.create(
                    h3_index="886a1080d3fffff",
                    resolution=8,
                    day_of_week=0,
                    time_bucket_minutes=60,
                    avg_active_count=Decimal("15.00"),
                    stddev_active_count=Decimal("1.50"),
                    sample_count=12,
                )
