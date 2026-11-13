"""
Tests for activity aggregation and historical baseline services and tasks (P3-F4).

Target coverage:
- Exact per-cell counts for known dataset (active_count distinct vs event_count total)
- Idempotent double-run (no duplicate rows, unique constraints hold)
- Bucket boundary: event on edge lands in later bucket
- Retention pruning: keeps 27 days, drops 29 days
- Baseline calculation on hand-computed series ([2,4,4,4,5,5,7,9] -> mean 5.00, pop-sd 2.00, n 8)
- Baseline re-run updates without duplicates
- Midnight crossing: UTC Sunday night -> IST Monday morning (dow=0, minutes=270)
- Single sample group -> stddev=0.00
- Empty DB handling
- Distinct users vs repeated events
- 56-day cutoff boundary
- Celery task wrappers
"""

from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import zoneinfo

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.activity.factories import ActivityAggregateFactory, UserActivityFactory
from apps.activity.models import ActivityAggregate, HistoricalBaseline, UserActivity
from apps.activity.services import aggregate_activity, recompute_baselines
from apps.activity.tasks import aggregate_hourly, recompute_baselines_task
from apps.places.factories import PlaceFactory

IST = zoneinfo.ZoneInfo("Asia/Kolkata")


@pytest.mark.django_db
class TestAggregateActivity:
    """Tests for aggregate_activity service function."""

    def test_known_dataset_exact_counts(self):
        """Known dataset yields exact per-cell active_count and event_count."""
        now = datetime(2026, 11, 2, 14, 2, 0, tzinfo=IST)
        # 14:02 IST floored to 5-min bucket is 14:00 IST [14:00, 14:05)
        bucket_time = datetime(2026, 11, 2, 14, 0, 0, tzinfo=IST)

        user1 = UserFactory(location_sharing_consent=True)
        user2 = UserFactory(location_sharing_consent=True)
        user3 = UserFactory(location_sharing_consent=True)

        place_a = PlaceFactory(location=Point(72.835, 18.94, srid=4326))
        place_b = PlaceFactory(location=Point(72.880, 19.05, srid=4326))

        # Place A: user1 (2 check-ins) + user2 (1 check-in) -> event=3, active=2
        UserActivityFactory(
            user=user1, place=place_a, timestamp=bucket_time + timedelta(minutes=1)
        )
        UserActivityFactory(
            user=user1, place=place_a, timestamp=bucket_time + timedelta(minutes=2)
        )
        UserActivityFactory(
            user=user2, place=place_a, timestamp=bucket_time + timedelta(minutes=3)
        )

        # Place B: user3 (1 check-in) -> event=1, active=1
        UserActivityFactory(
            user=user3, place=place_b, timestamp=bucket_time + timedelta(minutes=2)
        )

        summary = aggregate_activity(now=now, window_minutes=60, bucket_minutes=5, resolution=8)

        assert summary["buckets"] == 12
        assert summary["cells_written"] == 2
        assert summary["rows_pruned"] == 0

        agg_a = ActivityAggregate.objects.get(
            h3_index=place_a.h3_index_res8, resolution=8, time_bucket=bucket_time
        )
        assert agg_a.event_count == 3
        assert agg_a.active_count == 2

        agg_b = ActivityAggregate.objects.get(
            h3_index=place_b.h3_index_res8, resolution=8, time_bucket=bucket_time
        )
        assert agg_b.event_count == 1
        assert agg_b.active_count == 1

    def test_idempotent_double_run(self):
        """Running aggregation twice produces identical rows without duplicates."""
        now = datetime(2026, 11, 2, 14, 2, 0, tzinfo=IST)
        user = UserFactory(location_sharing_consent=True)
        place = PlaceFactory()

        UserActivityFactory(
            user=user, place=place, timestamp=datetime(2026, 11, 2, 14, 1, 0, tzinfo=IST)
        )

        summary1 = aggregate_activity(now=now)
        assert summary1["cells_written"] == 1
        assert ActivityAggregate.objects.count() == 1

        summary2 = aggregate_activity(now=now)
        assert summary2["cells_written"] == 1
        assert ActivityAggregate.objects.count() == 1

        agg = ActivityAggregate.objects.first()
        assert agg.h3_index == place.h3_index_res8
        assert agg.active_count == 1
        assert agg.event_count == 1

    def test_bucket_edge_lands_in_later_bucket(self):
        """Event exactly on a 5-min boundary lands in the later bucket [b, b+5m)."""
        # Bucket 1: 13:55:00 to 14:00:00 (timestamp < 14:00:00)
        # Bucket 2: 14:00:00 to 14:05:00 (timestamp >= 14:00:00)
        now = datetime(2026, 11, 2, 14, 2, 0, tzinfo=IST)
        b1_time = datetime(2026, 11, 2, 13, 55, 0, tzinfo=IST)
        b2_time = datetime(2026, 11, 2, 14, 0, 0, tzinfo=IST)

        user = UserFactory(location_sharing_consent=True)
        place = PlaceFactory()

        # 13:59:59.999 is strictly before 14:00:00 -> lands in bucket 13:55
        UserActivityFactory(
            user=user,
            place=place,
            timestamp=datetime(2026, 11, 2, 13, 59, 59, 999000, tzinfo=IST),
        )

        # 14:00:00.000 is exactly on boundary -> lands in bucket 14:00
        UserActivityFactory(
            user=user,
            place=place,
            timestamp=datetime(2026, 11, 2, 14, 0, 0, 0, tzinfo=IST),
        )

        aggregate_activity(now=now)

        agg_b1 = ActivityAggregate.objects.get(
            h3_index=place.h3_index_res8, resolution=8, time_bucket=b1_time
        )
        assert agg_b1.event_count == 1

        agg_b2 = ActivityAggregate.objects.get(
            h3_index=place.h3_index_res8, resolution=8, time_bucket=b2_time
        )
        assert agg_b2.event_count == 1

    def test_prune_keeps_27d_drops_29d(self):
        """Pruning deletes aggregates older than 28 days and preserves newer ones."""
        now = datetime(2026, 11, 2, 12, 0, 0, tzinfo=IST)

        agg_27d = ActivityAggregateFactory(
            time_bucket=now - timedelta(days=27),
            h3_index="886a1080d3fffff",
        )
        agg_29d = ActivityAggregateFactory(
            time_bucket=now - timedelta(days=29),
            h3_index="886a1080d5fffff",
        )

        summary = aggregate_activity(now=now)

        assert summary["rows_pruned"] == 1
        assert ActivityAggregate.objects.filter(id=agg_27d.id).exists()
        assert not ActivityAggregate.objects.filter(id=agg_29d.id).exists()

    def test_empty_db_cleans_stale_aggregates(self):
        """If activity is removed, subsequent aggregation cleans existing bucket rows."""
        now = datetime(2026, 11, 2, 14, 0, 0, tzinfo=IST)
        bucket_time = datetime(2026, 11, 2, 14, 0, 0, tzinfo=IST)

        stale_agg = ActivityAggregateFactory(
            time_bucket=bucket_time,
            resolution=8,
            h3_index="886a1080d3fffff",
        )

        summary = aggregate_activity(now=now)
        assert summary["cells_written"] == 0
        assert not ActivityAggregate.objects.filter(id=stale_agg.id).exists()

    def test_distinct_users_multiple_events(self):
        """One user generating multiple events in the same bucket results in active_count=1."""
        now = datetime(2026, 11, 2, 14, 2, 0, tzinfo=IST)
        bucket_time = datetime(2026, 11, 2, 14, 0, 0, tzinfo=IST)

        user = UserFactory(location_sharing_consent=True)
        place = PlaceFactory()

        for sec in [10, 20, 30, 40, 50]:
            UserActivityFactory(
                user=user,
                place=place,
                timestamp=bucket_time + timedelta(seconds=sec),
            )

        aggregate_activity(now=now)

        agg = ActivityAggregate.objects.get(
            h3_index=place.h3_index_res8, resolution=8, time_bucket=bucket_time
        )
        assert agg.active_count == 1
        assert agg.event_count == 5


