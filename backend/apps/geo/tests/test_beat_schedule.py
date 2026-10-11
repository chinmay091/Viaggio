"""
Schema guard for the Celery beat schedule (P2-F7): Phase 2 ships exactly the
two geo refresh jobs — no more, no fewer.
"""

from django.conf import settings


def test_beat_schedule_has_exactly_two_geo_entries():
    """Import CELERY_BEAT_SCHEDULE and assert exactly the two expected keys."""
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert set(schedule) == {
        "geo-refresh-weather-hourly",
        "geo-refresh-air-quality-6h",
    }
    assert schedule["geo-refresh-weather-hourly"]["task"] == "geo.refresh_weather"
    assert schedule["geo-refresh-air-quality-6h"]["task"] == "geo.refresh_air_quality"
