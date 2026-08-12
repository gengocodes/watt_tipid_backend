"""
User settings service layer
"""

import logging
import json
import secrets
from fastapi import HTTPException, status, BackgroundTasks
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.schemas.user_settings import (
    UserSettingsResponse,
    UserSettingsPatchRequest,
    UserProfileUpdateRequest,
    UserProfileResponse,
    UserEmailUpdateRequest,
    UserPasswordUpdateRequest,
    UserPasswordResponse,
)
from app.database.redis import redis_client
from app.core.security import verify_password, hash_password, hash_token
from app.services.email_service import EmailService
from app.core.config import (
    EMAIL_VERIFICATION_EXPIRE_MINUTES,
    EMAIL_VERIFICATION_RESEND_SECONDS,
    EMAIL_VERIFICATION_MAX_ATTEMPTS,
)

logger = logging.getLogger(__name__)

USER_PROFILE_NOT_FOUND = "User profile not found"


class UserSettingsService:
    """Handles query and update actions for user configurations"""

    def __init__(
        self,
        user_repo: UserRepository,
        refresh_token_repo: RefreshTokenRepository,
        email_service: EmailService,
    ):
        self.user_repo = user_repo
        self.refresh_token_repo = refresh_token_repo
        self.email_service = email_service

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

    async def request_email_change(
        self,
        user_id: str,
        data: UserEmailUpdateRequest,
        background_tasks: BackgroundTasks,
    ) -> str:
        """
        Verify password, normalize and check new email uniqueness,
        and store verification details in Redis.
        """
        user_db = self.user_repo.get_by_id(user_id)
        if not user_db:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if not user_db.password or not verify_password(
            data.current_password, user_db.password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
            )

        new_email = data.new_email.strip().lower()

        # Check uniqueness if changed
        if new_email == user_db.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New email must be different from current email.",
            )

        existing = self.user_repo.get_by_email(new_email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        data_key = f"email_change:data:{user_id}"
        code_key = f"email_change:code:{user_id}"
        cooldown_key = f"email_change:cooldown:{user_id}"

        ttl_seconds = EMAIL_VERIFICATION_EXPIRE_MINUTES * 60
        await redis_client.set(
            data_key, json.dumps({"new_email": new_email}), ex=ttl_seconds
        )

        # Generate, hash, and store verification code
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        code_hash = hash_token(code)
        pending_code = {
            "code_hash": code_hash,
            "attempts": 0,
        }
        await redis_client.set(code_key, json.dumps(pending_code), ex=ttl_seconds)

        # Set resend cooldown (60 seconds)
        await redis_client.set(cooldown_key, "1", ex=EMAIL_VERIFICATION_RESEND_SECONDS)

        # Schedule email delivery
        background_tasks.add_task(
            self.email_service.send_verification_email,
            new_email,
            code,
            "email_change",
        )

        logger.info(
            "Initiated email change verification for user %s to %s", user_id, new_email
        )
        return new_email

    async def verify_email_change(self, user_id: str, code: str) -> str:
        """
        Verify code, retrieve new email, update user email in database, and revoke refresh tokens.
        """
        code_key = f"email_change:code:{user_id}"
        data_key = f"email_change:data:{user_id}"
        cooldown_key = f"email_change:cooldown:{user_id}"

        code_data_json = await redis_client.get(code_key)
        if not code_data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired or not found. Please request again.",
            )

        code_data = json.loads(code_data_json)
        if code_data["attempts"] >= EMAIL_VERIFICATION_MAX_ATTEMPTS:
            await redis_client.delete(code_key, data_key, cooldown_key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many failed attempts. Please request email change again.",
            )

        hashed_input = hash_token(code.strip())
        if code_data["code_hash"] != hashed_input:
            code_data["attempts"] += 1
            remaining = EMAIL_VERIFICATION_MAX_ATTEMPTS - code_data["attempts"]
            if remaining <= 0:
                await redis_client.delete(code_key, data_key, cooldown_key)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Too many failed attempts. Please request email change again.",
                )
            else:
                ttl = await redis_client.ttl(code_key)
                if ttl > 0:
                    await redis_client.set(code_key, json.dumps(code_data), ex=ttl)
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid verification code. {remaining} attempt(s) remaining.",
                )

        data_json = await redis_client.get(data_key)
        if not data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email change session expired. Please request again.",
            )

        new_email = json.loads(data_json)["new_email"]

        existing = self.user_repo.get_by_email(new_email)
        if existing:
            await redis_client.delete(code_key, data_key, cooldown_key)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        self.user_repo.update_email(user_id, new_email)

        self.refresh_token_repo.revoke_all_user_tokens(user_id)
        await redis_client.delete(f"user:{user_id}")
        await redis_client.delete(code_key, data_key, cooldown_key)

        logger.info("Email changed successfully for user %s to %s", user_id, new_email)
        return new_email

    async def resend_email_change_code(
        self, user_id: str, background_tasks: BackgroundTasks
    ) -> None:
        """
        Resend verification code for the pending email change.
        """
        cooldown_key = f"email_change:cooldown:{user_id}"
        cooldown_exists = await redis_client.get(cooldown_key)
        if cooldown_exists:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait before requesting another code.",
            )

        data_key = f"email_change:data:{user_id}"
        data_json = await redis_client.get(data_key)
        if not data_json:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email change session expired. Please request again.",
            )

        new_email = json.loads(data_json)["new_email"]

        # Generate, hash, and store verification code
        code = "".join(secrets.choice("0123456789") for _ in range(6))
        code_hash = hash_token(code)
        pending_code = {
            "code_hash": code_hash,
            "attempts": 0,
        }

        ttl_seconds = EMAIL_VERIFICATION_EXPIRE_MINUTES * 60
        code_key = f"email_change:code:{user_id}"
        await redis_client.set(code_key, json.dumps(pending_code), ex=ttl_seconds)
        await redis_client.set(cooldown_key, "1", ex=EMAIL_VERIFICATION_RESEND_SECONDS)

        # Schedule email delivery
        background_tasks.add_task(
            self.email_service.send_verification_email,
            new_email,
            code,
            "email_change",
        )

        logger.info(
            "Resent email change verification code to %s for user %s",
            new_email,
            user_id,
        )

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

        if not user_db.password or not verify_password(
            data.current_password, user_db.password
        ):
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
