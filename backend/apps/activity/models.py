"""
Activity models for Viaggio City Pulse (Phase 3).

``UserActivity`` records individual user check-ins/views at a place.
``ActivityAggregate`` holds 5-minute bucketed activity counts per H3 cell.
``HistoricalBaseline`` stores weekly-recomputed average/stddev for anomaly detection.

Privacy: ``UserActivity`` rows are only written when the user has granted
``location_sharing_consent=True`` — enforced server-side in the API layer (P3-D3).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import AuditModel


class UserActivity(AuditModel):
    """
    Persistent user activity event (check-in or view at a place).

    H3 cells are denormalized from the place's location (v2 §6) and populated
    by the API layer (P3-D3) — never client-supplied. ``timestamp`` defaults
    to ``timezone.now`` (IST-aware via Django ``TIME_ZONE``).

    Only recorded when ``user.location_sharing_consent == True`` (P3-D3 hard gate).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="activities",
        help_text="User who performed the activity",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="activities",
        help_text="Place where the activity occurred",
    )
    h3_index_res8 = models.CharField(
        max_length=16,
        help_text="H3 cell at resolution 8, denormalized from place.location",
    )
    h3_index_res9 = models.CharField(
        max_length=16,
        help_text="H3 cell at resolution 9, denormalized from place.location",
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        help_text="Event time (IST-aware); created_at stays the audit stamp",
    )

    class Meta:
        db_table = "activity_useractivity"
        indexes = [
            models.Index(
                fields=["timestamp"],
                name="idx_actua_timestamp",
            ),
            models.Index(
                fields=["h3_index_res8", "timestamp"],
                name="idx_actua_h3r8_ts",
            ),
            models.Index(
                fields=["user", "timestamp"],
                name="idx_actua_user_ts",
            ),
        ]

    def __str__(self):
        return f"UserActivity({self.user_id}, {self.place_id}, {self.timestamp:%Y-%m-%d %H:%M})"


class ActivityAggregate(models.Model):
    """
    5-minute bucketed activity counts per H3 cell (P3-D2/D4).

    Documented exception to the AuditModel/UUID rule: high-volume time-series
    rows use a dense BigAutoField primary key (same convention as WeatherData).

    Recomputed hourly via delete-then-insert (P3-D4) — idempotent by construction.
    Pruned after 28 days.
    """

    id = models.BigAutoField(
        primary_key=True,
        help_text="Dense integer primary key (time-series volume)",
    )
    h3_index = models.CharField(
        max_length=16,
        help_text="H3 cell identifier (resolution 8)",
    )
    resolution = models.IntegerField(
        choices=((8, "Resolution 8"), (9, "Resolution 9")),
        help_text="H3 resolution (8 or 9)",
    )
    time_bucket = models.DateTimeField(
        help_text="Start of 5-minute time bucket (IST wall-clock, P3-D2)",
    )
    active_count = models.IntegerField(
        help_text="Distinct active users in this bucket",
    )
    event_count = models.IntegerField(
        help_text="Total activity events in this bucket",
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When this aggregate row was created",
    )

    class Meta:
        db_table = "activity_aggregate"
        constraints = [
            models.UniqueConstraint(
                fields=["h3_index", "resolution", "time_bucket"],
                name="uniq_actagg_h3_res_bucket",
            ),
        ]
        indexes = [
            models.Index(
                fields=["time_bucket"],
                name="idx_actagg_time_bucket",
            ),
        ]

    def __str__(self):
        return (
            f"ActivityAggregate({self.h3_index}, res{self.resolution}, "
            f"{self.time_bucket:%Y-%m-%d %H:%M}, active={self.active_count})"
        )


class HistoricalBaseline(models.Model):
    """
    Weekly-recomputed baseline for anomaly detection (P3-D5/D6).

    Stores mean + population stddev + sample_count per (H3, resolution,
    day_of_week, 5-minute slot). Used to compute z-scores for the pulse API.

    Documented exception to the AuditModel/UUID rule: BigAutoField PK.
    """

    id = models.BigAutoField(
        primary_key=True,
        help_text="Dense integer primary key",
    )
    h3_index = models.CharField(
        max_length=16,
        help_text="H3 cell identifier",
    )
    resolution = models.IntegerField(
        choices=((8, "Resolution 8"), (9, "Resolution 9")),
        help_text="H3 resolution (8 or 9)",
    )
    day_of_week = models.IntegerField(
        help_text="Day of week: 0=Monday, 6=Sunday",
    )
    time_bucket_minutes = models.IntegerField(
        help_text="Minutes since midnight (0, 5, 10, …, 1435) in IST",
    )
    avg_active_count = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Historical average active_count for this slot",
    )
    stddev_active_count = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Population standard deviation for z-score calculation",
    )
    sample_count = models.IntegerField(
        help_text="Number of data points (weeks) used to compute the stats",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Last time this baseline was recomputed",
    )

    class Meta:
        db_table = "activity_historicalbaseline"
        constraints = [
            models.UniqueConstraint(
                fields=["h3_index", "resolution", "day_of_week", "time_bucket_minutes"],
                name="uniq_actbase_h3_dow_min",
            ),
        ]

    def __str__(self):
        return (
            f"HistoricalBaseline({self.h3_index}, res{self.resolution}, "
            f"dow={self.day_of_week}, min={self.time_bucket_minutes}, "
            f"avg={self.avg_active_count})"
        )
