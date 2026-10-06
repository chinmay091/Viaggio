"""
Celery tasks and region parsing for ingestion jobs (P2-F3).
"""

from dataclasses import asdict
from typing import Optional

from celery import shared_task
from django.db.models import F
from django.utils import timezone

from apps.ingestion.models import IngestionJob
from apps.ingestion.providers import PROVIDERS
from apps.ingestion.providers.base import Region
from apps.ingestion.providers.overture import resolve_bbox


def parse_region(region_str: str) -> Region:
    """
    Parse a region scope string into a Region dataclass.
    Formats supported:
      - 'city:Mumbai'
      - 'bbox:72.80,18.90,72.88,19.02'
      - 'fixture:<path>'
    Also supports composite pipe-separated strings, e.g. 'fixture:<path>|city:Mumbai|limit:100'.
    """
    if not region_str or not isinstance(region_str, str):
        raise ValueError("region must be a non-empty string")

    parts = region_str.split("|")
    bbox: Optional[tuple[float, float, float, float]] = None
    city: str = ""
    fixture_path: Optional[str] = None
    limit: Optional[int] = None

    for part in parts:
        part = part.strip()
        if not part:
            continue
        if ":" not in part:
            raise ValueError(f"Invalid region part '{part}': missing ':'")
        key, val = part.split(":", 1)
        key = key.strip().lower()
        val = val.strip()

        if key == "city":
            city = val
        elif key == "fixture":
            fixture_path = val
        elif key == "bbox":
            bbox = resolve_bbox(bbox_str=val)
        elif key == "limit":
            try:
                limit = int(val)
            except ValueError:
                raise ValueError(f"Invalid limit value '{val}'")
        else:
            raise ValueError(f"Unknown region component '{key}'")

    if not city and not bbox and not fixture_path:
        raise ValueError(f"Region '{region_str}' did not provide city, bbox, or fixture")

    return Region(bbox=bbox, city=city, fixture_path=fixture_path, limit=limit)


@shared_task(name="ingestion.run_job", bind=True, max_retries=2, default_retry_delay=30)
def run_ingestion_job(self, job_id: str):
    """
    Execute an IngestionJob.
    Double-fire guard ensures only one worker transitions status to 'running'.
    Per-tile errors are isolated and recorded without failing the overall task.
    """
    job = IngestionJob.objects.filter(pk=job_id).first()
    if job is None or not job.mark_running():
        return {"status": "skipped"}

    try:
        provider_name = job.provider.upper()
        if provider_name not in PROVIDERS:
            raise ValueError(f"Unsupported provider: {job.provider}")

        provider = PROVIDERS[provider_name]()
        region = parse_region(job.region)

        features, fetch_errors = provider.fetch(region, log=print)
        job.total_records = len(features)
        job.save(update_fields=["total_records"])

        def on_batch(c: int, u: int, s: int):
            IngestionJob.objects.filter(pk=job.pk).update(
                processed_records=F("processed_records") + (c + u + s),
                created_records=F("created_records") + c,
                updated_records=F("updated_records") + u,
                skipped_records=F("skipped_records") + s,
            )

        def on_error(err: dict):
            job.append_error(err)

        result = provider.upsert(
            region,
            features,
            log=print,
            progress_cb=on_batch,
            on_error=on_error,
        )
        result.fetch_errors = fetch_errors

        # P2-F6 hook will be attached here: assign_cities_for_job(job)

        job.refresh_from_db()
        job.status = "completed"
        job.completed_at = timezone.now()
        job.error_count = result.fetch_errors + len(result.errors)
        job.error_log = result.errors[-100:]
        job.save()

        return {"status": "completed", **asdict(result)}
    except Exception as exc:
        job.refresh_from_db()
        job.status = "failed"
        job.append_error({"where": "task", "error": str(exc)})
        job.save()
        raise self.retry(exc=exc)
