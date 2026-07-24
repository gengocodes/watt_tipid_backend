"""
Database models representing BSON structures stored in MongoDB.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from app.core.config import DEFAULT_RATE

CREATED_AT_DESC = "UTC creation time"
USER_ID_DESC = "Owner's user UUIDv4 string"


class UserSettings(BaseModel):
    """Pydantic representation of user settings nested inside UserInDB"""

    electricity_rate_php_kwh: float = Field(
        default=DEFAULT_RATE, description="Electricity rate in PHP/kWh"
    )


class UserInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the users collection"""

    id: str = Field(..., description="Unique user UUIDv4 string")
    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Hashed password string")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    is_active: bool = Field(
        default=True, description="Whether the user account is active"
    )
    barangay_city: str = Field(..., description="User's location")
    settings: UserSettings = Field(
        default_factory=UserSettings,
        description="User configuration settings",
    )


class RefreshTokenInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the refresh_tokens collection"""

    id: str = Field(..., description="Unique refresh token record UUIDv4 string")
    user_id: str = Field(..., description=USER_ID_DESC)
    token_hash: str = Field(..., description="SHA-256 hash of the raw refresh token")
    expires_at: datetime = Field(..., description="UTC expiration time")
    revoked: bool = Field(default=False, description="Whether this token was revoked")
    created_at: datetime = Field(..., description=CREATED_AT_DESC)


class ApplianceInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the appliances collection"""

    id: str = Field(..., description="Unique appliance UUIDv4 string")
    user_id: str = Field(..., description=USER_ID_DESC)
    name: str = Field(..., description="Appliance name")
    category: str = Field(..., description="Appliance category")
    wattage_watts: float = Field(..., description="Wattage rating")
    daily_usage_hours: float = Field(..., description="Daily run hours")
    icon: str = Field(default="plug", description="Icon identifier string")
    is_active: bool = Field(
        default=True, description="Whether this appliance is active"
    )
    created_at: datetime = Field(..., description=CREATED_AT_DESC)
    updated_at: datetime = Field(..., description="UTC update time")


class MonthlyEnergyInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the monthly_energy collection"""

    id: Optional[str] = Field(None, description="Optional snapshot UUIDv4 string")
    user_id: str = Field(..., description=USER_ID_DESC)
    month: str = Field(..., description="YYYY-MM format representation of the month")
    kwh: float = Field(..., description="Total monthly consumption in kWh")
    cost_php: float = Field(..., description="Total projected cost in PHP")
    rate_php_kwh: Optional[float] = Field(
        None, description="Electricity rate in PHP/kWh"
    )
    created_at: Optional[datetime] = Field(None, description=CREATED_AT_DESC)
