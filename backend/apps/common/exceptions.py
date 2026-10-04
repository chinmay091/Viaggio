from django.http import Http404
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger("viaggio.exceptions")


def custom_exception_handler(exc, context):
    """
    Standardized DRF exception handler.
    Ensures all error responses conform to a unified schema:
    {
        "error": true,
        "message": "Human readable summary",
        "code": "ERROR_CODE",
        "details": { ... field errors or extra info ... },
        "correlation_id": "uuid"
    }
    """
    response = exception_handler(exc, context)
    request = context.get("request")
    correlation_id = getattr(request, "correlation_id", None) if request else None

    if response is not None:
        error_code = getattr(exc, "default_code", None)
        if error_code is None:
            # Bare django.http.Http404 (raised in initial()/URL handlers) has no
            # default_code; map it to the standard NOT_FOUND envelope code.
            error_code = "not_found" if isinstance(exc, Http404) else "ERROR"
        if isinstance(error_code, str):
            error_code = error_code.upper()

        message = "An error occurred while processing your request."
        details = response.data

        # If details is a dict with a 'detail' key, promote it to message
        if isinstance(details, dict):
            if "detail" in details:
                message = str(details.pop("detail"))
        elif isinstance(details, list):
            message = "; ".join(str(d) for d in details)
            details = {"errors": details}

        custom_data = {
            "error": True,
            "message": message,
            "code": error_code,
            "details": details if details else {},
            "correlation_id": correlation_id,
        }
        response.data = custom_data
    else:
        # Unhandled server exception
        logger.exception(f"Unhandled exception during request: {exc}", exc_info=exc)
        custom_data = {
            "error": True,
            "message": "An unexpected internal server error occurred.",
            "code": "INTERNAL_SERVER_ERROR",
            "details": {},
            "correlation_id": correlation_id,
        }
        response = Response(custom_data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return response
