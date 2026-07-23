"""
User settings schemas/DTOs
"""

from typing import Optional
from pydantic import BaseModel, Field


class UserSettingsResponse(BaseModel):
    """Outbound settings DTO"""

    electricity_rate_php_kwh: float = Field(
        ..., description="Electricity rate in PHP/kWh"
    )


class UserSettingsPatchRequest(BaseModel):
    """Inbound request to update user preferences"""

    electricity_rate_php_kwh: Optional[float] = Field(
        None, gt=0, description="New electricity rate in PHP/kWh"
    )
