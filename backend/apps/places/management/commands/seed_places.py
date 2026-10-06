"""
Seed canonical places from Overture Maps (P1-F5).

Refactored in P2-F2 to be a thin wrapper delegating to OvertureProvider.
Prefer ``ingest_places`` (records an IngestionJob); kept for Phase-1 compatibility.
"""

from django.core.management.base import BaseCommand

from apps.ingestion.providers.base import Region
from apps.ingestion.providers.overture import OvertureProvider, resolve_bbox


class Command(BaseCommand):
    """Seed canonical places from Overture Maps (live API or offline fixture)."""

    help = (
        "Upsert places from Overture Maps v0 (data=poi). Source is --fixture "
        "(offline GeoJSON) or the live API addressed by --bbox / --lat+--lng+--radius-km. "
        "Prefer ingest_places (records an IngestionJob); kept for Phase-1 compatibility."
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

    def handle(self, *args, **opts):
        provider = OvertureProvider()

        if opts["fixture"]:
            region = Region(
                fixture_path=opts["fixture"],
                city=opts["city"],
                limit=opts["limit"],
            )
            source_desc = f"fixture {opts['fixture']}"
        else:
            bbox = resolve_bbox(
                bbox_str=opts.get("bbox"),
                lat=opts.get("lat"),
                lng=opts.get("lng"),
                radius_km=opts.get("radius_km"),
            )
            region = Region(
                bbox=bbox,
                city=opts["city"],
                limit=opts["limit"],
            )
            source_desc = f"live Overture bbox={tuple(bbox)}"

        features, fetch_errors = provider.fetch(region, log=self.stderr.write)
        self.stdout.write(f"source:   {source_desc}")
        provider.upsert(region, features, log=self.stdout.write)

        if fetch_errors:
            self.stderr.write(f"errors:   {fetch_errors} tile request(s) failed")
        self.stdout.write(self.style.SUCCESS("seed_places done"))
