"""
MongoDB database connection
"""

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database
from app.core.config import MONGODB_URL, MONGODB_DATABASE

client: MongoClient = MongoClient(MONGODB_URL)
database: Database = client[MONGODB_DATABASE]
users_collection: Collection = database["users"]
refresh_tokens_collection: Collection = database["refresh_tokens"]

# Create TTL index on expires_at field.
# MongoDB automatically removes expired refresh tokens in the background.
refresh_tokens_collection.create_index("expires_at", expireAfterSeconds=0)
