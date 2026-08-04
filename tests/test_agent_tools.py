"""
Unit tests for agent tools (factories, typed Pydantic results, validation, and logging)
"""

from unittest.mock import MagicMock
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException, status

from app.schemas.energy import ApplianceResponse
from app.schemas.agent import AgentToolResult, ApplianceDeletePayload
from app.tools.agent_tools import (
    create_add_user_appliance_tool,
    create_update_user_appliance_tool,
    create_delete_user_appliance_tool,
)


@pytest.mark.anyio
async def test_add_user_appliance_tool_success():
    """
    Test add_user_appliance tool returning AgentToolResult[ApplianceResponse] on success.
    """
    mock_service = MagicMock()
    now = datetime.now(timezone.utc)
    expected_appliance = ApplianceResponse(
        id="app-123",
        user_id="user-1",
        name="Electric Fan",
        category="Devices",
        wattage_watts=60.0,
        daily_usage_hours=8.0,
        icon="plug",
        is_active=True,
        monthly_kwh=14.4,
        created_at=now,
        updated_at=now,
    )
    mock_service.create_appliance.return_value = expected_appliance

    tool = create_add_user_appliance_tool("user-1", mock_service)
    result = await tool.ainvoke(
        {
            "name": "Electric Fan",
            "category": "Devices",
            "wattage_watts": 60.0,
            "daily_usage_hours": 8.0,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is True
    assert "Electric Fan" in result.message
    assert result.data == expected_appliance
    mock_service.create_appliance.assert_called_once()


@pytest.mark.anyio
async def test_add_user_appliance_tool_validation_error():
    """
    Test add_user_appliance tool catching ValidationError on invalid input.
    """
    mock_service = MagicMock()
    tool = create_add_user_appliance_tool("user-1", mock_service)

    # Invalid wattage <= 0
    result = await tool.ainvoke(
        {
            "name": "Electric Fan",
            "category": "Devices",
            "wattage_watts": -10.0,
            "daily_usage_hours": 8.0,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is False
    assert "Failed to add appliance" in result.message
    assert result.data is None
    mock_service.create_appliance.assert_not_called()


@pytest.mark.anyio
async def test_update_user_appliance_tool_success():
    """
    Test update_user_appliance tool returning AgentToolResult[ApplianceResponse].
    """
    mock_service = MagicMock()
    now = datetime.now(timezone.utc)
    updated_appliance = ApplianceResponse(
        id="app-456",
        user_id="user-1",
        name="Air Conditioner",
        category="Cooling",
        wattage_watts=1000.0,
        daily_usage_hours=10.0,
        icon="plug",
        is_active=True,
        monthly_kwh=300.0,
        created_at=now,
        updated_at=now,
    )
    mock_service.update_appliance.return_value = updated_appliance

    tool = create_update_user_appliance_tool("user-1", mock_service)
    result = await tool.ainvoke(
        {
            "appliance_id": "app-456",
            "daily_usage_hours": 10.0,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is True
    assert result.data == updated_appliance
    mock_service.update_appliance.assert_called_once()


@pytest.mark.anyio
async def test_update_user_appliance_tool_not_found():
    """
    Test update_user_appliance tool catching HTTPException(404).
    """
    mock_service = MagicMock()
    mock_service.update_appliance.side_effect = HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Appliance not found or access denied",
    )

    tool = create_update_user_appliance_tool("user-1", mock_service)
    result = await tool.ainvoke(
        {
            "appliance_id": "non-existent-id",
            "daily_usage_hours": 5.0,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is False
    assert "Appliance not found or access denied" in result.message
    assert result.data is None


@pytest.mark.anyio
async def test_delete_user_appliance_tool_unconfirmed():
    """
    Test delete_user_appliance tool returning success=False when confirmed is False.
    """
    mock_service = MagicMock()
    tool = create_delete_user_appliance_tool("user-1", mock_service)

    result = await tool.ainvoke(
        {
            "appliance_id": "app-789",
            "confirmed": False,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is False
    assert "requires explicit confirmation" in result.message
    assert result.data is None
    mock_service.delete_appliance.assert_not_called()


@pytest.mark.anyio
async def test_delete_user_appliance_tool_confirmed_success():
    """
    Test delete_user_appliance tool performing deletion when confirmed is True.
    """
    mock_service = MagicMock()
    tool = create_delete_user_appliance_tool("user-1", mock_service)

    result = await tool.ainvoke(
        {
            "appliance_id": "app-789",
            "confirmed": True,
        }
    )

    assert isinstance(result, AgentToolResult)
    assert result.success is True
    assert isinstance(result.data, ApplianceDeletePayload)
    assert result.data.appliance_id == "app-789"
    mock_service.delete_appliance.assert_called_once_with("user-1", "app-789")
