"""
Request logging context middleware
"""

import logging
import time
import uuid
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.logging_config import user_id_ctx, request_id_ctx


class LoggingContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that initializes and resets request-scoped logging context (request_id, user_id)
    using try/finally to prevent context leaks across concurrent requests.
    """

    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())

        # Bind context variables and save their reset tokens
        token_rid = request_id_ctx.set(request_id)
        token_uid = user_id_ctx.set("N/A")

        logger = logging.getLogger(__name__)
        logger.debug("Request started: %s %s", request.method, request.url.path)

        start_time = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            logger.debug(
                "Request completed: %s %s - status %s - %.2f ms",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
        finally:
            request_id_ctx.reset(token_rid)
            user_id_ctx.reset(token_uid)
