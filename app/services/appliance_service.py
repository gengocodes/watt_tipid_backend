"""
Appliance service layer
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import List
from fastapi import HTTPException, status
from app.repositories.appliance import ApplianceRepository
from app.database.models import ApplianceInDB
from app.schemas.energy import ApplianceCreate, ApplianceUpdate, ApplianceResponse
from app.utils.energy_calc import calculate_appliance_kwh

logger = logging.getLogger(__name__)


class ApplianceService:
    """Handles CRUD queries and business logic for appliances"""

    def __init__(self, appliance_repo: ApplianceRepository):
        self.appliance_repo = appliance_repo

    def get_appliances(self, user_id: str) -> List[ApplianceResponse]:
        """
        Retrieve all appliances belonging to the authenticated user.
        Calculates monthly_kwh on the fly.
        """
        appliances = self.appliance_repo.get_user_appliances(user_id)
        result = []
        for app in appliances:
            kwh = calculate_appliance_kwh(app.wattage_watts, app.daily_usage_hours)
            result.append(
                ApplianceResponse(
                    id=app.id,
                    user_id=app.user_id,
                    name=app.name,
                    category=app.category,
                    wattage_watts=app.wattage_watts,
                    daily_usage_hours=app.daily_usage_hours,
                    icon=app.icon,
                    is_active=app.is_active,
                    monthly_kwh=kwh,
                    created_at=app.created_at,
                    updated_at=app.updated_at,
                )
            )
        return result

    def create_appliance(
        self, user_id: str, data: ApplianceCreate
    ) -> ApplianceResponse:
        """
        Register a new appliance in the database.
        """
        app_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        app = ApplianceInDB(
            id=app_id,
            user_id=user_id,
            name=data.name,
            category=data.category,
            wattage_watts=data.wattage_watts,
            daily_usage_hours=data.daily_usage_hours,
            icon=data.icon,
            is_active=True,
            created_at=now,
            updated_at=now,
        )

        self.appliance_repo.create_appliance(app)
        logger.info("Created appliance '%s' (id: %s)", data.name, app_id)

        kwh = calculate_appliance_kwh(data.wattage_watts, data.daily_usage_hours)
        return ApplianceResponse(
            id=app_id,
            user_id=user_id,
            name=data.name,
            category=data.category,
            wattage_watts=data.wattage_watts,
            daily_usage_hours=data.daily_usage_hours,
            icon=data.icon,
            is_active=True,
            monthly_kwh=kwh,
            created_at=now,
            updated_at=now,
        )

    def update_appliance(
        self, user_id: str, appliance_id: str, data: ApplianceUpdate
    ) -> ApplianceResponse:
        """
        Update an appliance configuration after verifying ownership.
        """
        existing = self.appliance_repo.get_by_id_and_user(appliance_id, user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )

        self.appliance_repo.update_appliance(appliance_id, user_id, data)

        # Fetch updated doc
        updated = self.appliance_repo.get_by_id_and_user(appliance_id, user_id)
        # Ensure it exists
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated appliance",
            )

        logger.info("Updated appliance '%s' (id: %s)", updated.name, updated.id)
        kwh = calculate_appliance_kwh(updated.wattage_watts, updated.daily_usage_hours)
        return ApplianceResponse(
            id=updated.id,
            user_id=updated.user_id,
            name=updated.name,
            category=updated.category,
            wattage_watts=updated.wattage_watts,
            daily_usage_hours=updated.daily_usage_hours,
            icon=updated.icon,
            is_active=updated.is_active,
            monthly_kwh=kwh,
            created_at=updated.created_at,
            updated_at=updated.updated_at,
        )

    def delete_appliance(self, user_id: str, appliance_id: str) -> None:
        """
        Delete an appliance after verifying ownership.
        """
        success = self.appliance_repo.delete_appliance(appliance_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )
        logger.info("Deleted appliance (id: %s)", appliance_id)
