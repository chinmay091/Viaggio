from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import status
from django.db import connection
from django.core.cache import cache
import time


class HealthCheckView(APIView):
    """
    Service health check endpoint.
    Verifies connectivity to PostgreSQL and Redis.
    Used by orchestrators, Docker health checks, and monitoring systems.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        health = {
            "status": "healthy",
            "version": "2.0.0",
            "timestamp": time.time(),
            "services": {
                "database": "unknown",
                "redis": "unknown",
            },
        }

        # Check Database
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                cursor.fetchone()
            health["services"]["database"] = "healthy"
        except Exception as e:
            health["services"]["database"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"

        # Check Redis Cache
        try:
            test_key = "viaggio_health_check"
            cache.set(test_key, "ok", timeout=5)
            val = cache.get(test_key)
            if val == "ok":
                health["services"]["redis"] = "healthy"
            else:
                health["services"]["redis"] = "unhealthy: cache get mismatch"
                health["status"] = "degraded"
        except Exception as e:
            health["services"]["redis"] = f"unhealthy: {str(e)}"
            health["status"] = "degraded"

        status_code = status.HTTP_200_OK if health["status"] == "healthy" else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(health, status=status_code)
