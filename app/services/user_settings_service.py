"""
User settings service layer
"""

from fastapi import HTTPException, status
from app.database.mongodb import users_collection
from app.schemas.user_settings import UserSettingsResponse, UserSettingsPatchRequest
from app.core.config import DEFAULT_RATE


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
                status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found"
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
                status_code=status.HTTP_404_NOT_FOUND, detail="User profile not found"
            )

        settings = user_doc.get("settings", {})

        if data.electricity_rate_php_kwh is not None:
            settings["electricity_rate_php_kwh"] = data.electricity_rate_php_kwh

        users_collection.update_one({"id": user_id}, {"$set": {"settings": settings}})

        rate = settings.get("electricity_rate_php_kwh", DEFAULT_RATE)
        return UserSettingsResponse(electricity_rate_php_kwh=rate)
