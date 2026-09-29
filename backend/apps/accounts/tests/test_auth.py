import pytest
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import UserPreference

User = get_user_model()
TEST_PASSWORD = "Viaggio-test-Passw0rd!x"

pytestmark = pytest.mark.django_db


class TestRegistration:
    """POST /api/v1/auth/register/"""

    def test_register_creates_user_and_returns_tokens(self, api_client):
        payload = {
            "email": "new-traveller@example.com",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        }
        response = api_client.post("/api/v1/auth/register/", payload, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["user"]["email"] == "new-traveller@example.com"
        assert set(data["tokens"]) == {"access", "refresh"}

        user = User.objects.get(email="new-traveller@example.com")
        assert user.check_password(TEST_PASSWORD)
        # Registration auto-initializes default preferences
        assert UserPreference.objects.filter(user=user).exists()

    def test_register_rejects_mismatched_passwords(self, api_client):
        payload = {
            "email": "mismatch@example.com",
            "password": TEST_PASSWORD,
            "password_confirm": "does-not-match-123!",
        }
        response = api_client.post("/api/v1/auth/register/", payload, format="json")

        assert response.status_code == 400
        # Standardized error envelope (apps.common.exceptions.custom_exception_handler)
        body = response.json()
        assert body["error"] is True
        assert body["code"] == "INVALID"
        assert "password" in body["details"]
        assert not User.objects.filter(email="mismatch@example.com").exists()

    def test_register_rejects_duplicate_email(self, api_client, user):
        payload = {
            "email": user.email,
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        }
        response = api_client.post("/api/v1/auth/register/", payload, format="json")

        assert response.status_code == 400
        assert User.objects.filter(email=user.email).count() == 1


class TestLogin:
    """POST /api/v1/auth/login/ (SimpleJWT pair + embedded user profile)."""

    def test_login_returns_tokens_and_user(self, api_client, user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": TEST_PASSWORD},
            format="json",
        )

        assert response.status_code == 200
        data = response.json()
        assert "access" in data
        assert "refresh" in data
        assert data["user"]["email"] == user.email

    def test_login_rejects_wrong_password(self, api_client, user):
        response = api_client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "wrong-password-123!"},
            format="json",
        )

        assert response.status_code == 401


class TestRefresh:
    """POST /api/v1/auth/refresh/"""

    def test_refresh_returns_new_access_token(self, api_client, user):
        refresh = str(RefreshToken.for_user(user))
        response = api_client.post(
            "/api/v1/auth/refresh/", {"refresh": refresh}, format="json"
        )

        assert response.status_code == 200
        assert "access" in response.json()


class TestMe:
    """GET /api/v1/auth/me/ (IsAuthenticated)."""

    def test_me_returns_authenticated_profile(self, api_client, user):
        token = str(RefreshToken.for_user(user).access_token)
        response = api_client.get(
            "/api/v1/auth/me/", HTTP_AUTHORIZATION=f"Bearer {token}"
        )

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_me_requires_authentication(self, api_client):
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == 401
