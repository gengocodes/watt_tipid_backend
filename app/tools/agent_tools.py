"""
LangChain data retrieval tools for WattTipid AI Agent
"""

import time
import logging
import inspect

from typing import List
from collections.abc import Callable
from functools import wraps
from langchain_core.tools import tool, BaseTool

from fastapi import HTTPException
from pydantic import ValidationError
from app.services.appliance_service import ApplianceService
from app.services.dashboard_service import DashboardService
from app.services.web_search_service import WebSearchService
from app.schemas.energy import (
    ApplianceCreate,
    ApplianceUpdate,
    ApplianceResponse,
    EnergySummaryResponse,
)
from app.schemas.agent import (
    AgentToolResult,
    ApplianceDeletePayload,
    SearchResultsResponse,
)

logger = logging.getLogger(__name__)


def log_tool_execution(tool_name: str):
    """
    Decorator to log the execution of a tool (sync or async).
    """

    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                logger.info("Agent tool %s invoked", tool_name)
                start_time = time.perf_counter()

                try:
                    result = await func(*args, **kwargs)

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

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
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

        return sync_wrapper

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


def create_add_user_appliance_tool(
    user_id: str, appliance_service: ApplianceService
) -> BaseTool:
    """
    Create request-scoped tool to add a new appliance for the authenticated user.
    """

    @tool
    @log_tool_execution("add_user_appliance")
    def add_user_appliance(
        name: str,
        category: str,
        wattage_watts: float,
        daily_usage_hours: float,
    ) -> AgentToolResult[ApplianceResponse]:
        """
        Register a new appliance for the authenticated user.

        Requires:
        - name: Name of the appliance (e.g. 'Living Room Fan')
        - category: One of 'Kitchen', 'Cooling', 'Entertainment', 'Laundry', 'Lighting', 'Devices', 'Other'
        - wattage_watts: Power rating in watts (must be > 0)
        - daily_usage_hours: Average hours used per day (must be > 0 and <= 24)
        """
        try:
            payload = ApplianceCreate(
                name=name,
                category=category,
                wattage_watts=wattage_watts,
                daily_usage_hours=daily_usage_hours,
                icon="plug",
            )
            created = appliance_service.create_appliance(user_id, payload)
            return AgentToolResult[ApplianceResponse](
                success=True,
                message=f"Appliance '{created.name}' added successfully.",
                data=created,
            )
        except (HTTPException, ValueError, ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            return AgentToolResult[ApplianceResponse](
                success=False,
                message=f"Failed to add appliance: {detail}",
                data=None,
            )

    return add_user_appliance


def create_update_user_appliance_tool(
    user_id: str, appliance_service: ApplianceService
) -> BaseTool:
    """
    Create request-scoped tool to update an existing appliance for the authenticated user.
    """

    @tool
    @log_tool_execution("update_user_appliance")
    def update_user_appliance(
        appliance_id: str,
        name: str | None = None,
        category: str | None = None,
        wattage_watts: float | None = None,
        daily_usage_hours: float | None = None,
        is_active: bool | None = None,
    ) -> AgentToolResult[ApplianceResponse]:
        """
        Update an existing appliance for the authenticated user.
        Requires appliance_id (UUID string).
        Optional fields to update: name, category, wattage_watts, daily_usage_hours, is_active.
        """
        try:
            payload = ApplianceUpdate(
                name=name,
                category=category,
                wattage_watts=wattage_watts,
                daily_usage_hours=daily_usage_hours,
                is_active=is_active,
            )
            updated = appliance_service.update_appliance(user_id, appliance_id, payload)
            return AgentToolResult[ApplianceResponse](
                success=True,
                message=f"Appliance '{updated.name}' updated successfully.",
                data=updated,
            )
        except (HTTPException, ValueError, ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            return AgentToolResult[ApplianceResponse](
                success=False,
                message=f"Failed to update appliance: {detail}",
                data=None,
            )

    return update_user_appliance


def create_delete_user_appliance_tool(
    user_id: str, appliance_service: ApplianceService
) -> BaseTool:
    """
    Create request-scoped tool to delete an appliance for the authenticated user.
    """

    @tool
    @log_tool_execution("delete_user_appliance")
    def delete_user_appliance(
        appliance_id: str,
        confirmed: bool = False,
    ) -> AgentToolResult[ApplianceDeletePayload]:
        """
        Delete an appliance for the authenticated user given its appliance_id.
        Requires explicit confirmed=True parameter before executing deletion.
        """
        if not confirmed:
            return AgentToolResult[ApplianceDeletePayload](
                success=False,
                message=(
                    "Deletion requires explicit confirmation from the user. "
                    "Please ask the user for confirmation and pass confirmed=True once confirmed."
                ),
                data=None,
            )

        try:
            appliance_service.delete_appliance(user_id, appliance_id)
            return AgentToolResult[ApplianceDeletePayload](
                success=True,
                message=f"Appliance '{appliance_id}' deleted successfully.",
                data=ApplianceDeletePayload(appliance_id=appliance_id),
            )
        except (HTTPException, ValueError, ValidationError) as e:
            detail = getattr(e, "detail", str(e))
            return AgentToolResult[ApplianceDeletePayload](
                success=False,
                message=f"Failed to delete appliance: {detail}",
                data=None,
            )

    return delete_user_appliance


def create_web_search_tool(
    web_search_service: WebSearchService,
) -> BaseTool:
    """
    Create tool allowing the AI agent to retrieve external information from the web.
    """

    @tool
    @log_tool_execution("web_search")
    async def web_search(query: str) -> AgentToolResult[SearchResultsResponse]:
        """
        Search the web for external information, such as appliance specifications,
        energy efficiency references, electricity-saving tips, and supporting sources.

        Requires:
        - query: Clear, concise search query string.

        Important: Once search results are retrieved, synthesize and answer the user directly.
        Do NOT perform repeated or redundant search queries.
        """
        return await web_search_service.search(query)

    return web_search
