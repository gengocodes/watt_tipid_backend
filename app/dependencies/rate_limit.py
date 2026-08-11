"""
Rate limit dependencies
"""

from fastapi import Depends, HTTPException, Request, status
from app.dependencies.auth import get_current_user
from app.database.redis import redis_client


def user_rate_limit(
    limit: int,
    window: int,
):
    """
    Rate limit dependency for authenticated users
    """

    async def dependency(
        user=Depends(get_current_user),
    ):

        key = f"rate:user:{user['id']}"
        count = await redis_client.incr(key)

        if count == 1:
            await redis_client.expire(key, window)

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )

    return dependency


def ip_rate_limit(
    limit: int,
    window: int,
):
    """
    Rate limit dependency for unauthenticated IP addresses (e.g. contact form submissions).
    Supports X-Forwarded-For headers when running behind proxies/load balancers.
    """

    async def dependency(request: Request):
        client_ip = request.client.host if request.client else "unknown"
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

        key = f"rate:ip:{client_ip}:{request.url.path}"
        count = await redis_client.incr(key)

        if count == 1:
            await redis_client.expire(key, window)

        if count > limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded for contact form. You can only send 1 message per day.",
            )

    return dependency
