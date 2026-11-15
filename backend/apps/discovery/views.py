"""
Saved-places endpoints (P3-F6).

Strictly scoped to the request user: every endpoint only ever sees or mutates
the authenticated user's own ``SavedPlace`` rows. Re-saving an already saved
place is an idempotent upsert (200, ``saved_at`` refreshed).
"""

import uuid as uuid_lib

from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.places.models import Place

from .models import SavedPlace
from .serializers import SavedPlaceCreateSerializer, SavedPlaceSerializer


def _get_active_saved_place(place_id, user):
    """
    Resolve the (user, place) bookmark, 404 envelope when absent.

    Malformed place UUIDs are rejected here too, so both a wrong id and a
    place not saved by this user produce the same 404 envelope.
    """
    try:
        pk = uuid_lib.UUID(place_id)
    except (ValueError, AttributeError, TypeError):
        raise Http404
    saved = SavedPlace.objects.filter(user=user, place_id=pk).first()
    if saved is None:
        raise NotFound
    return saved


class SavedPlaceListCreateView(generics.ListCreateAPIView):
    """GET|POST /api/v1/discovery/saved/"""

    permission_classes = [IsAuthenticated]
    serializer_class = SavedPlaceSerializer

    def get_queryset(self):
        return (
            SavedPlace.objects.filter(user=self.request.user)
            .select_related("place")
            .prefetch_related("place__tags")
        )

    @extend_schema(
        responses={200: SavedPlaceSerializer(many=True)},
        summary="List saved places",
        description="The request user's saved places, most recently saved first.",
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        request=SavedPlaceCreateSerializer,
        responses={200: SavedPlaceSerializer, 201: SavedPlaceSerializer},
        summary="Save a place (idempotent)",
        description=(
            "Bookmarks the given active place for the request user. Re-saving an "
            "already saved place returns 200 and refreshes `saved_at`. Unknown, "
            "inactive or malformed place ids return 404."
        ),
    )
    def create(self, request, *args, **kwargs):
        serializer = SavedPlaceCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        place_id = serializer.validated_data["place_id"]

        try:
            place = Place.objects.get(pk=place_id, is_active=True)
        except (Place.DoesNotExist, ValueError):
            raise NotFound

        saved, created = SavedPlace.objects.get_or_create(
            user=request.user,
            place=place,
        )
        if not created:
            saved.saved_at = timezone.now()
            saved.save(update_fields=["saved_at"])

        out = SavedPlaceSerializer(saved)
        return Response(out.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class SavedPlaceDeleteView(APIView):
    """DELETE /api/v1/discovery/saved/{place_id}/"""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={204: None},
        summary="Remove a saved place",
        description="Deletes the request user's bookmark for the place; 404 if not saved.",
    )
    def delete(self, request, place_id):
        saved = _get_active_saved_place(place_id, request.user)
        saved.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
