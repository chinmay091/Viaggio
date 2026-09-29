"""Root pytest fixtures shared by all app test suites."""
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    """DRF API test client (CSRF not enforced, like Django's test client)."""
    return APIClient()


@pytest.fixture
def user(db):
    """A regular active user, built via factory-boy."""
    from apps.accounts.factories import UserFactory

    return UserFactory()
