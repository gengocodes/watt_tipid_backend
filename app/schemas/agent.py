"""
Agent request and response schemas
"""

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
