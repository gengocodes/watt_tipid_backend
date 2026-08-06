"""
Appliance repository for accessing the appliances collection.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pymongo.collection import Collection
from app.database.models import ApplianceInDB
from app.schemas.energy import ApplianceUpdate


class ApplianceRepository:
    """Encapsulates MongoDB queries and updates for user appliances"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[ApplianceInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        return ApplianceInDB(**doc_copy)

    def get_user_appliances(self, user_id: str) -> List[ApplianceInDB]:
        """Fetch all appliances owned by a user"""
        cursor = self.collection.find({"user_id": user_id})
        appliances = []
        for doc in cursor:
            app = self._to_model(doc)
            if app is not None:
                appliances.append(app)
        return appliances

    def get_active_user_appliances(self, user_id: str) -> List[ApplianceInDB]:
        """Fetch all active appliances owned by a user"""
        cursor = self.collection.find({"user_id": user_id, "is_active": True})
        appliances = []
        for doc in cursor:
            app = self._to_model(doc)
            if app is not None:
                appliances.append(app)
        return appliances

    def get_by_id_and_user(
        self, appliance_id: str, user_id: str
    ) -> Optional[ApplianceInDB]:
        """Fetch a specific appliance by id and verify ownership"""
        doc = self.collection.find_one({"id": appliance_id, "user_id": user_id})
        return self._to_model(doc)

    def create_appliance(self, appliance: ApplianceInDB) -> None:
        """Insert a new appliance record"""
        self.collection.insert_one(appliance.model_dump())

    def update_appliance(
        self, appliance_id: str, user_id: str, data: ApplianceUpdate
    ) -> bool:
        """Update appliance fields based on typed update schema"""
        update_fields = {
            k: v
            for k, v in data.model_dump(exclude_unset=True).items()
            if v is not None
        }
        if not update_fields:
            return False

        update_fields["updated_at"] = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": appliance_id, "user_id": user_id},
            {"$set": update_fields},
        )
        return result.modified_count > 0

    def reset_appliance_analysis_status(self, appliance_id: str, user_id: str) -> bool:
        """
        Reset analysis_status to NOT_ANALYZED and analysis_session_id to None for a single appliance
        """
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": appliance_id, "user_id": user_id},
            {
                "$set": {
                    "analysis_status": "NOT_ANALYZED",
                    "analysis_session_id": None,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    def bulk_update_appliance_analysis_statuses(
        self,
        user_id: str,
        evaluated_status_map: dict,
        session_id: str,
    ) -> int:
        """
        Bulk update EVERY active appliance owned by the user after a successful analysis.
        - Appliances in evaluated_status_map are updated to EFFICIENT
          or HAS_RECOMMENDATIONS with analysis_session_id.
        - Any active appliance not in evaluated_status_map is updated
          to NOT_ANALYZED with analysis_session_id = None.
        """
        now = datetime.now(timezone.utc)
        active_appliances = self.get_active_user_appliances(user_id)
        modified_count = 0

        for app in active_appliances:
            if app.id in evaluated_status_map:
                new_status = (
                    evaluated_status_map[app.id].value
                    if hasattr(evaluated_status_map[app.id], "value")
                    else evaluated_status_map[app.id]
                )
                new_session_id = session_id
            else:
                new_status = "NOT_ANALYZED"
                new_session_id = None

            res = self.collection.update_one(
                {"id": app.id, "user_id": user_id},
                {
                    "$set": {
                        "analysis_status": new_status,
                        "analysis_session_id": new_session_id,
                        "updated_at": now,
                    }
                },
            )
            if res.modified_count > 0:
                modified_count += 1

        return modified_count

    def delete_appliance(self, appliance_id: str, user_id: str) -> bool:
        """Delete an appliance by id and user ownership"""
        result = self.collection.delete_one({"id": appliance_id, "user_id": user_id})
        return result.deleted_count > 0
