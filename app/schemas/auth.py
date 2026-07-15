"""
Authentication schemas
"""

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Register request schema"""

    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    """Token response schema"""

    access_token: str
    token_type: str
