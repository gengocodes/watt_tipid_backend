"""
Authentication dependencies
"""

from jose import jwt

from fastapi import Request, HTTPException, status

from app.core.config import JWT_SECRET, JWT_ALGORITHM
from app.database.mongodb import users_collection
from app.database.redis import redis_client
from app.schemas.auth import User


async def get_current_user(request: Request) -> User:
    """
    Get current user from HttpOnly access_token cookie
    """
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("sub is missing")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
        ) from e

    cache_key = f"user:{user_id}"

    # 1. Check Redis
    cached_user = await redis_client.get(cache_key)
    if cached_user:
        return User.model_validate_json(cached_user)

    # 2. Redis miss -> MongoDB
    user_doc = users_collection.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    user = User(**user_doc)

    # 3. Store in Redis for 15 minutes
    await redis_client.set(cache_key, user.model_dump_json(), ex=900)

    return user
