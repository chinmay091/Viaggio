"""
Ingestion models for Viaggio 2.0 (P2-F1).

Tracks background data ingestion jobs from external providers (Overture Maps, etc.)
with batched progress counters, error logging, and double-fire protection.
"""

from django.db import models
from django.utils import timezone

from apps.common.models import AuditModel
from apps.places.models import PlaceSource


class IngestionJob(AuditModel):
    """
    Tracks external data ingestion runs (bulk imports, updates, enrichments).
    Uses AuditModel for UUID PK and created_at/updated_at timestamps.
    """

    JOB_TYPES = (
        ("full_import", "Full Import"),
        ("incremental", "Incremental"),
        ("enrichment", "Enrichment"),
    )

    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    )

    provider = models.CharField(
        max_length=50,
        choices=PlaceSource.PROVIDERS,
        help_text="Data provider identifier (single source of truth from PlaceSource)",
    )
    job_type = models.CharField(
        max_length=30,
        choices=JOB_TYPES,
        default="full_import",
        help_text="Type of ingestion job",
    )
    region = models.CharField(
        max_length=100,
        help_text="Geographic scope: city:Mumbai | bbox:w,s,e,n | fixture:<path>",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
        help_text="Current job status",
    )
    total_records = models.IntegerField(default=0, help_text="Total records fetched/identified")
    processed_records = models.IntegerField(default=0, help_text="Total records processed so far")
    created_records = models.IntegerField(default=0, help_text="New records created")
    updated_records = models.IntegerField(default=0, help_text="Existing records updated")
    skipped_records = models.IntegerField(default=0, help_text="Records skipped (unnamed, invalid, etc.)")
    error_count = models.IntegerField(default=0, help_text="Number of errors encountered")
    started_at = models.DateTimeField(null=True, blank=True, help_text="When execution started")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="When execution finished")
    error_log = models.JSONField(
        default=list,
        blank=True,
        help_text="Last 100 error entries: [{'where': ..., 'error': ...}]",
    )

    class Meta:
        db_table = "ingestion_jobs"
        verbose_name = "Ingestion Job"
        verbose_name_plural = "Ingestion Jobs"
        indexes = [
            models.Index(fields=["status", "created_at"], name="idx_ingjob_status_created"),
            models.Index(fields=["provider", "job_type", "status"], name="idx_ingjob_prov_type_status"),
        ]

    def __str__(self):
        return f"IngestionJob({self.provider}, {self.job_type}, {self.status}, region={self.region})"

    def mark_running(self) -> bool:
        """
        Atomic state transition from 'pending' to 'running'.
        Returns True if this caller successfully transitioned the status, False otherwise
        (used as a double-fire guard by worker tasks).
        """
        rows_updated = IngestionJob.objects.filter(pk=self.pk, status="pending").update(
            status="running", started_at=timezone.now()
        )
        if rows_updated == 1:
            self.status = "running"
            return True
        return False

    def append_error(self, entry: dict):
        """
        Appends an error entry and keeps error_log bounded to the last 100 entries (P2-D5).
        """
        if not isinstance(self.error_log, list):
            self.error_log = []
        self.error_log.append(entry)
        if len(self.error_log) > 100:
            self.error_log = self.error_log[-100:]
