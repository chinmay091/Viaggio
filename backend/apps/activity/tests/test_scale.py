"""
Scale hardening for the activity pipeline (P3-F9).

5,000 synthetic UserActivity rows across 20 distinct res8 cells x 12
five-minute buckets, inserted in one bulk pass, then ``aggregate_activity``
must finish in < 30 s in-container with exact per-(cell, bucket) counts.
"""

import time
from datetime import timedelta, timezone as dt_timezone

import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.accounts.factories import UserFactory
from apps.places.factories import PlaceFactory

from apps.activity.models import ActivityAggregate, UserActivity
from apps.activity.services import aggregate_activity


def _utc_iso(value):
    """
    Normalize an aware datetime to a UTC ISO string.

    Test DBs read datetimes back as UTC-aware even though ``TIME_ZONE`` is
    Asia/Kolkata, so keys must compare instants, not offset representations.
    """
    return value.astimezone(dt_timezone.utc).isoformat()

pytestmark = pytest.mark.django_db

N_CELLS = 20
N_BUCKETS = 12
N_ROWS = 5000
N_USERS = 50
BASE_TS = "2026-11-19 06:00:00"  # fixed grid, IST-friendly (01:00 IST)
MUMBAI_LAT, MUMBAI_LNG = 18.94, 72.835
GRID_STEP = 0.02  # ~2.2 km — comfortably outside res8 hex adjacency


@pytest.fixture
def grid_places():
    """20 places in a 10x2 grid, each in its own res8 cell (verified)."""
    places = []
    for row in range(2):
        for col in range(10):
            places.append(
                PlaceFactory(
                    name=f"Scale Place {row}-{col}",
                    location=Point(
                        MUMBAI_LNG + col * GRID_STEP - 5 * GRID_STEP,
                        MUMBAI_LAT + row * GRID_STEP - GRID_STEP,
                        srid=4326,
                    ),
                )
            )
    cells = [p.h3_index_res8 for p in places]
    assert len(set(cells)) == N_CELLS, f"grid collision: only {len(set(cells))} distinct res8 cells"
    return places


@pytest.fixture
def seeded_activity(grid_places):
    """
    Insert N_ROWS rows: row i lands in cell i % 20, bucket i % 12, user i % 50.
    Returns (users, places, expected) where expected maps
    (h3_index_res8, bucket_start_iso) -> {"events": int, "active": int}.
    """
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone as tz
    from datetime import datetime as dt

    base = tz.make_aware(dt(2026, 11, 19, 6, 0, 0))  # 01:00 IST
    # now floors to the 06:55 bucket, so aggregate_activity's 12 buckets are
    # exactly 06:00..06:55 IST — matching the bucket_starts seeded below.
    now = base + timedelta(minutes=55)

    users = UserFactory.create_batch(N_USERS)
    rows = []
    expected = {}
    for i in range(N_ROWS):
        cell_idx = i % N_CELLS
        bucket_idx = i % N_BUCKETS
        bucket_start = base + timedelta(minutes=5 * (N_BUCKETS - 1 - bucket_idx))
        rows.append(
            UserActivity(
                user=users[i % N_USERS],
                place=grid_places[cell_idx],
                h3_index_res8=grid_places[cell_idx].h3_index_res8,
                h3_index_res9=grid_places[cell_idx].h3_index_res9,
                timestamp=bucket_start + timedelta(seconds=i % 299),
            )
        )
        key = (grid_places[cell_idx].h3_index_res8, _utc_iso(bucket_start))
        entry = expected.setdefault(key, {"events": 0, "users": set()})
        entry["events"] += 1
        entry["users"].add(users[i % N_USERS].pk)
    UserActivity.objects.bulk_create(rows, batch_size=1000)
    return users, grid_places, expected, now


class TestAggregationScale:
    def test_5000_rows_20_cells_exact_counts_under_30s(self, seeded_activity):
        _, _, expected, now = seeded_activity

        start = time.monotonic()
        res = aggregate_activity(now=now)
        elapsed = time.monotonic() - start

        assert elapsed < 30, f"aggregation took {elapsed:.1f}s (budget 30s)"
        assert res["cells_written"] == len(expected)

        db = {}
        for agg in ActivityAggregate.objects.all():
            db[(agg.h3_index, _utc_iso(agg.time_bucket))] = agg
        assert len(db) == len(expected)

        for key, exp in expected.items():
            agg = db[key]
            assert agg.event_count == exp["events"], f"event_count mismatch at {key}"
            assert agg.active_count == len(exp["users"]), f"active_count mismatch at {key}"
            assert agg.resolution == 8

    def test_double_run_idempotent_at_scale(self, seeded_activity):
        _, _, expected, now = seeded_activity

        first = aggregate_activity(now=now)
        second = aggregate_activity(now=now)

        assert first["cells_written"] == second["cells_written"] == len(expected)
        assert ActivityAggregate.objects.count() == len(expected)
