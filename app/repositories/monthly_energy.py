"""
Monthly energy repository for accessing the monthly_energy collection.
"""

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
