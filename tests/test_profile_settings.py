"""
Tests for user settings profile, email, and password update endpoints using repository stubs
"""

# pylint: disable=wrong-import-position

import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Mock redis_client and MongoClient before application imports to avoid network connections in CI
import pytest
import pymongo
import app.database.redis

pymongo.MongoClient = MagicMock()
if not isinstance(app.database.redis.redis_client, AsyncMock):
    app.database.redis.redis_client = AsyncMock()
app.database.redis.redis_client.incr.return_value = 1
app.database.redis.redis_client.expire.return_value = True

from app.database.redis import redis_client
from app.main import app
from app.dependencies.auth import get_current_user
from app.schemas.auth import User
from app.database.models import UserInDB, RefreshTokenInDB, UserSettings
from app.core.security import hash_password, hash_token
from app.dependencies.repositories import (
    get_user_repository,
    get_refresh_token_repository,
    get_appliance_repository,
    get_monthly_energy_repository,
)

# Setup mock repositories
mock_user_repo = MagicMock()
mock_token_repo = MagicMock()
mock_appliance_repo = MagicMock()
mock_energy_repo = MagicMock()

MOCK_USER_ID = "mock-user-uuid"
MOCK_PASSWORD_HASH = hash_password("ValidPassword123!")

# Database user representation
mock_user_db = UserInDB(
    id=MOCK_USER_ID,
    email="test@watttipid.ph",
    password=MOCK_PASSWORD_HASH,
    first_name="Maria",
    last_name="Santos",
    is_active=True,
    barangay_city="Cebu City",
    settings=UserSettings(electricity_rate_php_kwh=12.50),
)

# API user representation
mock_user = User(
    id=MOCK_USER_ID,
    email="test@watttipid.ph",
    password=MOCK_PASSWORD_HASH,
    first_name="Maria",
    last_name="Santos",
    is_active=True,
    barangay_city="Cebu City",
    created_at=datetime.now(timezone.utc),
)


async def mock_get_current_user():
    """Mock get_current_user dependency to return a fixed user"""
    return mock_user


@pytest.fixture(autouse=True)
def setup_overrides():
    """Set overrides and reset mock calls before each test execution"""
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    app.dependency_overrides[get_refresh_token_repository] = lambda: mock_token_repo
    app.dependency_overrides[get_appliance_repository] = lambda: mock_appliance_repo
    app.dependency_overrides[get_monthly_energy_repository] = lambda: mock_energy_repo
    app.dependency_overrides[get_current_user] = mock_get_current_user

    mock_user_repo.reset_mock()
    mock_token_repo.reset_mock()
    mock_appliance_repo.reset_mock()
    mock_energy_repo.reset_mock()
    
    redis_client.get.side_effect = None
    redis_client.get.return_value = None
    redis_client.get.reset_mock()
    yield


client = TestClient(app)


