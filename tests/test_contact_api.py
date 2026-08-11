"""
Tests for contact form endpoint and email dispatch
"""

from unittest.mock import MagicMock, AsyncMock
import pymongo

pymongo.MongoClient = MagicMock()

import app.database.redis
if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()

from fastapi.testclient import TestClient
from app.main import app as fastapi_app
from app.services.email_service import EmailService

# Mock EmailService send methods to prevent live SMTP calls
EmailService.send_verification_email = MagicMock()
EmailService.send_contact_form_email = MagicMock()

client = TestClient(fastapi_app)


def test_contact_form_submission_success():
    """Test successful submission of contact form"""
    EmailService.send_contact_form_email.reset_mock()

    payload = {
        "full_name": "Juan Dela Cruz",
        "email": "juan@example.com",
        "message": "Hello WattTipid team, I love the energy saving score feature!",
    }

    response = client.post("/contact", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["success"] is True
    assert "sent successfully" in data["message"]

    # Verify EmailService was called with correct parameters
    EmailService.send_contact_form_email.assert_called_once_with(
        full_name="Juan Dela Cruz",
        sender_email="juan@example.com",
        message="Hello WattTipid team, I love the energy saving score feature!",
    )


def test_contact_form_validation_failure():
    """Test validation errors for invalid payload"""
    response = client.post(
        "/contact",
        json={"full_name": "J", "email": "invalid-email"},
    )
    assert response.status_code == 422
