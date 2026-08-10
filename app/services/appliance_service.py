"""
Appliance service layer handling CRUD operations for user appliances.
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from app.repositories.appliance import ApplianceRepository
from app.repositories.saving_tip import SavingTipRepository
from app.database.models import ApplianceInDB, ApplianceAnalysisStatus
from app.schemas.energy import ApplianceCreate, ApplianceUpdate, ApplianceResponse
from app.utils.energy_calc import calculate_appliance_kwh
from app.utils.household_snapshot import serialize_appliance_snapshot

logger = logging.getLogger(__name__)


class ApplianceService:
    """Handles CRUD queries and business logic for appliances"""

    def __init__(
        self,
        appliance_repo: ApplianceRepository,
        saving_tip_repo: Optional[SavingTipRepository] = None,
    ):
        self.appliance_repo = appliance_repo
        self.saving_tip_repo = saving_tip_repo

    def get_appliances(self, user_id: str) -> List[ApplianceResponse]:
        """
        Retrieve all appliances belonging to the authenticated user.
        Calculates monthly_kwh on the fly.
        """
        appliances = self.appliance_repo.get_user_appliances(user_id)
        result = []
        for app in appliances:
            kwh = calculate_appliance_kwh(app.wattage_watts, app.daily_usage_hours)
            result.append(ApplianceResponse(**app.model_dump(), monthly_kwh=kwh))
        return result

    def create_appliance(
        self,
        user_id: str,
        data: ApplianceCreate,
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
            analysis_status=ApplianceAnalysisStatus.NOT_ANALYZED,
            analysis_session_id=None,
            created_at=now,
            updated_at=now,
        )

        self.appliance_repo.create_appliance(app)
        logger.info("Created appliance '%s' (id: %s)", data.name, app_id)

        kwh = calculate_appliance_kwh(data.wattage_watts, data.daily_usage_hours)
        return ApplianceResponse(**app.model_dump(), monthly_kwh=kwh)

    def update_appliance(
        self,
        user_id: str,
        appliance_id: str,
        data: ApplianceUpdate,
    ) -> ApplianceResponse:
        """
        Update an appliance configuration.
        If any field included in the household snapshot changes, resets analysis_status
        to NOT_ANALYZED and analysis_session_id to None for this appliance.
        """
        existing = self.appliance_repo.get_by_id_and_user(appliance_id, user_id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )

        self.appliance_repo.update_appliance(appliance_id, user_id, data)

        updated = self.appliance_repo.get_by_id_and_user(appliance_id, user_id)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated appliance",
            )

        # Check if snapshot-relevant fields changed using reusable serializer
        existing_snapshot = serialize_appliance_snapshot(existing)
        updated_snapshot = serialize_appliance_snapshot(updated)

        if existing_snapshot != updated_snapshot:
            self.appliance_repo.reset_appliance_analysis_status(appliance_id, user_id)
            updated = (
                self.appliance_repo.get_by_id_and_user(appliance_id, user_id) or updated
            )

        logger.info("Updated appliance '%s' (id: %s)", updated.name, updated.id)

        kwh = calculate_appliance_kwh(updated.wattage_watts, updated.daily_usage_hours)
        return ApplianceResponse(**updated.model_dump(), monthly_kwh=kwh)

    def delete_appliance(self, user_id: str, appliance_id: str) -> None:
        """
        Soft delete an appliance (is_active=False) and mark linked tips as STALE.
        """
        success = self.appliance_repo.delete_appliance(appliance_id, user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )
        if self.saving_tip_repo:
            self.saving_tip_repo.mark_tips_stale_by_appliance_id(appliance_id, user_id)
        logger.info("Soft-deleted appliance (id: %s)", appliance_id)
