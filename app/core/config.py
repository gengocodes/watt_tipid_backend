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

DEFAULT_RATE = float(os.getenv("DEFAULT_RATE", "12.50"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "WattTipid")

EMAIL_VERIFICATION_EXPIRE_MINUTES = int(
    os.getenv("EMAIL_VERIFICATION_EXPIRE_MINUTES", "5")
)
EMAIL_VERIFICATION_RESEND_SECONDS = int(
    os.getenv("EMAIL_VERIFICATION_RESEND_SECONDS", "60")
)
EMAIL_VERIFICATION_MAX_ATTEMPTS = int(os.getenv("EMAIL_VERIFICATION_MAX_ATTEMPTS", "3"))

COOKIE_SECURE: bool
COOKIE_SAMESITE: Literal["lax", "strict", "none"]

if ENV == "dev":
    COOKIE_SECURE = False
    COOKIE_SAMESITE = "lax"
else:
    COOKIE_SECURE = True
    COOKIE_SAMESITE = "none"
