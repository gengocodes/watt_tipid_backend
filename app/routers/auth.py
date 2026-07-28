"""
Authentication endpoints
"""

from typing import Annotated
from fastapi import (
    APIRouter,
    HTTPException,
    status,
    Response,
    Request,
    Depends,
    BackgroundTasks,
)

from app.schemas.auth import (
    RegisterRequest,
    LoginRequest,
    UserResponse,
    User,
    RegisterVerifyRequest,
    RegisterResendRequest,
)
from app.core.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS,
    COOKIE_SECURE,
    COOKIE_SAMESITE,
)
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_auth_service
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    status_code=status.HTTP_200_OK,
    responses={
        400: {
            "description": "Email already registered or verification already pending"
        },
        429: {"description": "Rate limit exceeded"},
    },
)
async def register(
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user (initiates email verification flow)"""
    email = await auth_service.register(data, background_tasks)
    return {"message": "Verification code sent", "email": email}


@router.post(
    "/register/verify",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Invalid code, expired code, or max attempts exceeded"},
    },
)
async def register_verify(
    data: RegisterVerifyRequest,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Verify registration code and commit user creation"""
    user_id = await auth_service.verify_register(data.email, data.code)
    return {"message": "Registration successful", "user_id": user_id}


@router.post(
    "/register/resend",
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Registration session expired"},
        429: {"description": "Cooldown active"},
    },
)
async def register_resend(
    data: RegisterResendRequest,
    background_tasks: BackgroundTasks,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Resend registration verification code"""
    await auth_service.resend_register_code(data.email, background_tasks)
    return {"message": "Verification code resent"}


@router.post(
    "/login",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid email or password"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def login(
    data: LoginRequest,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Authenticate user, store hashed refresh token, and set HttpOnly cookies"""
    user_res, access_token, raw_refresh_token = auth_service.login(data)

    # Set HttpOnly cookies
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

    return user_res


@router.post(
    "/refresh",
    status_code=status.HTTP_200_OK,
    responses={
        401: {"description": "Invalid or expired refresh token"},
    },
)
async def refresh(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Validate, rotate refresh token, and set new cookies"""
    raw_refresh_token = request.cookies.get("refresh_token")
    if not raw_refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token cookie missing",
        )

    new_access_token, new_raw_refresh_token = auth_service.refresh_token(
        raw_refresh_token
    )

    # Set cookies
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
async def logout(
    request: Request,
    response: Response,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Revoke refresh token and clear authentication cookies"""
    raw_refresh_token = request.cookies.get("refresh_token")
    auth_service.logout(raw_refresh_token)

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
        created_at=current_user.created_at,
    )
