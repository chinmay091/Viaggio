"""
Unit and integration tests for Celery ingestion job task and orchestration (P2-F3).
"""

import io
from unittest.mock import MagicMock, patch
import pytest
from django.core.management import call_command
from celery.exceptions import Retry

from apps.ingestion.models import IngestionJob
from apps.ingestion.providers.base import Region
from apps.ingestion.tasks import parse_region, run_ingestion_job
from apps.places.models import PlaceSource

FIXTURE_PATH = "apps/ingestion/fixtures/overture_sample_response.json"


class TestParseRegion:
    def test_parse_region_formats(self):
        """parse_region correctly parses city, bbox, and fixture formats."""
        r1 = parse_region("city:Mumbai")
        assert r1.city == "Mumbai"
        assert r1.bbox is None
        assert r1.fixture_path is None

        r2 = parse_region("bbox:72.80,18.90,72.88,19.02")
        assert r2.bbox == (72.80, 18.90, 72.88, 19.02)
        assert r2.city == ""

        r3 = parse_region("fixture:apps/ingestion/fixtures/test.json")
        assert r3.fixture_path == "apps/ingestion/fixtures/test.json"

        r4 = parse_region("fixture:test.json|city:Mumbai|limit:50")
        assert r4.fixture_path == "test.json"
        assert r4.city == "Mumbai"
        assert r4.limit == 50

    def test_parse_region_invalid_bbox_rejected(self):
        """Invalid bbox coordinates or formats raise ValueError."""
        with pytest.raises(Exception):
            parse_region("bbox:100,50,20,10")  # west > east

        with pytest.raises(Exception):
            parse_region("bbox:not,a,valid,box")

        with pytest.raises(ValueError):
            parse_region("")


@pytest.mark.django_db
class TestJobTaskExecution:
    def test_fixture_job_via_command_completed(self):
        """ingest_places creates a job that runs to completion with matching counters."""
        out = io.StringIO()
        call_command(
            "ingest_places",
            provider="overture",
            fixture=FIXTURE_PATH,
            city="Mumbai",
            sync=True,
            stdout=out,
        )
        job = IngestionJob.objects.latest("created_at")
        assert job.status == "completed"
        assert job.completed_at is not None
        assert job.created_records == 4
        assert job.updated_records == 0
        assert job.skipped_records == 2
        assert job.processed_records == 6
        assert job.processed_records == (
            job.created_records + job.updated_records + job.skipped_records
        )
        assert job.error_count >= 2

    def test_counter_arithmetic(self):
        """Counter invariant: processed == created + updated + skipped."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region=f"fixture:{FIXTURE_PATH}|city:Mumbai",
            status="pending",
        )
        result = run_ingestion_job(str(job.pk))
        assert result["status"] == "completed"

        job.refresh_from_db()
        assert job.processed_records == (
            job.created_records + job.updated_records + job.skipped_records
        )

    def test_double_fire_guard(self):
        """Second concurrent run_ingestion_job call for an active job no-ops cleanly."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region=f"fixture:{FIXTURE_PATH}|city:Mumbai",
            status="pending",
        )
        # First call wins and completes
        res1 = run_ingestion_job(str(job.pk))
        assert res1["status"] == "completed"

        # Second call sees status != 'pending' (won't mark_running), returns skipped
        res2 = run_ingestion_job(str(job.pk))
        assert res2["status"] == "skipped"

    def test_error_isolation_on_tile_failure(self):
        """Tile failure in provider does not crash the task; job finishes completed with error_count > 0."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region="bbox:72.80,18.90,72.85,18.95|city:Mumbai",
            status="pending",
        )

        # Mock provider fetch to simulate 1 failed tile with an error
        with patch("apps.ingestion.providers.overture.OvertureProvider.fetch") as mock_fetch:
            mock_fetch.return_value = (
                {
                    "poi.ok.1": {
                        "id": "poi.ok.1",
                        "geometry": {"type": "Point", "coordinates": [72.82, 18.92]},
                        "properties": {"name": "OK Place"},
                    }
                },
                1,  # 1 fetch error
            )
            result = run_ingestion_job(str(job.pk))

        assert result["status"] == "completed"
        job.refresh_from_db()
        assert job.status == "completed"
        assert job.error_count >= 1
        assert job.created_records == 1

    def test_unexpected_exception_marks_failed_and_retries(self):
        """Unexpected internal exceptions mark the job as failed and trigger task retry."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region=f"fixture:{FIXTURE_PATH}",
            status="pending",
        )

        with patch.object(run_ingestion_job, "retry", side_effect=Retry("Retrying")) as mock_retry:
            with patch("apps.ingestion.providers.overture.OvertureProvider.fetch", side_effect=RuntimeError("DB exploded")):
                with pytest.raises(Retry):
                    run_ingestion_job(str(job.pk))
                assert mock_retry.called

        job.refresh_from_db()
        assert job.status == "failed"
        assert len(job.error_log) > 0
        assert "DB exploded" in job.error_log[-1]["error"]

    def test_error_log_bounded_at_100(self):
        """IngestionJob.error_log preserves at most 100 errors."""
        job = IngestionJob.objects.create(
            provider=PlaceSource.OVERTURE,
            region="city:Mumbai",
            status="pending",
        )
        for i in range(150):
            job.append_error({"where": f"tile_{i}", "error": f"err_{i}"})
        assert len(job.error_log) == 100
        assert job.error_log[0]["where"] == "tile_50"

    def test_sync_flag_output_and_completion(self):
        """--sync outputs job status, counter summary, and finishes job as completed."""
        out = io.StringIO()
        call_command(
            "ingest_places",
            provider="overture",
            fixture=FIXTURE_PATH,
            city="Mumbai",
            sync=True,
            stdout=out,
        )
        output = out.getvalue()
        assert "status:   completed" in output
        assert "created:  " in output
        assert "finished:" in output
