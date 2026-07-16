"""
Authentication functions
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from app.core.config import JWT_SECRET, JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

pwd_context = CryptContext(schemes=["bcrypt"])


def hash_password(password: str):
    """Return the hashed password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    """Verify the hashed password"""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str):
    """Create an access token"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def generate_refresh_token() -> str:
    """Generate a secure random string to be used as a refresh token"""
    return secrets.token_urlsafe(64)


def hash_token(token: str) -> str:
    """Hash a token using SHA-256"""
    return hashlib.sha256(token.encode()).hexdigest()
