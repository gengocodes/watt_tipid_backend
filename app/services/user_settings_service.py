"""
User settings service layer
"""

import logging
from fastapi import HTTPException, status
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
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
from app.database.redis import redis_client
from app.core.security import verify_password, hash_password

logger = logging.getLogger(__name__)

USER_PROFILE_NOT_FOUND = "User profile not found"


class UserSettingsService:
    """Handles query and update actions for user configurations"""

    def __init__(
        self, user_repo: UserRepository, refresh_token_repo: RefreshTokenRepository
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo

    def get_settings(self, user_id: str) -> UserSettingsResponse:
        """
        Retrieve settings nested inside the user profile, falling back to defaults.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        return UserSettingsResponse(
            electricity_rate_php_kwh=user_db.settings.electricity_rate_php_kwh
        )

    def update_settings(
        self, user_id: str, data: UserSettingsPatchRequest
    ) -> UserSettingsResponse:
        """
        Perform a partial update on the user's settings payload.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if data.electricity_rate_php_kwh is not None:
            self.user_repo.update_settings(user_id, data.electricity_rate_php_kwh)
            rate = data.electricity_rate_php_kwh
        else:
            rate = user_db.settings.electricity_rate_php_kwh

        logger.info("Updated user settings")
        return UserSettingsResponse(electricity_rate_php_kwh=rate)

    async def update_profile(
        self, user_id: str, data: UserProfileUpdateRequest
    ) -> UserProfileResponse:
        """
        Update user first name and last name. Trim whitespace before saving.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        first_name = data.first_name.strip()
        last_name = data.last_name.strip()

        self.user_repo.update_profile(user_id, first_name, last_name)
        logger.info("Updated user profile")

        await redis_client.delete(f"user:{user_id}")

        return UserProfileResponse(first_name=first_name, last_name=last_name)

    async def update_email(
        self, user_id: str, data: UserEmailUpdateRequest
    ) -> UserEmailResponse:
        """
        Update user email address. Verifies current password first. Normalizes email.
        Revokes all active/non-expired refresh tokens.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if not verify_password(data.current_password, user_db.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
            )

        new_email = data.new_email.strip().lower()

        # Check uniqueness if changed
        if new_email != user_db.email:
            existing = self.user_repo.get_by_email(new_email)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        self.user_repo.update_email(user_id, new_email)
        logger.info("Updated user email address")

        # Revoke all active refresh tokens
        self.refresh_token_repo.revoke_all_user_tokens(user_id)

        await redis_client.delete(f"user:{user_id}")

        return UserEmailResponse(email=new_email)

    async def update_password(
        self, user_id: str, data: UserPasswordUpdateRequest
    ) -> UserPasswordResponse:
        """
        Update user password. Verifies current password first.
        Revokes all active/non-expired refresh tokens.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if not verify_password(data.current_password, user_db.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
            )

        hashed = hash_password(data.new_password)

        self.user_repo.update_password(user_id, hashed)
        logger.info("Updated user password")

        # Revoke all active refresh tokens
        self.refresh_token_repo.revoke_all_user_tokens(user_id)

        await redis_client.delete(f"user:{user_id}")

        return UserPasswordResponse(message="Password updated successfully")
