"""
Command to initiate and track place ingestion jobs via Celery (P2-F3).
"""

from django.core.management.base import BaseCommand, CommandError

from apps.ingestion.models import IngestionJob
from apps.ingestion.providers.overture import resolve_bbox
from apps.ingestion.tasks import run_ingestion_job
from apps.places.models import PlaceSource


class Command(BaseCommand):
    """Create and dispatch an IngestionJob to Celery, or run synchronously with --sync."""

    help = (
        "Create an IngestionJob and trigger Celery task run_ingestion_job. "
        "Supports --sync for immediate inline execution."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider",
            type=str,
            default="overture",
            help="Provider identifier (e.g. overture, swiggy, etc.)",
        )
        parser.add_argument("--lat", type=float, help="Center latitude (WGS84)")
        parser.add_argument("--lng", type=float, help="Center longitude (WGS84)")
        parser.add_argument("--radius-km", type=float, help="Search radius in kilometers")
        parser.add_argument(
            "--bbox",
            type=str,
            help="Bounding box as west,south,east,north (WGS84 degrees)",
        )
        parser.add_argument(
            "--city",
            type=str,
            default="",
            help="Fallback city name for features without a locality",
        )
        parser.add_argument(
            "--fixture",
            type=str,
            help="Path to an offline GeoJSON fixture file",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Cap on the number of features ingested",
        )
        parser.add_argument(
            "--job-type",
            type=str,
            default="full_import",
            choices=["full_import", "incremental", "enrichment"],
            help="Type of ingestion job",
        )
        parser.add_argument(
            "--sync",
            action="store_true",
            help="Run task inline synchronously without sending to broker",
        )

    def handle(self, *args, **opts):
        provider_key = opts["provider"].upper()
        valid_providers = [choice[0] for choice in PlaceSource.PROVIDERS]
        if provider_key not in valid_providers:
            raise CommandError(
                f"Invalid provider '{opts['provider']}'. Choices: {', '.join(valid_providers)}"
            )

        region_parts = []
        if opts["fixture"]:
            region_parts.append(f"fixture:{opts['fixture']}")
        else:
            bbox = resolve_bbox(
                bbox_str=opts.get("bbox"),
                lat=opts.get("lat"),
                lng=opts.get("lng"),
                radius_km=opts.get("radius_km"),
            )
            region_parts.append(f"bbox:{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}")

        if opts["city"]:
            region_parts.append(f"city:{opts['city']}")
        if opts["limit"] is not None:
            region_parts.append(f"limit:{opts['limit']}")

        region_str = "|".join(region_parts)

        job = IngestionJob.objects.create(
            provider=provider_key,
            job_type=opts["job_type"],
            region=region_str,
            status="pending",
        )

        self.stdout.write(f"Created IngestionJob {job.pk} ({job.status})")

        if opts["sync"]:
            self.stdout.write(f"Running job {job.pk} synchronously (--sync)...")
            result = run_ingestion_job(str(job.pk))
            job.refresh_from_db()
            self.stdout.write(f"status:   {job.status}")
            self.stdout.write(f"created:  {job.created_records}")
            self.stdout.write(f"updated:  {job.updated_records}")
            self.stdout.write(f"skipped:  {job.skipped_records}")
            self.stdout.write(f"errors:   {job.error_count}")
            self.stdout.write(self.style.SUCCESS(f"IngestionJob {job.pk} finished: {result}"))
        else:
            run_ingestion_job.delay(str(job.pk))
            self.stdout.write(self.style.SUCCESS(f"Dispatched IngestionJob {job.pk} to Celery worker"))
