"""
Rate limit dependencies
"""

from fastapi import Depends, HTTPException
from app.dependencies.auth import get_current_user
from app.database.redis import redis_client

# Sample usage:
# async def chat(
#     user=Depends(get_current_user),
#     _=Depends(
#         user_rate_limit(
#             limit=20,
#             window=60
#         )
#     )
# ):


def user_rate_limit(
    limit: int,
    window: int,
):
    """
    Rate limit dependency for users
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
                status_code=429,
                detail="Rate limit exceeded",
            )

    return dependency
