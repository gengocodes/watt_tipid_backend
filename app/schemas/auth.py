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


class UserResponse(BaseModel):
    """User response schema"""

    id: str
    email: EmailStr


class User(BaseModel):
    """User model schema"""

    id: str
    email: str
    password: str
    is_active: bool

