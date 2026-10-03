from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from .models import Place

LOCATION_SCHEMA = {
    "type": "object",
    "description": "WGS84 geographic coordinates",
    "properties": {
        "lat": {"type": "number", "format": "double", "description": "Latitude"},
        "lng": {"type": "number", "format": "double", "description": "Longitude"},
    },
    "required": ["lat", "lng"],
}

SOURCE_SCHEMA = {
    "type": "object",
    "description": "Upstream data source provenance",
    "properties": {
        "provider": {"type": "string", "description": "Provider identifier, e.g. OVERTURE"},
        "provider_url": {"type": "string", "format": "uri", "description": "URL of the source record"},
    },
    "required": ["provider", "provider_url"],
}

DISTANCE_M_SCHEMA = {
    "type": "integer",
    "description": "Whole-meter distance from the query center",
}


class PlaceListSerializer(serializers.ModelSerializer):
    """
    Place-card serializer for list/nearby responses (legacy-compatible shape).

    `location` is always emitted as `{"lat": ..., "lng": ...}` rounded to 6
    decimal places — never raw WKT. `distance_m` is populated by the view via
    a `Distance(...)` annotation on geography (meters) and is omitted entirely
    when the queryset was not distance-annotated.
    """

    tags = serializers.SerializerMethodField()
    location = serializers.SerializerMethodField()
    distance_m = serializers.SerializerMethodField()

    class Meta:
        model = Place
        fields = (
            "id",
            "name",
            "slug",
            "category",
            "subcategory",
            "rating",
            "review_count",
            "price_level",
            "address",
            "phone",
            "website",
            "photos",
            "tags",
            "location",
            "distance_m",
        )
        read_only_fields = fields

    def get_tags(self, obj):
        """Tag names (prefetched via `prefetch_related("tags")` in the view)."""
        return [tag.name for tag in obj.tags.all()]

    @extend_schema_field(LOCATION_SCHEMA)
    def get_location(self, obj):
        """Round-trip-safe {lat, lng} wire format; None when the place has no location."""
        if obj.location is None:
            return None
        return {"lat": round(obj.location.y, 6), "lng": round(obj.location.x, 6)}

    @extend_schema_field(DISTANCE_M_SCHEMA)
    def get_distance_m(self, obj):
        """
        Whole-meter distance from the query center, when the view annotated the
        queryset with `distance_m=Distance("location", center)`. On a geography
        field GeoDjango returns a measure object; `.m` yields meters. Returns
        None (field omitted) for non-spatial queries.
        """
        distance = getattr(obj, "distance_m", None)
        if distance is None:
            return None
        meters = getattr(distance, "m", distance)
        return int(round(float(meters)))

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if data.get("distance_m") is None:
            data.pop("distance_m", None)
        return data


class PlaceDetailSerializer(PlaceListSerializer):
    """
    Full place serializer for the detail endpoint: card fields plus
    description/hours/metadata, full address context, provenance and audit stamp.
    """

    sources = serializers.SerializerMethodField()

    class Meta(PlaceListSerializer.Meta):
        fields = PlaceListSerializer.Meta.fields + (
            "description",
            "opening_hours",
            "metadata",
            "city",
            "region",
            "country",
            "postal_code",
            "verified",
            "updated_at",
            "sources",
        )

    @extend_schema_field(SOURCE_SCHEMA)
    def get_sources(self, obj):
        """Read-only provenance list (prefetched via `prefetch_related("sources")`)."""
        return [
            {"provider": source.provider, "provider_url": source.provider_url}
            for source in obj.sources.all()
        ]