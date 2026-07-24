"""
Repository dependency injection providers.
"""

from app.database.mongodb import (
    users_collection,
    refresh_tokens_collection,
    appliances_collection,
    monthly_energy_collection,
)
from app.repositories.user import UserRepository
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.appliance import ApplianceRepository
from app.repositories.monthly_energy import MonthlyEnergyRepository


def get_user_repository() -> UserRepository:
    """Dependency provider for UserRepository"""
    return UserRepository(users_collection)


def get_refresh_token_repository() -> RefreshTokenRepository:
    """Dependency provider for RefreshTokenRepository"""
    return RefreshTokenRepository(refresh_tokens_collection)


def get_appliance_repository() -> ApplianceRepository:
    """Dependency provider for ApplianceRepository"""
    return ApplianceRepository(appliances_collection)


def get_monthly_energy_repository() -> MonthlyEnergyRepository:
    """Dependency provider for MonthlyEnergyRepository"""
    return MonthlyEnergyRepository(monthly_energy_collection)
