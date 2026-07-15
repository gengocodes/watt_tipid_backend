"""
Rate limit middleware
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi.responses import JSONResponse

from app.database.redis import redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limit middleware for IP addresses
    """

    REQUEST_LIMIT = 100
    WINDOW = 60

    async def dispatch(self, request: Request, call_next):

        ip = request.client.host if request.client else "unknown"

        key = f"rate:ip:{ip}"

        count = await redis_client.incr(key)

        if count == 1:
            await redis_client.expire(key, self.WINDOW)

        if count > self.REQUEST_LIMIT:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
            )

        return await call_next(request)
