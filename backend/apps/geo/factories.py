"""
Factory-boy factories for the geo app (P3-F5).

Provides ``WeatherDataFactory`` for hermetic testing of weather context.
"""

from decimal import Decimal
import factory
from django.utils import timezone

from apps.geo.models import WeatherData


class WeatherDataFactory(factory.django.DjangoModelFactory):
    """Synthetic WeatherData row for testing weather context."""

    class Meta:
        model = WeatherData

    h3_index = "87608b030ffffff"  # Res7 weather cell (Mumbai)
    timestamp = factory.LazyFunction(timezone.now)
    temperature_c = Decimal("31.20")
    precipitation_probability = Decimal("10.00")
    precipitation_mm = Decimal("0.00")
    wind_speed_kmh = Decimal("12.50")
    humidity_pct = Decimal("65.00")
    weather_code = 2  # Partly cloudy
    is_forecast = False
    source = "open_meteo"
