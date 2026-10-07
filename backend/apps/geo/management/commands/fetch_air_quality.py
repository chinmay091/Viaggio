"""
Command to fetch hourly air-quality data from Open-Meteo for a city (P2-F5).
"""

from django.core.management.base import BaseCommand
from apps.geo.services import fetch_air_quality_for_city


class Command(BaseCommand):
    """Fetch and store hourly air quality for a city's H3 res7 grid cells."""

    help = "Fetch Open-Meteo air-quality data for a city's H3 res7 grid cells."

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            type=str,
            required=True,
            help="Name of the city to fetch air quality for (e.g. Mumbai)",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=48,
            help="Number of forecast hours to ingest (default: 48)",
        )

    def handle(self, *args, **opts):
        city = opts["city"]
        hours = opts["hours"]

        self.stdout.write(f"Fetching air quality for city '{city}' ({hours} hours ahead)...")
        result = fetch_air_quality_for_city(city=city, hours_ahead=hours)

        self.stdout.write(f"cells:    {result['cells']}")
        self.stdout.write(f"rows:     {result['rows']}")
        self.stdout.write(f"upserted: {result['upserted']}")
        self.stdout.write(f"pruned:   {result['pruned']}")
        self.stdout.write(self.style.SUCCESS("fetch_air_quality done"))
