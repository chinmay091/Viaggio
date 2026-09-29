"""
Test settings.

Fast, hermetic configuration for the automated test suite:
- MD5 password hashing (no PBKDF2 latency)
- LocMem cache + in-memory channel layer (no Redis needed)
- Celery runs eager (synchronously)

Database:
- Default (Docker / CI): the real PostGIS engine inherited from base. Django
  creates and automatically drops a throwaway ``test_<NAME>`` database, so
  spatial queries are tested against real PostGIS (plan §9: "SQLite is dead
  for geo"). Requires the PostGIS service from docker-compose (or CI).
- USE_SQLITE=True (Windows, non-spatial work only): in-memory SQLite.
"""
from .base import *

DEBUG = False
SECRET_KEY = "test-secret-key-viaggio-not-for-production"

# Fast hashing for tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory cache for tests (the health endpoint's "redis" check reports
# healthy via LocMem — no Redis service needed)
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# In-memory Channel Layer for tests (no Redis needed)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# Celery tasks executed synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# --- Test database --------------------------------------------------------
if USE_SQLITE:
    # Fast, dependency-free, non-spatial only (accounts/common work on Windows)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }
else:
    # PostGIS test DB: Django prefixes NAME with ``test_`` and drops it when
    # the suite finishes. Override the base name if the environment demands it.
    DATABASES["default"]["NAME"] = os.environ.get("TEST_DB_NAME", "viaggio")
