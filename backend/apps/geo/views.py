"""
Public geo read endpoints (P3-F7, P2 carry-overs 1/3/4).

Read-only views over the cached ``WeatherData`` rows (P2-F4) and the cached
city boundaries (P2-F6). No new network I/O — everything answers from the
local PostGIS DB. All JWT-protected (P3-D8), all responses carry explicit
``timezone`` (Asia/Kolkata) + ``local_time`` for display.
"""

from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

import h3

from .geocoding import reverse_geocode_city
from .models import WeatherData
from .serializers import (
    ReverseGeocodeResponseSerializer,
    WeatherForecastResponseSerializer,
    WeatherPointSerializer,
)

WEATHER_RESOLUTION = 7
FORECAST_MIN_HOURS = 1
FORECAST_MAX_HOURS = 48

LAT_PARAM = OpenApiParameter(
    "lat", OpenApiTypes.FLOAT, location=OpenApiParameter.QUERY,
    required=True, description="Latitude (WGS84, -90..90)",
)
LNG_PARAM = OpenApiParameter(
    "lng", OpenApiTypes.FLOAT, location=OpenApiParameter.QUERY,
    required=True, description="Longitude (WGS84, -180..180)",
)
HOURS_PARAM = OpenApiParameter(
    "hours", OpenApiTypes.INT, location=OpenApiParameter.QUERY,
    description=f"Forecast horizon in hours (default 24, clamped {FORECAST_MIN_HOURS}-{FORECAST_MAX_HOURS})",
)


def _center_from_params(params):
    """Validate required lat/lng query params -> (lat, lng) floats; 400 envelope."""
    values = {}
    errors = {}
    for key, lo, hi in (("lat", -90.0, 90.0), ("lng", -180.0, 180.0)):
        raw = params.get(key, "")
        if raw is None or not str(raw).strip():
            errors[key] = "This query parameter is required."
            continue
        try:
            value = float(raw)
        except ValueError:
            errors[key] = "A valid number is required."
            continue
        if not (lo <= value <= hi):
            errors[key] = f"Must be between {lo} and {hi}."
            continue
        values[key] = value
    if errors:
        raise ValidationError(errors)
    return values["lat"], values["lng"]


def _hours_from_params(params):
    """hours: default 24, clamped to 1-48; malformed -> 400 envelope."""
    raw = params.get("hours", "")
    if raw is None or not str(raw).strip():
        return 24
    try:
        hours = int(str(raw))
    except ValueError:
        raise ValidationError({"hours": "A valid integer is required."})
    return max(FORECAST_MIN_HOURS, min(FORECAST_MAX_HOURS, hours))


def _anchor_cell(lat, lng):
    """H3 res7 cell (the P2-F4 weather grid resolution) containing the point."""
    return h3.latlng_to_cell(lat, lng, WEATHER_RESOLUTION)


def _point_payload(row) -> dict:
    return {
        "h3_index": row.h3_index,
        "timestamp": row.timestamp,
        "local_time": timezone.localtime(row.timestamp),
        "is_forecast": row.is_forecast,
        "temperature_c": row.temperature_c,
        "humidity_pct": row.humidity_pct,
        "precipitation_probability": row.precipitation_probability,
        "precipitation_mm": row.precipitation_mm,
        "wind_speed_kmh": row.wind_speed_kmh,
        "weather_code": row.weather_code,
        "source": row.source,
    }


class _GeoQueryView(APIView):
    """Shared permission + parameter validation for the geo read endpoints."""

    permission_classes = [IsAuthenticated]

    def get_center(self, request):
        return _center_from_params(request.query_params)


class WeatherNowView(_GeoQueryView):
    """GET /api/v1/geo/weather/now/?lat=..&lng=.."""

    @extend_schema(
        parameters=[LAT_PARAM, LNG_PARAM],
        responses={200: WeatherPointSerializer, 404: None},
        summary="Current weather at a point",
        description=(
            "Returns the latest cached weather row for the H3 res7 cell "
            "containing (lat, lng): the most recent observation, or the first "
            "forecast hour if none has been stored yet. 404 when the cell has "
            "no cached weather data."
        ),
    )
    def get(self, request, *args, **kwargs):
        lat, lng = self.get_center(request)
        cell = _anchor_cell(lat, lng)
        now = timezone.now()
        row = (
            WeatherData.objects.filter(h3_index=cell, timestamp__lte=now)
            .order_by("-timestamp")
            .first()
            or WeatherData.objects.filter(h3_index=cell, timestamp__gt=now)
            .order_by("timestamp")
            .first()
        )
        if row is None:
            raise NotFound("No cached weather data for this location.")
        data = WeatherPointSerializer(_point_payload(row)).data
        data["timezone"] = settings.TIME_ZONE
        return Response(data)


class WeatherForecastView(_GeoQueryView):
    """GET /api/v1/geo/weather/forecast/?lat=..&lng=..&hours=.."""

    @extend_schema(
        parameters=[LAT_PARAM, LNG_PARAM, HOURS_PARAM],
        responses={200: WeatherForecastResponseSerializer},
        summary="Hourly weather forecast at a point",
        description=(
            "Returns up to `hours` future hourly rows for the H3 res7 cell "
            "containing (lat, lng), oldest first. Returns 200 with an empty "
            "`points` list when the cell has no cached forecast."
        ),
    )
    def get(self, request, *args, **kwargs):
        lat, lng = self.get_center(request)
        hours = _hours_from_params(request.query_params)
        cell = _anchor_cell(lat, lng)
        now = timezone.now()
        rows = list(
            WeatherData.objects.filter(
                h3_index=cell,
                timestamp__gt=now,
                timestamp__lte=now + timedelta(hours=hours),
            )
            .order_by("timestamp")[: hours + 1]
        )
        data = {
            "h3_index": cell,
            "timezone": settings.TIME_ZONE,
            "generated_at": now,
            "hours": hours,
            "points": [WeatherPointSerializer(_point_payload(r)).data for r in rows],
        }
        return Response(WeatherForecastResponseSerializer(data).data)


class ReverseGeocodeView(_GeoQueryView):
    """GET /api/v1/geo/reverse-geocode/?lat=..&lng=.."""

    @extend_schema(
        parameters=[LAT_PARAM, LNG_PARAM],
        responses={200: ReverseGeocodeResponseSerializer},
        summary="Reverse geocode a point to a cached city",
        description=(
            "Point-in-boundary lookup over the cached City boundaries "
            "(P2-F6). 200 with `city: null` when no cached boundary contains "
            "the point."
        ),
    )
    def get(self, request, *args, **kwargs):
        lat, lng = self.get_center(request)
        city = reverse_geocode_city(lat, lng)
        data = {"city": city, "timezone": settings.TIME_ZONE}
        return Response(ReverseGeocodeResponseSerializer(data).data)
