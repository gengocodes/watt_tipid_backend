"""
Appliance and Energy management endpoints
"""

from typing import List, Annotated
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.schemas.auth import User
from app.schemas.energy import ApplianceCreate, ApplianceUpdate, ApplianceResponse
from app.services.appliance_service import ApplianceService

router = APIRouter(prefix="/energy", tags=["Energy/Appliances"])


@router.get(
    "/appliances",
    response_model=List[ApplianceResponse],
    status_code=status.HTTP_200_OK,
)
async def get_appliances(current_user: Annotated[User, Depends(get_current_user)]):
    """Retrieve the list of all active and inactive appliances for the authenticated user"""
    return ApplianceService.get_appliances(current_user.id)


@router.post(
    "/appliances", response_model=ApplianceResponse, status_code=status.HTTP_201_CREATED
)
async def create_appliance(
    data: ApplianceCreate, current_user: Annotated[User, Depends(get_current_user)]
):
    """Add a new appliance under the authenticated user's profile"""
    return ApplianceService.create_appliance(current_user.id, data)


@router.put(
    "/appliances/{appliance_id}",
    response_model=ApplianceResponse,
    status_code=status.HTTP_200_OK,
)
async def update_appliance(
    appliance_id: str,
    data: ApplianceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Modify details of an existing appliance configuration owned by the user"""
    return ApplianceService.update_appliance(current_user.id, appliance_id, data)


@router.delete("/appliances/{appliance_id}", status_code=status.HTTP_200_OK)
async def delete_appliance(
    appliance_id: str, current_user: Annotated[User, Depends(get_current_user)]
):
    """Remove an appliance configuration owned by the user"""
    ApplianceService.delete_appliance(current_user.id, appliance_id)
    return {"message": "Appliance deleted successfully"}
