"""
Configuration variables
"""

import os
from typing import Literal
from dotenv import load_dotenv

load_dotenv()


ENV = os.getenv("env")
MONGODB_URL = os.getenv("MONGODB_URL")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

COOKIE_SECURE: bool
COOKIE_SAMESITE: Literal["lax", "strict", "none"]

if ENV == "dev":
    COOKIE_SECURE = False
    COOKIE_SAMESITE = "lax"
else:
    COOKIE_SECURE = True
    COOKIE_SAMESITE = "none"
