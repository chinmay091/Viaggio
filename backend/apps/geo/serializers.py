"""
Serializers for the public geo read endpoints (P3-F7, P2 carry-over).

All responses carry explicit ``timezone`` + ``local_time`` (IST) so clients
never have to guess the display timezone (P2 hand-off item 3).
"""

from rest_framework import serializers


class WeatherPointSerializer(serializers.Serializer):
    """One hourly weather point (stored row, Open-Meteo source)."""

    h3_index = serializers.CharField()
    timestamp = serializers.DateTimeField(help_text="UTC event time")
    local_time = serializers.DateTimeField(help_text="IST display time")
    is_forecast = serializers.BooleanField()
    temperature_c = serializers.FloatField()
    humidity_pct = serializers.FloatField()
    precipitation_probability = serializers.FloatField()
    precipitation_mm = serializers.FloatField()
    wind_speed_kmh = serializers.FloatField()
    weather_code = serializers.IntegerField()
    source = serializers.CharField()


class WeatherForecastResponseSerializer(serializers.Serializer):
    """GET /geo/weather/forecast/ response."""

    h3_index = serializers.CharField(help_text="H3 res7 cell the point falls in")
    timezone = serializers.CharField()
    generated_at = serializers.DateTimeField()
    hours = serializers.IntegerField()
    points = WeatherPointSerializer(many=True)


class ReverseGeocodeResponseSerializer(serializers.Serializer):
    """
    GET /geo/reverse-geocode/ response.

    ``city`` is null when no cached city boundary contains the point (200 —
    this is a query result, not a missing resource).
    """

    city = serializers.SerializerMethodField()
    timezone = serializers.CharField()

    def get_city(self, obj):
        city = obj.get("city")
        if city is None:
            return None
        return {"name": city.name, "country": city.country}