@pytest.mark.django_db
class TestRecomputeBaselines:
    """Tests for recompute_baselines service function."""

    def test_baseline_math_hand_computed_series(self):
        """
        Verify mean 5.00, population stddev 2.00, sample_count 8 on series [2,4,4,4,5,5,7,9].
        Sum = 40, N = 8, Mean = 5.00.
        Sum of sq deviations = 9 + 1 + 1 + 1 + 0 + 0 + 4 + 16 = 32.
        Pop variance = 32 / 8 = 4.0 -> Pop stddev = 2.00.
        """
        # 2026-11-02 is a Monday (dow=0). Time: 10:00 AM IST (minutes = 600).
        now = datetime(2026, 11, 2, 10, 0, 0, tzinfo=IST)
        h3 = "886a1080d3fffff"
        counts = [2, 4, 4, 4, 5, 5, 7, 9]

        for week_idx, active_cnt in enumerate(counts):
            # Weeks 0..7 (all within 56 days) on Monday at 10:00 AM IST
            bucket_dt = now - timedelta(weeks=week_idx)
            ActivityAggregateFactory(
                h3_index=h3,
                resolution=8,
                time_bucket=bucket_dt,
                active_count=active_cnt,
                event_count=active_cnt * 2,
            )

        summary = recompute_baselines(now=now, weeks=8, resolution=8)

        assert summary["baselines_created"] == 1
        assert summary["baselines_updated"] == 0

        baseline = HistoricalBaseline.objects.get(
            h3_index=h3,
            resolution=8,
            day_of_week=0,
            time_bucket_minutes=600,
        )
        assert baseline.avg_active_count == Decimal("5.00")
        assert baseline.stddev_active_count == Decimal("2.00")
        assert baseline.sample_count == 8

    def test_rerun_updates_sample_count_without_dupes(self):
        """Re-running baseline updates the row in-place without duplicating."""
        now = datetime(2026, 11, 2, 10, 0, 0, tzinfo=IST)
        h3 = "886a1080d3fffff"

        ActivityAggregateFactory(
            h3_index=h3,
            resolution=8,
            time_bucket=now,
            active_count=10,
        )

        summary1 = recompute_baselines(now=now)
        assert summary1["baselines_created"] == 1
        assert HistoricalBaseline.objects.count() == 1

        # Second run on same data
        summary2 = recompute_baselines(now=now)
        assert summary2["baselines_created"] == 0
        assert summary2["baselines_updated"] == 1
        assert HistoricalBaseline.objects.count() == 1

    def test_dow_minutes_mapping_across_local_midnight(self):
        """
        UTC timestamp near midnight Sunday correctly maps to Monday morning in IST.
        2026-11-01 23:00:00 UTC == 2026-11-02 04:30:00 IST.
        IST: Monday (dow=0), 4h 30m = 270 minutes since midnight.
        """
        h3 = "886a1080d3fffff"
        utc_sunday_night = datetime(2026, 11, 1, 23, 0, 0, tzinfo=dt_timezone.utc)
        now_ist = datetime(2026, 11, 2, 12, 0, 0, tzinfo=IST)

        ActivityAggregateFactory(
            h3_index=h3,
            resolution=8,
            time_bucket=utc_sunday_night,
            active_count=7,
        )

        recompute_baselines(now=now_ist)

        baseline = HistoricalBaseline.objects.get(
            h3_index=h3,
            resolution=8,
            day_of_week=0,
            time_bucket_minutes=270,
        )
        assert baseline.day_of_week == 0
        assert baseline.time_bucket_minutes == 270
        assert baseline.avg_active_count == Decimal("7.00")

    def test_single_sample_group_stddev_zero(self):
        """A time slot with only 1 sample has stddev=0.00 (P3-D5)."""
        now = datetime(2026, 11, 2, 10, 0, 0, tzinfo=IST)
        h3 = "886a1080d3fffff"

        ActivityAggregateFactory(
            h3_index=h3,
            resolution=8,
            time_bucket=now,
            active_count=15,
        )

        recompute_baselines(now=now)

        baseline = HistoricalBaseline.objects.get(
            h3_index=h3,
            resolution=8,
            day_of_week=0,
            time_bucket_minutes=600,
        )
        assert baseline.sample_count == 1
        assert baseline.avg_active_count == Decimal("15.00")
        assert baseline.stddev_active_count == Decimal("0.00")

    def test_cutoff_ignores_aggregates_older_than_56_days(self):
        """Aggregates older than 56 days (8 weeks) are excluded from the baseline."""
        now = datetime(2026, 11, 2, 10, 0, 0, tzinfo=IST)
        h3 = "886a1080d3fffff"

        # 7 weeks ago (within 56 days)
        ActivityAggregateFactory(
            h3_index=h3,
            resolution=8,
            time_bucket=now - timedelta(days=49),
            active_count=10,
        )

        # 9 weeks ago (older than 56 days)
        ActivityAggregateFactory(
            h3_index=h3,
            resolution=8,
            time_bucket=now - timedelta(days=63),
            active_count=100,
        )

        recompute_baselines(now=now)

        baseline = HistoricalBaseline.objects.get(
            h3_index=h3,
            resolution=8,
            day_of_week=0,
            time_bucket_minutes=600,
        )
        # Should only reflect the 10-count aggregate, not the 100-count one
        assert baseline.sample_count == 1
        assert baseline.avg_active_count == Decimal("10.00")


@pytest.mark.django_db
class TestCeleryTasks:
    """Tests for shared_task wrappers in tasks.py."""

    def test_aggregate_hourly_task(self):
        """aggregate_hourly executes and returns expected summary keys."""
        summary = aggregate_hourly()
        assert "buckets" in summary
        assert "cells_written" in summary
        assert "rows_pruned" in summary

    def test_recompute_baselines_task(self):
        """recompute_baselines_task executes and returns expected summary keys."""
        summary = recompute_baselines_task()
        assert "baselines_created" in summary
        assert "baselines_updated" in summary
        assert "total" in summary
