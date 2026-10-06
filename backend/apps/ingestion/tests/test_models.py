"""
Tests for IngestionJob model (P2-F1).
"""

import uuid
import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.ingestion.models import IngestionJob
from apps.places.models import PlaceSource


@pytest.mark.django_db
class TestIngestionJobModel:
    def test_default_values(self):
        """Verify model defaults, UUID pk, status, and zeroed counters."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region="city:Mumbai",
        )
        assert isinstance(job.id, uuid.UUID)
        assert job.status == "pending"
        assert job.job_type == "full_import"
        assert job.total_records == 0
        assert job.processed_records == 0
        assert job.created_records == 0
        assert job.updated_records == 0
        assert job.skipped_records == 0
        assert job.error_count == 0
        assert job.started_at is None
        assert job.completed_at is None
        assert job.error_log == []
        assert "OVERTURE" in str(job)

    def test_choices_validation(self):
        """Verify provider, job_type, and status choices are respected."""
        job = IngestionJob(
            provider="INVALID_PROVIDER",
            job_type="invalid_job_type",
            region="city:Mumbai",
            status="invalid_status",
        )
        with pytest.raises(ValidationError):
            job.full_clean()

        # Valid choices pass full_clean
        valid_job = IngestionJob(
            provider=PlaceSource.OVERTURE,
            job_type="incremental",
            region="bbox:72.80,18.90,72.88,19.02",
            status="pending",
        )
        valid_job.full_clean()
        assert valid_job.provider == PlaceSource.OVERTURE

    def test_mark_running_atomic_transition(self):
        """Atomic mark_running flips pending -> running once and records started_at."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region="city:Mumbai",
        )
        assert job.status == "pending"
        assert job.started_at is None

        # First caller wins
        first_call = job.mark_running()
        assert first_call is True
        job.refresh_from_db()
        assert job.status == "running"
        assert job.started_at is not None

        # Second caller loses (double-fire guard)
        second_call = job.mark_running()
        assert second_call is False

    def test_append_error_bounded_at_100(self):
        """append_error preserves last 100 entries only (P2-D5)."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region="city:Mumbai",
        )
        for i in range(150):
            job.append_error({"where": f"tile_{i}", "error": f"err_{i}"})

        assert len(job.error_log) == 100
        assert job.error_log[0]["where"] == "tile_50"
        assert job.error_log[-1]["where"] == "tile_149"
        job.save()

        job.refresh_from_db()
        assert len(job.error_log) == 100
        assert job.error_log[-1]["where"] == "tile_149"
