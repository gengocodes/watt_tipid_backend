"""
User settings and preferences endpoints
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_user_settings_service
from app.schemas.auth import User
from app.schemas.user_settings import (
    UserSettingsResponse,
    UserSettingsPatchRequest,
    UserProfileUpdateRequest,
    UserProfileResponse,
    UserEmailUpdateRequest,
    UserEmailResponse,
    UserPasswordUpdateRequest,
    UserPasswordResponse,
)
from app.services.user_settings_service import UserSettingsService

router = APIRouter(prefix="/users", tags=["User Settings"])


@router.get(
    "/settings", response_model=UserSettingsResponse, status_code=status.HTTP_200_OK
)
async def get_settings(
    current_user: Annotated[User, Depends(get_current_user)],
    settings_service: UserSettingsService = Depends(get_user_settings_service),
):
    """Retrieve settings and configuration preferences for the authenticated user"""
    return settings_service.get_settings(current_user.id)


@router.patch(
    "/settings", response_model=UserSettingsResponse, status_code=status.HTTP_200_OK
)
async def update_settings(
    data: UserSettingsPatchRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings_service: UserSettingsService = Depends(get_user_settings_service),
):
    """Partially update user settings preferences"""
    return settings_service.update_settings(current_user.id, data)


@router.patch(
    "/profile", response_model=UserProfileResponse, status_code=status.HTTP_200_OK
)
async def update_profile(
    data: UserProfileUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings_service: UserSettingsService = Depends(get_user_settings_service),
):
    """Update user first name and last name (no password verify)"""
    return await settings_service.update_profile(current_user.id, data)


@router.patch(
    "/email", response_model=UserEmailResponse, status_code=status.HTTP_200_OK
)
async def update_email(
    data: UserEmailUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings_service: UserSettingsService = Depends(get_user_settings_service),
):
    """Update user email address. Requires current password verification."""
    return await settings_service.update_email(current_user.id, data)


@router.patch(
    "/password", response_model=UserPasswordResponse, status_code=status.HTTP_200_OK
)
async def update_password(
    data: UserPasswordUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    settings_service: UserSettingsService = Depends(get_user_settings_service),
):
    """Update user password. Requires current password verification."""
    return await settings_service.update_password(current_user.id, data)
