"""
Dashboard analytics endpoints
"""

from typing import Annotated
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_dashboard_service
from app.schemas.auth import User
from app.schemas.energy import EnergySummaryResponse
from app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/summary", response_model=EnergySummaryResponse, status_code=status.HTTP_200_OK
)
async def get_dashboard_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    dashboard_service: DashboardService = Depends(get_dashboard_service),
):
    """Retrieve dynamic aggregated cost projections and energy savings statistics"""
    return dashboard_service.get_dashboard_summary(current_user.id)
