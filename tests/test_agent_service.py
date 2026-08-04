"""
Unit tests for AgentService orchestration, tool binding, and tool execution flows
"""

from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import pytest
from langchain_core.messages import AIMessage

from app.services.agent_service import AgentService
from app.schemas.energy import ApplianceResponse


@pytest.mark.anyio
async def test_agent_service_binds_all_tools():
    """
    Test that AgentService binds all 5 tools (appliances, summary, add, update, delete).
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    mock_response = AIMessage(content="Hello!", tool_calls=[])
    bound_model.ainvoke = AsyncMock(return_value=mock_response)
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_dashboard_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
    )

    await service.chat("user123", "Juan", "Hi")

    mock_model.bind_tools.assert_called_once()
    bound_tools = mock_model.bind_tools.call_args[0][0]
    tool_names = [t.name for t in bound_tools]

    assert "get_user_appliances" in tool_names
    assert "get_user_energy_summary" in tool_names
    assert "add_user_appliance" in tool_names
    assert "update_user_appliance" in tool_names
    assert "delete_user_appliance" in tool_names


@pytest.mark.anyio
async def test_agent_service_add_appliance_tool_flow():
    """
    Test AgentService flow when model invokes add_user_appliance.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()

    initial_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "add_user_appliance",
                "args": {
                    "name": "Electric Fan",
                    "category": "Devices",
                    "wattage_watts": 60.0,
                    "daily_usage_hours": 8.0,
                },
                "id": "call_add_1",
            }
        ],
    )
    final_response = AIMessage(
        content="Nai-add ko na ang iyong Electric Fan!", tool_calls=[]
    )

    bound_model.ainvoke = AsyncMock(side_effect=[initial_response, final_response])
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    now = datetime.now(timezone.utc)
    mock_appliance_service = MagicMock()
    mock_appliance_service.create_appliance.return_value = ApplianceResponse(
        id="app-100",
        user_id="user123",
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
    mock_dashboard_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
    )

    res = await service.chat(
        "user123", "Juan", "Add my Electric Fan 60W Devices used 8 hours"
    )

    assert res.message == "Nai-add ko na ang iyong Electric Fan!"
    mock_appliance_service.create_appliance.assert_called_once()
