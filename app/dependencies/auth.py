"""
Authentication dependencies
"""

import json

from bson import ObjectId
from jose import jwt

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from app.core.config import JWT_SECRET, JWT_ALGORITHM
from app.database.mongodb import users_collection
from app.database.redis import redis_client

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)):
    """
    Get current user from token
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("sub is missing")

    except ValueError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}") from e

    cache_key = f"user:{user_id}"

    # 1. Check Redis
    cached_user = await redis_client.get(cache_key)
    if cached_user:
        return json.loads(cached_user)

    # 2. Redis miss -> MongoDB
    user = users_collection.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    user["_id"] = str(user["_id"])

    # 3. Store in Redis for 15 minutes
    await redis_client.set(cache_key, json.dumps(user), ex=900)

    return user
