import time
import uuid
import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger("viaggio.request")


class CorrelationIdMiddleware(MiddlewareMixin):
    """
    Attaches a unique correlation ID to every incoming request and echoes it in
    the response headers (X-Correlation-ID). This enables end-to-end tracing across
    logs, async tasks, and external services.
    """
    HEADER_NAME = "HTTP_X_CORRELATION_ID"
    RESPONSE_HEADER = "X-Correlation-ID"

    def process_request(self, request):
        correlation_id = request.META.get(self.HEADER_NAME)
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
        request.correlation_id = correlation_id

    def process_response(self, request, response):
        correlation_id = getattr(request, "correlation_id", None)
        if correlation_id:
            response[self.RESPONSE_HEADER] = correlation_id
        return response


class RequestLoggingMiddleware(MiddlewareMixin):
    """
    Logs structured metrics for each HTTP request: method, path, status code,
    latency in milliseconds, and the request's correlation ID.
    """
    def process_request(self, request):
        request._start_time = time.monotonic()

    def process_response(self, request, response):
        if hasattr(request, "_start_time"):
            duration_ms = round((time.monotonic() - request._start_time) * 1000, 2)
        else:
            duration_ms = 0.0

        correlation_id = getattr(request, "correlation_id", "-")
        user_id = getattr(getattr(request, "user", None), "id", "anonymous")

        # Skip logging healthcheck requests excessively in debug mode
        if not (request.path.startswith("/api/v1/health") and response.status_code == 200):
            logger.info(
                f"{request.method} {request.path} {response.status_code} "
                f"({duration_ms}ms) user={user_id} correlation_id={correlation_id}"
            )

        return response
