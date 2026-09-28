import uuid
from django.db import models


class UUIDModel(models.Model):
    """Abstract base model providing a UUID primary key."""
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier (UUID v4)"
    )

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Abstract base model providing creation and update timestamps."""
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when record was created"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when record was last updated"
    )

    class Meta:
        abstract = True


class AuditModel(UUIDModel, TimeStampedModel):
    """Abstract base model combining UUID primary key and timestamps."""
    class Meta:
        abstract = True


class OutboxEvent(AuditModel):
    """
    Transactional Outbox model.
    Guarantees reliable message publishing by storing domain events in the same
    database transaction as the business state changes.
    """
    event_type = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Name of the domain event, e.g. reservation.created"
    )
    aggregate_type = models.CharField(
        max_length=50,
        db_index=True,
        help_text="Type of the aggregate root, e.g. reservation, place"
    )
    aggregate_id = models.UUIDField(
        db_index=True,
        help_text="ID of the aggregate root entity"
    )
    payload = models.JSONField(
        help_text="Full event payload serialized as JSON"
    )
    published = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this event has been published to Redis Streams"
    )
    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when event was published"
    )

    class Meta:
        db_table = "outbox_events"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["published", "created_at"], name="outbox_pub_created_idx"),
        ]

    def __str__(self):
        return f"{self.event_type} ({self.aggregate_type}:{self.aggregate_id}) - {'published' if self.published else 'pending'}"
