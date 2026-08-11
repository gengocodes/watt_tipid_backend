"""
Dashboard analytics endpoints
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_dashboard_service
from app.schemas.auth import User
from app.schemas.energy import (
    EnergySummaryResponse,
    MonthlyTrendCreate,
    MonthlyTrendItem,
)
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary", response_model=EnergySummaryResponse, status_code=status.HTTP_200_OK
)
async def get_dashboard_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
):
    """Retrieve dynamic aggregated cost projections and energy savings statistics"""
    return dashboard_service.get_dashboard_summary(current_user.id)


@router.post(
    "/monthly-trend",
    response_model=MonthlyTrendItem,
    status_code=status.HTTP_201_CREATED,
)
async def log_monthly_trend(
    data: MonthlyTrendCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
):
    """Manually log or update a historical monthly energy record"""
    return dashboard_service.log_monthly_trend(current_user.id, data)


@router.delete(
    "/monthly-trend/{month}",
    status_code=status.HTTP_200_OK,
)
async def delete_monthly_trend(
    month: str,
    current_user: Annotated[User, Depends(get_current_user)],
    dashboard_service: Annotated[DashboardService, Depends(get_dashboard_service)],
):
    """Delete a historical monthly energy record"""
    dashboard_service.delete_monthly_trend(current_user.id, month)
    return {"message": f"Monthly record for {month} deleted successfully"}
