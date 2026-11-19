"""
Tests for the AreaContext precompute service (P3-F8, P3-D7).

Covers: top-cell selection by last-hour check-ins, content derivation
(top places / top categories / weather context / rule-based summary),
idempotent re-runs, the 20-cell cap, the 1 h window, and TTL pruning.
All hermetic — no network, `now` injected.
"""

from datetime import timedelta

import h3
import pytest
from django.contrib.gis.geos import Point
from django.utils import timezone

from apps.activity.factories import UserActivityFactory
from apps.activity.services import (
    AREA_CONTEXT_TTL_HOURS,
    refresh_area_context,
)
from apps.geo.factories import WeatherDataFactory
from apps.geo.models import AreaContext
from apps.places.factories import PlaceFactory

pytestmark = pytest.mark.django_db

NOW = timezone.now()
ANCHOR8 = h3.latlng_to_cell(18.94, 72.835, 8)
# 7 distinct res8 cells (anchor + ring 1).
CELLS = h3.grid_disk(ANCHOR8, 1)


def place_in_cell(cell: str):
    """A place located at the center of ``cell`` (derives matching h3)."""
    lat, lng = h3.cell_to_latlng(cell)
    return PlaceFactory(location=Point(lng, lat, srid=4326))


def check_ins_in_cell(cell: str, n: int, place=None, at=None):
    """Create ``n`` check-ins for ``place`` (or a new one in ``cell``)."""
    for _ in range(n):
        UserActivityFactory(
            place=place or place_in_cell(cell),
            timestamp=at if at is not None else NOW - timedelta(minutes=10),
        )


class TestRefreshAreaContext:
    def test_no_activity_no_rows(self):
        res = refresh_area_context(now=NOW)

        assert res["cells"] == 0
        assert AreaContext.objects.count() == 0

    def test_top_cell_written_with_derived_content(self):
        place = place_in_cell(CELLS[0])
        check_ins_in_cell(CELLS[0], 3, place=place)
        WeatherDataFactory(
            h3_index=h3.cell_to_parent(CELLS[0], 7),
            timestamp=NOW - timedelta(minutes=5),
            temperature_c="31.20",
        )

        res = refresh_area_context(now=NOW)

        assert res["cells"] == 1
        ctx = AreaContext.objects.get()
        assert ctx.h3_index == CELLS[0]
        assert ctx.llm_provider == "rule_based"
        assert ctx.expires_at == NOW + timedelta(hours=AREA_CONTEXT_TTL_HOURS)
        assert ctx.activity_summary == {"check_ins": 3, "window_minutes": 60}
        assert ctx.top_places == [
            {"place_id": str(place.pk), "name": place.name, "score": 3}
        ]
        assert ctx.top_categories == [
            {"category": place.category, "score": 3}
        ]
        assert ctx.weather_context["temperature_c"] == 31.2
        assert "3 check-ins in the last hour" in ctx.llm_summary
        assert place.category in ctx.llm_summary

    def test_activity_outside_last_hour_excluded(self):
        place = place_in_cell(CELLS[0])
        check_ins_in_cell(CELLS[0], 2, place=place, at=NOW - timedelta(hours=2))

        res = refresh_area_context(now=NOW)

        assert res["cells"] == 0
        assert AreaContext.objects.count() == 0

    def test_top_places_ranking_and_category_aggregation(self):
        a = place_in_cell(CELLS[0])
        b = place_in_cell(CELLS[0])
        c = place_in_cell(CELLS[0])
        check_ins_in_cell(CELLS[0], 5, place=a)
        check_ins_in_cell(CELLS[0], 3, place=b)
        check_ins_in_cell(CELLS[0], 1, place=c)

        refresh_area_context(now=NOW)

        ctx = AreaContext.objects.get()
        scores = {p["name"]: p["score"] for p in ctx.top_places}
        assert scores == {a.name: 5, b.name: 3, c.name: 1}
        # Ordered by score, descending.
        assert [p["score"] for p in ctx.top_places] == [5, 3, 1]
        # Same-category places aggregate their scores.
        cat = next(x for x in ctx.top_categories if x["category"] == a.category)
        expected = sum(
            n for p, n in ((a, 5), (b, 3), (c, 1)) if p.category == a.category
        )
        assert cat["score"] == expected

    def test_cell_cap_at_20(self):
        # More cells with activity than the cap: use 22 distinct cells.
        cells = h3.grid_disk(ANCHOR8, 2)  # 19 cells
        cells += h3.grid_ring(ANCHOR8, 3)[:3]  # +3 = 22
        for cell in cells:
            check_ins_in_cell(cell, 1)

        res = refresh_area_context(now=NOW)

        assert res["cells"] == 20
        assert AreaContext.objects.count() == 20

    def test_idempotent_rerun(self):
        place = place_in_cell(CELLS[0])
        check_ins_in_cell(CELLS[0], 2, place=place)

        first = refresh_area_context(now=NOW)
        second = refresh_area_context(now=NOW)

        assert first["cells"] == second["cells"] == 1
        assert AreaContext.objects.count() == 1  # update_or_create, no dupes

    def test_expired_rows_pruned(self):
        AreaContext.objects.create(
            h3_index=CELLS[0],
            time_bucket=NOW - timedelta(days=1),
            expires_at=NOW - timedelta(hours=1),
            llm_provider="rule_based",
        )

        res = refresh_area_context(now=NOW)

        assert res["pruned"] == 1
        assert AreaContext.objects.count() == 0

    def test_weather_absent_yields_empty_context(self):
        place = place_in_cell(CELLS[0])
        check_ins_in_cell(CELLS[0], 1, place=place)

        refresh_area_context(now=NOW)

        ctx = AreaContext.objects.get()
        assert ctx.weather_context == {}
        assert "temperature" not in ctx.llm_summary
