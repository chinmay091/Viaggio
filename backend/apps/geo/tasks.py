"""
Celery tasks for geo domain: weather and air-quality refresh (P2-F4, P2-F5).
"""

from celery import shared_task
from django.conf import settings

from apps.geo.services import fetch_air_quality_for_city, fetch_weather_for_city


def weather_cities() -> list[str]:
    """
    Cities for the periodic refresh jobs, from ``VIAGGIO_WEATHER_CITIES``
    (comma-separated env, default "Mumbai" — P3-F7, P3-D9). Read at call time
    so env changes and test overrides take effect without importing a constant.
    """
    return list(settings.VIAGGIO_WEATHER_CITIES)


@shared_task(name="geo.refresh_weather")
def refresh_weather():
    """
    Periodic task to refresh weather forecast data for active cities.
    Triggered hourly at minute :05 via Celery Beat.
    """
    summaries = {}
    for city in weather_cities():
        result = fetch_weather_for_city(city)
        summaries[city] = result
    return summaries


@shared_task(name="geo.refresh_air_quality")
def refresh_air_quality():
    """
    Periodic task to refresh hourly air-quality data for active cities.
    Triggered every 6 hours via Celery Beat.
    """
    summaries = {}
    for city in weather_cities():
        result = fetch_air_quality_for_city(city)
        summaries[city] = result
    return summaries
