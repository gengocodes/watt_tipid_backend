"""
Appliance and Energy management endpoints
"""

from typing import List, Annotated
from fastapi import APIRouter, Depends, status
from app.dependencies.auth import get_current_user
from app.dependencies.services import get_appliance_service
from app.schemas.auth import User
from app.schemas.energy import ApplianceCreate, ApplianceUpdate, ApplianceResponse
from app.services.appliance_service import ApplianceService

router = APIRouter(prefix="/energy", tags=["Energy/Appliances"])


@router.get(
    "/appliances",
    response_model=List[ApplianceResponse],
    status_code=status.HTTP_200_OK,
)
def get_appliances(
    current_user: Annotated[User, Depends(get_current_user)],
    appliance_service: Annotated[ApplianceService, Depends(get_appliance_service)],
):
    """Retrieve the list of all active and inactive appliances for the authenticated user"""
    return appliance_service.get_appliances(current_user.id)


@router.post(
    "/appliances", response_model=ApplianceResponse, status_code=status.HTTP_201_CREATED
)
def create_appliance(
    data: ApplianceCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    appliance_service: Annotated[ApplianceService, Depends(get_appliance_service)],
):
    """Add a new appliance under the authenticated user's profile"""
    return appliance_service.create_appliance(current_user.id, data)


@router.put(
    "/appliances/{appliance_id}",
    response_model=ApplianceResponse,
    status_code=status.HTTP_200_OK,
)
def update_appliance(
    appliance_id: str,
    data: ApplianceUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    appliance_service: Annotated[ApplianceService, Depends(get_appliance_service)],
):
    """Modify details of an existing appliance configuration owned by the user"""
    return appliance_service.update_appliance(current_user.id, appliance_id, data)


@router.delete("/appliances/{appliance_id}", status_code=status.HTTP_200_OK)
def delete_appliance(
    appliance_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    appliance_service: Annotated[ApplianceService, Depends(get_appliance_service)],
):
    """Remove an appliance configuration owned by the user"""
    appliance_service.delete_appliance(current_user.id, appliance_id)
    return {"message": "Appliance deleted successfully"}
