"""
Database models representing BSON structures stored in MongoDB.
"""

from datetime import datetime, timezone
from typing import Optional
from enum import Enum
from pydantic import BaseModel, Field
from app.core.config import DEFAULT_RATE

CREATED_AT_DESC = "UTC creation time"
USER_ID_DESC = "Owner's user UUIDv4 string"


class ApplianceAnalysisStatus(str, Enum):
    """Enum representing the analysis status of an appliance."""

    NOT_ANALYZED = "NOT_ANALYZED"
    EFFICIENT = "EFFICIENT"
    HAS_RECOMMENDATIONS = "HAS_RECOMMENDATIONS"


class AnalysisSessionStatus(str, Enum):
    """Enum representing the status of a saving tip analysis session."""

    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    OUTDATED = "OUTDATED"


class TipType(str, Enum):
    """Enum representing the type of saving tip."""

    CALCULATED = "CALCULATED"
    REFERENCE = "REFERENCE"


class TipStatus(str, Enum):
    """Enum representing the lifecycle status of a saving tip."""

    ACTIVE = "active"
    COMPLETED = "completed"
    STALE = "stale"
    DELETED = "deleted"


class PriorityLevel(str, Enum):
    """Enum representing the priority level of a saving tip."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class EffortLevel(str, Enum):
    """Enum representing the effort level required for a saving tip."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


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
    email_verified_at: Optional[datetime] = Field(
        default=None, description="UTC email verification time"
    )
    settings: UserSettings = Field(
        default_factory=UserSettings,
        description="User configuration settings",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description=CREATED_AT_DESC,
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
    analysis_status: ApplianceAnalysisStatus = Field(
        default=ApplianceAnalysisStatus.NOT_ANALYZED,
        description="Persisted analysis status for the appliance",
    )
    analysis_session_id: Optional[str] = Field(
        default=None,
        description="UUID of the analysis session that set the status",
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


class SavingTipSessionInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the saving_tip_sessions collection"""

    id: str = Field(..., description="Unique session UUIDv4 string")
    user_id: str = Field(..., description=USER_ID_DESC)
    household_snapshot_version: str = Field(
        ..., description="Deterministic serialized version of household energy state"
    )
    active_appliance_count: int = Field(
        ..., description="Number of active appliances evaluated in this session"
    )
    status: AnalysisSessionStatus = Field(
        ..., description="Session status: IN_PROGRESS, COMPLETED, FAILED, OUTDATED"
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time analysis started",
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="UTC time analysis completed"
    )
    next_allowed_analysis_at: Optional[datetime] = Field(
        default=None,
        description="UTC timestamp after which next analysis is allowed (24h cooldown)",
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if analysis failed or was invalidated"
    )
    tips_count: int = Field(
        default=0, description="Total tips generated during session"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description=CREATED_AT_DESC,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC update time",
    )


class SavingTipInDB(BaseModel):
    """Pydantic model representing a MongoDB document in the saving_tips collection"""

    id: str = Field(..., description="Unique saving tip UUIDv4 string")
    user_id: str = Field(..., description=USER_ID_DESC)
    session_id: Optional[str] = Field(
        default=None, description="Parent analysis session UUIDv4 string"
    )
    appliance_id: str = Field(..., description="Target appliance UUIDv4 string")
    appliance_name: str = Field(..., description="Snapshot of appliance name")
    appliance_category: str = Field(..., description="Snapshot of appliance category")
    appliance_wattage_watts: float = Field(
        ..., description="Snapshot of appliance wattage in watts"
    )
    appliance_daily_usage_hours: float = Field(
        ..., description="Snapshot of appliance daily usage in hours"
    )
    appliance_monthly_kwh: float = Field(
        ..., description="Snapshot of appliance projected monthly kWh"
    )
    title: str = Field(..., description="Saving tip title")
    description: str = Field(..., description="Detailed saving recommendation")
    priority: PriorityLevel = Field(
        ..., description="Priority level: LOW, MEDIUM, HIGH"
    )
    effort_level: EffortLevel = Field(
        ..., description="Effort required: LOW, MEDIUM, HIGH"
    )
    recommended_daily_usage_reduction_hours: Optional[float] = Field(
        default=None, description="Recommended daily reduction in hours"
    )
    estimated_monthly_savings: Optional[float] = Field(
        default=None, description="Calculated monthly savings in PHP"
    )
    tip_type: TipType = Field(..., description="Tip type: CALCULATED or REFERENCE")
    source_url: Optional[str] = Field(
        default=None, description="External reference URL"
    )
    source_name: Optional[str] = Field(
        default=None, description="External reference source name"
    )
    status: TipStatus = Field(
        default=TipStatus.ACTIVE,
        description="Lifecycle status: active, completed, stale, deleted",
    )
    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC time recommendation was generated by AI",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description=CREATED_AT_DESC,
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC update time",
    )
