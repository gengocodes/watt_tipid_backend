"""
Authentication schemas
"""

from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Register request schema"""

    email: EmailStr
    password: str
    first_name: str
    last_name: str
    barangay_city: str


class LoginRequest(BaseModel):
    """Login request schema"""

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response schema"""

    id: str
    email: EmailStr
    first_name: str
    last_name: str
    barangay_city: str


class User(BaseModel):
    """User model schema"""

    id: str
    email: str
    password: str
    first_name: str
    last_name: str
    is_active: bool
    barangay_city: str
