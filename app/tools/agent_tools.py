"""
LangChain data retrieval tools for WattTipid AI Agent
"""

import time
import logging

from typing import List
from collections.abc import Callable
from functools import wraps
from langchain_core.tools import tool, BaseTool

from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.schemas.energy import ApplianceResponse, EnergySummaryResponse

logger = logging.getLogger(__name__)


def log_tool_execution(tool_name: str):
    """
    Decorator to log the execution of a tool.
    """

    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            logger.info("Agent tool %s invoked", tool_name)
            start_time = time.perf_counter()

            try:
                result = func(*args, **kwargs)

                duration = time.perf_counter() - start_time
                logger.info(
                    "Agent tool %s completed successfully in %.3fs",
                    tool_name,
                    duration,
                )

                return result

            except Exception:
                duration = time.perf_counter() - start_time
                logger.exception(
                    "Agent tool %s failed after %.3fs",
                    tool_name,
                    duration,
                )
                raise

        return wrapper

    return decorator


def create_user_appliances_tool(
    user_id: str, appliance_service: ApplianceService
) -> BaseTool:
    """
    Create request-scoped tool to fetch appliances for the authenticated user.
    """

    @tool
    @log_tool_execution("get_user_appliances")
    def get_user_appliances() -> List[ApplianceResponse]:
        """
        Retrieve the list of registered appliances for the authenticated user,
        including name, category, wattage in watts, daily usage hours, active status,
        and calculated monthly energy usage in kWh.
        """
        return appliance_service.get_appliances(user_id)

    return get_user_appliances


def create_user_energy_summary_tool(
    user_id: str, dashboard_service: DashboardService
) -> BaseTool:
    """
    Create request-scoped tool to fetch energy summary for the authenticated user.
    """

    @tool
    @log_tool_execution("get_user_energy_summary")
    def get_user_energy_summary() -> EnergySummaryResponse:
        """
        Retrieve aggregated energy consumption summary for the authenticated user,
        including estimated monthly cost in PHP, total monthly energy consumption in kWh,
        energy saving score, score status tag, category shares, and monthly trend history.
        """
        return dashboard_service.get_dashboard_summary(user_id)

    return get_user_energy_summary
