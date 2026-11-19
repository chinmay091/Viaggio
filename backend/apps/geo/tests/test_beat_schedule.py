"""
Schema guard for the Celery beat schedule (P2-F7, extended in P3-F4/F8):
exactly the two geo refresh jobs + the three activity jobs — no more, no fewer.
"""

from django.conf import settings


def test_beat_schedule_has_exactly_expected_entries():
    """Import CELERY_BEAT_SCHEDULE and assert exactly the expected keys + tasks."""
    schedule = settings.CELERY_BEAT_SCHEDULE
    assert set(schedule) == {
        "geo-refresh-weather-hourly",
        "geo-refresh-air-quality-6h",
        "activity-aggregate-hourly",
        "activity-baseline-weekly",
        "activity-area-context-hourly",
    }
    assert schedule["geo-refresh-weather-hourly"]["task"] == "geo.refresh_weather"
    assert schedule["geo-refresh-air-quality-6h"]["task"] == "geo.refresh_air_quality"
    assert schedule["activity-aggregate-hourly"]["task"] == "activity.aggregate_hourly"
    assert schedule["activity-baseline-weekly"]["task"] == "activity.recompute_baselines"
    assert schedule["activity-area-context-hourly"]["task"] == "activity.refresh_area_context"
