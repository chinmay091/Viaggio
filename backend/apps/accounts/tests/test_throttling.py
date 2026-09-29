"""
F6 — DRF throttling on auth endpoints.

All three views use ``ScopedRateThrottle`` (DRF 3.17), which reads the view's
``throttle_scope`` at request time and identifies the caller by user PK when
authenticated, else by client IP:

- /auth/login/    scope "login"    5/min   (per client IP — requests are anonymous)
- /auth/register/ scope "register" 3/min   (per client IP — requests are anonymous)
- /auth/refresh/  scope "refresh"  20/min  (per user with a Bearer token, else per IP)

All test-client requests share one client IP, so throttle counters are cleared
before and after each test to keep them isolated from the rest of the suite.
"""
import pytest
from django.core.cache import cache

pytestmark = pytest.mark.django_db

LOGIN_URL = "/api/v1/auth/login/"
REGISTER_URL = "/api/v1/auth/register/"
REFRESH_URL = "/api/v1/auth/refresh/"

# Mirrors settings REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
LOGIN_RATE = 5
REGISTER_RATE = 3
REFRESH_RATE = 20

TEST_PASSWORD = "Viaggio-test-Passw0rd!x"


@pytest.fixture(autouse=True)
def _isolate_throttle_state():
    cache.clear()
    yield
    cache.clear()


def _assert_throttled(response):
    assert response.status_code == 429
    body = response.json()
    # Standardized error envelope (apps.common.exceptions.custom_exception_handler)
    assert body["error"] is True
    assert body["code"] == "THROTTLED"


class TestLoginThrottle:
    def test_login_is_throttled_after_rate_exceeded(self, api_client, user):
        payload = {"email": user.email, "password": "wrong-password-123!"}
        statuses = [
            api_client.post(LOGIN_URL, payload, format="json").status_code
            for _ in range(LOGIN_RATE)
        ]
        assert statuses == [401] * LOGIN_RATE

        _assert_throttled(api_client.post(LOGIN_URL, payload, format="json"))


class TestRegisterThrottle:
    def test_register_is_throttled_after_rate_exceeded(self, api_client):
        for i in range(REGISTER_RATE):
            payload = {
                "email": f"throttle-{i}@example.com",
                "password": TEST_PASSWORD,
                "password_confirm": TEST_PASSWORD,
            }
            assert (
                api_client.post(REGISTER_URL, payload, format="json").status_code
                == 201
            )

        payload = {
            "email": "throttle-overflow@example.com",
            "password": TEST_PASSWORD,
            "password_confirm": TEST_PASSWORD,
        }
        _assert_throttled(api_client.post(REGISTER_URL, payload, format="json"))


class TestRefreshThrottle:
    def test_refresh_is_throttled_after_rate_exceeded(self, api_client):
        # Invalid refresh token -> simplejwt InvalidToken (401), but every
        # request still counts against the throttle.
        payload = {"refresh": "not-a-real-token"}
        statuses = [
            api_client.post(REFRESH_URL, payload, format="json").status_code
            for _ in range(REFRESH_RATE)
        ]
        assert statuses == [401] * REFRESH_RATE

        _assert_throttled(api_client.post(REFRESH_URL, payload, format="json"))
