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
from app.services.email_service import EmailService
from app.services.web_search_service import WebSearchService
from app.services.agent_service import AgentService

from app.core.config import GEMINI_API_KEY, GEMINI_MODEL

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_google_genai import ChatGoogleGenerativeAI


def get_email_service() -> EmailService:
    """Dependency provider for EmailService"""
    return EmailService()


def get_web_search_service() -> WebSearchService:
    """Dependency provider for WebSearchService"""
    return WebSearchService()


def get_auth_service(
    user_repo: UserRepository = Depends(get_user_repository),
    token_repo: RefreshTokenRepository = Depends(get_refresh_token_repository),
    email_service: EmailService = Depends(get_email_service),
) -> AuthService:
    """Dependency provider for AuthService"""
    return AuthService(user_repo, token_repo, email_service)


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
    email_service: EmailService = Depends(get_email_service),
) -> UserSettingsService:
    """Dependency provider for UserSettingsService"""
    return UserSettingsService(user_repo, token_repo, email_service)


def get_gemini_model() -> BaseChatModel:
    """Dependency provider for Gemini Chat model returning BaseChatModel abstraction"""
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=GEMINI_API_KEY,
    )


def get_agent_service(
    model: BaseChatModel = Depends(get_gemini_model),
    appliance_service: ApplianceService = Depends(get_appliance_service),
    dashboard_service: DashboardService = Depends(get_dashboard_service),
    web_search_service: WebSearchService = Depends(get_web_search_service),
) -> AgentService:
    """Dependency provider for AgentService"""
    return AgentService(model, appliance_service, dashboard_service, web_search_service)
