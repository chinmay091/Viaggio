import uuid

import pytest

from apps.common.models import OutboxEvent

pytestmark = pytest.mark.django_db


class TestHealthCheck:
    """GET /api/v1/health/ — orchestrator/monitoring endpoint (AllowAny)."""

    def test_returns_200_with_healthy_payload(self, api_client):
        response = api_client.get("/api/v1/health/")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "200" or isinstance(data["version"], str)
        assert data["services"]["database"] == "healthy"
        # Test settings swap Redis for LocMem — the check must still pass.
        assert data["services"]["redis"] == "healthy"

    def test_response_includes_timestamp(self, api_client):
        data = api_client.get("/api/v1/health/").json()
        assert isinstance(data["timestamp"], (int, float))
        assert data["timestamp"] > 0


class TestOutboxEvent:
    """Transactional outbox model used for reliable event publishing."""

    def test_create_defaults_to_pending(self, db):
        event = OutboxEvent.objects.create(
            event_type="reservation.created",
            aggregate_type="reservation",
            aggregate_id=uuid.uuid4(),
            payload={"note": "hello"},
        )

        assert event.published is False
        assert event.published_at is None
        assert event.created_at is not None
        assert event.updated_at is not None

    def test_str_representation(self, db):
        event = OutboxEvent.objects.create(
            event_type="place.ingested",
            aggregate_type="place",
            aggregate_id=uuid.uuid4(),
            payload={},
        )
        assert "place.ingested" in str(event)
        assert "pending" in str(event)
