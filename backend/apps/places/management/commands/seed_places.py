"""
Seed canonical places from Overture Maps (P1-F5).

Pinned API baseline — Overture Maps API **v0** (per Phase-1 plan D6 scope):

    GET https://api.overturemaps.org/v0/data?bbox=<west>,<south>,<east>,<north>&data=poi&limit=1000

Response: GeoJSON ``FeatureCollection``. Each feature:

    {
      "type": "Feature",
      "id": "poi.1.<stable-hash>",
      "properties": {
        "name": "string",
        "category": ["top-level label"],        # e.g. ["food_and_drink"]
        "subcategory": ["finer label"],         # e.g. ["cafe"]
        "address": {"street": "string", "number": "string"},
        "locality": "string", "region": "string", "country": "ISO code",
        "phone": ["string"], "website": ["string"],
        "opening_hours": {"regular": [...], "exceptional": [...]} | null,
        "description": "string | null"
      },
      "geometry": {"type": "Point", "coordinates": [lng, lat]}
    }

NOTE: the live host could not be reached from this dev environment (no DNS
routed to api.overturemaps.org), so the v0 contract above is pinned as
documented by the Phase-1 plan; the ``--fixture`` mode exercises the exact
same mapping/upsert pipeline offline. Verify the live response on the first
run from a network that can reach the host.

Usage (from backend/):
    python manage.py seed_places --lat 18.9400 --lng 72.8350 --radius-km 12 --city Mumbai
    python manage.py seed_places --bbox 72.80,18.90,72.88,19.02 --city Mumbai
    python manage.py seed_places --fixture apps/places/fixtures/sample_pois.json --city Mumbai
"""

import json
import math
from pathlib import Path

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.places.models import Place, PlaceSource

# --- Pinned Overture v0 baseline -------------------------------------------
OVERTURE_DATA_URL = "https://api.overturemaps.org/v0/data"
PER_TILE_LIMIT = 1000        # max features per tile request (API cap)
HTTP_TIMEOUT_S = 30

# --- Pipeline constants -----------------------------------------------------
TILE_DEG = 0.05              # grid cell size for bbox tiling
BATCH_SIZE = 500             # bulk_create / bulk_update batch size
M_PER_DEG_LAT = 111_320.0    # planar approx: meters per degree latitude

# Overture label -> canonical Place.category (Phase-1 plan F5 table).
# Subcategory labels are checked first (finer), then top-level category.
CATEGORY_MAP = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "bar": "bar",
    "pub": "bar",
    "hotel": "hotel",
    "motel": "hotel",
    "lodging": "hotel",
    "museum": "attraction",
    "gallery": "attraction",
    "monument": "attraction",
    "park": "attraction",
    "zoo": "attraction",
    "shop": "shopping",
    "supermarket": "shopping",
    "mall": "shopping",
    "market": "shopping",
    "bank": "services",
    "pharmacy": "services",
    "clinic": "services",
    "transit_station": "services",
    "fuel": "services",
}
DEFAULT_CATEGORY = "other"

# Place columns refreshed on upsert-hit (enrichment fields such as
# rating/review_count/price_level/metadata/verified are never clobbered).
UPDATE_FIELDS = [
    "name", "normalized_name", "slug", "category", "subcategory",
    "description", "address", "city", "region", "country",
    "phone", "website", "opening_hours", "location",
    "h3_index_res8", "h3_index_res9", "is_active",
]

# --- Feature helpers --------------------------------------------------------


def _labels(props):
    """Overture labels: finer ``subcategory`` first, then top-level ``category``."""
    out = []
    for key in ("subcategory", "category"):
        value = props.get(key) or []
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, (list, tuple)):
            continue
        for item in value:
            label = str(item or "").strip().lower()
            if label and label not in out:
                out.append(label)
    return out


def _map_category(labels):
    """Canonical category + Overture label to preserve as ``subcategory``."""
    for label in labels:
        if label in CATEGORY_MAP:
            return CATEGORY_MAP[label], label
    return DEFAULT_CATEGORY, (labels[0] if labels else "")


