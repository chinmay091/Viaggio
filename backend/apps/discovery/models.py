"""
Discovery models for Viaggio (Phase 3).

``SavedPlace`` tracks user-bookmarked places.
``PlaceView`` records place detail views (both authenticated and anonymous).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import AuditModel


class SavedPlace(AuditModel):
    """
    User bookmark / saved place (P3-F2, data-model §2.8).

    Extends AuditModel (UUID PK). Strictly scoped to (user, place) with
    a unique constraint preventing duplicates.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="saved_places",
        help_text="User who saved the place",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="saved_places",
        help_text="Place saved by the user",
    )
    saved_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when the place was bookmarked / re-saved",
    )

    class Meta:
        db_table = "discovery_savedplace"
        ordering = ["-saved_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "place"],
                name="uniq_disco_saved_user_place",
            ),
        ]

    def __str__(self):
        return f"SavedPlace({self.user_id}, {self.place_id})"


class PlaceView(models.Model):
    """
    Place detail view record (P3-F2, data-model §2.8).

    Uses BigAutoField PK (high-volume time-series). Anonymous views are
    supported via null user and optional session_id (P3-D3). Debounced in
    the API layer (P3-D9).
    """

    SOURCE_MAP_CLICK = "map_click"
    SOURCE_SEARCH = "search"
    SOURCE_RECOMMENDATION = "recommendation"
    SOURCE_DIRECT = "direct"

    SOURCE_CHOICES = (
        (SOURCE_MAP_CLICK, "Map Click"),
        (SOURCE_SEARCH, "Search"),
        (SOURCE_RECOMMENDATION, "Recommendation"),
        (SOURCE_DIRECT, "Direct"),
    )

    id = models.BigAutoField(
        primary_key=True,
        help_text="Dense integer primary key (high volume)",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="place_views",
        help_text="Consented authenticated user (null for anonymous / non-consenting)",
    )
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="views",
        help_text="Place that was viewed",
    )
    session_id = models.CharField(
        max_length=64,
        blank=True,
        default="",
        help_text="Session identifier for anonymous tracking",
    )
    duration_seconds = models.IntegerField(
        default=0,
        help_text="Time spent on the place detail page in seconds",
    )
    source = models.CharField(
        max_length=30,
        choices=SOURCE_CHOICES,
        default=SOURCE_DIRECT,
        help_text="Referral source for the view",
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the view occurred",
    )

    class Meta:
        db_table = "discovery_placeview"
        indexes = [
            models.Index(
                fields=["place", "created_at"],
                name="idx_disco_pv_place_created",
            ),
            models.Index(
                fields=["user", "created_at"],
                name="idx_disco_pv_user_created",
            ),
        ]

    def __str__(self):
        user_or_sess = self.user_id or self.session_id or "anon"
        return f"PlaceView({self.place_id}, {user_or_sess}, {self.source})"
