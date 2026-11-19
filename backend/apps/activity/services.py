"""
Activity aggregation and baseline services (Phase 3 City Pulse).

P3-D2: 5-min buckets at H3 res8, IST timezone (Asia/Kolkata).
P3-D4: Recompute last 12 buckets (1h) via delete-then-insert (idempotent),
       prune aggregates older than 28 days.
P3-D5: Weekly baseline recompute over last 56 days of aggregates (8 weeks)
       using mean and population standard deviation. Groups with n < 2 get stddev=0.
"""

from collections import defaultdict
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
import logging
import math
from typing import Any, Optional
import zoneinfo

import h3

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Avg, Count, F, StdDev, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, ExtractMinute
from django.utils import timezone

from apps.activity.models import ActivityAggregate, HistoricalBaseline, UserActivity
from apps.geo.models import AreaContext, WeatherData
from apps.places.models import Place

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


def pulse_hotspots(
    center: Any,
    radius_m: float = 1000.0,
    now: Optional[datetime] = None,
    top_n: int = 10,
) -> dict[str, Any]:
    """
    Compute City Pulse hotspots within radius_m of center point (P3-F5).

    Computation:
    1. current bucket = floor(now to 5 min) in IST
    2. candidate cells = res8 cells whose centers are within radius_m of center
    3. ActivityAggregate(resolution=8, time_bucket=current, h3_index__in=cells) with active_count > 0
    4. per row: HistoricalBaseline(h3, 8, dow, minutes) -> z per P3-D6;
       hour_total = sum of the cell's last 12 buckets (event_count)
    5. order active_count desc, z_score desc nulls last, cap top_n (<= 50)
    6. weather = latest WeatherData for center's parent res7 cell (timestamp <= now + 1h, desc) or None

    Returns:
        dict: {"generated_at", "timezone", "bucket", "radius_m", "hotspots", "weather"}
    """
    if hasattr(center, "y") and hasattr(center, "x"):
        center_lat, center_lng = float(center.y), float(center.x)
    elif isinstance(center, (tuple, list)):
        center_lat, center_lng = float(center[0]), float(center[1])
    else:
        raise ValueError(f"Invalid center coordinates: {center}")

    if now is None:
        now = timezone.now()
    elif timezone.is_naive(now):
        now = timezone.make_aware(now, timezone.get_current_timezone())

    ist = _get_ist_timezone()
    now_ist = now.astimezone(ist)

    # Floor to nearest 5 minutes
    bucket_min = (now_ist.minute // 5) * 5
    bucket_time = now_ist.replace(minute=bucket_min, second=0, microsecond=0)

    # Candidate cells: centers within radius_m
    origin_cell = h3.latlng_to_cell(center_lat, center_lng, 8)
    k = int(math.ceil(radius_m / 500.0)) + 2
    ring_cells = h3.grid_disk(origin_cell, k)
    anchor_latlng = (center_lat, center_lng)
    candidate_cells = [
        cell
        for cell in ring_cells
        if h3.great_circle_distance(anchor_latlng, h3.cell_to_latlng(cell), unit="m") <= radius_m
    ]

    current_aggs = list(
        ActivityAggregate.objects.filter(
            resolution=8,
            time_bucket=bucket_time,
            h3_index__in=candidate_cells,
            active_count__gt=0,
        )
    )

    hotspots = []
    if current_aggs:
        matched_cell_indices = [agg.h3_index for agg in current_aggs]

        # Hour total: sum of event_count across last 12 buckets [bucket_time - 55m, bucket_time]
        start_hour_bucket = bucket_time - timedelta(minutes=55)
        hour_totals_qs = (
            ActivityAggregate.objects.filter(
                resolution=8,
                h3_index__in=matched_cell_indices,
                time_bucket__gte=start_hour_bucket,
                time_bucket__lte=bucket_time,
            )
            .values("h3_index")
            .annotate(total=Sum("event_count"))
        )
        hour_totals = {item["h3_index"]: item["total"] for item in hour_totals_qs}

        # Baseline per matched cell for this slot
        dow = bucket_time.weekday()
        minute_slot = bucket_time.hour * 60 + bucket_time.minute
        baselines_qs = HistoricalBaseline.objects.filter(
            resolution=8,
            h3_index__in=matched_cell_indices,
            day_of_week=dow,
            time_bucket_minutes=minute_slot,
        )
        baselines = {b.h3_index: b for b in baselines_qs}

        for agg in current_aggs:
            cell = agg.h3_index
            cell_lat, cell_lng = h3.cell_to_latlng(cell)
            polygon = [[lng, lat] for lat, lng in h3.cell_to_boundary(cell)]

            h_total = hour_totals.get(cell, agg.event_count)
            baseline = baselines.get(cell)

            baseline_avg = None
            z_score = None
            unusually_busy = False

            if baseline is not None:
                baseline_avg = float(baseline.avg_active_count)
                stddev = float(baseline.stddev_active_count)
                sample_count = baseline.sample_count

                # P3-D6: z = (active_count - avg) / stddev only when stddev > 0 and sample_count >= 3; else z = null.
                # unusually_busy = (z >= 2.0)
                if stddev > 0 and sample_count >= 3:
                    raw_z = (agg.active_count - baseline_avg) / stddev
                    z_score = round(raw_z, 2)
                    unusually_busy = bool(z_score >= 2.0)

            hotspots.append({
                "h3_index": cell,
                "center": {"lat": round(cell_lat, 6), "lng": round(cell_lng, 6)},
                "polygon": polygon,
                "active_count": agg.active_count,
                "event_count": agg.event_count,
                "hour_total": h_total,
                "baseline_avg": baseline_avg,
                "z_score": z_score,
                "unusually_busy": unusually_busy,
            })

        # Order: active_count desc, z_score desc nulls last
        def sort_key(item):
            has_z = 0 if item["z_score"] is not None else 1
            z_val = -item["z_score"] if item["z_score"] is not None else 0
            return (-item["active_count"], has_z, z_val)

        hotspots.sort(key=sort_key)
        clamped_top_n = min(50, max(1, top_n))
        hotspots = hotspots[:clamped_top_n]

    # Weather context for anchor's parent res7 cell
    anchor_res7 = h3.cell_to_parent(origin_cell, 7)
    latest_weather = (
        WeatherData.objects.filter(
            h3_index=anchor_res7,
            timestamp__lte=now + timedelta(hours=1),
        )
        .order_by("-timestamp")
        .first()
    )

    weather_dict = None
    if latest_weather:
        local_ts = latest_weather.timestamp.astimezone(ist)
        weather_dict = {
            "temperature_c": float(latest_weather.temperature_c),
            "weather_code": latest_weather.weather_code,
            "precipitation_probability": float(latest_weather.precipitation_probability),
            "is_forecast": latest_weather.is_forecast,
            "timestamp": latest_weather.timestamp.isoformat(),
            "local_time": local_ts.isoformat(),
        }

    return {
        "generated_at": now_ist.isoformat(),
        "timezone": "Asia/Kolkata",
        "bucket": bucket_time.isoformat(),
        "radius_m": radius_m,
        "hotspots": hotspots,
        "weather": weather_dict,
    }


AREA_CONTEXT_TOP_CELLS = 20
AREA_CONTEXT_TOP_PLACES = 5
AREA_CONTEXT_TOP_CATEGORIES = 5
AREA_CONTEXT_TTL_HOURS = 3


def refresh_area_context(now: Optional[datetime] = None) -> dict[str, Any]:
    """
    Precompute ``geo.AreaContext`` rows for the top res8 cells by last-hour
    check-ins (P3-D7).

    Rule-based enrichment only — ``llm_provider="rule_based"`` (LLM enrichment
    is Phase 4). Idempotent: ``update_or_create`` on the unique
    ``(h3_index, time_bucket)`` key; rows past their TTL are pruned in the
    same run.
    """
    now = now or timezone.now()
    ist = _get_ist_timezone()
    # Time bucket = top of the current IST hour, stored as an aware UTC datetime.
    bucket = (
        now.astimezone(ist)
        .replace(minute=0, second=0, microsecond=0)
        .astimezone(dt_timezone.utc)
    )
    window_start = now - timedelta(hours=1)

    top_cells = (
        UserActivity.objects.filter(timestamp__gte=window_start)
        .values("h3_index_res8")
        .annotate(check_ins=Count("id"))
        .order_by("-check_ins", "h3_index_res8")[:AREA_CONTEXT_TOP_CELLS]
    )

    written = 0
    for cell_row in top_cells:
        cell = cell_row["h3_index_res8"]
        check_ins = cell_row["check_ins"]

        place_counts = {
            str(r["place_id"]): r["n"]
            for r in UserActivity.objects.filter(
                timestamp__gte=window_start, h3_index_res8=cell
            )
            .values("place_id")
            .annotate(n=Count("id"))
        }
        ranked_places = []
        for place in Place.objects.filter(is_active=True, h3_index_res8=cell):
            n = place_counts.get(str(place.pk), 0)
            if n:
                ranked_places.append(
                    {"place_id": str(place.pk), "name": place.name, "score": n, "category": place.category}
                )
        ranked_places.sort(key=lambda p: (-p["score"], p["name"]))
        top_places = [
            {"place_id": p["place_id"], "name": p["name"], "score": p["score"]}
            for p in ranked_places[:AREA_CONTEXT_TOP_PLACES]
        ]

        category_scores: dict[str, int] = {}
        for p in ranked_places[:AREA_CONTEXT_TOP_PLACES]:
            if p["category"]:
                category_scores[p["category"]] = category_scores.get(p["category"], 0) + p["score"]
        top_categories = [
            {"category": c, "score": s}
            for c, s in sorted(category_scores.items(), key=lambda kv: (-kv[1], kv[0]))[
                :AREA_CONTEXT_TOP_CATEGORIES
            ]
        ]

        weather = (
            WeatherData.objects.filter(
                h3_index=h3.cell_to_parent(cell, 7),
                timestamp__lte=now + timedelta(hours=1),
            )
            .order_by("-timestamp")
            .first()
        )
        weather_context: dict[str, Any] = {}
        if weather:
            weather_context = {
                "h3_index": weather.h3_index,
                "timestamp": weather.timestamp.isoformat(),
                "local_time": weather.timestamp.astimezone(ist).isoformat(),
                "is_forecast": weather.is_forecast,
                "temperature_c": float(weather.temperature_c),
                "weather_code": weather.weather_code,
                "precipitation_probability": float(weather.precipitation_probability),
            }

        summary_parts = [
            f"{check_ins} check-in{'s' if check_ins != 1 else ''} in the last hour"
        ]
        if top_categories:
            summary_parts.append(
                "top categories: " + ", ".join(c["category"] for c in top_categories)
            )
        if weather_context:
            summary_parts.append(
                f"temperature {weather_context['temperature_c']:.0f}°C"
            )

        AreaContext.objects.update_or_create(
            h3_index=cell,
            time_bucket=bucket,
            defaults={
                "activity_summary": {"check_ins": check_ins, "window_minutes": 60},
                "top_categories": top_categories,
                "top_places": top_places,
                "weather_context": weather_context,
                "llm_summary": "; ".join(summary_parts) + ".",
                "llm_provider": "rule_based",
                "expires_at": now + timedelta(hours=AREA_CONTEXT_TTL_HOURS),
            },
        )
        written += 1

    pruned, _ = AreaContext.objects.filter(expires_at__lt=now).delete()
    return {"cells": written, "bucket": bucket.isoformat(), "pruned": pruned}

