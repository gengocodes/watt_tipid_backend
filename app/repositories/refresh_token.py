"""
Refresh token repository for accessing the refresh_tokens collection.
"""

from typing import Optional
from pymongo.collection import Collection
from app.database.models import RefreshTokenInDB


class RefreshTokenRepository:
    """Encapsulates MongoDB queries and updates for auth refresh tokens"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[RefreshTokenInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        return RefreshTokenInDB(**doc_copy)

    def get_by_hash(self, token_hash: str) -> Optional[RefreshTokenInDB]:
        """Fetch token record by SHA-256 hash"""
        doc = self.collection.find_one({"token_hash": token_hash})
        return self._to_model(doc)

    def create_token(self, token: RefreshTokenInDB) -> None:
        """Insert a new refresh token document"""
        self.collection.insert_one(token.model_dump())

    def revoke_token_by_id(self, token_id: str) -> bool:
        """Revoke a token record by id"""
        result = self.collection.update_one(
            {"id": token_id},
            {"$set": {"revoked": True}},
        )
        return result.modified_count > 0

    def revoke_token_by_hash(self, token_hash: str) -> bool:
        """Revoke a token record by hash"""
        result = self.collection.update_one(
            {"token_hash": token_hash},
            {"$set": {"revoked": True}},
        )
        return result.modified_count > 0

    def revoke_all_user_tokens(self, user_id: str) -> int:
        """Revoke all active refresh tokens belonging to a user ID"""
        result = self.collection.update_many(
            {"user_id": user_id, "revoked": False},
            {"$set": {"revoked": True}},
        )
        return result.modified_count
