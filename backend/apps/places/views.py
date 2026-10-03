"""
Place discovery endpoints (P1-F4).

All three GET endpoints are JWT-protected (locked decision D4). Spatial
queries run on PostGIS geography: ``location__dwithin`` uses the GiST index
and ``Distance("location", center)`` returns meters, so results come back in
true nearest-first order.
"""

import uuid as uuid_lib

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import Point
from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated

from .models import Place
from .serializers import PlaceDetailSerializer, PlaceListSerializer

DEFAULT_RADIUS_M = 1000
MIN_RADIUS_M = 100
MAX_RADIUS_M = 25000

LAT_PARAM = OpenApiParameter(
    "lat", OpenApiTypes.FLOAT, location=OpenApiParameter.QUERY,
    required=True, description="Center latitude (WGS84, -90..90)",
)
LNG_PARAM = OpenApiParameter(
    "lng", OpenApiTypes.FLOAT, location=OpenApiParameter.QUERY,
    required=True, description="Center longitude (WGS84, -180..180)",
)
RADIUS_PARAM = OpenApiParameter(
    "radius_m", OpenApiTypes.FLOAT, location=OpenApiParameter.QUERY,
    description=f"Search radius in meters (default {DEFAULT_RADIUS_M}, clamped {MIN_RADIUS_M}-{MAX_RADIUS_M})",
)
CATEGORY_PARAM = OpenApiParameter(
    "category", OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description="Exact category filter, e.g. 'restaurant', 'cafe', 'hotel'",
)
Q_PARAM = OpenApiParameter(
    "q", OpenApiTypes.STR, location=OpenApiParameter.QUERY,
    description="Name search (case-insensitive, trigram-index-backed)",
)


def _require_valid_uuid(pk):
    """404 (via the standard error envelope) for malformed UUID path params."""
    try:
        uuid_lib.UUID(pk)
    except (ValueError, AttributeError, TypeError):
        raise Http404


def _center_from_params(params):
    """Validate required lat/lng query params -> WGS84 Point(geography)."""
    errors = {}
    values = {}
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
    return Point(values["lng"], values["lat"], srid=4326)


def _radius_from_params(params):
    """radius_m: default 1000, clamped to 100-25000 (locked decision D5)."""
    raw = params.get("radius_m", "")
    if raw is None or not str(raw).strip():
        return DEFAULT_RADIUS_M
    try:
        radius = float(raw)
    except ValueError:
        raise ValidationError({"radius_m": "A valid number is required."})
    return max(MIN_RADIUS_M, min(MAX_RADIUS_M, radius))


def _spatial_queryset(anchor, radius_m, params, exclude_pk=None):
    """Active places within radius of ``anchor``, nearest first, distance-annotated."""
    qs = (
        Place.objects.filter(is_active=True)
        .filter(location__dwithin=(anchor, radius_m))
        .annotate(distance_m=Distance("location", anchor))
        .order_by("distance_m", "pk")
    )
    if exclude_pk is not None:
        qs = qs.exclude(pk=exclude_pk)
    category = (params.get("category") or "").strip()
    if category:
        qs = qs.filter(category=category)
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(normalized_name__icontains=q)
    return qs.prefetch_related("tags")


@extend_schema(
    parameters=[LAT_PARAM, LNG_PARAM, RADIUS_PARAM, CATEGORY_PARAM, Q_PARAM],
    responses=PlaceListSerializer(many=True),
    summary="List places near a point",
    description=(
        "Returns active places within `radius_m` of (lat, lng), nearest first. "
        "Each result includes `distance_m` (whole meters from the center)."
    ),
)
class PlacesNearView(generics.ListAPIView):
    """GET /api/v1/places/near/?lat=..&lng=..&radius_m=..&category=..&q=.."""

    permission_classes = [IsAuthenticated]
    serializer_class = PlaceListSerializer

    def get_queryset(self):
        params = self.request.query_params
        center = _center_from_params(params)
        radius = _radius_from_params(params)
        return _spatial_queryset(center, radius, params)


@extend_schema(
    responses=PlaceDetailSerializer,
    summary="Retrieve a place by UUID",
    description="Full place detail including description, hours, provenance and audit stamp.",
)
class PlaceDetailView(generics.RetrieveAPIView):
    """GET /api/v1/places/{uuid}/"""

    permission_classes = [IsAuthenticated]
    serializer_class = PlaceDetailSerializer

    def get_queryset(self):
        return Place.objects.filter(is_active=True).prefetch_related("tags", "sources")

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_valid_uuid(self.kwargs.get("pk"))


@extend_schema(
    parameters=[RADIUS_PARAM, CATEGORY_PARAM, Q_PARAM],
    responses=PlaceListSerializer(many=True),
    summary="List places near a place",
    description=(
        "Returns other active places within `radius_m` of the anchor place, "
        "nearest first. The anchor place itself is excluded."
    ),
)
class PlaceNearbyView(generics.ListAPIView):
    """GET /api/v1/places/{uuid}/nearby/?radius_m=..&category=..&q=.."""

    permission_classes = [IsAuthenticated]
    serializer_class = PlaceListSerializer

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        _require_valid_uuid(self.kwargs.get("pk"))

    def get_queryset(self):
        anchor = Place.objects.filter(is_active=True, pk=self.kwargs["pk"]).first()
        if anchor is None or anchor.location is None:
            raise Http404
        params = self.request.query_params
        radius = _radius_from_params(params)
        return _spatial_queryset(anchor.location, radius, params, exclude_pk=anchor.pk)