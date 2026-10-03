"""
Canonical place (POI) models for Viaggio.

``Place`` is the single source of truth for every point of interest
(restaurant, hotel, cafe, attraction, ...). Data arrives from one or more
providers via ``PlaceSource`` (provenance + raw payload for audit).

Spatial indexing:
- ``location`` is a PostGIS *geography* point (WGS84) with a GiST index,
  powering radius queries via ``location__dwithin`` / ``Distance``.
- ``h3_index_res8`` / ``h3_index_res9`` are precomputed H3 cells (D1) for
  future City Pulse aggregation; kept in sync automatically on save.
- ``normalized_name`` is backed by a trigram GIN index for fuzzy search.
"""

import h3

from django.contrib.gis.db import models
from django.contrib.postgres.indexes import GinIndex, GistIndex
from django.utils.text import slugify

from apps.common.models import AuditModel


def h3_cell(lat, lng, res):
    """Return the H3 cell (as hex string) for ``lat``/``lng`` at resolution ``res``."""
    return h3.latlng_to_cell(lat, lng, res)


class PlaceCategory(AuditModel):
    """Hierarchical category tree for places (e.g. restaurant > italian_restaurant)."""

    name = models.CharField(
        max_length=100,
        help_text="Human readable category name, e.g. 'Italian Restaurant'",
    )
    slug = models.SlugField(
        unique=True,
        help_text="URL-friendly category identifier",
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent category (null for top-level categories)",
    )
    icon = models.CharField(
        max_length=50,
        blank=True,
        default="",
        help_text="Icon identifier for UI rendering",
    )

    class Meta:
        db_table = "place_categories"
        verbose_name = "Place Category"
        verbose_name_plural = "Place Categories"

    def __str__(self):
        return self.name


class Place(AuditModel):
    """Canonical place entity, geo-indexed via PostGIS + H3."""

    # --- Identity ---
    name = models.CharField(
        max_length=255,
        help_text="Display name",
    )
    normalized_name = models.CharField(
        max_length=255,
        help_text="Lowercase, stripped name; derived from name, used for matching and fuzzy search",
    )
    slug = models.SlugField(
        unique=True,
        help_text="Globally unique URL-friendly identifier",
    )

    # --- Classification ---
    category = models.CharField(
        max_length=50,
        help_text="Primary category, e.g. 'restaurant', 'hotel', 'attraction'",
    )
    subcategory = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="More specific category, e.g. 'italian_restaurant', 'boutique_hotel'",
    )

    # --- Description / address ---
    description = models.TextField(
        blank=True,
        default="",
        help_text="Free text description",
    )
    address = models.TextField(
        blank=True,
        default="",
        help_text="Full address string",
    )
    city = models.CharField(max_length=100, blank=True, default="", help_text="City name")
    region = models.CharField(max_length=100, blank=True, default="", help_text="State/province")
    country = models.CharField(max_length=100, blank=True, default="", help_text="Country")
    postal_code = models.CharField(max_length=20, blank=True, default="", help_text="Postal/ZIP code")

    # --- Spatial ---
    location = models.PointField(
        geography=True,
        srid=4326,
        spatial_index=False,  # explicit GistIndex in Meta; suppress duplicate auto index
        help_text="PostGIS geography point (WGS84 lat/lng)",
    )
    h3_index_res8 = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Precomputed H3 index at resolution 8",
    )
    h3_index_res9 = models.CharField(
        max_length=16,
        blank=True,
        default="",
        help_text="Precomputed H3 index at resolution 9",
    )

    # --- Quality / commerce signals ---
    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Aggregate rating 0.00 - 5.00 (null until enriched by a rated provider)",
    )
    review_count = models.IntegerField(
        default=0,
        help_text="Total reviews across providers",
    )
    price_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="1-4 ($ to $$$$, null when unknown)",
    )
    phone = models.CharField(max_length=20, blank=True, default="", help_text="Contact phone number")
    website = models.URLField(max_length=500, blank=True, default="", help_text="Official website URL")

    # --- Structured data ---
    opening_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text='Structured hours, e.g. {"monday": [{"open": "09:00", "close": "22:00"}]}',
    )
    photos = models.JSONField(
        default=list,
        blank=True,
        help_text="Array of photo URLs",
    )
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Provider-specific extra data",
    )

    # --- Flags ---
    is_active = models.BooleanField(
        default=True,
        help_text="Soft delete flag; inactive places are hidden from search",
    )
    verified = models.BooleanField(
        default=False,
        help_text="Data quality flag (manually or automatically verified)",
    )

    class Meta:
        db_table = "places"
        verbose_name = "Place"
        verbose_name_plural = "Places"
        indexes = [
            GistIndex(fields=["location"], name="idx_places_location_gist"),
            GinIndex(
                fields=["normalized_name"],
                name="idx_places_name_trgm",
                opclasses=["gin_trgm_ops"],
            ),
            models.Index(fields=["category"], name="idx_places_category"),
            models.Index(fields=["city"], name="idx_places_city"),
            models.Index(fields=["rating"], name="idx_places_rating"),
            models.Index(fields=["price_level"], name="idx_places_price_level"),
            models.Index(fields=["h3_index_res8"], name="idx_places_h3_res8"),
            models.Index(fields=["h3_index_res9"], name="idx_places_h3_res9"),
        ]

    def __str__(self):
        return self.name

    # --- Derived-field maintenance -------------------------------------
    def fill_derived_fields(self):
        """Compute ``normalized_name``, a unique ``slug`` and H3 cells.

        Called automatically by :meth:`save`. ``bulk_create`` / ``bulk_update``
        bypass ``save()``, so bulk writers (seed command, benchmark) MUST call
        this explicitly before persisting.
        """
        self.normalized_name = (self.name or "").strip().lower()
        if not self.slug:
            self.slug = self._generate_unique_slug()
        if self.location is not None:
            self.h3_index_res8 = h3_cell(self.location.y, self.location.x, 8)
            self.h3_index_res9 = h3_cell(self.location.y, self.location.x, 9)
        return self

    def _generate_unique_slug(self):
        """Return a globally unique slug derived from ``normalized_name`` (D3)."""
        base = slugify(self.normalized_name, allow_unicode=True) or "place"
        candidate = base
        counter = 2
        existing = Place.objects.filter(slug=candidate).exclude(pk=self.pk)
        while existing.exists():
            candidate = f"{base}-{counter}"
            counter += 1
            existing = Place.objects.filter(slug=candidate).exclude(pk=self.pk)
        return candidate

    def save(self, *args, **kwargs):
        self.fill_derived_fields()
        super().save(*args, **kwargs)


