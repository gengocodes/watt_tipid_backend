"""
User repository for accessing the users collection.
"""

from typing import Optional
from pymongo.collection import Collection
from app.database.models import UserInDB


class UserRepository:
    """Encapsulates MongoDB queries and updates for user profiles"""

    def __init__(self, collection: Collection):
        self.collection = collection

    def _to_model(self, doc: Optional[dict]) -> Optional[UserInDB]:
        if not doc:
            return None
        doc_copy = dict(doc)
        doc_copy.pop("_id", None)
        # Handle cases where settings is stored as None
        if doc_copy.get("settings") is None:
            doc_copy.pop("settings", None)
        return UserInDB(**doc_copy)

    def get_by_id(self, user_id: str) -> Optional[UserInDB]:
        """Fetch user by id"""
        doc = self.collection.find_one({"id": user_id})
        return self._to_model(doc)

    def get_by_email(self, email: str) -> Optional[UserInDB]:
        """Fetch user by email address"""
        doc = self.collection.find_one({"email": email})
        return self._to_model(doc)

    def create_user(self, user: UserInDB) -> None:
        """Insert a new user document"""
        self.collection.insert_one(user.model_dump())

    def update_profile(self, user_id: str, first_name: str, last_name: str) -> bool:
        """Update user first name and last name"""
        result = self.collection.update_one(
            {"id": user_id},
            {"$set": {"first_name": first_name, "last_name": last_name}},
        )
        return result.modified_count > 0

    def update_email(self, user_id: str, email: str) -> bool:
        """Update user email address"""
        result = self.collection.update_one(
            {"id": user_id},
            {"$set": {"email": email}},
        )
        return result.modified_count > 0

    def update_password(self, user_id: str, password_hash: str) -> bool:
        """Update user password hash"""
        result = self.collection.update_one(
            {"id": user_id},
            {"$set": {"password": password_hash}},
        )
        return result.modified_count > 0

    def update_settings(self, user_id: str, rate: float) -> bool:
        """Update user settings nested fields"""
        result = self.collection.update_one(
            {"id": user_id},
            {"$set": {"settings.electricity_rate_php_kwh": rate}},
        )
        return result.modified_count > 0
