"""
Command to fetch weather forecast data from Open-Meteo for a city (P2-F4).
"""

from django.core.management.base import BaseCommand, CommandError
from apps.geo.services import fetch_weather_for_city


class Command(BaseCommand):
    """Fetch and store weather forecast for all H3 res7 cells covering a city."""

    help = "Fetch Open-Meteo forecast data for a city's H3 res7 grid cells."

    def add_arguments(self, parser):
        parser.add_argument(
            "--city",
            type=str,
            required=True,
            help="Name of the city to fetch weather for (e.g. Mumbai)",
        )
        parser.add_argument(
            "--hours",
            type=int,
            default=48,
            help="Number of forecast hours to ingest (default: 48)",
        )
        parser.add_argument(
            "--forecast-days",
            type=int,
            default=None,
            help="Optional override for forecast_days parameter",
        )

    def handle(self, *args, **opts):
        city = opts["city"]
        hours = opts["hours"]
        if opts["forecast_days"] is not None:
            hours = opts["forecast_days"] * 24

        self.stdout.write(f"Fetching weather for city '{city}' ({hours} hours ahead)...")
        result = fetch_weather_for_city(city=city, hours_ahead=hours)

        self.stdout.write(f"cells:    {result['cells']}")
        self.stdout.write(f"rows:     {result['rows']}")
        self.stdout.write(f"upserted: {result['upserted']}")
        self.stdout.write(f"pruned:   {result['pruned']}")
        self.stdout.write(self.style.SUCCESS("fetch_weather done"))
