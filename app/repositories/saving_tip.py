"""
Saving Tip repository for accessing the saving_tips collection.
"""

from datetime import datetime, timezone
from typing import Optional, List
from pymongo.collection import Collection
from app.database.models import SavingTipInDB


class SavingTipRepository:
    """Encapsulates MongoDB queries and updates for user saving tips"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[SavingTipInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        return SavingTipInDB(**doc_copy)

    def get_user_tips(self, user_id: str) -> List[SavingTipInDB]:
        """Fetch all visible (non-deleted) saving tips for a user"""
        cursor = self.collection.find(
            {"user_id": user_id, "status": {"$ne": "deleted"}}
        )
        tips = []
        for doc in cursor:
            tip = self._to_model(doc)
            if tip is not None:
                tips.append(tip)
        return tips

    def get_tips_by_session(self, session_id: str, user_id: str) -> List[SavingTipInDB]:
        """Fetch all saving tips generated for a specific analysis session"""
        cursor = self.collection.find(
            {"session_id": session_id, "user_id": user_id, "status": {"$ne": "deleted"}}
        )
        tips = []
        for doc in cursor:
            tip = self._to_model(doc)
            if tip is not None:
                tips.append(tip)
        return tips

    def get_by_id_and_user(self, tip_id: str, user_id: str) -> Optional[SavingTipInDB]:
        """Fetch a specific saving tip by id and verify ownership"""
        doc = self.collection.find_one({"id": tip_id, "user_id": user_id})
        return self._to_model(doc)

    def create_tips(self, tips: List[SavingTipInDB]) -> None:
        """Bulk insert saving tip records"""
        if not tips:
            return
        documents = [t.model_dump() for t in tips]
        self.collection.insert_many(documents)

    def update_status(self, tip_id: str, user_id: str, status: str) -> bool:
        """Update saving tip status (e.g., active, completed, deleted)"""
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": tip_id, "user_id": user_id},
            {"$set": {"status": status, "updated_at": now}},
        )
        return result.modified_count > 0
