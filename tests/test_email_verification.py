"""
Tests for registration and email update verification flows
"""

# pylint: disable=wrong-import-position

from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient
import json
import pytest

# Mock redis_client and MongoClient before importing app
import pymongo
import app.database.redis

pymongo.MongoClient = MagicMock()
if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()
mock_redis = app.database.redis.redis_client
mock_redis.incr.return_value = 1
mock_redis.expire.return_value = True

from app.main import app as fastapi_app
from app.dependencies.repositories import (
    get_user_repository,
    get_refresh_token_repository,
)
from app.core.security import hash_token
from app.services.email_service import EmailService

# Mock EmailService globally to prevent outbound SMTP connections in tests
EmailService.send_verification_email = MagicMock()

# Setup mock repositories
mock_user_repo = MagicMock()
mock_token_repo = MagicMock()


@pytest.fixture(autouse=True)
def setup_overrides():
    """Set up dependency overrides"""
    fastapi_app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    fastapi_app.dependency_overrides[get_refresh_token_repository] = (
        lambda: mock_token_repo
    )

    mock_user_repo.reset_mock()
    mock_token_repo.reset_mock()

    # Reset redis mock client calls
    mock_redis.get.side_effect = None
    mock_redis.get.return_value = None
    mock_redis.get.reset_mock()
    mock_redis.set.reset_mock()
    mock_redis.delete.reset_mock()
    mock_redis.exists.reset_mock()

    yield


client = TestClient(fastapi_app)


def test_registration_request_success():
    """Verify that registration request stashes data in Redis and does not write to MongoDB yet"""
    mock_user_repo.get_by_email.return_value = None

    # Simulate redis key not exist (nx=True success)
    mock_redis.set.return_value = True

    payload = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "barangay_city": "Cebu City",
        "email": "juan@watttipid.ph",
        "password": "Password123!",
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 200
    assert response.json()["email"] == "juan@watttipid.ph"
    mock_user_repo.create_user.assert_not_called()
    assert mock_redis.set.call_count >= 2  # Sets data and code


def test_registration_request_duplicate_pending():
    """
    Verify registration request fails if there is
    already a pending verification for this email
    """
    mock_user_repo.get_by_email.return_value = None

    # Simulate data key already exists (nx=True fails, returns None/False)
    mock_redis.set.return_value = None

    payload = {
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "barangay_city": "Cebu City",
        "email": "juan@watttipid.ph",
        "password": "Password123!",
    }
    response = client.post("/auth/register", json=payload)

    assert response.status_code == 400
    assert "Verification already pending" in response.json()["detail"]


def test_registration_verify_success():
    """Verify registration succeeds and commits to MongoDB when correct code is submitted"""
    code = "123456"
    hashed_code = hash_token(code)
    normalized_email = "juan@watttipid.ph"

    # Setup mock stashed data
    stashed_user = {
        "email": normalized_email,
        "password_hash": "hashedpass",
        "first_name": "Juan",
        "last_name": "Dela Cruz",
        "barangay_city": "Cebu City",
    }

    async def mock_redis_get(key):
        if key == f"register:code:{normalized_email}":
            return json.dumps({"code_hash": hashed_code, "attempts": 0})
        if key == f"register:data:{normalized_email}":
            return json.dumps(stashed_user)
        return None

    mock_redis.get.side_effect = mock_redis_get

    payload = {"email": normalized_email, "code": code}
    response = client.post("/auth/register/verify", json=payload)

    assert response.status_code == 201
    assert "user_id" in response.json()
    mock_user_repo.create_user.assert_called_once()
    mock_redis.delete.assert_called_once()


def test_registration_verify_invalid_code():
    """Verify registration fails with incorrect code and increments attempts"""
    normalized_email = "juan@watttipid.ph"
    code = "123456"
    hashed_code = hash_token(code)

    async def mock_redis_get(key):
        if key == f"register:code:{normalized_email}":
            return json.dumps({"code_hash": hashed_code, "attempts": 0})
        return None

    mock_redis.get.side_effect = mock_redis_get
    mock_redis.ttl.return_value = 100

    payload = {"email": normalized_email, "code": "wrongcode"}
    response = client.post("/auth/register/verify", json=payload)

    assert response.status_code == 400
    assert "Invalid verification code" in response.json()["detail"]
    mock_redis.set.assert_called_once()  # Updates attempts


def test_registration_verify_max_attempts():
    """Verify registration session is deleted and fails after maximum failed attempts"""
    normalized_email = "juan@watttipid.ph"
    code = "123456"
    hashed_code = hash_token(code)

    async def mock_redis_get(key):
        if key == f"register:code:{normalized_email}":
            return json.dumps({"code_hash": hashed_code, "attempts": 2})  # 3rd attempt
        return None

    mock_redis.get.side_effect = mock_redis_get

    payload = {"email": normalized_email, "code": "wrongcode"}
    response = client.post("/auth/register/verify", json=payload)

    assert response.status_code == 400
    assert "Too many failed attempts" in response.json()["detail"]
    mock_redis.delete.assert_called_once()


def test_registration_resend_cooldown():
    """Verify resending code fails if cooldown key exists in Redis"""
    normalized_email = "juan@watttipid.ph"

    # Cooldown key exists
    mock_redis.get.return_value = "1"

    payload = {"email": normalized_email}
    response = client.post("/auth/register/resend", json=payload)

    assert response.status_code == 429
    assert "wait before requesting" in response.json()["detail"]
