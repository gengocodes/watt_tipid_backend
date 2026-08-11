"""
Monthly energy repository for accessing the monthly_energy collection.
"""

from datetime import datetime, timezone
from uuid import uuid4
from typing import Optional, List
from pymongo.collection import Collection
from app.database.models import MonthlyEnergyInDB


class MonthlyEnergyRepository:
    """Encapsulates MongoDB queries for historical monthly energy trends"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[MonthlyEnergyInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        return MonthlyEnergyInDB(**doc_copy)

    def get_user_trends(self, user_id: str) -> List[MonthlyEnergyInDB]:
        """Fetch historical monthly energy trends for a user, sorted by month"""
        cursor = self.collection.find({"user_id": user_id}).sort("month", 1)
        trends = []
        for doc in cursor:
            t = self._to_model(doc)
            if t is not None:
                trends.append(t)
        return trends

    def upsert_trend(
        self,
        user_id: str,
        month: str,
        kwh: float,
        cost_php: float,
        rate_php_kwh: Optional[float] = None,
    ) -> MonthlyEnergyInDB:
        """Create or update a monthly energy record for a user"""
        now = datetime.now(timezone.utc)
        existing = self.collection.find_one({"user_id": user_id, "month": month})
        record_id = (
            existing.get("id")
            if existing and isinstance(existing.get("id"), str)
            else str(uuid4())
        )
        created_at_val = existing.get("created_at") if existing else now
        if isinstance(created_at_val, datetime):
            created_at_dt = created_at_val
        else:
            created_at_dt = now

        doc = {
            "id": record_id,
            "user_id": user_id,
            "month": month,
            "kwh": float(kwh),
            "cost_php": float(cost_php),
            "rate_php_kwh": float(rate_php_kwh) if rate_php_kwh is not None else None,
            "created_at": created_at_dt,
        }

        self.collection.update_one(
            {"user_id": user_id, "month": month},
            {"$set": doc},
            upsert=True,
        )

        return MonthlyEnergyInDB(
            id=record_id,
            user_id=user_id,
            month=month,
            kwh=float(kwh),
            cost_php=float(cost_php),
            rate_php_kwh=float(rate_php_kwh) if rate_php_kwh is not None else None,
            created_at=created_at_dt,
        )

    def delete_trend(self, user_id: str, month: str) -> bool:
        """Delete a monthly energy record for a user"""
        result = self.collection.delete_one({"user_id": user_id, "month": month})
        return result.deleted_count > 0
