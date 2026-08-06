from typing import Optional
import re
from pydantic import BaseModel, Field, EmailStr, field_validator, model_validator
from app.database.models import UserSettings


class UserSettingsResponse(UserSettings):
    """Outbound settings DTO"""

    pass


class UserSettingsPatchRequest(BaseModel):
    """Inbound request to update user preferences"""

    electricity_rate_php_kwh: Optional[float] = Field(
        None, gt=0, description="New electricity rate in PHP/kWh"
    )


class UserProfileUpdateRequest(BaseModel):
    """Inbound request to update profile name fields"""

    first_name: str = Field(..., min_length=1, description="First name")
    last_name: str = Field(..., min_length=1, description="Last name")


class UserProfileResponse(BaseModel):
    """Outbound profile names response"""

    first_name: str
    last_name: str


class UserEmailUpdateRequest(BaseModel):
    """Inbound request to update user email"""

    current_password: str = Field(..., description="Current password to verify change")
    new_email: EmailStr = Field(..., description="New email address")


class UserEmailResponse(BaseModel):
    """Outbound email update response"""

    email: EmailStr


class UserPasswordUpdateRequest(BaseModel):
    """Inbound request to update user password with complexity constraints"""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")
    confirm_password: str = Field(..., min_length=8, description="Confirm new password")

    @field_validator("new_password")
    @classmethod
    def validate_password_complexity(cls, v: str) -> str:
        """Enforce standard strength: 1 uppercase, 1 lowercase, 1 digit, 1 special char"""
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r'[ !"#$%&\'()*+,\-./:;<=>?@[\\\]^_`{|}~]', v):
            raise ValueError("Password must contain at least one special character")
        return v

    @model_validator(mode="after")
    def passwords_match(self):
        """Enforce new password matching the confirmation password"""
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password do not match")
        return self


class UserPasswordResponse(BaseModel):
    """Outbound password update confirmation"""

    message: str


class UserEmailVerifyRequest(BaseModel):
    """Email update verification code request"""

    code: str = Field(..., description="6-digit verification code")
