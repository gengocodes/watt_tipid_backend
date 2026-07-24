"""
User settings service layer
"""

from fastapi import HTTPException, status
from app.database.mongodb import users_collection
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
from app.database.mongodb import refresh_tokens_collection
from app.core.security import verify_password, hash_password
from app.core.config import DEFAULT_RATE

USER_PROFILE_NOT_FOUND = "User profile not found"


class UserSettingsService:
    """Handles query and update actions for user configurations"""

    @staticmethod
    def get_settings(user_id: str) -> UserSettingsResponse:
        """
        Retrieve settings nested inside the user profile, falling back to defaults.
        """
        user_doc = users_collection.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        settings = user_doc.get("settings", {})
        rate = settings.get("electricity_rate_php_kwh", DEFAULT_RATE)

        return UserSettingsResponse(electricity_rate_php_kwh=rate)

    @staticmethod
    def update_settings(
        user_id: str, data: UserSettingsPatchRequest
    ) -> UserSettingsResponse:
        """
        Perform a partial update on the user's settings payload.
        """
        user_doc = users_collection.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        settings = user_doc.get("settings", {})

        if data.electricity_rate_php_kwh is not None:
            settings["electricity_rate_php_kwh"] = data.electricity_rate_php_kwh

        users_collection.update_one({"id": user_id}, {"$set": {"settings": settings}})

        rate = settings.get("electricity_rate_php_kwh", DEFAULT_RATE)
        return UserSettingsResponse(electricity_rate_php_kwh=rate)

    @staticmethod
    def update_profile(
        user_id: str, data: UserProfileUpdateRequest
    ) -> UserProfileResponse:
        """
        Update user first name and last name. Trim whitespace before saving.
        """
        user_doc = users_collection.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        first_name = data.first_name.strip()
        last_name = data.last_name.strip()

        users_collection.update_one(
            {"id": user_id},
            {"$set": {"first_name": first_name, "last_name": last_name}},
        )

        return UserProfileResponse(first_name=first_name, last_name=last_name)

    @staticmethod
    def update_email(user_id: str, data: UserEmailUpdateRequest) -> UserEmailResponse:
        """
        Update user email address. Verifies current password first. Normalizes email.
        Revokes all active/non-expired refresh tokens.
        """
        user_doc = users_collection.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if not verify_password(data.current_password, user_doc["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
            )

        new_email = data.new_email.strip().lower()

        # Check uniqueness if changed
        if new_email != user_doc.get("email"):
            existing = users_collection.find_one({"email": new_email})
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered",
                )

        users_collection.update_one({"id": user_id}, {"$set": {"email": new_email}})

        # Revoke all active refresh tokens
        refresh_tokens_collection.update_many(
            {"user_id": user_id, "revoked": False}, {"$set": {"revoked": True}}
        )

        return UserEmailResponse(email=new_email)

    @staticmethod
    def update_password(
        user_id: str, data: UserPasswordUpdateRequest
    ) -> UserPasswordResponse:
        """
        Update user password. Verifies current password first.
        Revokes all active/non-expired refresh tokens.
        """
        user_doc = users_collection.find_one({"id": user_id})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=USER_PROFILE_NOT_FOUND
            )

        if not verify_password(data.current_password, user_doc["password"]):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password"
            )

        hashed = hash_password(data.new_password)

        users_collection.update_one({"id": user_id}, {"$set": {"password": hashed}})

        # Revoke all active refresh tokens
        refresh_tokens_collection.update_many(
            {"user_id": user_id, "revoked": False}, {"$set": {"revoked": True}}
        )

        return UserPasswordResponse(message="Password updated successfully")
