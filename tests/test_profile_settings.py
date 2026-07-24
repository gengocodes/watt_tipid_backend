"""
Tests for user settings profile, email, and password update endpoints
"""

# pylint: disable=wrong-import-position

import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

# Mock redis_client and MongoClient before application imports to avoid network connections in CI
import pymongo
import app.database.redis

pymongo.MongoClient = MagicMock()
app.database.redis.redis_client = AsyncMock()
app.database.redis.redis_client.incr.return_value = 1
app.database.redis.redis_client.expire.return_value = True

from app.main import app
from app.dependencies.auth import get_current_user
from app.schemas.auth import User
from app.core.security import hash_password

MOCK_USER_ID = "mock-user-uuid"
MOCK_PASSWORD_HASH = hash_password("ValidPassword123!")

mock_user = User(
    id=MOCK_USER_ID,
    email="test@watttipid.ph",
    password=MOCK_PASSWORD_HASH,
    first_name="Maria",
    last_name="Santos",
    is_active=True,
    barangay_city="Cebu City",
)


async def mock_get_current_user():
    """Mock get_current_user dependency to return a fixed user"""
    return mock_user


app.dependency_overrides[get_current_user] = mock_get_current_user
client = TestClient(app)


@patch("app.services.user_settings_service.users_collection")
def test_update_profile_success(mock_users_coll):
    """Verify name fields update successfully and trim whitespace"""
    mock_users_coll.find_one.return_value = mock_user.model_dump()

    payload = {"first_name": "  Juan  ", "last_name": "  Dela Cruz  "}
    response = client.patch("/users/profile", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["first_name"] == "Juan"
    assert data["last_name"] == "Dela Cruz"
    mock_users_coll.update_one.assert_called_once_with(
        {"id": MOCK_USER_ID},
        {"$set": {"first_name": "Juan", "last_name": "Dela Cruz"}},
    )


@patch("app.services.user_settings_service.users_collection")
def test_update_email_fails_incorrect_password(mock_users_coll):
    """Verify email update fails if current password is wrong"""
    mock_users_coll.find_one.return_value = mock_user.model_dump()

    payload = {"current_password": "wrongpassword", "new_email": "new@watttipid.ph"}
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


@patch("app.services.user_settings_service.refresh_tokens_collection")
@patch("app.services.user_settings_service.users_collection")
def test_update_email_success_and_revokes_tokens(mock_users_coll, mock_refresh_coll):
    """Verify email update succeeds with correct password, normalizes email, and revokes tokens"""
    mock_users_coll.find_one.side_effect = [
        mock_user.model_dump(),  # 1. when service finds user
        None,  # 2. when checking email uniqueness (existing=None)
    ]

    payload = {
        "current_password": "ValidPassword123!",
        "new_email": "  NEW_EMAIL@watttipid.ph  ",
    }
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 200
    assert response.json()["email"] == "new_email@watttipid.ph"
    mock_users_coll.update_one.assert_called_once_with(
        {"id": MOCK_USER_ID},
        {"$set": {"email": "new_email@watttipid.ph"}},
    )
    mock_refresh_coll.update_many.assert_called_once_with(
        {"user_id": MOCK_USER_ID, "revoked": False},
        {"$set": {"revoked": True}},
    )


@patch("app.services.user_settings_service.users_collection")
def test_update_email_enforces_uniqueness(mock_users_coll):
    """Verify email update fails if new email is already taken by another user"""
    mock_users_coll.find_one.side_effect = [
        mock_user.model_dump(),  # 1. when service finds user
        {"id": "another-user-id"},  # 2. when checking uniqueness (existing user found)
    ]

    payload = {
        "current_password": "ValidPassword123!",
        "new_email": "taken@watttipid.ph",
    }
    response = client.patch("/users/email", json=payload)

    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@patch("app.services.user_settings_service.users_collection")
def test_update_password_fails_incorrect_password(mock_users_coll):
    """Verify password update fails if current password is wrong"""
    mock_users_coll.find_one.return_value = mock_user.model_dump()

    payload = {
        "current_password": "wrongpassword",
        "new_password": "NewValidPassword99!",
        "confirm_password": "NewValidPassword99!",
    }
    response = client.patch("/users/password", json=payload)

    assert response.status_code == 401
    assert response.json()["detail"] == "Incorrect password"


@patch("app.services.user_settings_service.users_collection")
def test_update_password_fails_complexity_checks(mock_users_coll):
    """Verify password update fails if new password does not meet complexity constraints"""
    mock_users_coll.find_one.return_value = mock_user.model_dump()

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


@patch("app.services.user_settings_service.refresh_tokens_collection")
@patch("app.services.user_settings_service.users_collection")
def test_update_password_success_and_revokes_tokens(mock_users_coll, mock_refresh_coll):
    """Verify password update succeeds with complexity check, and revokes tokens"""
    mock_users_coll.find_one.return_value = mock_user.model_dump()

    payload = {
        "current_password": "ValidPassword123!",
        "new_password": "NewValidPassword99!",
        "confirm_password": "NewValidPassword99!",
    }
    response = client.patch("/users/password", json=payload)

    assert response.status_code == 200
    assert response.json()["message"] == "Password updated successfully"
    mock_users_coll.update_one.assert_called_once()
    mock_refresh_coll.update_many.assert_called_once_with(
        {"user_id": MOCK_USER_ID, "revoked": False},
        {"$set": {"revoked": True}},
    )


@patch("app.routers.auth.refresh_tokens_collection")
def test_protected_endpoints_reject_revoked_refresh_tokens(mock_refresh_coll):
    """Verify auth refresh rejects revoked refresh tokens after access token expiration"""
    # Mocking refresh token as revoked
    mock_refresh_coll.find_one.return_value = {
        "_id": "token-id",
        "user_id": MOCK_USER_ID,
        "token_hash": "somehash",
        "expires_at": datetime.datetime.now(datetime.timezone.utc)
        + datetime.timedelta(days=1),
        "revoked": True,
    }

    response = client.post("/auth/refresh", cookies={"refresh_token": "some-raw-token"})
    assert response.status_code == 401
    assert "Expired or revoked refresh token" in response.json()["detail"]
