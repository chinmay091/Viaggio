"""
Activity write endpoints (P3-F3).

``POST /activity/check-in/`` — consent hard gate (P3-D3): no row is written
when ``location_sharing_consent`` is False.

``POST /activity/view/`` — consent gates *identity* (P3-D3): consented users
are tracked by user id; non-consented users are tracked anonymously via an
optional client ``session_id``. Repeated views for the same identity within
10 minutes debounce into the existing row (P3-D9).

H3 cells and event timestamps are always derived server-side — clients never
submit raw coordinates or times.
"""

from datetime import timedelta
from django.contrib.gis.geos import Point
from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.discovery.models import PlaceView
from apps.places.models import Place, h3_cell

from .models import UserActivity
from .serializers import (
    CheckInResponseSerializer,
    CheckInSerializer,
    PlaceViewCreateSerializer,
    PlaceViewResponseSerializer,
    PulseResponseSerializer,
)
from .services import pulse_hotspots

VIEW_DEBOUNCE_MINUTES = 10


def _get_active_place(place_id):
    """
    Resolve the active place for a client-supplied UUID (already validated
    by the serializer as a ``UUID``). Unknown or inactive places map to a
    404 via the standard error envelope — no existence oracle (P1-F4 pattern).
    """
    place = Place.objects.filter(is_active=True, pk=place_id).first()
    if place is None:
        raise Http404
    return place


def _place_h3_cells(place):
    """(res8, res9) cells for the place — recomputed from location if blank."""
    if place.h3_index_res8 and place.h3_index_res9:
        return place.h3_index_res8, place.h3_index_res9
    lat, lng = place.location.y, place.location.x
    return h3_cell(lat, lng, 8), h3_cell(lat, lng, 9)


class CheckInView(APIView):
    """POST /api/v1/activity/check-in/ — body ``{"place_id": "<uuid>"}``"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=CheckInSerializer,
        responses={201: CheckInResponseSerializer},
        summary="Check in at a place (consent-gated)",
        description=(
            "Records a check-in for the authenticated user at the given place. "
            "Requires `location_sharing_consent=True` — otherwise 403 and nothing "
            "is stored (P3-D3 hard gate). H3 cells are derived server-side from "
            "the place's location and the timestamp is server time."
        ),
    )
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        place = _get_active_place(serializer.validated_data["place_id"])

        if not request.user.location_sharing_consent:
            raise PermissionDenied("Location sharing consent is required to check in.")

        res8, res9 = _place_h3_cells(place)
        activity = UserActivity.objects.create(
            user=request.user,
            place=place,
            h3_index_res8=res8,
            h3_index_res9=res9,
        )
        return Response(
            CheckInResponseSerializer(activity).data,
            status=status.HTTP_201_CREATED,
        )


class PlaceViewCreateView(APIView):
    """POST /api/v1/activity/view/ — debounced place-view tracking (P3-D9)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PlaceViewCreateSerializer,
        responses={200: PlaceViewResponseSerializer, 201: PlaceViewResponseSerializer},
        summary="Record a place view (debounced)",
        description=(
            "Tracks a place detail view. Consented users are stored with their "
            "user id; non-consented users are stored anonymously with the "
            "optional client `session_id` (P3-D3). A second view for the same "
            "identity within 10 minutes merges into the existing row "
            "(`duration_seconds` keeps the max) and returns 200 with the same id."
        ),
    )
    def post(self, request):
        serializer = PlaceViewCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        place = _get_active_place(serializer.validated_data["place_id"])

        if request.user.location_sharing_consent:
            user, session_id = request.user, ""
        else:
            user, session_id = None, serializer.validated_data.get("session_id") or ""

        view, created = self._record(
            user,
            session_id,
            place,
            serializer.validated_data.get("source", PlaceView.SOURCE_DIRECT),
            serializer.validated_data.get("duration_seconds", 0),
        )
        return Response(
            {
                "id": view.id,
                "place_id": str(view.place_id),
                "source": view.source,
                "duration_seconds": view.duration_seconds,
                "created_at": view.created_at,
                "status": "created" if created else "merged",
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @staticmethod
    def _record(user, session_id, place, source, duration_seconds):
        """
        Create or merge a PlaceView for (identity, place) within the debounce
        window. Returns ``(view, created)``.
        """
        window_start = timezone.now() - timedelta(minutes=VIEW_DEBOUNCE_MINUTES)
        with transaction.atomic():
            qs = PlaceView.objects.filter(place=place, created_at__gte=window_start)
            if user is not None:
                qs = qs.filter(user=user)
            else:
                qs = qs.filter(user__isnull=True, session_id=session_id)
            existing = qs.order_by("-created_at").first()
            if existing is not None:
                if duration_seconds > existing.duration_seconds:
                    existing.duration_seconds = duration_seconds
                    existing.save(update_fields=["duration_seconds"])
                return existing, False
            view = PlaceView.objects.create(
                user=user,
                place=place,
                session_id=session_id,
                duration_seconds=duration_seconds,
                source=source,
            )
            return view, True


DEFAULT_RADIUS_M = 1000
MIN_RADIUS_M = 100
MAX_RADIUS_M = 25000
DEFAULT_TOP_N = 10
MAX_TOP_N = 50

LAT_PARAM = OpenApiParameter(
    "lat",
    OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Center latitude (WGS84, -90..90)",
)
LNG_PARAM = OpenApiParameter(
    "lng",
    OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    required=True,
    description="Center longitude (WGS84, -180..180)",
)
RADIUS_PARAM = OpenApiParameter(
    "radius_m",
    OpenApiTypes.FLOAT,
    location=OpenApiParameter.QUERY,
    description=f"Search radius in meters (default {DEFAULT_RADIUS_M}, clamped {MIN_RADIUS_M}-{MAX_RADIUS_M})",
)
TOP_N_PARAM = OpenApiParameter(
    "top_n",
    OpenApiTypes.INT,
    location=OpenApiParameter.QUERY,
    description=f"Max hotspots to return (default {DEFAULT_TOP_N}, clamped 1-{MAX_TOP_N})",
)


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
    """radius_m: default 1000, clamped to 100-25000."""
    raw = params.get("radius_m", "")
    if raw is None or not str(raw).strip():
        return DEFAULT_RADIUS_M
    try:
        radius = float(raw)
    except ValueError:
        raise ValidationError({"radius_m": "A valid number is required."})
    return max(MIN_RADIUS_M, min(MAX_RADIUS_M, radius))


def _top_n_from_params(params):
    """top_n: default 10, clamped 1-50."""
    raw = params.get("top_n", "")
    if raw is None or not str(raw).strip():
        return DEFAULT_TOP_N
    try:
        top_n = int(raw)
    except ValueError:
        raise ValidationError({"top_n": "A valid integer is required."})
    return max(1, min(MAX_TOP_N, top_n))


class PulseView(APIView):
    """GET /api/v1/activity/pulse/ — City Pulse hotspots vs baseline (P3-F5)."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[LAT_PARAM, LNG_PARAM, RADIUS_PARAM, TOP_N_PARAM],
        responses={200: PulseResponseSerializer},
        summary="City Pulse hotspots",
        description=(
            "Returns active H3 resolution 8 hotspots within radius_m of the anchor point, "
            "with baseline comparisons (z-score, unusually_busy flag) and parent-cell weather context."
        ),
    )
    def get(self, request):
        center = _center_from_params(request.query_params)
        radius_m = _radius_from_params(request.query_params)
        top_n = _top_n_from_params(request.query_params)
        data = pulse_hotspots(center=center, radius_m=radius_m, top_n=top_n)
        return Response(data, status=status.HTTP_200_OK)

