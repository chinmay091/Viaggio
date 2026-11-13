"""
Activity aggregation and baseline services (Phase 3 City Pulse).

P3-D2: 5-min buckets at H3 res8, IST timezone (Asia/Kolkata).
P3-D4: Recompute last 12 buckets (1h) via delete-then-insert (idempotent),
       prune aggregates older than 28 days.
P3-D5: Weekly baseline recompute over last 56 days of aggregates (8 weeks)
       using mean and population standard deviation. Groups with n < 2 get stddev=0.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import logging
from typing import Any, Optional
import zoneinfo

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Avg, Count, F, StdDev
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, ExtractMinute
from django.utils import timezone

from apps.activity.models import ActivityAggregate, HistoricalBaseline, UserActivity

logger = logging.getLogger(__name__)


def _get_ist_timezone() -> zoneinfo.ZoneInfo:
    tz_name = getattr(settings, "TIME_ZONE", "Asia/Kolkata")
    try:
        return zoneinfo.ZoneInfo(tz_name)
    except Exception:
        return zoneinfo.ZoneInfo("Asia/Kolkata")


def aggregate_activity(
    now: Optional[datetime] = None,
    window_minutes: int = 60,
    bucket_minutes: int = 5,
    resolution: int = 8,
) -> dict[str, Any]:
    """
    Derive 5-minute bucketed activity counts for the last window_minutes
    (default 12 buckets / 1 hour) and prune aggregates older than 28 days (P3-D4).

    For each bucket [b, b+5m), UserActivity rows are grouped by H3 cell to produce:
    - event_count: total activity events
    - active_count: distinct active users

    Existing ActivityAggregate rows for that bucket and resolution are deleted
    before bulk creating new ones (delete-then-bulk_create, idempotent).

    Returns:
        dict: {"buckets": 12, "cells_written": N, "rows_pruned": M}
    """
    if now is None:
        now = timezone.now()
    elif timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())

    ist = _get_ist_timezone()
    now_ist = now.astimezone(ist)

    # Floor to nearest bucket_minutes
    bucket_min = (now_ist.minute // bucket_minutes) * bucket_minutes
    latest_bucket = now_ist.replace(minute=bucket_min, second=0, microsecond=0)

    total_buckets = window_minutes // bucket_minutes
    buckets = [
        latest_bucket - timedelta(minutes=bucket_minutes * i)
        for i in reversed(range(total_buckets))
    ]

    h3_field = f"h3_index_res{resolution}"
    total_cells_written = 0

    with transaction.atomic():
        for b in buckets:
            b_end = b + timedelta(minutes=bucket_minutes)
            # Event exactly on b_end lands in the later bucket (timestamp__lt=b_end)
            qs = (
                UserActivity.objects.filter(
                    timestamp__gte=b,
                    timestamp__lt=b_end,
                )
                .values(h3_index=F(h3_field))
                .annotate(
                    event_count=Count("id"),
                    active_count=Count("user_id", distinct=True),
                )
            )

            # Idempotent delete-then-bulk_create (P3-D4)
            ActivityAggregate.objects.filter(
                resolution=resolution,
                time_bucket=b,
            ).delete()

            rows_to_create = [
                ActivityAggregate(
                    h3_index=item["h3_index"],
                    resolution=resolution,
                    time_bucket=b,
                    active_count=item["active_count"],
                    event_count=item["event_count"],
                )
                for item in qs
                if item["h3_index"]
            ]

            if rows_to_create:
                ActivityAggregate.objects.bulk_create(rows_to_create)
                total_cells_written += len(rows_to_create)

        # Prune aggregates older than 28 days
        prune_cutoff = now - timedelta(days=28)
        rows_pruned, _ = ActivityAggregate.objects.filter(
            time_bucket__lt=prune_cutoff
        ).delete()

    summary = {
        "buckets": len(buckets),
        "cells_written": total_cells_written,
        "rows_pruned": rows_pruned,
    }
    logger.info("aggregate_activity completed: %s", summary)
    return summary


def recompute_baselines(
    now: Optional[datetime] = None,
    weeks: int = 8,
    resolution: int = 8,
) -> dict[str, Any]:
    """
    Recompute historical baselines per (h3, resolution, dow, minutes)
    over the last weeks*7 days (default 56 days / 8 weeks) (P3-D5).

    Computes:
    - avg_active_count: mean active_count over historical slots
    - stddev_active_count: population standard deviation (0.00 if sample_count < 2)
    - sample_count: number of historical data points

    dow and minutes are derived from the IST wall-clock of time_bucket (P3-D2):
    - dow: 0=Monday ... 6=Sunday
    - minutes: 0, 5, 10 ... 1435

    Returns:
        dict: {"baselines_created": N, "baselines_updated": M, "total": N+M}
    """
    if now is None:
        now = timezone.now()
    elif timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())

    ist = _get_ist_timezone()
    cutoff = now - timedelta(days=weeks * 7)

    created_count = 0
    updated_count = 0

    with transaction.atomic():
        if connection.vendor == "sqlite":
            # Fallback for SQLite in local non-spatial test environments
            aggs = ActivityAggregate.objects.filter(
                resolution=resolution,
                time_bucket__gte=cutoff,
                time_bucket__lte=now,
            )
            groups = defaultdict(list)
            for agg in aggs:
                tb_ist = agg.time_bucket.astimezone(ist)
                dow = tb_ist.weekday()  # 0=Monday, 6=Sunday
                minute_slot = tb_ist.hour * 60 + tb_ist.minute
                groups[(agg.h3_index, agg.resolution, dow, minute_slot)].append(
                    agg.active_count
                )

            for (h3, res, dow, minute_slot), counts in groups.items():
                n = len(counts)
                avg_val = Decimal(str(round(sum(counts) / n, 2)))
                if n < 2:
                    sd_val = Decimal("0.00")
                else:
                    mean = sum(counts) / n
                    variance = sum((x - mean) ** 2 for x in counts) / n
                    sd_val = Decimal(str(round(variance ** 0.5, 2)))

                _, was_created = HistoricalBaseline.objects.update_or_create(
                    h3_index=h3,
                    resolution=res,
                    day_of_week=dow,
                    time_bucket_minutes=minute_slot,
                    defaults={
                        "avg_active_count": avg_val,
                        "stddev_active_count": sd_val,
                        "sample_count": n,
                    },
                )
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1
        else:
            # Native SQL aggregation for PostgreSQL
            qs = (
                ActivityAggregate.objects.filter(
                    resolution=resolution,
                    time_bucket__gte=cutoff,
                    time_bucket__lte=now,
                )
                .annotate(
                    dow=ExtractIsoWeekDay("time_bucket", tzinfo=ist) - 1,
                    minutes=ExtractHour("time_bucket", tzinfo=ist) * 60
                    + ExtractMinute("time_bucket", tzinfo=ist),
                )
                .values("h3_index", "resolution", "dow", "minutes")
                .annotate(
                    avg=Avg("active_count"),
                    sd=StdDev("active_count", sample=False),
                    n=Count("id"),
                )
            )

            for item in qs:
                h3 = item["h3_index"]
                res = item["resolution"]
                dow = int(item["dow"])
                minute_slot = int(item["minutes"])
                n = item["n"]
                avg_val = Decimal(str(round(item["avg"], 2)))
                sd_val = (
                    Decimal("0.00")
                    if n < 2 or item["sd"] is None
                    else Decimal(str(round(item["sd"], 2)))
                )

                _, was_created = HistoricalBaseline.objects.update_or_create(
                    h3_index=h3,
                    resolution=res,
                    day_of_week=dow,
                    time_bucket_minutes=minute_slot,
                    defaults={
                        "avg_active_count": avg_val,
                        "stddev_active_count": sd_val,
                        "sample_count": n,
                    },
                )
                if was_created:
                    created_count += 1
                else:
                    updated_count += 1

    summary = {
        "baselines_created": created_count,
        "baselines_updated": updated_count,
        "total": created_count + updated_count,
    }
    logger.info("recompute_baselines completed: %s", summary)
    return summary
