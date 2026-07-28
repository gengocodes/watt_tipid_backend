"""
Authentication schemas
"""

from datetime import datetime
from pydantic import BaseModel, EmailStr


class RegisterRequest(BaseModel):
    """Register request schema"""

    email: EmailStr
    password: str
    first_name: str
    last_name: str
    barangay_city: str


class RegisterResponse(BaseModel):
    """Register response schema"""

    message: str


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
    created_at: datetime


class User(BaseModel):
    """User model schema"""

    id: str
    email: str
    password: str
    first_name: str
    last_name: str
    is_active: bool
    barangay_city: str
    created_at: datetime


class RegisterVerifyRequest(BaseModel):
    """Registration verification request schema"""

    email: EmailStr
    code: str


class RegisterResendRequest(BaseModel):
    """Registration code resend request schema"""

    email: EmailStr
