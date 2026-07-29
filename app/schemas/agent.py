"""
Agent request and response schemas
"""

from typing import Optional, Union, Dict
from pydantic import BaseModel, Field


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
