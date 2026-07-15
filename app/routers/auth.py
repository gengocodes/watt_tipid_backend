"""
Authentication endpoints
"""

from fastapi import APIRouter, HTTPException, status

from app.database.mongodb import users_collection
from app.schemas.auth import RegisterRequest, LoginRequest, TokenResponse
from app.core.security import hash_password, verify_password, create_access_token

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

    user = {
        "email": data.email,
        "password_hash": hash_password(data.password),
        "is_active": True,
    }

    result = users_collection.insert_one(user)

    return {"message": "User created", "user_id": str(result.inserted_id)}


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {
            "description": "Invalid email or password",
        },
        429: {
            "description": "Rate limit exceeded",
        },
    },
)
async def login(data: LoginRequest):
    """Authenticate a user and return a JWT access token."""

    user = users_collection.find_one({"email": data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(data.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_access_token(str(user["_id"]))

    return TokenResponse(
        access_token=token,
        token_type="bearer",
    )