class Tag(AuditModel):
    """Free-form label attached to places (e.g. 'outdoor_seating', 'pet_friendly')."""

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="e.g. 'outdoor_seating', 'pet_friendly', 'live_music'",
    )
    places = models.ManyToManyField(
        Place,
        related_name="tags",
        blank=True,
        help_text="Places carrying this tag",
    )

    class Meta:
        db_table = "tags"
        verbose_name = "Tag"
        verbose_name_plural = "Tags"

    def __str__(self):
        return self.name

class PlaceSource(AuditModel):
    """Provenance record: which provider contributed (or can re-enrich) a Place."""

    OVERTURE = "OVERTURE"
    FOURSQUARE = "FOURSQUARE"
    GOOGLE = "GOOGLE"
    SWIGGY = "SWIGGY"
    PROVIDERS = (
        (OVERTURE, "Overture Maps"),
        (FOURSQUARE, "Foursquare"),
        (GOOGLE, "Google Places"),
        (SWIGGY, "Swiggy"),
    )

    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name="sources",
        help_text="Canonical place this source feeds",
    )
    provider = models.CharField(
        max_length=50,
        choices=PROVIDERS,
        help_text="Data provider identifier",
    )
    provider_id = models.CharField(
        max_length=255,
        help_text="ID of the place in the provider's system",
    )
    provider_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        help_text="Link to the provider's listing",
    )
    provider_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw provider response (kept for audit/re-ingestion)",
    )
    confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=1.00,
        help_text="Match confidence 0.00 - 1.00",
    )
    last_synced_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of the last enrichment from this provider",
    )

    class Meta:
        db_table = "place_sources"
        verbose_name = "Place Source"
        verbose_name_plural = "Place Sources"
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "provider_id"],
                name="uniq_place_source_provider_id",
            ),
        ]

    def __str__(self):
        return f"{self.provider}:{self.provider_id}"

