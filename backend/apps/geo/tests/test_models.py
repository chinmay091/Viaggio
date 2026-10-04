"""
Model tests for the geo app (P1-F6).

WeatherData is a schema-only time-series table in Phase 1; AreaContext is a
schema-only per-cell context cache. Tests pin the contract the Phase 3
pipeline will rely on: field types, the hot-path index, and the
(h3_index, time_bucket) uniqueness guarantee.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from django.db import IntegrityError, transaction

from apps.geo.models import AreaContext, WeatherData

pytestmark = pytest.mark.django_db

H3_CELL = "85283470fffffff"  # valid res-7 cell string (shape matters, not exact geometry)
TIME_BUCKET = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


def make_weather(**overrides):
    defaults = dict(
        h3_index=H3_CELL,
        timestamp=TIME_BUCKET,
        temperature_c=Decimal("24.50"),
        precipitation_probability=Decimal("12.00"),
        precipitation_mm=Decimal("0.00"),
        wind_speed_kmh=Decimal("8.25"),
        humidity_pct=Decimal("61.00"),
        weather_code=1,
        is_forecast=False,
    )
    defaults.update(overrides)
    return WeatherData.objects.create(**defaults)


class TestWeatherData:
    """Time-series row contract (dense BigAutoField PK, hot-path index)."""

    def test_create_with_all_fields(self):
        row = make_weather()

        assert row.id is not None
        assert row.h3_index == H3_CELL
        assert float(row.temperature_c) == 24.50
        assert row.is_forecast is False
        assert row.source == "open_meteo"
        assert row.fetched_at is not None

    def test_pk_is_dense_autofield(self):
        id_field = WeatherData._meta.get_field("id")

        assert id_field.primary_key is True
        # Django 5 project default (DEFAULT_AUTO_FIELD) is BigAutoField.
        assert id_field.get_internal_type() == "BigAutoField"

    def test_hot_path_index_present(self):
        names = {idx.name for idx in WeatherData._meta.indexes}

        assert "idx_geoweather_h3_ts" in names

    def test_str_representation(self):
        observation = make_weather()
        forecast = make_weather(
            h3_index="85283471fffffff",
            is_forecast=True,
            timestamp=datetime(2026, 10, 4, 12, 30, tzinfo=timezone.utc),
        )

        assert "observation" in str(observation)
        assert "forecast" in str(forecast)


class TestAreaContext:
    """Per-cell, per-bucket context with a uniqueness constraint."""

    def test_create_with_json_defaults(self):
        ctx = AreaContext.objects.create(
            h3_index=H3_CELL,
            time_bucket=TIME_BUCKET,
            expires_at=TIME_BUCKET.replace(hour=13),
            llm_summary="Quiet afternoon in the area.",
            llm_provider="gpt-4o-mini",
        )

        assert ctx.activity_summary == {}
        assert ctx.top_categories == []
        assert ctx.top_places == []
        assert ctx.weather_context == {}
        assert ctx.created_at is not None
        assert ctx.updated_at is not None

    def test_duplicate_h3_and_bucket_raises_integrity_error(self):
        AreaContext.objects.create(
            h3_index=H3_CELL, time_bucket=TIME_BUCKET, expires_at=TIME_BUCKET.replace(hour=13)
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AreaContext.objects.create(
                    h3_index=H3_CELL,
                    time_bucket=TIME_BUCKET,
                    expires_at=TIME_BUCKET.replace(hour=14),
                )

    def test_same_cell_different_bucket_allowed(self):
        first = AreaContext.objects.create(
            h3_index=H3_CELL, time_bucket=TIME_BUCKET, expires_at=TIME_BUCKET.replace(hour=13)
        )
        second = AreaContext.objects.create(
            h3_index=H3_CELL,
            time_bucket=TIME_BUCKET.replace(hour=13),
            expires_at=TIME_BUCKET.replace(hour=14),
        )

        assert first.pk != second.pk

    def test_uniqueness_constraint_declared(self):
        names = {c.name for c in AreaContext._meta.constraints}

        assert "uniq_geoacontext_h3_bucket" in names
