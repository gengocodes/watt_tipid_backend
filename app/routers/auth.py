"""
Authentication endpoints
"""

import uuid
from typing import Annotated
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, status, Response, Request, Depends

from app.database.mongodb import users_collection, refresh_tokens_collection
from app.schemas.auth import RegisterRequest, LoginRequest, UserResponse, User
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token,
)
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
)
from app.dependencies.auth import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Email already registered"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def register(data: RegisterRequest):
    """Register a new user"""

    existing_user = users_collection.find_one({"email": data.email})
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    user_id = str(uuid.uuid4())
    user = User(
        id=user_id,
        email=data.email,
        first_name=data.first_name,
        last_name=data.last_name,
        barangay_city=data.barangay_city,
        password=hash_password(data.password),
        is_active=True,
    )

    users_collection.insert_one(user.model_dump())

    return {"message": "User created", "user_id": user_id}


@router.post(
    "/login",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid email or password"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def login(data: LoginRequest, response: Response):
    """Authenticate user, store hashed refresh token, and set HttpOnly cookies"""

    user_doc = users_collection.find_one({"email": data.email})
    if not user_doc or not verify_password(data.password, user_doc["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    user = User(**user_doc)
    user_id = user.id

    # 1. Create tokens
    access_token = create_access_token(user_id)
    raw_refresh_token = generate_refresh_token()
    hashed_refresh_token = hash_token(raw_refresh_token)

    # 2. Save hashed refresh token record
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token_hash": hashed_refresh_token,
        "expires_at": expires_at,
        "revoked": False,
        "created_at": datetime.now(timezone.utc),
    }
    refresh_tokens_collection.insert_one(refresh_token_record)

    # 3. Set HttpOnly cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return UserResponse(
        id=user_id,
        email=user.email,
        first_name=user.first_name,
        last_name=user.last_name,
        barangay_city=user.barangay_city,
    )


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(request: Request, response: Response):
    """Validate, rotate refresh token, and set new cookies"""

    raw_refresh_token = request.cookies.get("refresh_token")
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )

    hashed_refresh_token = hash_token(raw_refresh_token)

    # Find token in DB
    token_record = refresh_tokens_collection.find_one(
        {"token_hash": hashed_refresh_token}
    )

    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    # Convert expires_at to aware datetime if it is naive
    expires_at = token_record["expires_at"]
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Verify not expired and not revoked
    if token_record["revoked"] or expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired or revoked refresh token",
        )

    user_id = token_record["user_id"]

    # 1. Revoke the old refresh token
    refresh_tokens_collection.update_one(
        {"_id": token_record["_id"]}, {"$set": {"revoked": True}}
    )

    # 2. Generate new tokens (Rotation)
    new_access_token = create_access_token(user_id)
    new_raw_refresh_token = generate_refresh_token()
    new_hashed_refresh_token = hash_token(new_raw_refresh_token)

    new_expires_at = datetime.now(timezone.utc) + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )
    new_refresh_token_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "token_hash": new_hashed_refresh_token,
        "expires_at": new_expires_at,
        "revoked": False,
        "created_at": datetime.now(timezone.utc),
    }
    refresh_tokens_collection.insert_one(new_refresh_token_record)

    # 3. Set cookies
    response.set_cookie(
        key="access_token",
        value=new_access_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    response.set_cookie(
        key="refresh_token",
        value=new_raw_refresh_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
    )

    return {"message": "Tokens refreshed"}


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(request: Request, response: Response):
    """Revoke refresh token and clear authentication cookies"""

    raw_refresh_token = request.cookies.get("refresh_token")
    if raw_refresh_token:
        hashed_refresh_token = hash_token(raw_refresh_token)
        refresh_tokens_collection.update_one(
            {"token_hash": hashed_refresh_token}, {"$set": {"revoked": True}}
        )

    # Clear cookies
    response.delete_cookie(
        key="access_token",
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )
    response.delete_cookie(
        key="refresh_token",
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
    )

    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse, status_code=status.HTTP_200_OK)
async def me(current_user: Annotated[User, Depends(get_current_user)]):
    """Return currently logged-in user profile"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        barangay_city=current_user.barangay_city,
    )
