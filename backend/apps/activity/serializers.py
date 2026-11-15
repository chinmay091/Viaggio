"""
Serializers for the activity write API (P3-F3).

Request schemas for ``check-in`` / ``view`` and response schemas documented
via ``extend_schema``. H3 cells and timestamps are always server-derived —
clients never submit raw coordinates or event times (P3-D3).
"""

from rest_framework import serializers

from apps.discovery.models import PlaceView

from .models import UserActivity


class CheckInSerializer(serializers.Serializer):
    """POST /activity/check-in/ request body."""

    place_id = serializers.UUIDField()


class CheckInResponseSerializer(serializers.ModelSerializer):
    """POST /activity/check-in/ 201 response."""

    class Meta:
        model = UserActivity
        fields = ("id", "place_id", "h3_index_res8", "h3_index_res9", "timestamp")


class PlaceViewCreateSerializer(serializers.Serializer):
    """
    POST /activity/view/ request body (debounced, P3-D9).

    ``session_id`` only has meaning for non-consented users (anonymity by
    design — consented users are tracked by their user id, P3-D3).
    """

    place_id = serializers.UUIDField()
    source = serializers.ChoiceField(
        choices=PlaceView.SOURCE_CHOICES,
        default=PlaceView.SOURCE_DIRECT,
        required=False,
    )
    session_id = serializers.CharField(
        max_length=64,
        required=False,
        allow_blank=True,
        default="",
        help_text="Client session id; only used when location_sharing_consent is off",
    )
    duration_seconds = serializers.IntegerField(
        min_value=0,
        required=False,
        default=0,
        help_text="Seconds spent on the place detail page",
    )


class PlaceViewResponseSerializer(serializers.Serializer):
    """POST /activity/view/ response (201 created / 200 merged)."""

    id = serializers.IntegerField(help_text="Dense PlaceView row id")
    place_id = serializers.UUIDField()
    source = serializers.CharField()
    duration_seconds = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    status = serializers.ChoiceField(
        choices=("created", "merged"),
        help_text="'created' for a new view; 'merged' when debounced into an existing row",
    )


class CenterCoordinatesSerializer(serializers.Serializer):
    """Lat/lng center point."""

    lat = serializers.FloatField()
    lng = serializers.FloatField()


class HotspotSerializer(serializers.Serializer):
    """City Pulse hotspot item."""

    h3_index = serializers.CharField()
    center = CenterCoordinatesSerializer()
    polygon = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2)
    )
    active_count = serializers.IntegerField()
    event_count = serializers.IntegerField()
    hour_total = serializers.IntegerField()
    baseline_avg = serializers.FloatField(allow_null=True)
    z_score = serializers.FloatField(allow_null=True)
    unusually_busy = serializers.BooleanField()


class WeatherContextSerializer(serializers.Serializer):
    """Weather context for parent res7 cell."""

    temperature_c = serializers.FloatField()
    weather_code = serializers.IntegerField()
    precipitation_probability = serializers.FloatField()
    is_forecast = serializers.BooleanField()
    timestamp = serializers.DateTimeField()
    local_time = serializers.DateTimeField()


class PulseResponseSerializer(serializers.Serializer):
    """GET /activity/pulse/ response."""

    generated_at = serializers.DateTimeField()
    timezone = serializers.CharField()
    bucket = serializers.DateTimeField()
    radius_m = serializers.FloatField()
    hotspots = HotspotSerializer(many=True)
    weather = WeatherContextSerializer(allow_null=True)

