"""
Beat schedule guard for the activity jobs (P3-F9; mirrors the geo lock).

Exactly three activity entries in ``CELERY_BEAT_SCHEDULE`` — no more, no
fewer (the full five-entry lock lives in ``apps/geo/tests/test_beat_schedule.py``).
"""

from django.conf import settings

import pytest

pytestmark = pytest.mark.django_db


def test_activity_beat_entries_locked():
    schedule = settings.CELERY_BEAT_SCHEDULE

    activity_entries = {k: v for k, v in schedule.items() if k.startswith("activity-")}
    assert set(activity_entries) == {
        "activity-aggregate-hourly",
        "activity-baseline-weekly",
        "activity-area-context-hourly",
    }
    assert activity_entries["activity-aggregate-hourly"]["task"] == "activity.aggregate_hourly"
    assert activity_entries["activity-baseline-weekly"]["task"] == "activity.recompute_baselines"
    assert (
        activity_entries["activity-area-context-hourly"]["task"]
        == "activity.refresh_area_context"
    )
