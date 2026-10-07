"""
Celery tasks for geo domain: weather and air-quality refresh (P2-F4, P2-F5).
"""

from celery import shared_task
from apps.geo.services import fetch_air_quality_for_city, fetch_weather_for_city

WEATHER_CITIES = ["Mumbai"]


@shared_task(name="geo.refresh_weather")
def refresh_weather():
    """
    Periodic task to refresh weather forecast data for active cities.
    Triggered hourly at minute :05 via Celery Beat.
    """
    summaries = {}
    for city in WEATHER_CITIES:
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
    for city in WEATHER_CITIES:
        result = fetch_air_quality_for_city(city)
        summaries[city] = result
    return summaries
