"""
Contact form request/response schemas
"""

from pydantic import BaseModel, EmailStr, Field


class ContactRequest(BaseModel):
    """Schema for submitting contact form messages"""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Sender's full name",
    )
    email: EmailStr = Field(
        ...,
        description="Sender's contact email address",
    )
    message: str = Field(
        ...,
        min_length=10,
        max_length=3000,
        description="Message content",
    )


class ContactResponse(BaseModel):
    """Schema for contact submission response"""

    success: bool = Field(..., description="Whether the email was dispatched")
    message: str = Field(..., description="Human-readable result message")
