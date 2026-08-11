"""
Contact router for landing page inquiries
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.contact import ContactRequest, ContactResponse
from app.services.email_service import EmailService
from app.dependencies.rate_limit import ip_rate_limit

router = APIRouter(prefix="/contact", tags=["Contact"])
email_service = EmailService()


@router.post(
    "",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(ip_rate_limit(limit=1, window=86400))],
)
def send_contact_message(payload: ContactRequest) -> ContactResponse:
    """
    Public endpoint for visitors to submit messages via the contact form.
    Rate-limited to 1 request per 24 hours per IP address.
    Dispatches formatted email to CONTACT_FORM_RECIPIENT_EMAIL.
    """
    try:
        email_service.send_contact_form_email(
            full_name=payload.full_name,
            sender_email=payload.email,
            message=payload.message,
        )
        return ContactResponse(
            success=True,
            message="Your message has been sent successfully. We will get back to you soon!",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to transmit contact email: {str(e)}",
        ) from e
