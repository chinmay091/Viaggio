"""
Load/refresh a cached City boundary (P2-F6, P2-D3).

Exactly one source, mutually exclusive:
  --source nominatim   one Nominatim search call (polygon_geojson=1, <= 1 req/s)
  --geojson PATH       offline GeoJSON file (Feature / FeatureCollection / Geometry)
  --bbox W,S,E,N       last-resort rectangle

Idempotent: ``update_or_create(name=...)`` — re-running refreshes the
boundary/centroid. Nominatim failure raises CommandError and writes nothing.
"""

import json
import os
import time
from typing import Optional

import requests
from django.contrib.gis.geos import MultiPolygon, Polygon
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from apps.geo.models import City

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Viaggio/2.0 (dev project; contact: ops@viaggio.local)"


def _boundary_from_geojson(geojson) -> MultiPolygon:
    """Normalize a GeoJSON value (Geometry/Feature/FeatureCollection) to MultiPolygon."""
    gj = geojson
    while isinstance(gj, dict):
        gtype = gj.get("type")
        if gtype == "FeatureCollection":
            features = gj.get("features") or []
            if not features:
                raise CommandError("GeoJSON FeatureCollection has no features")
            gj = features[0]
        elif gtype == "Feature":
            gj = gj.get("geometry")
            if gj is None:
                raise CommandError("GeoJSON Feature has no geometry")
        elif gtype in ("Polygon", "MultiPolygon"):
            break
        else:
            raise CommandError(f"Unsupported GeoJSON type: {gtype!r}")
    if not isinstance(gj, dict) or gj.get("type") not in ("Polygon", "MultiPolygon"):
        raise CommandError("GeoJSON did not yield a Polygon/MultiPolygon geometry")
    if gj["type"] == "Polygon":
        return MultiPolygon(Polygon(gj["coordinates"][0]))
    return MultiPolygon(Polygon(ring) for ring in gj["coordinates"])


def _boundary_from_bbox(bbox_str: str) -> MultiPolygon:
    """Build a rectangle MultiPolygon from 'W,S,E,N'."""
    try:
        w, s, e, n = (float(x) for x in bbox_str.split(","))
    except (ValueError, AttributeError):
        raise CommandError("--bbox must be W,S,E,N (four comma-separated floats)")
    if w >= e or s >= n:
        raise CommandError("--bbox must satisfy west < east and south < north")
    return MultiPolygon(Polygon([(w, s), (e, s), (e, n), (w, n), (w, s)]))


def _fetch_nominatim(name: str, session: Optional[requests.Session] = None) -> dict:
    """
    One (or at most two, with a 1.1 s sleep) Nominatim search call.
    Returns the first hit that carries a ``geojson`` boundary member.
    """
    session = session or requests.Session()
    params = {"q": name, "format": "jsonv2", "polygon_geojson": 1, "limit": 1}
    for attempt in (1, 2):
        try:
            resp = session.get(
                NOMINATIM_URL,
                params=params,
                headers={"User-Agent": USER_AGENT},
                timeout=30,
            )
        except requests.RequestException as exc:
            status, reason = None, f"connection error: {exc}"
        else:
            status, reason = resp.status_code, f"HTTP {resp.status_code}"
        if status == 200:
            break
        if attempt == 1:
            time.sleep(1.1)  # Nominatim usage policy: at most 1 request/second
            continue
        raise CommandError(
            f"Nominatim unreachable ({reason}). "
            "Retry later, or use --geojson / --bbox (P2-D3 offline fallbacks)."
        )
    results = resp.json()
    if not results:
        raise CommandError(
            f"Nominatim returned no results for {name!r}; use --geojson / --bbox."
        )
    hit = results[0]
    if not hit.get("geojson"):
        raise CommandError(
            f"Nominatim returned {name!r} without a geojson boundary. "
            "Use --geojson / --bbox."
        )
    return hit

class Command(BaseCommand):
    help = "Load/refresh a cached City boundary (nominatim | geojson | bbox)."

    def add_arguments(self, parser):
        parser.add_argument("--name", required=True, help="City display name (unique)")
        parser.add_argument("--source", choices=["nominatim", "geojson", "bbox"])
        parser.add_argument("--geojson", help="Path to a GeoJSON file")
        parser.add_argument("--bbox", help="W,S,E,N rectangle")
        parser.add_argument("--country", default="", help="Override country name")

    def handle(self, *args, **opts):
        name = opts["name"].strip()
        if not name:
            raise CommandError("--name must be non-empty")
        if opts["geojson"] and opts["bbox"]:
            raise CommandError("--geojson and --bbox are mutually exclusive")

        src = opts["source"]
        if opts["geojson"]:
            src = "geojson"
        elif opts["bbox"]:
            src = "bbox"
        if not src:
            raise CommandError("Provide --source nominatim, --geojson PATH, or --bbox W,S,E,N.")

        country = opts["country"]
        source_id = ""
        if src == "nominatim":
            hit = _fetch_nominatim(name)
            boundary = _boundary_from_geojson(hit["geojson"])
            country = country or (hit.get("address") or {}).get("country", "")
            source_id = f"{hit.get('osm_type')}/{hit.get('osm_id')}"
        elif src == "geojson":
            path = opts["geojson"]
            if not os.path.exists(path):
                raise CommandError(f"GeoJSON file not found: {path}")
            with open(path, encoding="utf-8") as fh:
                boundary = _boundary_from_geojson(json.load(fh))
            source_id = os.path.basename(path)
        else:
            boundary = _boundary_from_bbox(opts["bbox"])

        City.objects.update_or_create(
            name=name,
            defaults={
                "slug": slugify(name),
                "country": country,
                "boundary": boundary,
                "centroid": boundary.centroid,
                "source": src,
                "source_id": source_id,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"City {name!r} stored (source={src}, source_id={source_id or '-'})"
            )
        )
