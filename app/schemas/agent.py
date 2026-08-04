"""
Agent request and response schemas
"""

from typing import Annotated, Literal, Union, TypedDict
from pydantic import BaseModel, ConfigDict, Field


class ChatRequest(BaseModel):
    """
    Chat request schema
    """

    message: str = Field(..., min_length=1, description="User prompt or question")


class ChatResponse(BaseModel):
    """
    Chat response schema
    """

    message: str = Field(..., description="Assistant response content")


class GeminiContentBlock(BaseModel):
    """
    Structured content block returned by Gemini through LangChain AIMessage.
    """

    model_config = ConfigDict(extra="ignore")

    type: str
    text: str


StreamStatus = Literal["analyzing", "executing_tools", "generating_response"]


ActivityStatus = Literal["started", "completed"]


class StreamActivityEvent(BaseModel):
    """Event emitted for milestone activity lifecycle"""

    type: Literal["activity"] = "activity"
    id: str
    message: str
    status: ActivityStatus


class StreamStatusEvent(BaseModel):
    """Event emitted when agent status changes"""

    type: Literal["status"] = "status"
    status: StreamStatus
    message: str | None = None


class StreamToolStartEvent(BaseModel):
    """Event emitted before executing a tool"""

    type: Literal["tool_start"] = "tool_start"
    tool_name: str


class StreamToolEndEvent(BaseModel):
    """Event emitted after executing a tool"""

    type: Literal["tool_end"] = "tool_end"
    tool_name: str


class StreamTokenEvent(BaseModel):
    """Event emitted for each streamed response token"""

    type: Literal["token"] = "token"
    token: str


class StreamErrorEvent(BaseModel):
    """Event emitted when an error occurs during streaming"""

    type: Literal["error"] = "error"
    error: str


class StreamCompleteEvent(BaseModel):
    """Event emitted when streaming completes successfully"""

    type: Literal["complete"] = "complete"


AgentStreamEvent = Annotated[
    Union[
        StreamStatusEvent,
        StreamActivityEvent,
        StreamToolStartEvent,
        StreamToolEndEvent,
        StreamTokenEvent,
        StreamErrorEvent,
        StreamCompleteEvent,
    ],
    Field(discriminator="type"),
]

class ToolActivityConfig(TypedDict):
    """ Configuration for tool's activity lifecycle """
    id: str
    started: str
    completed: str
