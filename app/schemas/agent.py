"""
Agent request and response schemas
"""

from typing import Annotated, Literal, Union, TypedDict, Generic, TypeVar
from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class AgentToolResult(BaseModel, Generic[T]):
    """Generic strongly-typed response model for agent tools."""

    success: bool = Field(..., description="Whether the tool operation succeeded")
    message: str = Field(..., description="Human-readable result or error message")
    data: T | None = Field(default=None, description="Typed result payload")


class ApplianceDeletePayload(BaseModel):
    """Typed payload for appliance deletion tool result."""

    appliance_id: str = Field(..., description="UUID of the deleted appliance")


class SearchResultItem(BaseModel):
    """Structured search result item."""

    title: str = Field(..., description="Title of the search result page")
    url: str = Field(..., description="URL link of the search result")
    snippet: str = Field(..., description="Short description or content snippet")


class SearchResultsResponse(BaseModel):
    """Typed payload containing web search results."""

    query: str = Field(..., description="The query used for web search")
    results: list[SearchResultItem] = Field(
        default_factory=list, description="List of structured search result items"
    )


class WebSearchToolArgs(BaseModel):
    """Typed arguments payload for web_search tool call."""

    model_config = ConfigDict(extra="ignore")
    query: str = Field(..., min_length=1, description="Web search query string")


class ChatHistoryMessage(BaseModel):
    """Schema representing a past message turn in the conversation"""

    role: Literal["user", "assistant"] = Field(..., description="Sender role")
    content: str = Field(
        ..., min_length=1, max_length=5000, description="Message text content"
    )


class ChatRequest(BaseModel):
    """
    Chat request schema
    """

    message: str = Field(..., min_length=1, description="User prompt or question")
    history: list[ChatHistoryMessage] = Field(
        default_factory=list, description="Prior client-provided conversation history"
    )


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


StreamStatus = Literal["analyzing", "executing_tools"]


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
    """Configuration for tool's activity lifecycle"""

    id: str
    started: str
    completed: str
