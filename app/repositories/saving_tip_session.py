"""
Saving Tip Session repository for accessing the saving_tip_sessions collection.
"""

from datetime import datetime, timezone
from typing import Optional
from pymongo.collection import Collection
from app.database.models import SavingTipSessionInDB, AnalysisSessionStatus


class SavingTipSessionRepository:
    """Encapsulates MongoDB queries and updates for household analysis sessions"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[SavingTipSessionInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        return SavingTipSessionInDB(**doc_copy)

    def get_latest_session(self, user_id: str) -> Optional[SavingTipSessionInDB]:
        """Fetch the most recently created session for a user"""
        doc = self.collection.find_one({"user_id": user_id}, sort=[("started_at", -1)])
        return self._to_model(doc)

    def get_latest_completed_session(
        self, user_id: str
    ) -> Optional[SavingTipSessionInDB]:
        """Fetch the most recently COMPLETED session for a user"""
        doc = self.collection.find_one(
            {"user_id": user_id, "status": AnalysisSessionStatus.COMPLETED.value},
            sort=[("completed_at", -1)],
        )
        return self._to_model(doc)

    def get_active_in_progress_session(
        self, user_id: str
    ) -> Optional[SavingTipSessionInDB]:
        """Fetch an active IN_PROGRESS session for a user if one exists"""
        doc = self.collection.find_one(
            {
                "user_id": user_id,
                "status": AnalysisSessionStatus.IN_PROGRESS.value,
            }
        )
        return self._to_model(doc)

    def create_session(self, session: SavingTipSessionInDB) -> None:
        """Insert a new saving tip session record"""
        self.collection.insert_one(session.model_dump())

    def complete_session(
        self,
        session_id: str,
        user_id: str,
        tips_count: int,
        next_allowed_analysis_at: datetime,
    ) -> bool:
        """Mark a session as COMPLETED and record final metadata and cooldown"""
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": session_id, "user_id": user_id},
            {
                "$set": {
                    "status": AnalysisSessionStatus.COMPLETED.value,
                    "tips_count": tips_count,
                    "completed_at": now,
                    "next_allowed_analysis_at": next_allowed_analysis_at,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    def fail_session(self, session_id: str, user_id: str, error_message: str) -> bool:
        """Mark a session as FAILED without consuming cooldown"""
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": session_id, "user_id": user_id},
            {
                "$set": {
                    "status": AnalysisSessionStatus.FAILED.value,
                    "error_message": error_message,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0

    def mark_session_outdated(self, session_id: str, user_id: str, reason: str) -> bool:
        """Mark a session as OUTDATED due to mid-analysis household changes"""
        now = datetime.now(timezone.utc)
        result = self.collection.update_one(
            {"id": session_id, "user_id": user_id},
            {
                "$set": {
                    "status": AnalysisSessionStatus.OUTDATED.value,
                    "error_message": reason,
                    "updated_at": now,
                }
            },
        )
        return result.modified_count > 0
