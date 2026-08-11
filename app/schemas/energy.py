"""
Energy and Appliance schemas/DTOs
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from app.database.models import ApplianceInDB


class ApplianceCreate(BaseModel):
    """Schema for registering a new appliance"""

    name: str = Field(..., description="Appliance name (e.g. Air Conditioner)")
    category: str = Field(
        ...,
        description=(
            "Category (Kitchen | Cooling | Entertainment | Laundry | "
            "Lighting | Devices | Other)"
        ),
    )
    wattage_watts: float = Field(
        ..., gt=0, description="Appliance power rating in watts"
    )
    daily_usage_hours: float = Field(
        ..., gt=0, le=24, description="Average run hours per day"
    )
    icon: str = Field("plug", description="Icon identifier string")


class ApplianceUpdate(BaseModel):
    """Schema for modifying an existing appliance"""

    name: Optional[str] = Field(None, description="Appliance name")
    category: Optional[str] = Field(None, description="Category")
    wattage_watts: Optional[float] = Field(
        None, gt=0, description="Appliance power rating in watts"
    )
    daily_usage_hours: Optional[float] = Field(
        None, gt=0, le=24, description="Average run hours per day"
    )
    icon: Optional[str] = Field(None, description="Icon identifier string")
    is_active: Optional[bool] = Field(None, description="Toggle active status")


class ApplianceResponse(ApplianceInDB):
    """DTO for outbound appliance details (includes computed monthly_kwh)"""

    monthly_kwh: float = Field(
        ..., description="Calculated monthly energy usage in kWh"
    )


class CategoryShare(BaseModel):
    """Energy consumption share per appliance category"""

    category: str
    kwh: float
    percentage: float


class MonthlyTrendItem(BaseModel):
    """Historical energy snapshot item for trend graphs"""

    month: str = Field(..., description="YYYY-MM format")
    kwh: float
    cost: float


class MonthlyTrendCreate(BaseModel):
    """Schema for manually logging or updating a monthly energy trend record"""

    month: str = Field(
        ...,
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
        description="Month in YYYY-MM format",
    )
    kwh: float = Field(..., gt=0, description="Monthly energy consumption in kWh")
    cost_php: Optional[float] = Field(
        None, gt=0, description="Optional total bill cost in PHP"
    )


class EnergySummaryResponse(BaseModel):
    """Aggregated projection DTO for the dashboard/summary"""

    estimated_monthly_cost: float = Field(
        ..., description="Projected monthly cost in PHP"
    )
    total_monthly_kwh: float = Field(
        ..., description="Total monthly energy consumption in kWh"
    )
    appliance_count: int = Field(..., description="Number of active appliances")
    electricity_rate_php_kwh: float = Field(
        ..., description="Electricity rate in PHP/kWh used for estimate"
    )
    energy_saving_score: int = Field(
        ..., ge=0, le=100, description="Calculated saving score"
    )
    score_status: str = Field(
        ..., description="Score status tag (Excellent | Good | Fair | Needs Work)"
    )
    category_shares: List[CategoryShare] = Field(
        ..., description="Breakdown of energy consumption by category"
    )
    monthly_trend: List[MonthlyTrendItem] = Field(
        ..., description="Historical energy logs for trend graphs"
    )
