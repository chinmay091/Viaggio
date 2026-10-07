"""
Overture Maps data provider (P2-F2).

Extracted from seed_places.py with added per-tile retry isolation (3 attempts, backoff 2s/10s),
idempotent bulk upsert, and offline fixture support.
"""

import json
import math
import time
from pathlib import Path
from typing import Callable, Optional

import requests
from django.conf import settings
from django.contrib.gis.geos import Point
from django.core.management.base import CommandError

from apps.ingestion.providers.base import PlaceProvider, Region
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


def _labels(props: dict) -> list[str]:
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


def _map_category(labels: list[str]) -> tuple[str, str]:
    """Canonical category + Overture label to preserve as ``subcategory``."""
    for label in labels:
        if label in CATEGORY_MAP:
            return CATEGORY_MAP[label], label
    return DEFAULT_CATEGORY, (labels[0] if labels else "")


def _first_str(value) -> str:
    """First non-empty string from a plain string or a list of strings."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (list, tuple)):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item.strip()
    return ""


def _point_from_geometry(geometry: Optional[dict]) -> Optional[Point]:
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


def _bbox_from_center(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """(west, south, east, north) around a center for a radius, planar approx."""
    radius_m = radius_km * 1000.0
    dlat = radius_m / M_PER_DEG_LAT
    dlng = radius_m / (M_PER_DEG_LAT * max(math.cos(math.radians(lat)), 0.01))
    return (round(lng - dlng, 6), round(lat - dlat, 6),
            round(lng + dlng, 6), round(lat + dlat, 6))


def _tile_bbox(west: float, south: float, east: float, north: float) -> list[tuple[float, float, float, float]]:
    """Split a bbox into ~0.05° grid cells (each fetch stays ≤1000 features)."""
    cells = []
    eps = 1e-9  # guard against float drift (e.g. 72.80 + 0.05 + 0.05 < 72.90)
    lon = west
    while lon < east - eps:
        cell_east = min(lon + TILE_DEG, east)
        lat = south
        while lat < north - eps:
            cell_north = min(lat + TILE_DEG, north)
            cells.append((round(lon, 6), round(lat, 6),
                          round(cell_east, 6), round(cell_north, 6)))
            lat = cell_north
        lon = cell_east
    return cells


def _load_fixture(path_str: str) -> dict[str, dict]:
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


def resolve_bbox(
    bbox_str: Optional[str] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    radius_km: Optional[float] = None,
) -> tuple[float, float, float, float]:
    """Shared validator / resolver for bbox and center+radius coordinates."""
    if bbox_str:
        try:
            west, south, east, north = (float(part) for part in bbox_str.split(","))
        except ValueError:
            raise CommandError("--bbox must be west,south,east,north")
        if not (west < east and south < north):
            raise CommandError("--bbox must satisfy west<east and south<north")
        if not (-180.0 <= west <= 180.0 and -180.0 <= east <= 180.0
                and -90.0 <= south <= 90.0 and -90.0 <= north <= 90.0):
            raise CommandError("--bbox values out of WGS84 range")
        return (west, south, east, north)
    if lat is not None and lng is not None and radius_km is not None:
        return _bbox_from_center(lat, lng, radius_km)
    raise CommandError("provide --fixture, or --bbox, or --lat+--lng+--radius-km")


class OvertureProvider(PlaceProvider):
    PROVIDER = PlaceSource.OVERTURE
    BATCH_SIZE = BATCH_SIZE

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()

    def fetch(
        self,
        region: Region,
        log: Callable = print,
        on_error: Optional[Callable[[dict], None]] = None,
    ) -> tuple[dict[str, dict], int]:
        """
        Fetch Overture features from fixture or live API.
        Per-tile retry: 3 attempts with 2s / 10s backoff; on error, records failure
        (via ``on_error``) and continues with the remaining tiles.
        """
        if region.fixture_path:
            # Fixture load failures (missing file, bad shape) raise CommandError /
            # ValueError -> structural job failure in the task, not silent empty runs.
            features = _load_fixture(region.fixture_path)
            return features, 0

        if not region.bbox:
            raise CommandError("Region must specify either fixture_path or bbox")

        bboxes = _tile_bbox(*region.bbox)
        log(f"fetching {len(bboxes)} tile(s) from Overture v0 bbox={region.bbox} ...")
        features: dict[str, dict] = {}
        fetch_errors = 0

        retry_backoffs = [2.0, 10.0]

        for (w, s, e, n) in bboxes:
            params = {"bbox": f"{w},{s},{e},{n}", "data": "poi", "limit": PER_TILE_LIMIT}
            success = False

            for attempt in range(3):
                try:
                    resp = self.session.get(OVERTURE_DATA_URL, params=params, timeout=HTTP_TIMEOUT_S)
                    resp.raise_for_status()
                    collection = resp.json()
                    success = True
                    for feature in collection.get("features") or []:
                        if not isinstance(feature, dict):
                            continue
                        fid = feature.get("id")
                        if not fid or fid in features:
                            continue
                        features[fid] = feature
                    break
                except (requests.RequestException, ValueError) as exc:
                    if attempt < 2:
                        backoff = retry_backoffs[attempt]
                        time.sleep(backoff)
                    else:
                        fetch_errors += 1
                        log(f"  ! tile {w},{s},{e},{n} failed after 3 attempts: {exc}")
                        if on_error:
                            on_error(
                                {"where": f"tile {w},{s},{e},{n}", "error": str(exc)}
                            )

        return features, fetch_errors

    def apply(self, place: Place, feature: dict, city_fallback: str) -> None:
        """Map Overture properties onto a Place instance."""
        props = feature.get("properties") or {}
        address = props.get("address") if isinstance(props, dict) else {}
        point = _point_from_geometry(feature.get("geometry"))

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
