"""
Saving Tips endpoints for triggering on-demand household energy analysis,
polling analysis status, retrieving recommendations, and updating lifecycle status.
"""

from typing import List, Annotated
from fastapi import APIRouter, Depends, status, BackgroundTasks
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_saving_tip_service
from app.schemas.auth import User
from app.schemas.saving_tip import (
    SavingTipResponse,
    SavingTipStatusUpdate,
    SavingTipsSummaryResponse,
    GenerateTipsResponse,
    HouseholdAnalysisStatusResponse,
)
from app.services.saving_tip_service import SavingTipService

router = APIRouter(prefix="/saving-tips", tags=["Saving Tips"])


@router.post(
    "/generate",
    response_model=GenerateTipsResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_saving_tips(
    current_user: Annotated[User, Depends(get_current_user)],
    background_tasks: BackgroundTasks,
    saving_tip_service: Annotated[SavingTipService, Depends(get_saving_tip_service)],
):
    """
    Trigger on-demand household energy analysis for all active user appliances.
    Single entry point for Gemini AI generation.
    """
    return saving_tip_service.start_household_analysis(
        current_user.id, background_tasks
    )


@router.get(
    "/analysis-status",
    response_model=HouseholdAnalysisStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def get_household_analysis_status(
    current_user: Annotated[User, Depends(get_current_user)],
    saving_tip_service: Annotated[SavingTipService, Depends(get_saving_tip_service)],
):
    """
    Retrieve current household analysis session status, cooldown metadata, and snapshot versions.
    """
    return saving_tip_service.get_analysis_status(current_user.id)


@router.get(
    "",
    response_model=List[SavingTipResponse],
    status_code=status.HTTP_200_OK,
)
async def get_saving_tips(
    current_user: Annotated[User, Depends(get_current_user)],
    saving_tip_service: Annotated[SavingTipService, Depends(get_saving_tip_service)],
):
    """
    Retrieve all visible saving tips from the active completed session for the authenticated
    """
    return saving_tip_service.get_user_tips(current_user.id)


@router.get(
    "/summary",
    response_model=SavingTipsSummaryResponse,
    status_code=status.HTTP_200_OK,
)
async def get_saving_tips_summary(
    current_user: Annotated[User, Depends(get_current_user)],
    saving_tip_service: Annotated[SavingTipService, Depends(get_saving_tip_service)],
):
    """
    Retrieve top summary stats for saving tips including total potential savings and reduction %.
    """
    return saving_tip_service.get_user_tips_summary(current_user.id)


@router.patch(
    "/{tip_id}/status",
    response_model=SavingTipResponse,
    status_code=status.HTTP_200_OK,
)
async def update_saving_tip_status(
    tip_id: str,
    data: SavingTipStatusUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    saving_tip_service: Annotated[SavingTipService, Depends(get_saving_tip_service)],
):
    """Update saving tip lifecycle status (active, completed, deleted)"""
    return saving_tip_service.update_tip_status(current_user.id, tip_id, data.status)
