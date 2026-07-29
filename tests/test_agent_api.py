"""
Unit tests for AI Agent service and router
"""

from unittest.mock import AsyncMock, MagicMock
import pytest
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from app.services.agent_service import AgentService, AgentServiceError
from app.schemas.agent import ChatResponse
from app.prompts.agent import SYSTEM_PROMPT


@pytest.mark.anyio
async def test_agent_service_success():
    """
    Test the success case of the AgentService with a plain string response.
    """
    mock_model = MagicMock()
    mock_response = AIMessage(content="Turn off unused lights to save electricity.")
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    service = AgentService(model=mock_model)
    result = await service.chat("How do I save energy?")

    assert isinstance(result, ChatResponse)
    assert result.message == "Turn off unused lights to save electricity."

    mock_model.ainvoke.assert_called_once()
    called_messages = mock_model.ainvoke.call_args[0][0]
    assert len(called_messages) == 2
    assert isinstance(called_messages[0], SystemMessage)
    assert called_messages[0].content == SYSTEM_PROMPT
    assert isinstance(called_messages[1], HumanMessage)
    assert called_messages[1].content == "How do I save energy?"


@pytest.mark.anyio
async def test_agent_service_structured_dict_content():
    """
    Test AgentService text extraction from structured list containing dicts with extras.
    """
    mock_model = MagicMock()
    mock_response = AIMessage(
        content=[
            {
                "type": "text",
                "text": "Hello! I am WattTipid AI.",
                "extras": {"signature": "abc123xyz"},
            }
        ]
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    service = AgentService(model=mock_model)
    result = await service.chat("Hi")

    assert isinstance(result, ChatResponse)
    assert result.message == "Hello! I am WattTipid AI."


@pytest.mark.anyio
async def test_agent_service_mixed_list_content():
    """
    Test AgentService text extraction from a mixed content list (strings and dicts).
    """
    mock_model = MagicMock()
    mock_response = AIMessage(
        content=[
            "Hello! ",
            {"type": "text", "text": "I am WattTipid AI."},
            {"invalid_key": 123},
        ]
    )
    mock_model.ainvoke = AsyncMock(return_value=mock_response)

    service = AgentService(model=mock_model)
    result = await service.chat("Hi")

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
        content=[{"text": "Structured text 1"}, {"text": " and text 2"}]
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
    mock_model.ainvoke = AsyncMock(side_effect=Exception("API key expired"))

    service = AgentService(model=mock_model)

    with pytest.raises(AgentServiceError) as exc_info:
        await service.chat("Test message")

    assert "Failed to generate AI response." in str(exc_info.value)
