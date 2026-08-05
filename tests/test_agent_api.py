"""
Unit tests for AI Agent service and router
"""

import io
import logging
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone
import pytest
from langchain_core.messages import (
    SystemMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    AIMessageChunk,
)

from app.services.agent_service import AgentService, AgentServiceError
from app.schemas.agent import (
    ChatResponse,
    StreamStatusEvent,
    StreamActivityEvent,
    StreamToolStartEvent,
    StreamToolEndEvent,
    StreamTokenEvent,
    StreamErrorEvent,
    StreamCompleteEvent,
)
from app.schemas.energy import ApplianceResponse
from app.prompts.agent import get_system_prompt
from app.tools.agent_tools import (
    create_user_appliances_tool,
    create_user_energy_summary_tool,
)


@pytest.mark.anyio
async def test_agent_service_success():
    """
    Test the success case of the AgentService with a plain string response.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    mock_response = AIMessage(
        content="Turn off unused lights to save electricity.", tool_calls=[]
    )
    bound_model.ainvoke = AsyncMock(return_value=mock_response)
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )
    result = await service.chat("user123", "Juan", "How do I save energy?")

    assert isinstance(result, ChatResponse)
    assert result.message == "Turn off unused lights to save electricity."

    mock_model.bind_tools.assert_called_once()
    bound_model.ainvoke.assert_called_once()
    called_messages = bound_model.ainvoke.call_args[0][0]
    assert len(called_messages) == 2
    assert isinstance(called_messages[0], SystemMessage)
    assert called_messages[0].content == get_system_prompt("Juan")
    assert isinstance(called_messages[1], HumanMessage)
    assert called_messages[1].content == "How do I save energy?"


@pytest.mark.anyio
async def test_agent_service_tool_invocation():
    """
    Test AgentService when LLM invokes get_user_appliances tool.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()

    initial_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_user_appliances",
                "args": {},
                "id": "call_123",
            }
        ],
    )
    final_response = AIMessage(
        content="You have 1 Air Conditioner registered.", tool_calls=[]
    )

    bound_model.ainvoke = AsyncMock(side_effect=[initial_response, final_response])
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    now = datetime.now(timezone.utc)
    mock_appliance_service.get_appliances.return_value = [
        ApplianceResponse(
            id="app-1",
            user_id="user123",
            name="Air Conditioner",
            category="Cooling",
            wattage_watts=1000.0,
            daily_usage_hours=8.0,
            icon="fan",
            is_active=True,
            monthly_kwh=240.0,
            created_at=now,
            updated_at=now,
        )
    ]
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )
    result = await service.chat("user123", "Maria", "What appliances do I have?")

    assert result.message == "You have 1 Air Conditioner registered."
    mock_appliance_service.get_appliances.assert_called_once_with("user123")
    assert bound_model.ainvoke.call_count == 2


@pytest.mark.anyio
async def test_tools_logging_success_and_duration():
    """
    Test that agent tools log invocation, completion, and duration without exposing user_id.
    """
    logger = logging.getLogger("app.tools.agent_tools")
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)

    mock_appliance_service = MagicMock()
    mock_appliance_service.get_appliances.return_value = []

    appliances_tool = create_user_appliances_tool(
        "secret-user-123", mock_appliance_service
    )

    try:
        res = await appliances_tool.ainvoke({})
        output = stream.getvalue()
        assert res == []
        assert "Agent tool get_user_appliances invoked" in output
        assert "Agent tool get_user_appliances completed successfully in" in output
        assert "secret-user-123" not in output
    finally:
        logger.removeHandler(handler)


@pytest.mark.anyio
async def test_tools_logging_failure():
    """
    Test that agent tools log failures and duration before propagating exception without exposing user_id.
    """
    logger = logging.getLogger("app.tools.agent_tools")
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    logger.addHandler(handler)

    mock_dashboard_service = MagicMock()
    mock_dashboard_service.get_dashboard_summary.side_effect = ValueError(
        "Database unreachable"
    )

    energy_tool = create_user_energy_summary_tool(
        "secret-user-456", mock_dashboard_service
    )

    try:
        with pytest.raises(ValueError, match="Database unreachable"):
            await energy_tool.ainvoke({})
        output = stream.getvalue()
        assert "Agent tool get_user_energy_summary invoked" in output
        assert "Agent tool get_user_energy_summary failed after" in output
        assert "secret-user-456" not in output
    finally:
        logger.removeHandler(handler)