def test_update_profile_success():
    """Verify name fields update successfully and trim whitespace"""
    mock_user_repo.get_by_id.return_value = mock_user_db

    payload = {"first_name": "  Juan  ", "last_name": "  Dela Cruz  "}
    response = client.patch("/users/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Juan"
    assert data["last_name"] == "Dela Cruz"
    mock_user_repo.update_profile.assert_called_once_with(
        MOCK_USER_ID, "Juan", "Dela Cruz"
    )


def test_update_email_fails_incorrect_password():
    """Verify email update fails if current password is wrong"""
    mock_user_repo.get_by_id.return_value = mock_user_db

    payload = {"current_password": "wrongpassword", "new_email": "new@watttipid.ph"}
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


def test_update_email_success_and_stashes_in_redis():
    """Verify email update request succeeds with correct password, normalizes email, and stashes in Redis"""
    mock_user_repo.get_by_id.return_value = mock_user_db
    mock_user_repo.get_by_email.return_value = None  # No user exists with the new email

    payload = {
        "current_password": "ValidPassword123!",
        "new_email": "  NEW_EMAIL@watttipid.ph  ",
    }
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 200
    assert response.json()["email"] == "new_email@watttipid.ph"
    mock_user_repo.update_email.assert_not_called()
    mock_token_repo.revoke_all_user_tokens.assert_not_called()


def test_verify_email_change_success():
    """Verify email verification succeeds, updates DB, and revokes tokens"""
    code = "123456"
    hashed_code = hash_token(code)
    
    mock_user_repo.get_by_email.return_value = None
    
    async def mock_redis_get(key):
        if key == f"email_change:data:{MOCK_USER_ID}":
            return json.dumps({"new_email": "new_email@watttipid.ph"})
        if key == f"email_change:code:{MOCK_USER_ID}":
            return json.dumps({"code_hash": hashed_code, "attempts": 0})
        return None
        
    redis_client.get.side_effect = mock_redis_get
    
    payload = {"code": code}
    response = client.post("/users/email/verify", json=payload)
    
    assert response.status_code == 200
    assert response.json()["email"] == "new_email@watttipid.ph"
    mock_user_repo.update_email.assert_called_once_with(
        MOCK_USER_ID, "new_email@watttipid.ph"
    )
    mock_token_repo.revoke_all_user_tokens.assert_called_once_with(MOCK_USER_ID)


def test_update_email_enforces_uniqueness():
    """Verify email update fails if new email is already taken by another user"""
    mock_user_repo.get_by_id.return_value = mock_user_db
    # Return another user to simulate a collision
    mock_user_repo.get_by_email.return_value = UserInDB(
        id="another-user-id",
        email="taken@watttipid.ph",
        password="anotherhash",
        first_name="Juan",
        last_name="Cruz",
        barangay_city="Manila",
    )

    payload = {
        "current_password": "ValidPassword123!",
        "new_email": "taken@watttipid.ph",
    }
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


def test_update_password_fails_incorrect_password():
    """Verify password update fails if current password is wrong"""
    mock_user_repo.get_by_id.return_value = mock_user_db

    payload = {
        "current_password": "wrongpassword",
        "new_password": "NewValidPassword99!",
        "confirm_password": "NewValidPassword99!",
    }
    response = client.patch("/users/password", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


def test_update_password_fails_complexity_checks():
    """Verify password update fails if new password does not meet complexity constraints"""
    mock_user_repo.get_by_id.return_value = mock_user_db

    # 1. Too short
    payload = {
        "current_password": "ValidPassword123!",
        "new_password": "Short1!",
        "confirm_password": "Short1!",
    }
    response = client.patch("/users/password", json=payload)
    assert response.status_code == 422

    # 2. No uppercase
    payload["new_password"] = "lowercase123!"
    payload["confirm_password"] = "lowercase123!"
    response = client.patch("/users/password", json=payload)
    assert response.status_code == 422

    # 3. Passwords mismatch
    payload["new_password"] = "NewValid123!"
    payload["confirm_password"] = "DifferentValid123!"
    response = client.patch("/users/password", json=payload)
    assert response.status_code == 422


def test_update_password_success_and_revokes_tokens():
    """Verify password update succeeds with complexity check, and revokes tokens"""
    mock_user_repo.get_by_id.return_value = mock_user_db

    payload = {
        "current_password": "ValidPassword123!",
        "new_password": "NewValidPassword99!",
        "confirm_password": "NewValidPassword99!",
    }
    response = client.patch("/users/password", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    mock_user_repo.update_password.assert_called_once()
    mock_token_repo.revoke_all_user_tokens.assert_called_once_with(MOCK_USER_ID)


def test_protected_endpoints_reject_revoked_refresh_tokens():
    """Verify auth refresh rejects revoked refresh tokens after access token expiration"""
    mock_token_repo.get_by_hash.return_value = RefreshTokenInDB(
        id="token-id",
        user_id=MOCK_USER_ID,
        token_hash="somehash",
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=1),
        revoked=True,
        created_at=datetime.now(timezone.utc),
    )

    response = client.post("/auth/refresh", cookies={"refresh_token": "some-raw-token"})
    assert response.status_code == 401
    assert "Expired or revoked refresh token" in response.json()["detail"]
