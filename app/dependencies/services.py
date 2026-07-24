"""
Service dependency injection providers.
"""

from fastapi import Depends
from app.dependencies.repositories import (
    get_user_repository,
    get_refresh_token_repository,
    get_appliance_repository,
    get_monthly_energy_repository,
)
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.appliance import ApplianceRepository
from app.repositories.monthly_energy import MonthlyEnergyRepository

from app.services.auth_service import AuthService
from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.services.user_settings_service import UserSettingsService


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> AuthService:
    """Dependency provider for AuthService"""
    return AuthService(user_repo, token_repo)


def get_appliance_service(
    app_repo: ApplianceRepository = Depends(get_appliance_repository),
) -> ApplianceService:
    """Dependency provider for ApplianceService"""
    return ApplianceService(app_repo)


def get_dashboard_service(
    app_repo: ApplianceRepository = Depends(get_appliance_repository),
    energy_repo: MonthlyEnergyRepository = Depends(get_monthly_energy_repository),
    user_repo: UserRepository = Depends(get_user_repository),
) -> DashboardService:
    """Dependency provider for DashboardService"""
    return DashboardService(app_repo, energy_repo, user_repo)


def get_user_settings_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
) -> UserSettingsService:
    """Dependency provider for UserSettingsService"""
    return UserSettingsService(user_repo, token_repo)