@pytest.mark.anyio
async def test_agent_service_structured_dict_content():
    """
    Test AgentService text extraction from structured list containing dicts with extras.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    mock_response = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Hello! I am WattTipid AI.",
                "extras": {"signature": "abc123xyz"},
            }
        ],
        tool_calls=[],
    )
    bound_model.ainvoke = AsyncMock(return_value=mock_response)
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )
    result = await service.chat("user123", "Pedro", "Hi")

    assert isinstance(result, ChatResponse)
    assert result.message == "Hello! I am WattTipid AI."


@pytest.mark.anyio
async def test_agent_service_mixed_list_content():
    """
    Test AgentService text extraction from a mixed content list (strings and dicts).
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    mock_response = AIMessage(
        content=[
            "Hello! ",
            {"type": "text", "text": "I am WattTipid AI."},
        ],
        tool_calls=[],
    )
    bound_model.ainvoke = AsyncMock(return_value=mock_response)
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )
    result = await service.chat("user123", "Pedro", "Hi")

    assert isinstance(result, ChatResponse)
    assert result.message == "Hello! I am WattTipid AI."


@pytest.mark.anyio
async def test_agent_service_extract_message_text_static_method():
    """
    Directly unit test _extract_message_text static method.
    """
    msg_str = AIMessage(content="Simple string content")
    assert AgentService._extract_message_text(msg_str) == "Simple string content"

    msg_list_dict = AIMessage(
        content=[
            {"type": "text", "text": "Structured text 1"},
            {"type": "text", "text": " and text 2"},
        ]
    )
    assert (
        AgentService._extract_message_text(msg_list_dict)
        == "Structured text 1 and text 2"
    )


@pytest.mark.anyio
async def test_agent_service_error_handling():
    """
    Test the AgentService error handling.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    bound_model.ainvoke = AsyncMock(side_effect=Exception("API key expired"))
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )

    with pytest.raises(AgentServiceError) as exc_info:
        await service.chat("user123", "Pedro", "Test message")

    assert "Failed to generate AI response." in str(exc_info.value)


@pytest.mark.anyio
async def test_agent_service_duplicate_tool_calls():
    """
    Test that duplicate tool calls in a single turn execute the tool only once,
    while appending ToolMessage for every original tool_call_id.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()

    initial_response = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "get_user_appliances",
                "args": {},
                "id": "call_1",
            },
            {
                "name": "get_user_appliances",
                "args": {},
                "id": "call_2",
            },
        ],
    )
    final_response = AIMessage(
        content="You have 0 appliances registered.", tool_calls=[]
    )

    bound_model.ainvoke = AsyncMock(side_effect=[initial_response, final_response])
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_appliance_service.get_appliances.return_value = []
    mock_dashboard_service = MagicMock()
    mock_web_search_service = MagicMock()

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=mock_dashboard_service,
        web_search_service=mock_web_search_service,
    )
    result = await service.chat("user123", "Maria", "Check my appliances")

    assert result.message == "You have 0 appliances registered."
    # Tool invocation underlying service should only be called ONCE due to deduplication cache
    mock_appliance_service.get_appliances.assert_called_once_with("user123")

    # Verify messages sent on second ainvoke call contain 2 ToolMessages
    second_ainvoke_call_messages = bound_model.ainvoke.call_args_list[1][0][0]
    tool_messages = [
        msg for msg in second_ainvoke_call_messages if isinstance(msg, ToolMessage)
    ]
    assert len(tool_messages) == 2
    assert tool_messages[0].tool_call_id == "call_1"
    assert tool_messages[1].tool_call_id == "call_2"


async def _async_gen(items):
    for item in items:
        yield item