def _first_str(value):
    """First non-empty string from a plain string or a list of strings."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _point_from_geometry(geometry):
    """WGS84 geography Point from a GeoJSON Point geometry, else None."""
    if not isinstance(geometry, dict) or geometry.get("type") != "Point":
        return None
    coords = geometry.get("coordinates")
    if not isinstance(coords, (list, tuple)) or len(coords) < 2:
        return None
    try:
        lng, lat = float(coords[0]), float(coords[1])
    except (TypeError, ValueError):
        return None
    if not (-180.0 <= lng <= 180.0 and -90.0 <= lat <= 90.0):
        return None
    return Point(lng, lat, srid=4326)


def _apply_fields(place, props, point, city_fallback):
    """Copy Overture properties onto a Place (create or update)."""
    address = props.get("address")
    place.name = _first_str(props.get("name"))
    place.address = _first_str(address.get("street")) if isinstance(address, dict) else ""
    place.city = _first_str(props.get("locality")) or city_fallback
    place.region = _first_str(props.get("region"))
    place.country = _first_str(props.get("country"))
    place.phone = _first_str(props.get("phone"))
    place.website = _first_str(props.get("website"))
    hours = props.get("opening_hours")
    place.opening_hours = hours if isinstance(hours, dict) else {}
    place.description = _first_str(props.get("description"))
    place.location = point
    place.category, place.subcategory = _map_category(_labels(props))
    place.is_active = True


# --- Geometry / fetch -------------------------------------------------------


def _bbox_from_center(lat, lng, radius_km):
    """(west, south, east, north) around a center for a radius, planar approx."""
    radius_m = radius_km * 1000.0
    dlat = radius_m / M_PER_DEG_LAT
    dlng = radius_m / (M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return (round(lng - dlng, 6), round(lat - dlat, 6),
            round(lng + dlng, 6), round(lat + dlat, 6))


def _tile_bbox(west, south, east, north):
    """Split a bbox into ~0.05° grid cells (each fetch stays ≤1000 features)."""
    cells = []
    lon = west
    while lon < east:
        cell_east = min(lon + TILE_DEG, east)
        lat = south
        while lat < north:
            cell_north = min(lat + TILE_DEG, north)
            cells.append((round(lon, 6), round(lat, 6),
                          round(cell_east, 6), round(cell_north, 6)))
            lat = cell_north
        lon = cell_east
    return cells


def _fetch_features(bboxes):
    """One Overture request per tile; dedupe by feature ``id``.

    Returns (features dict id->feature, error_count).
    """
    session = requests.Session()
    features, errors = {}, 0
    for (w, s, e, n) in bboxes:
        params = {"bbox": f"{w},{s},{e},{n}", "data": "poi", "limit": PER_TILE_LIMIT}
        try:
            resp = session.get(OVERTURE_DATA_URL, params=params, timeout=HTTP_TIMEOUT_S)
            resp.raise_for_status()
            collection = resp.json()
        except (requests.RequestException, ValueError) as exc:
            errors += 1
            print(f"  ! tile {w},{s},{e},{n} failed: {exc}")
            continue
        for feature in collection.get("features") or []:
            if not isinstance(feature, dict):
                continue
            fid = feature.get("id")
            if not fid or fid in features:
                continue
            features[fid] = feature
    return features, errors


def _load_fixture(path_str):
    """Offline mode: read an Overture-style GeoJSON file (FeatureCollection or list)."""
    path = Path(path_str)
    if not path.is_absolute() and not path.exists():
        candidate = settings.BASE_DIR / path_str
        if candidate.exists():
            path = candidate
    if not path.exists():
        raise CommandError(f"fixture not found: {path_str}")
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        features = data.get("features") or []
    elif isinstance(data, list):
        features = data
    else:
        raise CommandError("fixture must be a GeoJSON FeatureCollection or a list of features")
    out = {}
    for feature in features:
        if isinstance(feature, dict) and feature.get("id") and feature["id"] not in out:
            out[feature["id"]] = feature
    return out

# --- Upsert -----------------------------------------------------------------


def _flush_creates(places, sources):
    """bulk_create places (fills pks), then their PlaceSource rows."""
    if not places:
        return
    Place.objects.bulk_create(places, batch_size=BATCH_SIZE)
    PlaceSource.objects.bulk_create(sources, batch_size=BATCH_SIZE)


def _upsert(features, city_fallback, limit, log=print):
    """Upsert Overture features; returns (created, updated, skipped)."""
    now = timezone.now()
    source_map = {
        source.provider_id: source
        for source in PlaceSource.objects.filter(provider=PlaceSource.OVERTURE)
        .select_related("place")
    }

    created = updated = skipped = 0
    created_places, created_sources = [], []
    updated_places, updated_sources = [], []
    local_slugs = set()  # slugs reserved earlier in this run

    def reserve_slug(place):
        # fill_derived_fields checks slug uniqueness against the DB only, so two
        # same-named POIs ingested in one run could both reserve the same slug
        # before either batch is flushed; make the in-run reservation unique too.
        if place.slug in local_slugs:
            base, counter = place.slug, 2
            while f"{base}-{counter}" in local_slugs:
                counter += 1
            place.slug = f"{base}-{counter}"
        local_slugs.add(place.slug)

    def flush():
        nonlocal created_places, created_sources, updated_places, updated_sources
        if created_places:
            _flush_creates(created_places, created_sources)
            created_places, created_sources = [], []
        if updated_places:
            Place.objects.bulk_update(updated_places, UPDATE_FIELDS, batch_size=BATCH_SIZE)
            PlaceSource.objects.bulk_update(
                updated_sources, ["provider_data", "last_synced_at"], batch_size=BATCH_SIZE
            )
            updated_places, updated_sources = [], []

    for fid, feature in features.items():
        if limit is not None and created + updated >= limit:
            break
        props = feature.get("properties") or {}
        if not isinstance(props, dict):
            skipped += 1
            continue
        name = _first_str(props.get("name"))
        point = _point_from_geometry(feature.get("geometry"))
        if not name or point is None:
            skipped += 1  # unnamed POI or unusable geometry
            continue

        source = source_map.get(fid)
        if source is None or source.place is None:
            place = Place(name=name)
            _apply_fields(place, props, point, city_fallback)
            place.fill_derived_fields()  # bulk_create bypasses save()
            reserve_slug(place)
            created_places.append(place)
            created_sources.append(PlaceSource(
                place=place,
                provider=PlaceSource.OVERTURE,
                provider_id=fid,
                provider_data=feature,
                confidence=1.00,
                last_synced_at=now,
            ))
            created += 1
        else:
            place = source.place
            _apply_fields(place, props, point, city_fallback)
            place.fill_derived_fields()  # keep h3 cells in sync on move
            updated_places.append(place)
            source.provider_data = feature
            source.last_synced_at = now
            updated_sources.append(source)
            updated += 1

        if len(created_places) >= BATCH_SIZE or len(updated_places) >= BATCH_SIZE:
            flush()

    flush()
    log(f"fetched:  {len(features)}")
    log(f"created:  {created}")
    log(f"updated:  {updated}")
    log(f"skipped:  {skipped}")
    return created, updated, skipped


# --- Command -----------------------------------------------------------------


class Command(BaseCommand):
    """Seed canonical places from Overture Maps (live API or offline fixture)."""

    help = (
        "Upsert places from Overture Maps v0 (data=poi). Source is --fixture "
        "(offline GeoJSON) or the live API addressed by --bbox / --lat+--lng+--radius-km."
    )

    def add_arguments(self, parser):
        parser.add_argument("--lat", type=float, help="Center latitude (WGS84)")
        parser.add_argument("--lng", type=float, help="Center longitude (WGS84)")
        parser.add_argument("--radius-km", type=float, help="Search radius in kilometers")
        parser.add_argument(
            "--bbox", type=str,
            help="Bounding box as west,south,east,north (WGS84 degrees)",
        )
        parser.add_argument(
            "--city", type=str, default="",
            help="Fallback city name for features without a locality",
        )
        parser.add_argument(
            "--fixture", type=str,
            help="Path to an Overture-style GeoJSON file (offline/hermetic mode)",
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Cap on the number of features ingested",
        )

    def _resolve_bbox(self, opts):
        if opts["bbox"]:
            try:
                west, south, east, north = (
                    float(part) for part in opts["bbox"].split(",")
                )
            except ValueError:
                raise CommandError("--bbox must be west,south,east,north")
            if not (west < east and south < north):
                raise CommandError("--bbox must satisfy west<east and south<north")
            if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0
                    and -90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
                raise CommandError("--bbox values out of WGS84 range")
            return (west, south, east, north)
        if (opts["lat"] is not None and opts["lng"] is not None
                and opts["radius_km"] is not None):
            return _bbox_from_center(opts["lat"], opts["lng"], opts["radius_km"])
        raise CommandError(
            "provide --fixture, or --bbox, or --lat+--lng+--radius-km"
        )

    def handle(self, *args, **opts):
        if opts["fixture"]:
            features = _load_fixture(opts["fixture"])
            source_desc = f"fixture {opts['fixture']}"
            fetch_errors = 0
        else:
            bbox = self._resolve_bbox(opts)
            cells = _tile_bbox(*bbox)
            self.stderr.write(
                f"fetching {len(cells)} tile(s) from Overture v0 "
                f"bbox={tuple(bbox)} ..."
            )
            features, fetch_errors = _fetch_features(cells)
            source_desc = f"live Overture bbox={tuple(bbox)}"

        self.stdout.write(f"source:   {source_desc}")
        _upsert(features, opts["city"], opts["limit"], log=self.stdout.write)
        if fetch_errors:
            self.stderr.write(f"errors:   {fetch_errors} tile request(s) failed")
        self.stdout.write(self.style.SUCCESS("seed_places done"))

