"""
Factory-boy factories for the places app (P1-F6).

All synthetic places are jittered deterministically around the Mumbai anchor
(18.94 / 72.835, decision D4). Tests that need *exact* distances should pass
an explicit ``location=Point(lng, lat)`` override instead of relying on the
jitter.
"""

import factory
from django.contrib.gis.geos import Point

from .models import Place, PlaceCategory, PlaceSource, Tag

# Synthetic-data anchor (Mumbai). The default jitter keeps places within a
# ~2 km box around this point, so radius queries centred on the anchor hit.
ANCHOR_LAT = 18.9400
ANCHOR_LNG = 72.8350

CATEGORIES = ("cafe", "restaurant", "hotel", "attraction", "shopping")

# Jitter step in degrees (~77 m per step). The default scatter is a
# deterministic row-major grid around the anchor: ~140 places per row,
# covering +/- ~5.4 km in latitude and longitude.
_JITTER_DEG = 0.0007


def _jittered_location(n):
    """Deterministic point for the n-th factory instance, jittered around the anchor."""
    row, col = divmod(n, 140)
    lat = ANCHOR_LAT + (col - 70) * _JITTER_DEG
    lng = ANCHOR_LNG + (row - 70) * _JITTER_DEG
    return Point(lng, lat, srid=4326)


def _cycling_category(n):
    return CATEGORIES[n % len(CATEGORIES)]


class PlaceCategoryFactory(factory.django.DjangoModelFactory):
    """Category in the hierarchical PlaceCategory tree."""

    class Meta:
        model = PlaceCategory

    name = factory.Sequence(lambda n: f"Category {n + 1}")
    slug = factory.Sequence(lambda n: f"category-{n + 1}")
    parent = None


class TagFactory(factory.django.DjangoModelFactory):
    """Free-form tag; ``name`` is globally unique."""

    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag-{n + 1}")


class PlaceFactory(factory.django.DjangoModelFactory):
    """
    Canonical place. ``save()`` derives normalized_name / slug / H3 cells, so
    the factory only seeds the raw provider-style inputs.
    """

    class Meta:
        model = Place

    name = factory.Sequence(lambda n: f"Bench Place {n + 1}")
    category = factory.Sequence(_cycling_category)
    subcategory = ""
    description = "A synthetic place created by the test suite."
    address = factory.Sequence(lambda n: f"{n + 1} Test Street")
    city = "Mumbai"
    region = "Maharashtra"
    country = "India"
    phone = factory.Sequence(lambda n: f"+91 22 4000 {n + 1:04d}")
    website = ""
    is_active = True
    verified = False
    location = factory.Sequence(_jittered_location)

    @factory.post_generation
    def tags(self, create, extracted, **kwargs):
        if create and extracted:
            self.tags.set(extracted)

    @factory.post_generation
    def sources(self, create, extracted, **kwargs):
        if create and extracted:
            for source in extracted:
                source.place = self
                source.save()


class SourceFactory(factory.django.DjangoModelFactory):
    """Provenance row; (provider, provider_id) is globally unique."""

    class Meta:
        model = PlaceSource

    place = factory.SubFactory(PlaceFactory)
    provider = PlaceSource.OVERTURE
    provider_id = factory.Sequence(lambda n: f"poi.test.{n + 1:08d}")
    provider_url = ""
    confidence = 1.00
