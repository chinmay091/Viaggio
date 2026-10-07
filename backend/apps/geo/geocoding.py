"""
Local reverse geocoding over cached City boundaries (P2-F6, P2-D3).

Nominatim is NEVER called per-point: this is a GiST-backed point-in-boundary
query against the cached ``geo_cities`` rows. Consumed by the Phase 3 geo
API and P7 labels.
"""

from django.contrib.gis.geos import Point

from apps.geo.models import City


def reverse_geocode_city(lat: float, lng: float):
    """
    Return the City whose cached boundary contains (lat, lng), or None.

    With overlapping boundaries the result is deterministic: cities are
    ordered by name, so the first containing city alphabetically wins.
    """
    return (
        City.objects.filter(boundary__contains=Point(lng, lat, srid=4326))
        .order_by("name")
        .first()
    )
