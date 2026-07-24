"""
Appliance service layer
"""

import uuid
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException, status
from app.database.mongodb import appliances_collection
from app.schemas.energy import ApplianceCreate, ApplianceUpdate, ApplianceResponse
from app.utils.energy_calc import calculate_appliance_kwh

logger = logging.getLogger(__name__)


class ApplianceService:
    """Handles CRUD queries and business logic for appliances"""

    @staticmethod
    def get_appliances(user_id: str) -> List[ApplianceResponse]:
        """
        Retrieve all appliances belonging to the authenticated user.
        Calculates monthly_kwh on the fly.
        """
        cursor = appliances_collection.find({"user_id": user_id})
        result = []
        for doc in cursor:
            kwh = calculate_appliance_kwh(
                doc.get("wattage_watts", 0.0), doc.get("daily_usage_hours", 0.0)
            )
            result.append(
                ApplianceResponse(
                    id=doc["id"],
                    user_id=doc["user_id"],
                    name=doc["name"],
                    category=doc["category"],
                    wattage_watts=doc["wattage_watts"],
                    daily_usage_hours=doc["daily_usage_hours"],
                    icon=doc["icon"],
                    is_active=doc.get("is_active", True),
                    monthly_kwh=kwh,
                    created_at=doc["created_at"],
                    updated_at=doc["updated_at"],
                )
            )
        return result

    @staticmethod
    def create_appliance(user_id: str, data: ApplianceCreate) -> ApplianceResponse:
        """
        Register a new appliance in the database.
        """
        app_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        doc = {
            "id": app_id,
            "user_id": user_id,
            "name": data.name,
            "category": data.category,
            "wattage_watts": data.wattage_watts,
            "daily_usage_hours": data.daily_usage_hours,
            "icon": data.icon,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        appliances_collection.insert_one(doc)
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

    @staticmethod
    def update_appliance(
        user_id: str, appliance_id: str, data: ApplianceUpdate
    ) -> ApplianceResponse:
        """
        Update an appliance configuration after verifying ownership.
        """
        query = {"id": appliance_id, "user_id": user_id}
        existing = appliances_collection.find_one(query)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )

        update_fields: Dict[str, Any] = {}
        if data.name is not None:
            update_fields["name"] = data.name
        if data.category is not None:
            update_fields["category"] = data.category
        if data.wattage_watts is not None:
            update_fields["wattage_watts"] = data.wattage_watts
        if data.daily_usage_hours is not None:
            update_fields["daily_usage_hours"] = data.daily_usage_hours
        if data.icon is not None:
            update_fields["icon"] = data.icon
        if data.is_active is not None:
            update_fields["is_active"] = data.is_active

        update_fields["updated_at"] = datetime.now(timezone.utc)

        appliances_collection.update_one(query, {"$set": update_fields})

        # Fetch updated doc
        doc = appliances_collection.find_one(query)
        # Ensure it exists
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve updated appliance",
            )

        logger.info("Updated appliance '%s' (id: %s)", doc["name"], doc["id"])
        kwh = calculate_appliance_kwh(doc["wattage_watts"], doc["daily_usage_hours"])
        return ApplianceResponse(
            id=doc["id"],
            user_id=doc["user_id"],
            name=doc["name"],
            category=doc["category"],
            wattage_watts=doc["wattage_watts"],
            daily_usage_hours=doc["daily_usage_hours"],
            icon=doc["icon"],
            is_active=doc.get("is_active", True),
            monthly_kwh=kwh,
            created_at=doc["created_at"],
            updated_at=doc["updated_at"],
        )

    @staticmethod
    def delete_appliance(user_id: str, appliance_id: str) -> None:
        """
        Delete an appliance after verifying ownership.
        """
        query = {"id": appliance_id, "user_id": user_id}
        result = appliances_collection.delete_one(query)
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Appliance not found or access denied",
            )
        logger.info("Deleted appliance (id: %s)", appliance_id)
