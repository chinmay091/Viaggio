"""
Serializers for the saved-places API (P3-F6).

List items embed the legacy-compatible place card (``PlaceListSerializer``)
plus ``saved_at``. The card's ``distance_m`` is omitted automatically because
saved places are not distance-annotated.
"""

from rest_framework import serializers

from apps.places.serializers import PlaceListSerializer

from .models import SavedPlace


class SavedPlaceSerializer(serializers.ModelSerializer):
    """Saved-place card: place card + saved_at."""

    place = PlaceListSerializer(read_only=True)

    class Meta:
        model = SavedPlace
        fields = ("id", "place", "saved_at")
        read_only_fields = fields


class SavedPlaceCreateSerializer(serializers.Serializer):
    """POST /discovery/saved/ request body."""

    place_id = serializers.UUIDField()