@pytest.mark.anyio
async def test_agent_service_stream_chat_success_no_tools():
    """
    Test stream_chat yielding status, activity, token,
    and complete events when no tools are invoked.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()

    chunk1 = AIMessageChunk(content="Save energy by using LED bulbs.")
    final_output = AIMessage(content="Save energy by using LED bulbs.", tool_calls=[])

    events = [
        {"event": "on_chat_model_stream", "data": {"chunk": chunk1}},
        {"event": "on_chat_model_end", "data": {"output": final_output}},
    ]

    bound_model.astream_events = MagicMock(return_value=_async_gen(events))
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    service = AgentService(
        model=mock_model,
        appliance_service=MagicMock(),
        dashboard_service=MagicMock(),
        web_search_service=MagicMock(),
    )

    emitted_events = [
        event async for event in service.stream_chat("user1", "Juan", "Tips to save?")
    ]

    event_types = [type(e) for e in emitted_events]
    assert StreamStatusEvent in event_types
    assert StreamActivityEvent in event_types
    assert StreamTokenEvent in event_types
    assert StreamCompleteEvent in event_types

    token_events = [e for e in emitted_events if isinstance(e, StreamTokenEvent)]
    assert len(token_events) == 1
    assert token_events[0].token == "Save energy by using LED bulbs."


@pytest.mark.anyio
async def test_agent_service_stream_chat_with_tools():
    """
    Test stream_chat sequence when tools are requested by the model.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()

    tool_call_output = AIMessage(
        content="",
        tool_calls=[{"name": "get_user_appliances", "args": {}, "id": "call_999"}],
    )
    turn1_events = [
        {"event": "on_chat_model_end", "data": {"output": tool_call_output}},
    ]

    chunk_final = AIMessageChunk(content="You have 1 AC.")
    turn2_output = AIMessage(content="You have 1 AC.", tool_calls=[])
    turn2_events = [
        {"event": "on_chat_model_stream", "data": {"chunk": chunk_final}},
        {"event": "on_chat_model_end", "data": {"output": turn2_output}},
    ]

    bound_model.astream_events = MagicMock(
        side_effect=[_async_gen(turn1_events), _async_gen(turn2_events)]
    )
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    mock_appliance_service = MagicMock()
    mock_appliance_service.get_appliances.return_value = []

    service = AgentService(
        model=mock_model,
        appliance_service=mock_appliance_service,
        dashboard_service=MagicMock(),
        web_search_service=MagicMock(),
    )

    emitted_events = [
        event async for event in service.stream_chat("user1", "Maria", "My appliances?")
    ]

    event_types = [type(e) for e in emitted_events]
    assert StreamStatusEvent in event_types
    assert StreamActivityEvent in event_types
    assert StreamToolStartEvent in event_types
    assert StreamToolEndEvent in event_types
    assert StreamTokenEvent in event_types
    assert StreamCompleteEvent in event_types

    activity_events = [e for e in emitted_events if isinstance(e, StreamActivityEvent)]
    appliances_activities = [a for a in activity_events if a.id == "act-appliances"]
    assert len(appliances_activities) == 2
    assert appliances_activities[0].status == "started"
    assert appliances_activities[1].status == "completed"


@pytest.mark.anyio
async def test_agent_service_stream_chat_error_handling():
    """
    Test stream_chat error handling yielding user-safe StreamErrorEvent on exception.
    """
    mock_model = MagicMock()
    bound_model = MagicMock()
    bound_model.astream_events = MagicMock(
        side_effect=RuntimeError("Model service down")
    )
    mock_model.bind_tools = MagicMock(return_value=bound_model)

    service = AgentService(
        model=mock_model,
        appliance_service=MagicMock(),
        dashboard_service=MagicMock(),
        web_search_service=MagicMock(),
    )

    emitted_events = [
        event async for event in service.stream_chat("user1", "Juan", "Test error")
    ]

    assert len(emitted_events) == 3
    assert isinstance(emitted_events[0], StreamStatusEvent)
    assert isinstance(emitted_events[1], StreamActivityEvent)
    assert isinstance(emitted_events[2], StreamErrorEvent)
    assert (
        emitted_events[2].error
        == "Failed to generate AI response. Please try again later."
    )
